from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tidalwave.models.db import Listen
from tidalwave.stats.queries import _scope
from tidalwave.stats.scope import Scope


async def artist_counts(session: AsyncSession, scope: Scope) -> dict[str, int]:
    stmt = _scope(select(Listen.artist, func.count()), scope).group_by(Listen.artist)
    return {artist: int(n) for artist, n in (await session.execute(stmt)).all()}


def _only(counts: dict[str, int], other: dict[str, int], limit: int) -> list[dict]:
    rows = sorted(
        ((a, n) for a, n in counts.items() if n > 0 and other.get(a, 0) == 0),
        key=lambda r: (-r[1], r[0]),
    )
    return [{"artist": a, "count": n} for a, n in rows[:limit]]


def compare(you: dict[str, int], partner: dict[str, int], *, limit: int) -> dict:
    """Overlap is the sum, over all artists, of the smaller of the two listen
    shares: 1 for the same distribution, 0 for no artist in common."""
    total_you = sum(you.values())
    total_partner = sum(partner.values())
    common = [a for a, n in you.items() if n > 0 and partner.get(a, 0) > 0]
    overlap: float | None = None
    shared: list[dict] = []
    if total_you and total_partner:

        def common_share(artist: str) -> float:
            return min(you[artist] / total_you, partner[artist] / total_partner)

        overlap = sum(common_share(a) for a in common)
        ranked = sorted(
            common, key=lambda a: (-common_share(a), -(you[a] + partner[a]), a)
        )
        shared = [{"artist": a, "you": you[a], "partner": partner[a]} for a in ranked[:limit]]
    return {
        "overlap": overlap,
        "listens": {"you": total_you, "partner": total_partner},
        "shared_artists": len(common),
        "shared": shared,
        "only_you": _only(you, partner, limit),
        "only_partner": _only(partner, you, limit),
    }
