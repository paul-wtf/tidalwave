from __future__ import annotations

from dataclasses import replace

from sqlalchemy import and_, func, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from tidalwave.models.db import AlbumArt, Listen
from tidalwave.stats.queries import artist_cover_subquery, bounded
from tidalwave.stats.scope import Scope

SEARCH_LIMIT = 5


def _in_range(scope: Scope):
    conditions = []
    if scope.since is not None:
        conditions.append(Listen.played_at >= scope.since)
    if scope.until is not None:
        conditions.append(Listen.played_at < scope.until)
    return and_(*conditions) if conditions else true()


async def search(session: AsyncSession, scope: Scope, q: str) -> dict:
    q = q.strip()
    if not q:
        return {"artists": [], "albums": [], "tracks": []}
    in_range = func.count().filter(_in_range(scope))
    order = (in_range.desc(), func.count().desc())

    cover = artist_cover_subquery(replace(scope, since=scope.floor, until=scope.ceiling))
    artists = (
        bounded(select(Listen.artist, in_range, cover.c.image_url), scope)
        .outerjoin(cover, cover.c.artist == Listen.artist)
        .where(Listen.artist.icontains(q, autoescape=True))
        .group_by(Listen.artist, cover.c.image_url)
        .order_by(*order, Listen.artist.asc())
        .limit(SEARCH_LIMIT)
    )
    albums = (
        bounded(select(Listen.album, Listen.artist, in_range, AlbumArt.image_url), scope)
        .outerjoin(AlbumArt, and_(AlbumArt.artist == Listen.artist, AlbumArt.album == Listen.album))
        .where(Listen.album.icontains(q, autoescape=True))
        .group_by(Listen.album, Listen.artist, AlbumArt.image_url)
        .order_by(*order, Listen.album.asc(), Listen.artist.asc())
        .limit(SEARCH_LIMIT)
    )
    tracks = (
        bounded(select(Listen.track_title, Listen.artist, in_range), scope)
        .where(Listen.track_title.icontains(q, autoescape=True))
        .group_by(Listen.track_title, Listen.artist)
        .order_by(*order, Listen.track_title.asc(), Listen.artist.asc())
        .limit(SEARCH_LIMIT)
    )
    return {
        "artists": [
            {"artist": r[0], "count": r[1], "image_url": r[2]}
            for r in (await session.execute(artists)).all()
        ],
        "albums": [
            {"album": r[0], "artist": r[1], "count": r[2], "image_url": r[3]}
            for r in (await session.execute(albums)).all()
        ],
        "tracks": [
            {"track": r[0], "artist": r[1], "count": r[2]}
            for r in (await session.execute(tracks)).all()
        ],
    }
