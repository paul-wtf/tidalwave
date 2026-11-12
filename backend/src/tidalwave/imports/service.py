from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import DateTime, Integer, and_, column, delete, func, or_, select, tuple_, update
from sqlalchemy import values as sa_values
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tidalwave.imports.parsers import (
    ImportFileError,
    Play,
    Skip,
    parse_record,
    read_records,
    scrobblable,
)
from tidalwave.models.db import Import, Listen, TrackDuration
from tidalwave.spellings.normalize import spelling_key, track_key
from tidalwave.spellings.service import alias_map
from tidalwave.stats.queries import _scope, bounded
from tidalwave.stats.scope import Scope, iso_in

log = logging.getLogger(__name__)

ACTIVE = ("pending", "running")
# Last.fm stores when a track started, Spotify when it ended (start is derived
# from ms_played, which leaves out pauses), and clocks of players drift. Ten
# minutes covers the length of almost any track on top of that, while two
# plays of one song in a row stay apart: each existing listen can absorb at
# most one imported play.
DEDUP_WINDOW = timedelta(minutes=10)
BATCH_SIZE = 2000
STALE_AFTER = timedelta(minutes=10)
# Zips of JSON shrink to about a tenth; this leaves room for that.
UNPACK_FACTOR = 20
_PG_MAX_BIND_PARAMS = 32767

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


class ImportBusy(Exception):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


def serialize(imp: Import, tz: str) -> dict:
    def when(moment: datetime | None) -> str | None:
        return iso_in(moment, tz) if moment is not None else None

    return {
        "id": imp.id,
        "filename": imp.filename,
        "source": imp.source,
        "status": imp.status,
        "error": imp.error,
        "read": imp.read,
        "skipped": imp.skipped,
        "too_short": imp.too_short,
        "duplicates": imp.duplicates,
        "added": imp.added,
        "first_played_at": when(imp.first_played_at),
        "last_played_at": when(imp.last_played_at),
        "created_at": when(imp.created_at),
        "finished_at": when(imp.finished_at),
    }


async def _expire_stale(session: AsyncSession, user_id: int) -> None:
    now = _now()
    await session.execute(
        update(Import)
        .where(
            Import.user_id == user_id,
            Import.status.in_(ACTIVE),
            Import.updated_at < now - STALE_AFTER,
        )
        .values(status="failed", error="The import was interrupted", finished_at=now)
    )


async def active_import(session: AsyncSession, user_id: int) -> Import | None:
    await _expire_stale(session, user_id)
    return (await session.execute(
        select(Import).where(Import.user_id == user_id, Import.status.in_(ACTIVE))
    )).scalar_one_or_none()


async def start_import(session: AsyncSession, user_id: int, filename: str) -> Import:
    if await active_import(session, user_id) is not None:
        raise ImportBusy
    imp = Import(user_id=user_id, filename=filename, status="pending")
    try:
        async with session.begin_nested():
            session.add(imp)
    except IntegrityError as e:
        raise ImportBusy from e
    await session.refresh(imp)
    return imp


async def undo_import(session: AsyncSession, user_id: int, import_id: int) -> Import | None:
    imp = (await session.execute(
        select(Import).where(Import.id == import_id, Import.user_id == user_id)
    )).scalar_one_or_none()
    if imp is None:
        return None
    if imp.status in ACTIVE:
        raise ImportBusy
    await session.execute(
        delete(Listen).where(Listen.user_id == user_id, Listen.import_id == import_id)
    )
    imp.status = "undone"
    imp.updated_at = _now()
    await session.flush()
    return imp


def _artist_keys(*names: str) -> set[str]:
    return {spelling_key(n) for n in names}


async def _known_durations(
    session: AsyncSession, pairs: set[tuple[str, str]]
) -> dict[tuple[str, str], int]:
    if not pairs:
        return {}
    rows = await session.execute(
        select(TrackDuration.artist, TrackDuration.track_title, TrackDuration.duration_sec)
        .where(
            tuple_(TrackDuration.artist, TrackDuration.track_title).in_(list(pairs)),
            TrackDuration.duration_sec.is_not(None),
        )
    )
    return {(a, t): d for a, t, d in rows.tuples().all() if d is not None}


async def _duplicates(
    session: AsyncSession, imp: Import, plays: list[tuple[Play, str]], matched: set[int]
) -> set[int]:
    """Indexes of the plays that an existing listen of the user already covers."""
    wanted = sa_values(
        column("i", Integer), column("t", DateTime(timezone=True)), name="plays"
    ).data([(i, play.played_at) for i, (play, _) in enumerate(plays)])
    rows = (await session.execute(
        select(
            wanted.c.i, Listen.id, Listen.artist, Listen.artist_raw,
            Listen.track_title, Listen.played_at,
        )
        .join(Listen, and_(
            Listen.user_id == imp.user_id,
            Listen.played_at >= wanted.c.t - DEDUP_WINDOW,
            Listen.played_at <= wanted.c.t + DEDUP_WINDOW,
        ))
        .where(or_(Listen.import_id.is_(None), Listen.import_id != imp.id))
    )).all()
    pairs = []
    for i, listen_id, artist, artist_raw, title, played_at in rows:
        if listen_id in matched:
            continue
        play, canonical = plays[i]
        if track_key(title) != track_key(play.track):
            continue
        if not _artist_keys(artist, artist_raw) & _artist_keys(play.artist, canonical):
            continue
        pairs.append((abs(played_at - play.played_at), i, listen_id))
    found: set[int] = set()
    for _, i, listen_id in sorted(pairs):
        if i in found or listen_id in matched:
            continue
        found.add(i)
        matched.add(listen_id)
    return found


