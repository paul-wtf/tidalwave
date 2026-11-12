from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tidalwave.auth.allowlist import runtime_usernames
from tidalwave.auth.registration import ensure_allowed
from tidalwave.models.db import User


async def upsert_user_from_session(
    session: AsyncSession,
    username: str,
    session_key: str,
    *,
    mode: str,
    allowlist: list[str],
) -> User:
    """Create the user (first connect) or refresh an existing user's session key."""
    existing = (
        await session.execute(select(User).where(User.lastfm_username == username))
    ).scalar_one_or_none()
    if existing is not None:
        existing.lastfm_session_key = session_key
        existing.disconnected = False
        await session.flush()
        return existing

    if mode != "open":
        allowlist = [*allowlist, *await runtime_usernames(session)]
    ensure_allowed(username, mode=mode, allowlist=allowlist)
    is_first = (await session.execute(select(func.count()).select_from(User))).scalar_one() == 0
    user = User(
        lastfm_username=username,
        lastfm_session_key=session_key,
        is_admin=is_first,
    )
    session.add(user)
    await session.flush()
    return user


async def delete_account(session: AsyncSession, user: User) -> None:
    # Everything a user owns references users.id with ON DELETE CASCADE.
    await session.delete(user)
    await session.flush()
