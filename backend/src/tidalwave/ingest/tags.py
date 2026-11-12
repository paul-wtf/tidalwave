from __future__ import annotations

import asyncio
import logging
import re
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from tidalwave.lastfm.client import LastfmError
from tidalwave.models.db import ArtistTags, Listen

log = logging.getLogger(__name__)

_RATE_LIMITED = 29

# Last.fm weights are relative to the artist's strongest tag (100). Below a
# fifth of that a tag is usually one listener's opinion.
MIN_TAG_WEIGHT = 20
MAX_TAGS = 5

# Tags that say something about the listener, the singer or the country
# instead of the music.
NON_GENRE_TAGS = frozenset({
    "seen live", "favorites", "favourites", "favorite", "favourite",
    "favorite artists", "favourite artists", "love", "awesome", "beautiful",
    "all", "under 2000 listeners", "spotify",
    "female vocalists", "female vocalist", "male vocalists", "male vocalist",
    "american", "usa", "british", "uk", "english", "german", "french", "swedish",
    "canadian", "australian", "japanese",
})
_YEAR_OR_DECADE = re.compile(r"(\d{4}|(\d{2})?\d0)s?")


def _squash(name: str) -> str:
    return re.sub(r"[\W_]+", "", name.casefold())


def pick_genres(artist: str, tags: list[tuple[str, int]]) -> list[str]:
    own_name = _squash(artist)
    genres: list[str] = []
    for name, weight in tags:
        tag = name.strip().lower()
        if (
            weight < MIN_TAG_WEIGHT
            or not tag
            or tag in genres
            or tag in NON_GENRE_TAGS
            or _YEAR_OR_DECADE.fullmatch(tag)
            or _squash(tag) == own_name
        ):
            continue
        genres.append(tag)
        if len(genres) == MAX_TAGS:
            break
    return genres


class ArtistTagSource(Protocol):
    async def get_artist_top_tags(self, artist: str) -> list[tuple[str, int]]: ...


async def fill_missing_artist_tags(
    session: AsyncSession,
    client: ArtistTagSource,
    *,
    max_artists: int | None = None,
) -> int:
    """Fetch genre tags for listened artists without an ``artist_tags`` row.

    Failed lookups write nothing and are retried on the next run. A rate-limit
    error ends the run. Returns the number of rows written.
    """
    known = select(ArtistTags.id).where(ArtistTags.artist == Listen.artist)
    stmt = select(Listen.artist).where(~known.exists()).group_by(Listen.artist)
    if max_artists is not None:
        stmt = stmt.order_by(func.random()).limit(max_artists)

    written = 0
    for artist in (await session.execute(stmt)).scalars().all():
        try:
            tags = await client.get_artist_top_tags(artist)
        except LastfmError as e:
            log.warning("artist.getTopTags failed for %s: %s", artist, e)
            if e.code == _RATE_LIMITED:
                break
            continue
        except Exception:
            log.exception("artist.getTopTags errored for %s", artist)
            continue
        finally:
            await asyncio.sleep(0.1)
        await session.execute(
            pg_insert(ArtistTags)
            .values(artist=artist, tags=pick_genres(artist, tags))
            .on_conflict_do_nothing(constraint="uq_artist_tags")
        )
        written += 1
    return written
