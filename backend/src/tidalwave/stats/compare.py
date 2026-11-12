from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tidalwave.models.db import Listen
from tidalwave.spellings.normalize import spelling_key
from tidalwave.stats.queries import _scope
from tidalwave.stats.scope import Scope


async def artist_counts(session: AsyncSession, scope: Scope) -> dict[str, int]:
    stmt = _scope(select(Listen.artist, func.count()), scope).group_by(Listen.artist)
    return {artist: int(n) for artist, n in (await session.execute(stmt)).all()}


Side = dict[str, tuple[str, int]]


def _by_spelling(counts: dict[str, int]) -> Side:
    """Listen counts per spelling key, under the side's most played spelling."""
    groups: dict[str, list[tuple[str, int]]] = {}
    for artist, n in counts.items():
        if n > 0:
            groups.setdefault(spelling_key(artist), []).append((artist, n))
    return {
        key: (min(names, key=lambda r: (-r[1], r[0]))[0], sum(n for _, n in names))
        for key, names in groups.items()
    }


def _only(side: Side, other: Side, limit: int) -> list[dict]:
    rows = sorted(
        (named for key, named in side.items() if key not in other),
        key=lambda r: (-r[1], r[0]),
    )
    return [{"artist": a, "count": n} for a, n in rows[:limit]]


def compare(you: dict[str, int], partner: dict[str, int], *, limit: int) -> dict:
    """Overlap is the sum, over all artists, of the smaller of the two listen
    shares: 1 for the same distribution, 0 for no artist in common. Artists
    match by spelling key, and each side keeps its own spelling."""
    mine = _by_spelling(you)
    theirs = _by_spelling(partner)
    total_you = sum(n for _, n in mine.values())
    total_partner = sum(n for _, n in theirs.values())
    common = [key for key in mine if key in theirs]
    overlap: float | None = None
    shared: list[dict] = []
    if total_you and total_partner:

        def common_share(key: str) -> float:
            return min(mine[key][1] / total_you, theirs[key][1] / total_partner)

        overlap = sum(common_share(k) for k in common)
        ranked = sorted(
            common,
            key=lambda k: (-common_share(k), -(mine[k][1] + theirs[k][1]), mine[k][0]),
        )
        shared = [
            {"artist": mine[k][0], "you": mine[k][1], "partner": theirs[k][1]}
            for k in ranked[:limit]
        ]
    return {
        "overlap": overlap,
        "listens": {"you": total_you, "partner": total_partner},
        "shared_artists": len(common),
        "shared": shared,
        "only_you": _only(mine, theirs, limit),
        "only_partner": _only(theirs, mine, limit),
    }
