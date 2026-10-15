import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
import respx

from tidalwave.lastfm.client import LastfmClient

FIX = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
async def client():
    async with httpx.AsyncClient() as http:
        yield LastfmClient(http, api_key="KEY", api_secret="SECRET")


@respx.mock
async def test_parses_recent_tracks_and_nowplaying(client):
    payload = json.loads((FIX / "recent_tracks_page1.json").read_text())
    respx.get("https://ws.audioscrobbler.com/2.0/").respond(json=payload)

    page = await client.get_recent_tracks("alice", page=1)

    assert page.page == 1
    assert page.total_pages == 2
    assert len(page.scrobbles) == 2

    np = page.scrobbles[0]
    assert np.now_playing is True
    assert np.played_at is None
    assert np.track_title == "Nightcall"

    done = page.scrobbles[1]
    assert done.now_playing is False
    assert done.played_at == datetime.fromtimestamp(1700000000, tz=UTC)
    assert done.artist == "Daft Punk"
    assert done.track_title == "Aerodynamic"
    assert done.album == "Discovery"
    assert done.album_mbid is None  # empty string normalized to None


@respx.mock
async def test_single_track_dict_is_wrapped(client):
    """Last.fm returns a bare dict (not a list) when there is exactly one track."""
    payload = {
        "recenttracks": {
            "@attr": {"user": "alice", "page": "1", "perPage": "200", "totalPages": "1", "total": "1"},
            "track": {
                "artist": {"#text": "Daft Punk", "mbid": "a2"},
                "name": "Aerodynamic",
                "album": {"#text": "Discovery", "mbid": ""},
                "mbid": "",
                "date": {"uts": "1700000000", "#text": "14 Nov 2023, 22:13"},
            },
        }
    }
    respx.get("https://ws.audioscrobbler.com/2.0/").respond(json=payload)

    page = await client.get_recent_tracks("alice", page=1)

    assert len(page.scrobbles) == 1
    track = page.scrobbles[0]
    assert track.track_title == "Aerodynamic"
    assert track.artist == "Daft Punk"
    assert track.now_playing is False
    assert track.played_at == datetime.fromtimestamp(1700000000, tz=UTC)


_EMPTY = {"recenttracks": {"@attr": {"page": "1", "totalPages": "1"}, "track": []}}


@respx.mock
async def test_recent_tracks_authenticated_when_session_key_given(client):
    route = respx.get("https://ws.audioscrobbler.com/2.0/").respond(json=_EMPTY)
    await client.get_recent_tracks("alice", session_key="SK", page=1)
    params = dict(httpx.QueryParams(route.calls.last.request.url.query))
    assert params["sk"] == "SK"
    assert "api_sig" in params
    assert params["user"] == "alice"


@respx.mock
async def test_recent_tracks_unsigned_when_no_session_key(client):
    route = respx.get("https://ws.audioscrobbler.com/2.0/").respond(json=_EMPTY)
    await client.get_recent_tracks("alice", page=1)
    params = dict(httpx.QueryParams(route.calls.last.request.url.query))
    assert "sk" not in params
    assert "api_sig" not in params


@respx.mock
async def test_unavailable_with_html_body_raises_http_status_error(client):
    respx.get("https://ws.audioscrobbler.com/2.0/").respond(
        503, text="<html><body>Service Unavailable</body></html>"
    )
    with pytest.raises(httpx.HTTPStatusError):
        await client.get_recent_tracks("alice", session_key="SK", page=1)
