from __future__ import annotations

from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from tidalwave.ingest.repository import (
    advance_sync_state,
    get_sync_state,
    mark_synced,
    upsert_album_art,
    upsert_listens,
)
from tidalwave.lastfm.client import RecentTracksPage
from tidalwave.models.db import User
from tidalwave.models.domain import Scrobble


class RecentTracksSource(Protocol):
    async def get_recent_tracks(
        self,
        username: str,
        *,
        from_ts: int | None = ...,
        page: int = ...,
        limit: int = ...,
        session_key: str | None = ...,
    ) -> RecentTracksPage: ...


async def ingest_user(session: AsyncSession, client: RecentTracksSource, user: User) -> int:
    state = await get_sync_state(session, user.id)
    from_ts: int | None = None
    if state is not None and state.last_played_at is not None:
        from_ts = int(state.last_played_at.timestamp()) + 1
    return await _collect_and_store(session, client, user, from_ts=from_ts)


async def backfill_user(session: AsyncSession, client: RecentTracksSource, user: User) -> int:
    """Import the full history (no sync floor). Idempotent via the dedup constraint."""
    return await _collect_and_store(session, client, user, from_ts=None)


async def _collect_and_store(
    session: AsyncSession, client: RecentTracksSource, user: User, *, from_ts: int | None
) -> int:
    collected: list[Scrobble] = []
    page = 1
    total_pages = 1
    while page <= total_pages:
        result = await client.get_recent_tracks(
            user.lastfm_username,
            from_ts=from_ts,
            page=page,
            session_key=user.lastfm_session_key,
        )
        total_pages = result.total_pages
        collected.extend(result.scrobbles)
        page += 1

    inserted = await upsert_listens(session, user.id, collected)
    await upsert_album_art(session, collected)
    newest = max((s.played_at for s in collected if s.played_at is not None), default=None)
    if newest is not None:
        await advance_sync_state(session, user.id, last_played_at=newest)
    else:
        await mark_synced(session, user.id)
    return inserted
