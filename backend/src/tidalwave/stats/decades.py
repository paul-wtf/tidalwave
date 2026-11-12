from __future__ import annotations

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from tidalwave.models.db import AlbumYear, Listen
from tidalwave.stats.queries import _scope
from tidalwave.stats.scope import Scope


async def decades(session: AsyncSession, scope: Scope) -> dict:
    """Listens per release decade of their album. ``unknown`` counts the listens
    without a known year; ``pending`` is the part of them that carries a
    MusicBrainz id and has not been looked up yet."""
    decade = (AlbumYear.year // 10 * 10).label("decade")
    waiting = and_(
        AlbumYear.id.is_(None),
        Listen.album.is_not(None),
        or_(Listen.album_mbid.is_not(None), Listen.track_mbid.is_not(None)),
    )
    rows = (await session.execute(
        _scope(select(decade, func.count(), func.count().filter(waiting)), scope)
        .select_from(Listen)
        .outerjoin(
            AlbumYear, and_(AlbumYear.artist == Listen.artist, AlbumYear.album == Listen.album)
        )
        .group_by(decade)
    )).all()
    counts = {r[0]: r[1] for r in rows if r[0] is not None}
    unknown = sum(r[1] for r in rows if r[0] is None)
    span = range(min(counts), max(counts) + 10, 10) if counts else ()
    return {
        "decades": [{"decade": d, "listens": counts.get(d, 0)} for d in span],
        "known": sum(counts.values()),
        "unknown": unknown,
        "pending": sum(r[2] for r in rows),
    }
