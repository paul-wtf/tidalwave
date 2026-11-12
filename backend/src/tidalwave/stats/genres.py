from __future__ import annotations

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tidalwave.models.db import ArtistTags, Listen
from tidalwave.stats.queries import _entity, _scope, bounded, top_tags
from tidalwave.stats.scope import Scope


async def genres(session: AsyncSession, scope: Scope, *, limit: int = 20) -> dict:
    """Genres ranked by the listens of their artists. ``tagged_artists`` counts
    the artists in range that have been looked up, with or without a result."""
    per_artist = (
        _scope(select(Listen.artist.label("artist"), func.count().label("n")), scope)
        .group_by(Listen.artist)
        .subquery()
    )
    tagged = (
        select(per_artist.c.n, func.unnest(top_tags()).label("genre"))
        .join(ArtistTags, ArtistTags.artist == per_artist.c.artist)
        .subquery()
    )
    listens = func.sum(tagged.c.n)
    rows = (await session.execute(
        select(tagged.c.genre, listens, func.count())
        .group_by(tagged.c.genre)
        .order_by(listens.desc(), tagged.c.genre.asc())
        .limit(limit)
    )).all()
    artists, looked_up = (await session.execute(
        select(func.count(), func.count(ArtistTags.id))
        .select_from(per_artist)
        .outerjoin(ArtistTags, ArtistTags.artist == per_artist.c.artist)
    )).one()
    return {
        "genres": [{"genre": r[0], "listens": int(r[1]), "artists": r[2]} for r in rows],
        "artists": artists,
        "tagged_artists": looked_up,
    }


async def genre_detail(session: AsyncSession, scope: Scope, genre: str) -> dict | None:
    genre = genre.strip().lower()
    known = _entity(bounded(select(Listen.id), scope), None, None, None, genre).limit(1)
    if (await session.execute(known)).first() is None:
        return None
    row = (await session.execute(_entity(
        _scope(select(
            func.count(),
            func.coalesce(func.sum(Listen.duration_sec), 0),
            func.count(distinct(Listen.artist)),
        ), scope),
        None, None, None, genre,
    ))).one()
    return {"genre": genre, "listens": int(row[0]), "seconds": int(row[1]), "artists": int(row[2])}
