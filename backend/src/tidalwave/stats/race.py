from __future__ import annotations

import heapq
from datetime import timedelta
from itertools import groupby

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tidalwave.models.db import Listen
from tidalwave.stats.queries import _scope, artist_cover_subquery
from tidalwave.stats.scope import Scope

# The frontend's rule for trend charts: days up to about a quarter, months
# beyond that. A share view cannot apply it, because it does not know its range.
_DAY_BUCKET_SPAN = timedelta(days=92)


async def _bucket_for(session: AsyncSession, scope: Scope) -> str:
    start, end = scope.since, scope.until
    if start is None or end is None:
        first, last = (await session.execute(
            _scope(select(func.min(Listen.played_at), func.max(Listen.played_at)), scope)
        )).one()
        start, end = start or first, end or last
    if start is None or end is None:
        return "day"
    return "day" if end - start <= _DAY_BUCKET_SPAN else "month"


async def artist_race(
    session: AsyncSession, scope: Scope, *, bucket: str | None = None, limit: int = 10
) -> dict:
    """Running listen totals per period for every artist that is among the top
    ``limit`` at the end of some period. Ranking those artists by their total
    at a period gives exactly the top ``limit`` of that period."""
    bucket = bucket or await _bucket_for(session, scope)
    period = func.date_trunc(bucket, func.timezone(scope.tz, Listen.played_at))
    rows = (await session.execute(
        _scope(select(period, Listen.artist, func.count()), scope)
        .group_by(period, Listen.artist)
        .order_by(period)
    )).all()
    frames = [(key, list(group)) for key, group in groupby(rows, key=lambda r: r[0])]

    totals: dict[str, int] = {}
    leaders: list[str] = []
    racers: set[str] = set()
    for _, plays in frames:
        for _, artist, n in plays:
            totals[artist] = totals.get(artist, 0) + n
        # Only an artist with listens in this period can have overtaken a leader.
        candidates = {*leaders, *(artist for _, artist, _ in plays)}
        leaders = heapq.nsmallest(limit, candidates, key=lambda a: (-totals[a], a))
        racers.update(leaders)

    running = {artist: 0 for artist in racers}
    series: dict[str, list[int]] = {artist: [] for artist in racers}
    for _, plays in frames:
        for _, artist, n in plays:
            if artist in running:
                running[artist] += n
        for artist, total in running.items():
            series[artist].append(total)

    covers: dict[str, str | None] = {}
    if racers:
        cover = artist_cover_subquery(scope)
        found = await session.execute(
            select(cover.c.artist, cover.c.image_url).where(cover.c.artist.in_(racers))
        )
        covers = {row[0]: row[1] for row in found.all()}
    return {
        "bucket": bucket,
        "periods": [key.isoformat() for key, _ in frames],
        "artists": [
            {"artist": artist, "image_url": covers.get(artist), "totals": series[artist]}
            for artist in sorted(racers, key=lambda a: (-totals[a], a))
        ],
    }
