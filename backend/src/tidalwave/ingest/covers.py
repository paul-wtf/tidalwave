from __future__ import annotations

import asyncio
import logging
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from tidalwave.lastfm.client import LastfmError
from tidalwave.models.db import AlbumArt, Listen

log = logging.getLogger(__name__)

_RATE_LIMITED = 29


class AlbumInfoSource(Protocol):
    async def get_album_info(self, artist: str, album: str) -> str | None: ...


async def fill_missing_covers(
    session: AsyncSession,
    client: AlbumInfoSource,
    *,
    max_albums: int | None = None,
) -> int:
    """Fetch covers for listened albums without an ``album_art`` row.

    A NULL URL is written only when Last.fm answers that it has no cover; failed
    lookups write nothing and are retried on the next run. A rate-limit error ends
    the run. Returns the number of rows written.
    """
    known = select(AlbumArt.id).where(
        AlbumArt.artist == Listen.artist, AlbumArt.album == Listen.album
    )
    stmt = (
        select(Listen.artist, Listen.album)
        .where(Listen.album.is_not(None), ~known.exists())
        .group_by(Listen.artist, Listen.album)
    )
    if max_albums is not None:
        stmt = stmt.order_by(func.random()).limit(max_albums)

    pairs = [(row[0], row[1]) for row in (await session.execute(stmt)).all()]
    written = 0
    for artist, album in pairs:
        try:
            url = await client.get_album_info(artist, album)
        except LastfmError as e:
            log.warning("album.getInfo failed for %s — %s: %s", artist, album, e)
            if e.code == _RATE_LIMITED:
                break
            continue
        except Exception:
            log.exception("album.getInfo errored for %s — %s", artist, album)
            continue
        finally:
            await asyncio.sleep(0.1)
        await session.execute(
            pg_insert(AlbumArt)
            .values(artist=artist, album=album, image_url=url)
            .on_conflict_do_nothing(constraint="uq_album_art")
        )
        written += 1
    return written
