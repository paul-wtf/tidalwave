from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from tidalwave.models.db import AlbumArt, Listen, SyncState
from tidalwave.models.domain import Scrobble

# Postgres binds at most 32767 parameters per statement. Dividing by the column
# count gives the largest number of rows a single INSERT can carry.
_PG_MAX_BIND_PARAMS = 32767


async def upsert_listens(
    session: AsyncSession, user_id: int, scrobbles: list[Scrobble]
) -> int:
    """Insert datable scrobbles, skipping any without a timestamp and any duplicates.

    Returns the number of rows actually inserted. Scrobbles with ``played_at is None``
    (now-playing tracks and dateless tracks) are skipped — they cannot be stored because
    ``played_at`` is part of the dedup key and is NOT NULL.
    """
    rows = [
        {
            "user_id": user_id,
            "track_title": s.track_title,
            "artist": s.artist,
            "album": s.album,
            "played_at": s.played_at,
            "track_mbid": s.track_mbid,
            "artist_mbid": s.artist_mbid,
            "album_mbid": s.album_mbid,
        }
        for s in scrobbles
        if s.played_at is not None
    ]
    if not rows:
        return 0
    # A first backfill spans the whole listening history, which is far more rows than
    # one statement can bind — insert in chunks that stay under the parameter limit.
    chunk_size = _PG_MAX_BIND_PARAMS // len(rows[0])
    inserted = 0
    for start in range(0, len(rows), chunk_size):
        stmt = (
            pg_insert(Listen)
            .values(rows[start : start + chunk_size])
            .on_conflict_do_nothing(constraint="uq_listen_dedup")
            .returning(Listen.id)
        )
        result = await session.execute(stmt)
        inserted += len(result.fetchall())
    return inserted


async def get_sync_state(session: AsyncSession, user_id: int) -> SyncState | None:
    return (
        await session.execute(select(SyncState).where(SyncState.user_id == user_id))
    ).scalar_one_or_none()


async def advance_sync_state(
    session: AsyncSession, user_id: int, *, last_played_at: datetime
) -> None:
    stmt = (
        pg_insert(SyncState)
        .values(user_id=user_id, last_played_at=last_played_at, last_synced_at=func.now())
        .on_conflict_do_update(
            index_elements=[SyncState.user_id],
            set_={"last_played_at": last_played_at, "last_synced_at": func.now()},
        )
    )
    await session.execute(stmt)


async def mark_synced(session: AsyncSession, user_id: int) -> None:
    stmt = (
        pg_insert(SyncState)
        .values(user_id=user_id, last_synced_at=func.now())
        .on_conflict_do_update(
            index_elements=[SyncState.user_id], set_={"last_synced_at": func.now()}
        )
    )
    await session.execute(stmt)


async def upsert_album_art(session: AsyncSession, scrobbles: Sequence[Scrobble]) -> None:
    """Record (artist, album) pairs; a known URL is never overwritten by a missing one."""
    pairs: dict[tuple[str, str], str | None] = {}
    for s in scrobbles:
        if s.album is None:
            continue
        key = (s.artist, s.album)
        pairs[key] = s.image_url or pairs.get(key)
    if not pairs:
        return
    rows = [{"artist": a, "album": b, "image_url": url} for (a, b), url in pairs.items()]
    chunk_size = _PG_MAX_BIND_PARAMS // 3
    for start in range(0, len(rows), chunk_size):
        stmt = pg_insert(AlbumArt).values(rows[start : start + chunk_size])
        stmt = stmt.on_conflict_do_update(
            constraint="uq_album_art",
            set_={
                "image_url": func.coalesce(stmt.excluded.image_url, AlbumArt.image_url),
                "fetched_at": func.now(),
            },
        )
        await session.execute(stmt)
