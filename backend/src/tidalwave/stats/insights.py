from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import Date, Integer, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tidalwave.models.db import Listen
from tidalwave.stats.queries import _scope, artist_cover_subquery, bounded
from tidalwave.stats.scope import Scope, iso_in

REDISCOVERY_GAP = timedelta(days=180)
ON_THIS_DAY_TRACKS = 3
SESSION_GAP = timedelta(minutes=30)
HEATMAP_DAYS = 365


def _first_seen(scope: Scope, *columns):
    return (
        bounded(select(*columns, func.min(Listen.played_at).label("first")), scope)
        .group_by(*columns)
        .subquery()
    )


def _in_range(column, scope: Scope):
    conditions = [column >= scope.since]
    if scope.until is not None:
        conditions.append(column < scope.until)
    return conditions


async def _new_artists(session, scope: Scope, limit: int) -> list[dict]:
    first = _first_seen(scope, Listen.artist)
    cover = artist_cover_subquery(scope)
    stmt = (
        _scope(select(Listen.artist, first.c.first, func.count(), cover.c.image_url), scope)
        .join(first, first.c.artist == Listen.artist)
        .outerjoin(cover, cover.c.artist == Listen.artist)
        .where(*_in_range(first.c.first, scope))
        .group_by(Listen.artist, first.c.first, cover.c.image_url)
        .order_by(func.count().desc(), Listen.artist.asc())
        .limit(limit)
    )
    return [
        {"artist": r[0], "first_listen": iso_in(r[1], scope.tz), "listens": r[2], "image_url": r[3]}
        for r in (await session.execute(stmt)).all()
    ]


async def _new_tracks(session, scope: Scope, limit: int) -> tuple[int, list[dict]]:
    first = _first_seen(scope, Listen.artist, Listen.track_title)
    joined = (
        _scope(select(Listen.track_title, Listen.artist, first.c.first, func.count().label("n")), scope)
        .join(first, (first.c.artist == Listen.artist) & (first.c.track_title == Listen.track_title))
        .where(*_in_range(first.c.first, scope))
        .group_by(Listen.track_title, Listen.artist, first.c.first)
    )
    total = (await session.execute(select(func.count()).select_from(joined.subquery()))).scalar_one()
    rows = (await session.execute(
        joined.order_by(func.count().desc(), Listen.track_title.asc(), Listen.artist.asc()).limit(limit)
    )).all()
    return int(total), [
        {"track": r[0], "artist": r[1], "first_listen": iso_in(r[2], scope.tz), "listens": r[3]}
        for r in rows
    ]


async def _rediscoveries(session, scope: Scope, limit: int) -> list[dict]:
    current = (
        _scope(select(Listen.artist, func.min(Listen.played_at).label("first"),
                      func.count().label("n")), scope)
        .group_by(Listen.artist)
        .subquery()
    )
    previous = (
        bounded(select(Listen.artist, func.max(Listen.played_at).label("last")), scope)
        .where(Listen.played_at < scope.since)
        .group_by(Listen.artist)
        .subquery()
    )
    gap = current.c.first - previous.c.last
    stmt = (
        select(current.c.artist, previous.c.last, gap, current.c.n)
        .join(previous, previous.c.artist == current.c.artist)
        .where(gap >= REDISCOVERY_GAP)
        .order_by(gap.desc(), current.c.artist.asc())
        .limit(limit)
    )
    return [
        {"artist": r[0], "previous_listen": iso_in(r[1], scope.tz), "gap_days": r[2].days, "listens": r[3]}
        for r in (await session.execute(stmt)).all()
    ]


async def discoveries(session: AsyncSession, scope: Scope, *, limit: int = 20) -> dict:
    if scope.since is None:
        return {"new_artists": [], "new_tracks_count": 0, "new_tracks": [], "rediscoveries": []}
    count, tracks = await _new_tracks(session, scope, limit)
    return {
        "new_artists": await _new_artists(session, scope, limit),
        "new_tracks_count": count,
        "new_tracks": tracks,
        "rediscoveries": await _rediscoveries(session, scope, limit),
    }


async def on_this_day(
    session: AsyncSession, scope: Scope, *, now: datetime | None = None
) -> list[dict]:
    today = (now or datetime.now(UTC)).astimezone(ZoneInfo(scope.tz))
    local = func.timezone(scope.tz, Listen.played_at)
    year = cast(func.extract("year", local), Integer)
    stmt = (
        bounded(select(year.label("year"), Listen.track_title, Listen.artist, func.count()), scope)
        .where(
            cast(func.extract("month", local), Integer) == today.month,
            cast(func.extract("day", local), Integer) == today.day,
            year < today.year,
        )
        .group_by(year, Listen.track_title, Listen.artist)
    )
    years: dict[int, dict] = {}
    for y, track, artist, n in (await session.execute(stmt)).all():
        entry = years.setdefault(y, {"year": y, "listens": 0, "top_tracks": []})
        entry["listens"] += n
        entry["top_tracks"].append({"track": track, "artist": artist, "count": n})
    result = []
    for y in sorted(years, reverse=True):
        entry = years[y]
        entry["top_tracks"].sort(key=lambda t: (-t["count"], t["track"], t["artist"]))
        entry["top_tracks"] = entry["top_tracks"][:ON_THIS_DAY_TRACKS]
        result.append(entry)
    return result


