from __future__ import annotations

from datetime import timedelta

from sqlalchemy import Integer, and_, cast, distinct, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from tidalwave.models.db import AlbumArt, Listen
from tidalwave.stats.queries import _scope
from tidalwave.stats.scope import Scope, iso_in

# Last.fm does not say how many tracks an album has, so "played through" is a
# heuristic: at least this many different tracks of one album in a row, and no
# pause between two of them longer than the gap.
RUN_MIN_TRACKS = 6
RUN_MAX_GAP = timedelta(minutes=10)


async def album_runs(
    session: AsyncSession, scope: Scope, *, limit: int = 20,
    artist: str | None = None, album: str | None = None,
) -> dict:
    order = (Listen.played_at, Listen.id)

    def previous(column):
        return func.lag(column).over(order_by=order)

    stream = _scope(
        select(
            Listen.id, Listen.played_at, Listen.artist, Listen.album, Listen.track_title,
            Listen.duration_sec,
            previous(Listen.played_at).label("prev_at"),
            previous(Listen.duration_sec).label("prev_len"),
            previous(Listen.artist).label("prev_artist"),
            previous(Listen.album).label("prev_album"),
        ),
        scope,
    ).subquery()
    # played_at is when a track started, so the pause begins where the previous
    # track ended. Without a known length it counts from that track's start.
    pause = (
        stream.c.played_at - stream.c.prev_at
        - func.coalesce(stream.c.prev_len, 0) * timedelta(seconds=1)
    )
    starts_run = func.coalesce(
        or_(
            stream.c.artist != stream.c.prev_artist,
            stream.c.album.is_distinct_from(stream.c.prev_album),
            pause > RUN_MAX_GAP,
        ),
        True,
    )
    numbered = select(
        stream,
        func.sum(cast(starts_run, Integer)).over(order_by=(stream.c.played_at, stream.c.id)).label("run"),
    ).subquery()
    tracks = func.count(distinct(numbered.c.track_title))
    runs = (
        select(
            numbered.c.artist, numbered.c.album,
            func.min(numbered.c.played_at).label("started_at"),
            tracks.label("tracks"),
            func.count().label("listens"),
            func.coalesce(func.sum(numbered.c.duration_sec), 0).label("seconds"),
        )
        .where(numbered.c.album.is_not(None))
        .group_by(numbered.c.run, numbered.c.artist, numbered.c.album)
        .having(tracks >= RUN_MIN_TRACKS)
        .subquery()
    )
    wanted = []
    if artist is not None:
        wanted.append(runs.c.artist == artist)
    if album is not None:
        wanted.append(runs.c.album == album)
    total = (await session.execute(
        select(func.count()).select_from(runs).where(*wanted)
    )).scalar_one()
    rows = (await session.execute(
        select(runs, AlbumArt.image_url)
        .outerjoin(AlbumArt, and_(AlbumArt.artist == runs.c.artist, AlbumArt.album == runs.c.album))
        .where(*wanted)
        .order_by(runs.c.started_at.desc())
        .limit(limit)
    )).all()
    return {
        "total": total,
        "runs": [
            {
                "artist": r.artist, "album": r.album, "started_at": iso_in(r.started_at, scope.tz),
                "tracks": r.tracks, "listens": r.listens, "seconds": int(r.seconds),
                "image_url": r.image_url,
            }
            for r in rows
        ],
    }