async def _store(
    session: AsyncSession, imp: Import, plays: list[Play], matched: set[int]
) -> None:
    aliases = await alias_map(session, imp.user_id)
    named = [(p, aliases.get(p.artist, p.artist)) for p in plays]
    durations = await _known_durations(
        session, {(c, p.track) for p, c in named if p.duration_ms is None}
    )
    kept: list[tuple[Play, str, int | None]] = []
    for play, canonical in named:
        length = play.duration_ms
        if length is None and (canonical, play.track) in durations:
            length = durations[(canonical, play.track)] * 1000
        if scrobblable(play, length):
            kept.append((play, canonical, length))
        else:
            imp.too_short += 1
    if not kept:
        return
    known = await _duplicates(session, imp, [(p, c) for p, c, _ in kept], matched)
    imp.duplicates += len(known)
    rows: list[dict[str, Any]] = [
        {
            "user_id": imp.user_id,
            "track_title": play.track,
            "artist": canonical,
            "artist_raw": play.artist,
            "album": play.album,
            "played_at": play.played_at,
            "track_mbid": play.track_mbid,
            "artist_mbid": play.artist_mbid,
            "album_mbid": play.album_mbid,
            "duration_sec": length // 1000 if length is not None else None,
            "source": play.source,
            "import_id": imp.id,
        }
        for i, (play, canonical, length) in enumerate(kept)
        if i not in known
    ]
    if not rows:
        return
    chunk = _PG_MAX_BIND_PARAMS // len(rows[0])
    inserted: list[datetime] = []
    for start in range(0, len(rows), chunk):
        result = await session.execute(
            pg_insert(Listen)
            .values(rows[start : start + chunk])
            .on_conflict_do_nothing(constraint="uq_listen_dedup")
            .returning(Listen.played_at)
        )
        inserted.extend(result.scalars().all())
    imp.duplicates += len(rows) - len(inserted)
    imp.added += len(inserted)
    if inserted:
        first, last = min(inserted), max(inserted)
        imp.first_played_at = min(first, imp.first_played_at or first)
        imp.last_played_at = max(last, imp.last_played_at or last)


_NOTHING_FOUND = (
    "No listens found. Upload Spotify's Extended streaming history "
    "(Streaming_History_Audio_*.json or the zip) or a ListenBrainz export."
)


async def _consume(session: AsyncSession, imp: Import, path: Path, max_bytes: int) -> None:
    matched: set[int] = set()
    batch: list[Play] = []
    try:
        for record in read_records(path, max_bytes=max_bytes * UNPACK_FACTOR):
            imp.read += 1
            play = parse_record(record)
            if isinstance(play, Skip):
                imp.skipped += 1
                continue
            imp.source = imp.source or play.source
            batch.append(play)
            if len(batch) >= BATCH_SIZE:
                await _store(session, imp, batch, matched)
                batch = []
                imp.updated_at = _now()
                await session.commit()
    finally:
        if batch:
            await _store(session, imp, batch, matched)
    if imp.source is None:
        raise ImportFileError(_NOTHING_FOUND)


async def run_import(
    factory: SessionFactory, import_id: int, path: Path, *, max_bytes: int
) -> None:
    """Read an uploaded file into the user's listens. Runs after the upload
    answered, so it never raises: the outcome is in the import's status."""
    try:
        async with factory() as session:
            imp = await session.get(Import, import_id)
            if imp is None:
                return
            imp.status = "running"
            imp.updated_at = _now()
            await session.commit()
            try:
                await _consume(session, imp, path, max_bytes)
                imp.status = "done"
            except ImportFileError as e:
                imp.status = "failed"
                imp.error = str(e)
            except Exception:
                log.exception("import %s failed", import_id)
                await session.rollback()
                imp = await session.get(Import, import_id, populate_existing=True)
                if imp is None:
                    return
                imp.status = "failed"
                imp.error = "The import stopped on an unexpected error"
            imp.finished_at = imp.updated_at = _now()
            await session.commit()
    except Exception:
        log.exception("could not record the outcome of import %s", import_id)
    finally:
        path.unlink(missing_ok=True)


async def source_summary(session: AsyncSession, scope: Scope) -> dict:
    """Where the listens in range come from: the imported ones per source, and
    how many of them are older than the first listen from Last.fm."""
    lastfm_first = (await session.execute(
        bounded(select(func.min(Listen.played_at)), scope).where(Listen.source == "lastfm")
    )).scalar_one()
    imported = Listen.source != "lastfm"
    before = (
        and_(imported, Listen.played_at < lastfm_first)
        if lastfm_first is not None else imported
    )
    rows = (await session.execute(
        _scope(select(Listen.source, func.count(), func.count().filter(before)), scope)
        .where(imported)
        .group_by(Listen.source)
        .order_by(func.count().desc(), Listen.source)
    )).all()
    return {
        "imported": sum(r[1] for r in rows),
        "imported_before_lastfm": sum(r[2] for r in rows),
        "lastfm_first": iso_in(lastfm_first, scope.tz) if lastfm_first is not None else None,
        "sources": [{"source": r[0], "listens": r[1]} for r in rows],
    }
