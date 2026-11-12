from __future__ import annotations

import logging
from typing import Protocol

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from tidalwave.models.db import AlbumYear, Listen
from tidalwave.musicbrainz.client import MusicBrainzRateLimited

log = logging.getLogger(__name__)


class ReleaseYearSource(Protocol):
    async def release_year(self, release_mbid: str) -> int | None: ...

    async def track_release_year(self, track_mbid: str) -> int | None: ...


async def fill_missing_album_years(
    session: AsyncSession,
    client: ReleaseYearSource,
    *,
    max_albums: int | None = None,
) -> int:
    """Look up the release year of listened albums without an ``album_years`` row.

    Last.fm's album id is a MusicBrainz release id and its track id a MusicBrainz
    track id, which leads to the release it sits on. The album id is asked
    first, the track id when that yields no year. Albums whose listens carry
    neither id are left alone.

    Failed lookups write nothing and are retried on the next run. Rate limiting
    ends the run. Returns the number of rows written.
    """
    known = select(AlbumYear.id).where(
        AlbumYear.artist == Listen.artist, AlbumYear.album == Listen.album
    )
    stmt = (
        select(
            Listen.artist,
            Listen.album,
            func.mode().within_group(Listen.album_mbid),
            func.mode().within_group(Listen.track_mbid),
        )
        .where(
            Listen.album.is_not(None),
            or_(Listen.album_mbid.is_not(None), Listen.track_mbid.is_not(None)),
            ~known.exists(),
        )
        .group_by(Listen.artist, Listen.album)
    )
    if max_albums is not None:
        stmt = stmt.order_by(func.random()).limit(max_albums)

    written = 0
    for artist, album, album_mbid, track_mbid in (await session.execute(stmt)).all():
        try:
            year = await client.release_year(album_mbid) if album_mbid else None
            if year is None and track_mbid:
                year = await client.track_release_year(track_mbid)
        except MusicBrainzRateLimited:
            log.warning("MusicBrainz is rate limiting, stopping this run")
            break
        except Exception:
            log.exception("MusicBrainz lookup errored for %s by %s", album, artist)
            continue
        await session.execute(
            pg_insert(AlbumYear)
            .values(artist=artist, album=album, year=year)
            .on_conflict_do_nothing(constraint="uq_album_year")
        )
        written += 1
    return written
