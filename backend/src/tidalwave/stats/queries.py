from __future__ import annotations

from sqlalchemy import Integer, and_, cast, distinct, func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from tidalwave.models.db import AlbumArt, Listen
from tidalwave.stats.scope import Scope, iso_in


def _scope(stmt, scope: Scope):
    stmt = stmt.where(Listen.user_id == scope.user_id)
    if scope.since is not None:
        stmt = stmt.where(Listen.played_at >= scope.since)
    if scope.until is not None:
        stmt = stmt.where(Listen.played_at < scope.until)
    return stmt


def bounded(stmt, scope: Scope):
    stmt = stmt.where(Listen.user_id == scope.user_id)
    if scope.floor is not None:
        stmt = stmt.where(Listen.played_at >= scope.floor)
    if scope.ceiling is not None:
        stmt = stmt.where(Listen.played_at < scope.ceiling)
    return stmt


def _entity(stmt, artist: str | None, album: str | None, track: str | None):
    if artist is not None:
        stmt = stmt.where(Listen.artist == artist)
    if album is not None:
        stmt = stmt.where(Listen.album == album)
    if track is not None:
        stmt = stmt.where(Listen.track_title == track)
    return stmt


def _distinct_albums():
    return func.count(distinct(tuple_(Listen.artist, Listen.album))).filter(Listen.album.is_not(None))


async def _top(session, scope, column, label, *, limit, extra=None, artist=None, album=None, track=None):
    """Top-N by listen count. ``extra`` is an optional ``(column, label)`` pair
    that is added to the GROUP BY and returned alongside each row — used so a
    track row also carries its artist (lets the UI build a precise search link)."""
    cols = [column.label(label), func.count().label("count")]
    groups = [column]
    if extra is not None:
        extra_col, extra_label = extra
        cols.insert(1, extra_col.label(extra_label))
        groups.insert(0, extra_col)
    order = [func.count().desc(), column.asc()]
    if extra is not None:
        order.append(extra[0].asc())
    stmt = _entity(_scope(select(*cols), scope), artist, album, track).group_by(*groups).order_by(*order).limit(limit)
    rows = (await session.execute(stmt)).all()
    if extra is None:
        return [{label: row[0], "count": row[1]} for row in rows]
    return [{label: row[0], extra[1]: row[1], "count": row[2]} for row in rows]


def artist_cover_subquery(scope: Scope, artist: str | None = None):
    """One row per artist: ``(artist, image_url)``, the cover of the artist's
    most-listened album with a cover inside ``scope`` (ties by album name)."""
    n = func.count().label("n")
    stmt = (
        select(Listen.artist.label("artist"), Listen.album.label("album"),
               AlbumArt.image_url.label("image_url"), n)
        .join(AlbumArt, and_(AlbumArt.artist == Listen.artist, AlbumArt.album == Listen.album))
        .where(AlbumArt.image_url.is_not(None))
    )
    if artist is not None:
        stmt = stmt.where(Listen.artist == artist)
    per_album = _scope(stmt, scope).group_by(Listen.artist, Listen.album, AlbumArt.image_url).subquery()
    ranked = select(
        per_album.c.artist,
        per_album.c.image_url,
        func.row_number().over(
            partition_by=per_album.c.artist,
            order_by=(per_album.c.n.desc(), per_album.c.album.asc()),
        ).label("rn"),
    ).subquery()
    return select(ranked.c.artist, ranked.c.image_url).where(ranked.c.rn == 1).subquery()


async def top_artists(session: AsyncSession, scope: Scope, *, limit: int = 20) -> list[dict]:
    cover = artist_cover_subquery(scope)
    stmt = (
        _scope(select(Listen.artist, func.count().label("count"), cover.c.image_url), scope)
        .outerjoin(cover, cover.c.artist == Listen.artist)
        .group_by(Listen.artist, cover.c.image_url)
        .order_by(func.count().desc(), Listen.artist.asc())
        .limit(limit)
    )
    return [
        {"artist": r[0], "count": r[1], "image_url": r[2]}
        for r in (await session.execute(stmt)).all()
    ]


async def top_tracks(
    session: AsyncSession, scope: Scope, *, limit: int = 20,
    artist: str | None = None, album: str | None = None, track: str | None = None,
) -> list[dict]:
    # Group by (artist, track_title) so identically-titled songs by different
    # artists stay distinct and each row carries its artist.
    return await _top(session, scope, Listen.track_title, "track", limit=limit,
                      extra=(Listen.artist, "artist"), artist=artist, album=album, track=track)


async def top_albums(
    session: AsyncSession, scope: Scope, *, limit: int = 20,
    artist: str | None = None, album: str | None = None, track: str | None = None,
) -> list[dict]:
    stmt = (
        _entity(_scope(
            select(Listen.album, Listen.artist, func.count().label("count"), AlbumArt.image_url),
            scope,
        ), artist, album, track)
        .outerjoin(AlbumArt, and_(AlbumArt.artist == Listen.artist, AlbumArt.album == Listen.album))
        .group_by(Listen.album, Listen.artist, AlbumArt.image_url)
        .order_by(func.count().desc(), Listen.album.asc(), Listen.artist.asc())
        .limit(limit)
    )
    return [
        {"album": r[0], "artist": r[1], "count": r[2], "image_url": r[3]}
        for r in (await session.execute(stmt)).all()
    ]


