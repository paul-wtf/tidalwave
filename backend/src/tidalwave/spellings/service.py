from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from sqlalchemy import delete, func, literal, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from tidalwave.models.db import AlbumArt, AlbumYear, ArtistMerge, ArtistTags, Listen, TrackDuration
from tidalwave.spellings.normalize import spelling_key

SUGGESTION_LIMIT = 50


class MergeError(ValueError):
    pass


async def alias_map(session: AsyncSession, user_id: int) -> dict[str, str]:
    rows = await session.execute(
        select(ArtistMerge.variant, ArtistMerge.canonical).where(ArtistMerge.user_id == user_id)
    )
    return {variant: canonical for variant, canonical in rows.all()}


def _clean(names: Iterable[str]) -> list[str]:
    seen: list[str] = []
    for name in names:
        name = name.strip()
        if name and name not in seen:
            seen.append(name)
    return seen


async def merge_spellings(
    session: AsyncSession, user_id: int, canonical: str, variants: Iterable[str]
) -> None:
    canonical = canonical.strip()
    if not canonical:
        raise MergeError("The name to merge into is empty")
    wanted = [v for v in _clean(variants) if v != canonical]
    if not wanted:
        raise MergeError("Pick at least one other spelling")
    aliases = await alias_map(session, user_id)
    if canonical in aliases:
        raise MergeError(f"{canonical} is itself merged into {aliases[canonical]}")

    moved = wanted + [v for v, c in aliases.items() if c in wanted and v not in wanted]
    await session.execute(
        delete(ArtistMerge).where(ArtistMerge.user_id == user_id, ArtistMerge.variant.in_(moved))
    )
    session.add_all(
        ArtistMerge(user_id=user_id, variant=v, canonical=canonical) for v in moved
    )
    await session.execute(
        update(Listen)
        .where(Listen.user_id == user_id, Listen.artist_raw.in_(moved))
        .values(artist=canonical)
    )
    await _copy_lookups(session, moved, canonical)
    await session.flush()


async def _copy_lookups(session: AsyncSession, variants: list[str], canonical: str) -> None:
    """Covers, tags, release years and durations are cached per spelling. The
    canonical name takes what the variants already have, so the merged listens
    keep them without new lookups."""
    art = pg_insert(AlbumArt).from_select(
        ["artist", "album", "image_url"],
        select(literal(canonical), AlbumArt.album, func.max(AlbumArt.image_url))
        .where(AlbumArt.artist.in_(variants))
        .group_by(AlbumArt.album),
    )
    await session.execute(art.on_conflict_do_update(
        constraint="uq_album_art",
        set_={"image_url": func.coalesce(AlbumArt.image_url, art.excluded.image_url)},
    ))
    years = pg_insert(AlbumYear).from_select(
        ["artist", "album", "year"],
        select(literal(canonical), AlbumYear.album, func.min(AlbumYear.year))
        .where(AlbumYear.artist.in_(variants))
        .group_by(AlbumYear.album),
    )
    await session.execute(years.on_conflict_do_update(
        constraint="uq_album_year",
        set_={"year": func.coalesce(AlbumYear.year, years.excluded.year)},
    ))
    durations = pg_insert(TrackDuration).from_select(
        ["artist", "track_title", "duration_sec"],
        select(literal(canonical), TrackDuration.track_title, func.max(TrackDuration.duration_sec))
        .where(TrackDuration.artist.in_(variants))
        .group_by(TrackDuration.track_title),
    )
    await session.execute(durations.on_conflict_do_update(
        constraint="uq_track_duration",
        set_={"duration_sec": func.coalesce(
            TrackDuration.duration_sec, durations.excluded.duration_sec
        )},
    ))
    tagged = (await session.execute(
        select(ArtistTags.tags)
        .where(ArtistTags.artist.in_(variants), func.cardinality(ArtistTags.tags) > 0)
        .order_by(func.cardinality(ArtistTags.tags).desc())
        .limit(1)
    )).scalar_one_or_none()
    if tagged is not None:
        tags = pg_insert(ArtistTags).values(artist=canonical, tags=tagged)
        await session.execute(tags.on_conflict_do_update(
            constraint="uq_artist_tags",
            set_={"tags": tags.excluded.tags},
            where=func.cardinality(ArtistTags.tags) == 0,
        ))


async def unmerge(
    session: AsyncSession, user_id: int, canonical: str, variant: str | None = None
) -> int:
    """Undo a merge, of one variant or of all of them. Returns how many
    spellings were split off again."""
    where = [ArtistMerge.user_id == user_id, ArtistMerge.canonical == canonical]
    if variant is not None:
        where.append(ArtistMerge.variant == variant)
    removed = (await session.execute(
        delete(ArtistMerge).where(*where).returning(ArtistMerge.variant)
    )).scalars().all()
    if removed:
        await session.execute(
            update(Listen)
            .where(
                Listen.user_id == user_id,
                Listen.artist_raw.in_(removed),
                Listen.artist == canonical,
            )
            .values(artist=Listen.artist_raw)
        )
    return len(removed)


async def _listens_by_raw(session: AsyncSession, user_id: int) -> dict[str, int]:
    rows = await session.execute(
        select(Listen.artist_raw, func.count())
        .where(Listen.user_id == user_id)
        .group_by(Listen.artist_raw)
    )
    return dict(rows.tuples().all())


async def list_merges(session: AsyncSession, user_id: int) -> list[dict]:
    aliases = await alias_map(session, user_id)
    if not aliases:
        return []
    counts = await _listens_by_raw(session, user_id)
    groups: dict[str, list[str]] = defaultdict(list)
    for variant, canonical in aliases.items():
        groups[canonical].append(variant)
    merges: list[dict[str, Any]] = []
    for canonical, variants in groups.items():
        ranked = sorted(variants, key=lambda v: (-counts.get(v, 0), v))
        own = counts.get(canonical, 0) if canonical not in aliases else 0
        merges.append({
            "canonical": canonical,
            "listens": own + sum(counts.get(v, 0) for v in ranked),
            "variants": [{"artist": v, "listens": counts.get(v, 0)} for v in ranked],
        })
    merges.sort(key=lambda m: (-m["listens"], m["canonical"]))
    return merges


async def suggestions(
    session: AsyncSession, user_id: int, *, limit: int = SUGGESTION_LIMIT
) -> list[dict]:
    """Spellings of the user's artists that look like one artist, as candidates
    the user may merge. Nothing here changes data."""
    rows = await session.execute(
        select(Listen.artist, func.count())
        .where(Listen.user_id == user_id)
        .group_by(Listen.artist)
    )
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for artist, listens in rows.tuples().all():
        groups[spelling_key(artist)].append({"artist": artist, "listens": listens})
    found: list[dict[str, Any]] = []
    for names in groups.values():
        if len(names) < 2:
            continue
        names.sort(key=lambda n: (-n["listens"], n["artist"]))
        found.append({"names": names, "listens": sum(n["listens"] for n in names)})
    found.sort(key=lambda g: (-g["listens"], g["names"][0]["artist"]))
    return found[:limit]
