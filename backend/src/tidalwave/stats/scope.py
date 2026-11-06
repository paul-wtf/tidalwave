from __future__ import annotations

import calendar as _calendar
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tidalwave.auth.session import current_user
from tidalwave.deps import get_session
from tidalwave.models.db import Share, User


@dataclass(frozen=True, slots=True)
class Scope:
    user_id: int
    tz: str
    since: datetime | None
    until: datetime | None
    floor: datetime | None = None
    ceiling: datetime | None = None
    shared: bool = False


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _local_midnight(day: date, tz: str) -> datetime:
    return datetime.combine(day, time.min, tzinfo=ZoneInfo(tz)).astimezone(UTC)


def resolve_range(
    tz: str,
    *,
    since: datetime | None,
    until: datetime | None,
    start: date | None,
    end: date | None,
) -> tuple[datetime | None, datetime | None]:
    if (start is not None or end is not None) and (since is not None or until is not None):
        raise HTTPException(status_code=422, detail="Use either since/until or start/end")
    if start is not None or end is not None:
        return (
            _local_midnight(start, tz) if start is not None else None,
            _local_midnight(end, tz) if end is not None else None,
        )
    return _aware(since), _aware(until)


def intersect(
    since: datetime | None,
    until: datetime | None,
    floor: datetime | None,
    ceiling: datetime | None,
) -> tuple[datetime | None, datetime | None]:
    lows = [v for v in (since, floor) if v is not None]
    highs = [v for v in (until, ceiling) if v is not None]
    return (max(lows) if lows else None, min(highs) if highs else None)


def _shift_back(moment: datetime, tz: str, unit: Literal["week", "month", "year"]) -> datetime:
    local = moment.astimezone(ZoneInfo(tz)).replace(tzinfo=None)
    if unit == "week":
        shifted = local - timedelta(days=7)
    else:
        months = 1 if unit == "month" else 12
        index = local.year * 12 + local.month - 1 - months
        year, month = divmod(index, 12)
        month += 1
        day = min(local.day, _calendar.monthrange(year, month)[1])
        shifted = local.replace(year=year, month=month, day=day)
    return shifted.replace(tzinfo=ZoneInfo(tz)).astimezone(UTC)


def previous_range(
    tz: str,
    since: datetime,
    until: datetime | None,
    calendar: Literal["week", "month", "year"] | None,
    now: datetime,
) -> tuple[datetime, datetime]:
    end = until if until is not None else now
    if calendar is None:
        return since - (end - since), since
    return _shift_back(since, tz, calendar), _shift_back(end, tz, calendar)


def user_tz(user: User) -> str:
    return user.timezone or "UTC"


async def own_scope(
    user: User = Depends(current_user),
    since: datetime | None = None,
    until: datetime | None = None,
    start: date | None = None,
    end: date | None = None,
) -> Scope:
    tz = user_tz(user)
    lo, hi = resolve_range(tz, since=since, until=until, start=start, end=end)
    return Scope(user_id=user.id, tz=tz, since=lo, until=hi)


async def shared_scope(
    token: str,
    since: datetime | None = None,
    until: datetime | None = None,
    start: date | None = None,
    end: date | None = None,
    session: AsyncSession = Depends(get_session),
) -> Scope:
    share = (
        await session.execute(
            select(Share).where(Share.share_token == token, Share.revoked_at.is_(None))
        )
    ).scalar_one_or_none()
    if share is None:
        raise HTTPException(status_code=404, detail="Share not found")
    owner = await session.get(User, share.user_id)
    tz = user_tz(owner) if owner is not None else "UTC"
    lo, hi = resolve_range(tz, since=since, until=until, start=start, end=end)
    floor, ceiling = _aware(share.range_from), _aware(share.range_to)
    lo, hi = intersect(lo, hi, floor, ceiling)
    return Scope(
        user_id=share.user_id, tz=tz, since=lo, until=hi,
        floor=floor, ceiling=ceiling, shared=True,
    )
