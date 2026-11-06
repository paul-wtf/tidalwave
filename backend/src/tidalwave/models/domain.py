from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Scrobble:
    """A single parsed Last.fm listen. `played_at` is None for a now-playing track."""

    artist: str
    track_title: str
    album: str | None
    played_at: datetime | None
    track_mbid: str | None = None
    artist_mbid: str | None = None
    album_mbid: str | None = None
    now_playing: bool = False
    image_url: str | None = None
