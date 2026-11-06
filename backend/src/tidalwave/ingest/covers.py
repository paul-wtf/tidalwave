from __future__ import annotations

import asyncio
import logging
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from tidalwave.lastfm.client import LastfmError
from tidalwave.models.db import AlbumArt, Listen

log = logging.getLogger(__name__)


class AlbumInfoSource(Protocol):
    async def get_album_info(self, artist: str, album: str) -> str | None: ...


async def fill_missing_covers(
    session: AsyncSession,
    client: AlbumInfoSource,
    *,
    max_albums: int | None = None,
) -> int:
    """Fetch covers for listened albums without an ``album_art`` row.

    A row is written for every album looked up, with a NULL URL when Last.fm has
    no cover or the lookup failed. Returns the number of rows written.
    """
    known = select(AlbumArt.id).where(
        AlbumArt.artist == Listen.artist, AlbumArt.album == Listen.album
    )
    stmt = (
        select(Listen.artist, Listen.album)
        .where(Listen.album.is_not(None), ~known.exists())
        .distinct()
    )
    if max_albums is not None:
        stmt = stmt.limit(max_albums)

    pairs = [(row[0], row[1]) for row in (await session.execute(stmt)).all()]
    for artist, album in pairs:
        url: str | None = None
        try:
            url = await client.get_album_info(artist, album)
            await asyncio.sleep(0.1)  # be polite to the Last.fm API
        except LastfmError as e:
            log.warning("album.getInfo failed for %s — %s: %s", artist, album, e)
        except Exception:
            log.exception("album.getInfo errored for %s — %s", artist, album)
        await session.execute(
            pg_insert(AlbumArt)
            .values(artist=artist, album=album, image_url=url)
            .on_conflict_do_nothing(constraint="uq_album_art")
        )
    return len(pairs)
