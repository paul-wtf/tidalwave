from __future__ import annotations

import asyncio
import re
import time
from importlib.metadata import version

import httpx

# MusicBrainz blocks clients that do not say who they are and how to reach them.
USER_AGENT = f"tidalwave/{version('tidalwave')} (https://github.com/paul-wtf/tidalwave)"

# MusicBrainz allows one request per second per client; the margin covers jitter.
MIN_INTERVAL = 1.1

_YEAR = re.compile(r"\d{4}")
_UNKNOWN_ID = (400, 404)


class MusicBrainzRateLimited(Exception):
    pass


def _year(date: object) -> int | None:
    match = _YEAR.match(date) if isinstance(date, str) else None
    return int(match.group()) if match else None


def _release_year(release: dict) -> int | None:
    # A release carries the date of its own pressing, which for a reissue is
    # decades after the album first came out. The release group has that date.
    group = release.get("release-group") or {}
    return _year(group.get("first-release-date")) or _year(release.get("date"))


class MusicBrainzClient:
    def __init__(
        self, http: httpx.AsyncClient, *, base_url: str, min_interval: float = MIN_INTERVAL
    ) -> None:
        self._http = http
        self._base = base_url.rstrip("/")
        self._min_interval = min_interval
        self._last_request: float | None = None

    async def _get(self, path: str, params: dict[str, str]) -> dict | None:
        if self._last_request is not None:
            wait = self._last_request + self._min_interval - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
        self._last_request = time.monotonic()
        resp = await self._http.get(
            f"{self._base}/{path}",
            params={**params, "fmt": "json", "inc": "release-groups"},
            headers={"User-Agent": USER_AGENT},
        )
        if resp.status_code == 503:
            raise MusicBrainzRateLimited
        if resp.status_code in _UNKNOWN_ID:
            return None
        resp.raise_for_status()
        return resp.json()

    async def release_year(self, release_mbid: str) -> int | None:
        """Year the album of this release first came out, or None if unknown."""
        data = await self._get(f"release/{release_mbid}", {})
        return _release_year(data) if data is not None else None

    async def track_release_year(self, track_mbid: str) -> int | None:
        """Earliest year among the releases that hold this track id."""
        data = await self._get("release", {"track": track_mbid})
        if data is None:
            return None
        years = [y for r in data.get("releases", []) if (y := _release_year(r)) is not None]
        return min(years) if years else None
