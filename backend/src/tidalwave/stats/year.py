from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime

from sqlalchemy import Date, Integer, and_, cast, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tidalwave.models.db import AlbumArt, Listen
from tidalwave.stats import album_runs, decades, genres, insights, queries
from tidalwave.stats.scope import Scope, _local_midnight, iso_in

TOP = 10
NEW_ARTISTS = 10
GENRES = 8
RUNS = 6


def year_bounds(year: int, tz: str) -> tuple[datetime, datetime]:
    return _local_midnight(date(year, 1, 1), tz), _local_midnight(date(year + 1, 1, 1), tz)


def year_scope(scope: Scope, year: int) -> Scope | None:
    """The scope of one calendar year in the owner's timezone, or None when a
    share does not cover that whole year."""
    since, until = year_bounds(year, scope.tz)
    if scope.floor is not None and scope.floor > since:
        return None
    if scope.ceiling is not None and scope.ceiling < until:
        return None
    return replace(scope, since=since, until=until)


def _local_year(scope: Scope):
    return cast(func.extract("year", func.timezone(scope.tz, Listen.played_at)), Integer)


async def years(session: AsyncSession, scope: Scope) -> list[dict]:
    year = _local_year(scope)
    rows = (await session.execute(
        queries.bounded(select(year, func.count()), scope).group_by(year).order_by(year.desc())
    )).all()
    return [
        {"year": int(y), "listens": int(n)}
        for y, n in rows
        if year_scope(scope, int(y)) is not None
    ]


async def _months(session: AsyncSession, scope: Scope) -> list[dict]:
    month = cast(func.extract("month", func.timezone(scope.tz, Listen.played_at)), Integer)
    totals = {
        int(m): (int(n), int(sec), int(art))
        for m, n, sec, art in (await session.execute(
            queries._scope(select(
                month, func.count(),
                func.coalesce(func.sum(Listen.duration_sec), 0),
                func.count(distinct(Listen.artist)),
            ), scope).group_by(month)
        )).all()
    }
    per_artist = queries._scope(
        select(month.label("m"), Listen.artist.label("artist"), func.count().label("n")), scope
    ).group_by(month, Listen.artist).subquery()
    ranked = select(
        per_artist.c.m, per_artist.c.artist,
        func.row_number().over(
            partition_by=per_artist.c.m,
            order_by=(per_artist.c.n.desc(), per_artist.c.artist.asc()),
        ).label("rn"),
    ).subquery()
    tops = dict((await session.execute(
        select(ranked.c.m, ranked.c.artist).where(ranked.c.rn == 1)
    )).tuples().all())
    return [
        {
            "month": m,
            "listens": totals.get(m, (0, 0, 0))[0],
            "seconds": totals.get(m, (0, 0, 0))[1],
            "artists": totals.get(m, (0, 0, 0))[2],
            "top_artist": tops.get(m),
        }
        for m in range(1, 13)
    ]


async def _busiest_day(session: AsyncSession, scope: Scope) -> dict | None:
    busiest = await insights._busiest_day(session, scope)
    if busiest is None:
        return None
    day = cast(func.timezone(scope.tz, Listen.played_at), Date)
    top = (await session.execute(
        queries._scope(select(Listen.artist), scope)
        .where(day == date.fromisoformat(busiest["date"]))
        .group_by(Listen.artist)
        .order_by(func.count().desc(), Listen.artist.asc())
        .limit(1)
    )).scalar_one_or_none()
    return {**busiest, "top_artist": top}


async def _edge_listen(session: AsyncSession, scope: Scope, *, last: bool) -> dict | None:
    order = Listen.played_at.desc() if last else Listen.played_at.asc()
    row = (await session.execute(
        queries._scope(select(
            Listen.track_title, Listen.artist, Listen.album, Listen.played_at, AlbumArt.image_url
        ), scope)
        .outerjoin(AlbumArt, and_(AlbumArt.artist == Listen.artist, AlbumArt.album == Listen.album))
        .order_by(order, Listen.id.desc() if last else Listen.id.asc())
        .limit(1)
    )).first()
    if row is None:
        return None
    return {
        "track": row[0], "artist": row[1], "album": row[2],
        "played_at": iso_in(row[3], scope.tz), "image_url": row[4],
    }


async def _new_artists(session: AsyncSession, scope: Scope) -> dict:
    first = insights._first_seen(scope, Listen.artist)
    count = (await session.execute(
        select(func.count()).select_from(first).where(*insights._in_range(first.c.first, scope))
    )).scalar_one()
    return {
        "count": int(count),
        "top": await insights._new_artists(session, scope, NEW_ARTISTS),
    }


async def year_in_review(
    session: AsyncSession, scope: Scope, year: int, *, compare: bool
) -> dict:
    previous = None
    if compare:
        since, until = year_bounds(year - 1, scope.tz)
        previous = await queries.summary_stats(session, replace(scope, since=since, until=until))
    return {
        "year": year,
        "summary": await queries.summary_stats(session, scope),
        "previous": previous,
        "top_artists": await queries.top_artists(session, scope, limit=TOP),
        "top_tracks": await queries.top_tracks(session, scope, limit=TOP),
        "top_albums": await queries.top_albums(session, scope, limit=TOP),
        "months": await _months(session, scope),
        "busiest_day": await _busiest_day(session, scope),
        "first_listen": await _edge_listen(session, scope, last=False),
        "last_listen": await _edge_listen(session, scope, last=True),
        "new_artists": await _new_artists(session, scope),
        "genres": await genres.genres(session, scope, limit=GENRES),
        "decades": await decades.decades(session, scope),
        "longest_streak": await insights._longest_streak(session, scope),
        "album_runs": await album_runs.album_runs(session, scope, limit=RUNS),
    }
