from __future__ import annotations

import logging

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tidalwave.db import session_scope

from tidalwave.ingest.service import RecentTracksSource, ingest_user
from tidalwave.lastfm.client import LastfmError
from tidalwave.models.db import User

log = logging.getLogger(__name__)

# Last.fm error codes that mean the session key is invalid / revoked.
# The user must reconnect; keep polling them forever serves no purpose.
_AUTH_ERROR_CODES = {4, 9}


async def ingest_one_user(
    session: AsyncSession, client: RecentTracksSource, user: User
) -> int | str:
    """Ingest one user. Returns inserted count, or "disconnected"/"error".

    Auth errors (codes 4/9) flip user.disconnected; transient errors are logged.
    Does not commit — the caller owns the transaction.
    """
    try:
        return await ingest_user(session, client, user)
    except LastfmError as e:
        if e.code in _AUTH_ERROR_CODES:
            # Expected operational state (user revoked their session key) —
            # warn without a stack trace, then stop polling them.
            log.warning(
                "disconnecting %s: Last.fm auth error %s (%s)",
                user.lastfm_username, e.code, e,
            )
            user.disconnected = True
            await session.flush()
            return "disconnected"
        log.exception("ingest failed for %s", user.lastfm_username)
        return "error"
    except httpx.HTTPError as e:
        log.warning("ingest failed for %s: Last.fm unreachable (%s)", user.lastfm_username, e)
        return "error"


async def ingest_user_now(
    session_factory: async_sessionmaker[AsyncSession],
    client: RecentTracksSource,
    user_id: int,
) -> None:
    """Background-task entrypoint: ingest a single user right after they connect.

    Opens its own session (the request session is closed by now), re-loads the
    user by id, ingests, and commits. Never raises — the HTTP response is already
    sent, so failures are only logged.
    """
    try:
        async with session_scope(session_factory) as session:
            user = await session.get(User, user_id)
            if user is None:
                return
            await ingest_one_user(session, client, user)
            await session.commit()
    except Exception:
        log.exception("immediate ingest failed for user_id=%s", user_id)


async def poll_all_users(
    session: AsyncSession, client: RecentTracksSource
) -> dict[str, int | str]:
    """Ingest for every connected user. Per-user failures are isolated, not raised."""
    users = (
        await session.execute(select(User).where(User.disconnected.is_(False)))
    ).scalars().all()
    report: dict[str, int | str] = {}
    for user in users:
        report[user.lastfm_username] = await ingest_one_user(session, client, user)
    return report
