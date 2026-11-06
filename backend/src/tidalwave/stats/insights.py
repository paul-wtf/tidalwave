from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import Integer, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tidalwave.models.db import Listen
from tidalwave.stats.queries import _scope, artist_cover_subquery, bounded
from tidalwave.stats.scope import Scope

REDISCOVERY_GAP = timedelta(days=180)
ON_THIS_DAY_TRACKS = 3


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
        {"artist": r[0], "first_listen": r[1].isoformat(), "listens": r[2], "image_url": r[3]}
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
        {"track": r[0], "artist": r[1], "first_listen": r[2].isoformat(), "listens": r[3]}
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
        {"artist": r[0], "previous_listen": r[1].isoformat(), "gap_days": r[2].days, "listens": r[3]}
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
