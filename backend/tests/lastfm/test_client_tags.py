import httpx
import pytest
import respx

from tidalwave.lastfm.client import LastfmClient, LastfmError

API = "https://ws.audioscrobbler.com/2.0/"


@pytest.fixture
async def client():
    async with httpx.AsyncClient() as http:
        yield LastfmClient(http, api_key="KEY", api_secret="SECRET")


@respx.mock
async def test_get_artist_top_tags_returns_names_with_weights(client):
    route = respx.get(API).respond(json={"toptags": {
        "tag": [
            {"count": 100, "name": "pop", "url": "https://www.last.fm/tag/pop"},
            {"count": 6, "name": "Disco", "url": "https://www.last.fm/tag/Disco"},
        ],
        "@attr": {"artist": "Cher"},
    }})

    assert await client.get_artist_top_tags("Cher") == [("pop", 100), ("Disco", 6)]
    params = route.calls.last.request.url.params
    assert params["method"] == "artist.getTopTags"
    assert params["artist"] == "Cher"
    assert "api_sig" not in params


@respx.mock
async def test_get_artist_top_tags_wraps_a_single_tag(client):
    respx.get(API).respond(json={"toptags": {"tag": {"count": 100, "name": "folk"}}})
    assert await client.get_artist_top_tags("X") == [("folk", 100)]


@respx.mock
async def test_get_artist_top_tags_without_tags_is_empty(client):
    respx.get(API).respond(json={"toptags": {"tag": [], "@attr": {"artist": "X"}}})
    assert await client.get_artist_top_tags("X") == []


@respx.mock
async def test_get_artist_top_tags_unknown_artist_is_empty(client):
    respx.get(API).respond(
        json={"error": 6, "message": "The artist you supplied could not be found"}
    )
    assert await client.get_artist_top_tags("X") == []


@respx.mock
async def test_get_artist_top_tags_passes_other_errors_on(client):
    respx.get(API).respond(json={"error": 29, "message": "Rate limit exceeded"})
    with pytest.raises(LastfmError) as raised:
        await client.get_artist_top_tags("X")
    assert raised.value.code == 29
