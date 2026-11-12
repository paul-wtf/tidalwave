from __future__ import annotations

import logging
import time

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tidalwave.ingest.service import RecentTracksSource
from tidalwave.lastfm.client import LastfmError
from tidalwave.models.db import AlbumArt, User

log = logging.getLogger(__name__)

# The frontend asks every 30 seconds per open tab. Half of that keeps the answer
# fresh while several tabs or reloads still cost one Last.fm request.
NOW_PLAYING_TTL = 15.0

Cache = dict[int, tuple[float, dict | None]]


def _clock() -> float:
    return time.monotonic()


async def _ask(session: AsyncSession, client: RecentTracksSource, user: User) -> dict | None:
    try:
        page = await client.get_recent_tracks(
            user.lastfm_username, limit=1, session_key=user.lastfm_session_key
        )
    except (LastfmError, httpx.HTTPError) as e:
        log.warning("now playing unavailable for %s: %s", user.lastfm_username, e)
        return None
    playing = next((s for s in page.scrobbles if s.now_playing), None)
    if playing is None:
        return None
    image_url = playing.image_url
    if image_url is None and playing.album is not None:
        image_url = await session.scalar(
            select(AlbumArt.image_url).where(
                AlbumArt.artist == playing.artist, AlbumArt.album == playing.album
            )
        )
    return {
        "track": playing.track_title,
        "artist": playing.artist,
        "album": playing.album,
        "image_url": image_url,
    }


async def now_playing(
    cache: Cache, session: AsyncSession, client: RecentTracksSource, user_id: int
) -> dict | None:
    cached = cache.get(user_id)
    if cached is not None and _clock() - cached[0] < NOW_PLAYING_TTL:
        return cached[1]
    user = await session.get(User, user_id)
    if user is None or user.disconnected:
        return None
    result = await _ask(session, client, user)
    cache[user_id] = (_clock(), result)
    return result