async def total_listens(session: AsyncSession, scope: Scope) -> int:
    stmt = _scope(select(func.count()).select_from(Listen), scope)
    return (await session.execute(stmt)).scalar_one()


async def summary_stats(session: AsyncSession, scope: Scope) -> dict:
    """Headline totals for the overview: listens, distinct artists/tracks/albums
    and total seconds listened (summed from resolved track durations)."""
    stmt = _scope(
        select(
            func.count().label("total_listens"),
            func.count(distinct(Listen.artist)).label("distinct_artists"),
            func.count(distinct(tuple_(Listen.artist, Listen.track_title))).label("distinct_tracks"),
            _distinct_albums().label("distinct_albums"),
            func.coalesce(func.sum(Listen.duration_sec), 0).label("total_seconds"),
        ),
        scope,
    )
    row = (await session.execute(stmt)).one()
    return {
        "total_listens": int(row.total_listens),
        "distinct_artists": int(row.distinct_artists),
        "distinct_tracks": int(row.distinct_tracks),
        "distinct_albums": int(row.distinct_albums),
        "total_seconds": int(row.total_seconds),
    }


async def metrics_over_time(
    session: AsyncSession, scope: Scope, *, bucket: str = "day",
    artist: str | None = None, album: str | None = None, track: str | None = None,
) -> list[dict]:
    """Per-period listens, distinct artists/albums and seconds — drives the
    over-time graphs. Returns chronological rows keyed by ISO period."""
    period = func.date_trunc(bucket, func.timezone(scope.tz, Listen.played_at))
    stmt = (
        _entity(_scope(
            select(
                period.label("period"),
                func.count().label("listens"),
                func.count(distinct(Listen.artist)).label("artists"),
                _distinct_albums().label("albums"),
                func.coalesce(func.sum(Listen.duration_sec), 0).label("seconds"),
            ),
            scope,
        ), artist, album, track)
        .group_by(period)
        .order_by(period.asc())
    )
    return [
        {
            "period": row.period.isoformat(),
            "listens": int(row.listens),
            "artists": int(row.artists),
            "albums": int(row.albums),
            "seconds": int(row.seconds),
        }
        for row in (await session.execute(stmt)).all()
    ]


async def listening_clock(session: AsyncSession, scope: Scope) -> list[int]:
    """Returns a 24-element list: listens per local hour-of-day."""
    hour = cast(func.extract("hour", func.timezone(scope.tz, Listen.played_at)), Integer)
    stmt = _scope(select(hour, func.count()), scope).group_by(hour)
    counts = {int(h): int(c) for h, c in (await session.execute(stmt)).all()}
    return [counts.get(h, 0) for h in range(24)]


async def listening_weekday(session: AsyncSession, scope: Scope) -> list[int]:
    """Returns a 7-element list: listens per ISO weekday, index 0 = Monday .. 6 = Sunday."""
    dow = cast(func.extract("isodow", func.timezone(scope.tz, Listen.played_at)), Integer)
    stmt = _scope(select(dow, func.count()), scope).group_by(dow)
    counts = {int(d): int(c) for d, c in (await session.execute(stmt)).all()}
    return [counts.get(d, 0) for d in range(1, 8)]


async def listening_hour_weekday(session: AsyncSession, scope: Scope) -> list[list[int]]:
    """Returns 7 rows (Monday .. Sunday) of 24 local hour-of-day counts."""
    local = func.timezone(scope.tz, Listen.played_at)
    dow = cast(func.extract("isodow", local), Integer)
    hour = cast(func.extract("hour", local), Integer)
    stmt = _scope(select(dow, hour, func.count()), scope).group_by(dow, hour)
    grid = [[0] * 24 for _ in range(7)]
    for d, h, c in (await session.execute(stmt)).all():
        grid[int(d) - 1][int(h)] = int(c)
    return grid


async def listens_over_time(session: AsyncSession, scope: Scope, *, bucket: str = "day") -> list[dict]:
    """Listens grouped by calendar period. `bucket` is one of day|week|month.

    Returns chronological [{"period": <iso date/datetime>, "count": <int>}].
    """
    period = func.date_trunc(bucket, func.timezone(scope.tz, Listen.played_at))
    stmt = (
        _scope(select(period.label("period"), func.count().label("count")), scope)
        .group_by(period)
        .order_by(period.asc())
    )
    return [
        {"period": row[0].isoformat(), "count": row[1]}
        for row in (await session.execute(stmt)).all()
    ]


async def recent_listens(
    session: AsyncSession, scope: Scope, *, limit: int = 50,
    artist: str | None = None, album: str | None = None, track: str | None = None,
) -> list[dict]:
    stmt = (
        _entity(_scope(
            select(Listen.track_title, Listen.artist, Listen.album, Listen.played_at, AlbumArt.image_url),
            scope,
        ), artist, album, track)
        .outerjoin(AlbumArt, and_(AlbumArt.artist == Listen.artist, AlbumArt.album == Listen.album))
        .order_by(Listen.played_at.desc())
        .limit(limit)
    )
    return [
        {"track": r[0], "artist": r[1], "album": r[2], "played_at": iso_in(r[3], scope.tz), "image_url": r[4]}
        for r in (await session.execute(stmt)).all()
    ]
