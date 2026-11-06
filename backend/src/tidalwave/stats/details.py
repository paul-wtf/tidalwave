from __future__ import annotations

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tidalwave.models.db import AlbumArt, Listen
from tidalwave.stats.queries import _entity, _scope, artist_cover_subquery, bounded
from tidalwave.stats.scope import Scope, iso_in


def _iso(value, tz: str) -> str | None:
    return iso_in(value, tz) if value is not None else None


async def _totals(session, scope, artist, album, track) -> tuple[int, int]:
    stmt = _entity(
        _scope(select(func.count(), func.coalesce(func.sum(Listen.duration_sec), 0)), scope),
        artist, album, track,
    )
    row = (await session.execute(stmt)).one()
    return int(row[0]), int(row[1])


async def _span(session, scope, artist, album, track) -> tuple[str | None, str | None]:
    stmt = _entity(
        bounded(select(func.min(Listen.played_at), func.max(Listen.played_at)), scope),
        artist, album, track,
    )
    first, last = (await session.execute(stmt)).one()
    return _iso(first, scope.tz), _iso(last, scope.tz)


async def _cover(session, artist: str, album: str | None) -> str | None:
    if album is None:
        return None
    stmt = select(AlbumArt.image_url).where(AlbumArt.artist == artist, AlbumArt.album == album)
    return (await session.execute(stmt)).scalar_one_or_none()


async def artist_detail(session: AsyncSession, scope: Scope, artist: str) -> dict | None:
    first, last = await _span(session, scope, artist, None, None)
    if first is None:
        return None
    listens, seconds = await _totals(session, scope, artist, None, None)
    rank = None
    if listens:
        counts = _scope(
            select(Listen.artist.label("artist"), func.count().label("n")), scope
        ).group_by(Listen.artist).subquery()
        ahead = (
            select(func.count())
            .select_from(counts)
            .where((counts.c.n > listens) | and_(counts.c.n == listens, counts.c.artist < artist))
        )
        rank = int((await session.execute(ahead)).scalar_one()) + 1
    cover = artist_cover_subquery(scope, artist)
    image_url = (await session.execute(select(cover.c.image_url))).scalar_one_or_none()
    return {
        "artist": artist, "listens": listens, "seconds": seconds, "rank": rank,
        "first_listen": first, "last_listen": last, "image_url": image_url,
    }


async def album_detail(session: AsyncSession, scope: Scope, artist: str, album: str) -> dict | None:
    first, last = await _span(session, scope, artist, album, None)
    if first is None:
        return None
    listens, seconds = await _totals(session, scope, artist, album, None)
    return {
        "artist": artist, "album": album, "listens": listens, "seconds": seconds,
        "first_listen": first, "last_listen": last,
        "image_url": await _cover(session, artist, album),
    }


async def _track_album(session, scope, artist, track) -> str | None:
    def most_listened(stmt):
        return (
            _entity(stmt, artist, None, track)
            .where(Listen.album.is_not(None))
            .group_by(Listen.album)
            .order_by(func.count().desc(), Listen.album.asc())
            .limit(1)
        )

    in_scope = most_listened(_scope(select(Listen.album), scope))
    found = (await session.execute(in_scope)).scalar_one_or_none()
    if found is not None:
        return found
    overall = most_listened(bounded(select(Listen.album), scope))
    return (await session.execute(overall)).scalar_one_or_none()


async def track_detail(session: AsyncSession, scope: Scope, artist: str, track: str) -> dict | None:
    first, last = await _span(session, scope, artist, None, track)
    if first is None:
        return None
    listens, seconds = await _totals(session, scope, artist, None, track)
    album = await _track_album(session, scope, artist, track)
    return {
        "artist": artist, "track": track, "album": album, "listens": listens, "seconds": seconds,
        "first_listen": first, "last_listen": last,
        "image_url": await _cover(session, artist, album),
    }