def _local_day(scope: Scope):
    return cast(func.timezone(scope.tz, Listen.played_at), Date)


def _islands(scope: Scope, *, bound_only: bool = False):
    select_days = bounded if bound_only else _scope
    days = select_days(select(_local_day(scope).label("day")), scope).distinct().subquery()
    key = (days.c.day - cast(func.row_number().over(order_by=days.c.day), Integer)).label("key")
    keyed = select(days.c.day, key).subquery()
    return (
        select(
            func.count().label("days"),
            func.min(keyed.c.day).label("start"),
            func.max(keyed.c.day).label("end"),
        )
        .group_by(keyed.c.key)
        .subquery()
    )


async def _longest_streak(session, scope: Scope) -> dict | None:
    islands = _islands(scope)
    row = (await session.execute(
        select(islands).order_by(islands.c.days.desc(), islands.c.start.asc()).limit(1)
    )).first()
    if row is None:
        return None
    return {"days": row.days, "start": row.start.isoformat(), "end": row.end.isoformat()}


async def _current_streak(session, scope: Scope, now: datetime) -> dict | None:
    if (scope.until is not None and scope.until <= now) or (
        scope.since is not None and scope.since > now
    ):
        return None
    today = now.astimezone(ZoneInfo(scope.tz)).date()
    islands = _islands(scope, bound_only=True)
    row = (await session.execute(
        select(islands).order_by(islands.c.end.desc()).limit(1)
    )).first()
    if row is None or row.end < today - timedelta(days=1):
        return None
    return {"days": row.days, "start": row.start.isoformat()}


async def _busiest_day(session, scope: Scope) -> dict | None:
    day = _local_day(scope)
    row = (await session.execute(
        _scope(select(day.label("day"), func.count().label("n")), scope)
        .group_by(day)
        .order_by(func.count().desc(), day.asc())
        .limit(1)
    )).first()
    if row is None:
        return None
    return {"date": row.day.isoformat(), "listens": row.n}


async def _longest_session(session, scope: Scope) -> dict | None:
    previous = func.lag(Listen.played_at).over(order_by=Listen.played_at)
    gapped = _scope(
        select(Listen.played_at, Listen.duration_sec, previous.label("prev")), scope
    ).subquery()
    is_break = func.coalesce(gapped.c.played_at - gapped.c.prev > SESSION_GAP, True)
    numbered = select(
        gapped.c.played_at,
        gapped.c.duration_sec,
        func.sum(cast(is_break, Integer)).over(order_by=gapped.c.played_at).label("sid"),
    ).subquery()
    row = (await session.execute(
        select(
            func.min(numbered.c.played_at).label("start"),
            func.count().label("n"),
            func.coalesce(func.sum(numbered.c.duration_sec), 0).label("seconds"),
        )
        .group_by(numbered.c.sid)
        .order_by(func.count().desc(), func.min(numbered.c.played_at).asc())
        .limit(1)
    )).first()
    if row is None:
        return None
    return {"start": iso_in(row.start, scope.tz), "listens": row.n, "seconds": int(row.seconds)}


async def records(
    session: AsyncSession, scope: Scope, *, now: datetime | None = None
) -> dict:
    now = now or datetime.now(UTC)
    return {
        "longest_streak": await _longest_streak(session, scope),
        "current_streak": await _current_streak(session, scope, now),
        "busiest_day": await _busiest_day(session, scope),
        "longest_session": await _longest_session(session, scope),
    }


def _heatmap_window(scope: Scope, now: datetime) -> tuple[date, date]:
    zone = ZoneInfo(scope.tz)
    end_instant = scope.until - timedelta(microseconds=1) if scope.until is not None else now
    end = end_instant.astimezone(zone).date()
    if scope.since is not None:
        start = min(scope.since.astimezone(zone).date(), end)
        if (end - start).days + 1 <= 366:
            return start, end
    return end - timedelta(days=HEATMAP_DAYS - 1), end


async def heatmap(
    session: AsyncSession, scope: Scope, *, now: datetime | None = None
) -> dict:
    start, end = _heatmap_window(scope, now or datetime.now(UTC))
    day = _local_day(scope)
    rows = (await session.execute(
        _scope(select(day.label("day"), func.count().label("n")), scope)
        .where(day >= start, day <= end)
        .group_by(day)
        .order_by(day)
    )).all()
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "days": [{"date": r.day.isoformat(), "listens": r.n} for r in rows],
    }
