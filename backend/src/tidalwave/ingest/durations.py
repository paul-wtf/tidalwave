from __future__ import annotations

import asyncio
import logging
from typing import Any, Protocol, cast

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from tidalwave.lastfm.client import LastfmError
from tidalwave.models.db import Listen, TrackDuration

log = logging.getLogger(__name__)


class TrackInfoSource(Protocol):
    async def get_track_info(self, artist: str, track: str) -> int | None: ...


_NOT_FOUND = 6
_RATE_LIMITED = 29


class _RateLimited(Exception):
    pass


async def fill_missing_durations(
    session: AsyncSession,
    client: TrackInfoSource,
    *,
    user_id: int | None = None,
    max_tracks: int | None = None,
) -> int:
    """Resolve track lengths for listens that don't have one yet.

    Finds distinct (artist, track) pairs among listens with ``duration_sec IS
    NULL`` that are not cached as unknown, looks each up in the
    ``track_durations`` cache, fetches from Last.fm on a miss, then writes the
    length back onto the matching listens.

    A track is cached as unknown only when Last.fm answers without a length or
    reports it as not found; failed lookups are retried on the next run, and a
    rate-limit error ends the run. ``max_tracks`` caps how many distinct tracks
    are processed per call; ``user_id`` scopes the work to one user. Returns the
    number of listen rows updated.
    """
    known_unknown = select(TrackDuration.id).where(
        TrackDuration.artist == Listen.artist,
        TrackDuration.track_title == Listen.track_title,
        TrackDuration.duration_sec.is_(None),
    )
    stmt = (
        select(Listen.artist, Listen.track_title)
        .where(Listen.duration_sec.is_(None), ~known_unknown.exists())
        .group_by(Listen.artist, Listen.track_title)
    )
    if user_id is not None:
        stmt = stmt.where(Listen.user_id == user_id)
    if max_tracks is not None:
        stmt = stmt.order_by(func.random()).limit(max_tracks)

    pairs = [(row[0], row[1]) for row in (await session.execute(stmt)).all()]
    updated = 0
    for artist, track in pairs:
        try:
            duration = await _resolve_one(session, client, artist, track)
        except _RateLimited:
            break
        if duration is None:
            continue
        upd = update(Listen).where(
            Listen.artist == artist,
            Listen.track_title == track,
            Listen.duration_sec.is_(None),
        )
        if user_id is not None:
            upd = upd.where(Listen.user_id == user_id)
        result = cast("CursorResult[Any]", await session.execute(upd.values(duration_sec=duration)))
        updated += result.rowcount or 0
    return updated


async def _resolve_one(
    session: AsyncSession, client: TrackInfoSource, artist: str, track: str
) -> int | None:
    """Return a track's length in seconds via the cache, fetching once on a miss."""
    cached = (
        await session.execute(
            select(TrackDuration.duration_sec).where(
                TrackDuration.artist == artist, TrackDuration.track_title == track
            )
        )
    ).first()
    if cached is not None:
        return cached[0]

    try:
        duration = await client.get_track_info(artist, track)
    except LastfmError as e:
        log.warning("track.getInfo failed for %s — %s: %s", artist, track, e)
        if e.code == _RATE_LIMITED:
            raise _RateLimited from e
        if e.code != _NOT_FOUND:
            return None
        duration = None
    except Exception:
        log.exception("track.getInfo errored for %s — %s", artist, track)
        return None
    finally:
        await asyncio.sleep(0.1)

    await session.execute(
        pg_insert(TrackDuration)
        .values(artist=artist, track_title=track, duration_sec=duration)
        .on_conflict_do_nothing(constraint="uq_track_duration")
    )
    return duration
