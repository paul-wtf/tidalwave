from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from tidalwave.lastfm.signing import sign
from tidalwave.models.domain import Scrobble

_API = "https://ws.audioscrobbler.com/2.0/"
_PLACEHOLDER_HASH = "2a96cbd8b46e442fc41c2b86b821562f"
_NOT_FOUND = 6


@dataclass(frozen=True, slots=True)
class LastfmError(Exception):
    code: int
    message: str

    def __str__(self) -> str:
        return f"Last.fm error {self.code}: {self.message}"


def _raise_for_status(resp: httpx.Response) -> None:
    # httpx's own message quotes the request URL, which holds the keys.
    if resp.is_error:
        raise httpx.HTTPStatusError(
            f"Last.fm answered {resp.status_code}", request=resp.request, response=resp
        ) from None


@dataclass(frozen=True, slots=True)
class RecentTracksPage:
    scrobbles: tuple[Scrobble, ...]
    page: int
    total_pages: int


class LastfmClient:
    def __init__(self, http: httpx.AsyncClient, *, api_key: str, api_secret: str) -> None:
        self._http = http
        self._key = api_key
        self._secret = api_secret

    async def _call(self, params: dict[str, str], *, signed: bool) -> dict:
        q = {**params, "api_key": self._key, "format": "json"}
        if signed:
            q["api_sig"] = sign({**params, "api_key": self._key}, secret=self._secret)
        resp = await self._http.get(_API, params=q)
        try:
            data = resp.json()
        except ValueError:
            _raise_for_status(resp)
            raise
        if "error" in data:
            raise LastfmError(int(data["error"]), data.get("message", ""))
        _raise_for_status(resp)
        return data

    async def get_session(self, token: str) -> tuple[str, str]:
        """Exchange an auth token for (username, session_key)."""
        data = await self._call(
            {"method": "auth.getSession", "token": token}, signed=True
        )
        session = data["session"]
        return session["name"], session["key"]

    async def get_recent_tracks(
        self,
        username: str,
        *,
        from_ts: int | None = None,
        page: int = 1,
        limit: int = 200,
        session_key: str | None = None,
    ) -> RecentTracksPage:
        params: dict[str, str] = {
            "method": "user.getRecentTracks",
            "user": username,
            "limit": str(limit),
            "page": str(page),
            "extended": "0",
        }
        if from_ts is not None:
            params["from"] = str(from_ts)
        if session_key is not None:
            params["sk"] = session_key
            data = await self._call(params, signed=True)
        else:
            data = await self._call(params, signed=False)
        return _parse_recent_tracks(data)

    async def get_track_info(self, artist: str, track: str) -> int | None:
        """Return the track length in whole seconds, or None if Last.fm has none.

        Uses the public (unsigned) track.getInfo method. Last.fm reports the
        duration in milliseconds and uses "0" for tracks it has no length for.
        """
        data = await self._call(
            {"method": "track.getInfo", "artist": artist, "track": track},
            signed=False,
        )
        raw = data.get("track", {}).get("duration")
        if raw is None:
            return None
        try:
            ms = int(raw)
        except (TypeError, ValueError):
            return None
        return ms // 1000 if ms > 0 else None

    async def get_album_info(self, artist: str, album: str) -> str | None:
        """Return the extralarge cover URL, or None if Last.fm has no usable one."""
        try:
            data = await self._call(
                {"method": "album.getInfo", "artist": artist, "album": album},
                signed=False,
            )
        except LastfmError as e:
            if e.code == _NOT_FOUND:
                return None
            raise
        return _extralarge(data.get("album", {}).get("image"))

    async def get_artist_top_tags(self, artist: str) -> list[tuple[str, int]]:
        """Return the artist's tags as (name, weight), strongest first.

        Last.fm scales the weight to the artist's strongest tag, which gets 100.
        """
        try:
            data = await self._call(
                {"method": "artist.getTopTags", "artist": artist}, signed=False
            )
        except LastfmError as e:
            if e.code == _NOT_FOUND:
                return []
            raise
        raw = data.get("toptags", {}).get("tag", [])
        if isinstance(raw, dict):
            raw = [raw]
        tags: list[tuple[str, int]] = []
        for entry in raw:
            try:
                tags.append((str(entry["name"]), int(entry["count"])))
            except (KeyError, TypeError, ValueError):
                continue
        return tags


def _extralarge(images: object) -> str | None:
    if not isinstance(images, list):
        return None
    for entry in images:
        if isinstance(entry, dict) and entry.get("size") == "extralarge":
            url = entry.get("#text") or None
            if url is None or _PLACEHOLDER_HASH in url:
                return None
            return url
    return None


def _parse_recent_tracks(data: dict) -> RecentTracksPage:
    block = data["recenttracks"]
    attr = block["@attr"]
    raw = block.get("track", [])
    if isinstance(raw, dict):  # Last.fm returns a bare object for a single track
        raw = [raw]
    scrobbles = tuple(_parse_track(t) for t in raw)
    return RecentTracksPage(
        scrobbles=scrobbles,
        page=int(attr["page"]),
        total_pages=int(attr["totalPages"]),
    )


def _parse_track(t: dict) -> Scrobble:
    now_playing = t.get("@attr", {}).get("nowplaying") == "true"
    played_at: datetime | None = None
    if not now_playing and "date" in t:
        played_at = datetime.fromtimestamp(int(t["date"]["uts"]), tz=UTC)
    album = t.get("album", {}).get("#text") or None
    return Scrobble(
        artist=t["artist"]["#text"],
        track_title=t["name"],
        album=album,
        played_at=played_at,
        track_mbid=t.get("mbid") or None,
        artist_mbid=t.get("artist", {}).get("mbid") or None,
        album_mbid=t.get("album", {}).get("mbid") or None,
        now_playing=now_playing,
        image_url=_extralarge(t.get("image")),
    )
