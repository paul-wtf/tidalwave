from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tidalwave.models.db import AllowlistEntry


@dataclass(frozen=True, slots=True)
class Entry:
    username: str
    fixed: bool
    added_at: datetime | None


class AlreadyListed(Exception):
    pass


class FixedEntry(Exception):
    pass


async def runtime_usernames(session: AsyncSession) -> list[str]:
    return list((await session.execute(select(AllowlistEntry.lastfm_username))).scalars())


async def entries(session: AsyncSession, env: list[str]) -> list[Entry]:
    fixed = {name.lower(): Entry(name, True, None) for name in env}
    rows = (await session.execute(select(AllowlistEntry))).scalars()
    added = {
        row.lastfm_username.lower(): Entry(row.lastfm_username, False, row.created_at)
        for row in rows
        if row.lastfm_username.lower() not in fixed
    }
    return sorted([*fixed.values(), *added.values()], key=lambda e: e.username.lower())


async def add(session: AsyncSession, env: list[str], username: str) -> Entry:
    key = username.lower()
    taken = await session.scalar(
        select(AllowlistEntry.id).where(func.lower(AllowlistEntry.lastfm_username) == key)
    )
    if taken is not None or key in {name.lower() for name in env}:
        raise AlreadyListed(username)
    row = AllowlistEntry(lastfm_username=username)
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return Entry(row.lastfm_username, False, row.created_at)


async def remove(session: AsyncSession, env: list[str], username: str) -> bool:
    key = username.lower()
    if key in {name.lower() for name in env}:
        raise FixedEntry(username)
    removed = await session.scalar(
        delete(AllowlistEntry)
        .where(func.lower(AllowlistEntry.lastfm_username) == key)
        .returning(AllowlistEntry.id)
    )
    return removed is not None
