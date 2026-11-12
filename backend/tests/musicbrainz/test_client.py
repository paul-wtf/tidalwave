import httpx
import pytest
import respx

from tidalwave.musicbrainz.client import MusicBrainzClient, MusicBrainzRateLimited

BASE = "https://mb.test/ws/2"
RELEASE = "0c0f9ff9-0b07-4d12-8978-6522601eca9d"
TRACK = "e077bfa8-c27c-4d9c-9416-2bf6ee4168b4"


@pytest.fixture
async def client():
    async with httpx.AsyncClient() as http:
        yield MusicBrainzClient(http, base_url=BASE + "/", min_interval=0)


@respx.mock
async def test_release_year_prefers_the_first_release_of_the_release_group(client):
    route = respx.get(f"{BASE}/release/{RELEASE}").respond(json={
        "id": RELEASE, "title": "Streetlights", "date": "2001-10-16",
        "release-group": {"id": "x", "first-release-date": "1974"},
    })

    assert await client.release_year(RELEASE) == 1974
    request = route.calls.last.request
    assert dict(request.url.params) == {"fmt": "json", "inc": "release-groups"}
    assert request.headers["user-agent"].startswith("tidalwave/")
    assert "https://github.com/paul-wtf/tidalwave" in request.headers["user-agent"]


@respx.mock
async def test_release_year_falls_back_to_the_release_date(client):
    respx.get(f"{BASE}/release/{RELEASE}").respond(json={
        "date": "1998-03-17", "release-group": {"first-release-date": ""},
    })
    assert await client.release_year(RELEASE) == 1998


@respx.mock
async def test_release_year_is_none_without_any_date(client):
    respx.get(f"{BASE}/release/{RELEASE}").respond(json={"date": "", "release-group": {}})
    assert await client.release_year(RELEASE) is None


@respx.mock
@pytest.mark.parametrize("status", [400, 404])
async def test_release_year_is_none_for_an_id_musicbrainz_does_not_know(client, status):
    respx.get(f"{BASE}/release/{RELEASE}").respond(status, json={"error": "Not Found"})
    assert await client.release_year(RELEASE) is None


@respx.mock
async def test_track_release_year_takes_the_earliest_release_holding_the_track(client):
    route = respx.get(f"{BASE}/release").respond(json={"releases": [
        {"date": "2018-12-26", "release-group": {"first-release-date": "1977-09-29"}},
        {"date": "1975", "release-group": {}},
        {"date": "", "release-group": {}},
    ]})

    assert await client.track_release_year(TRACK) == 1975
    assert dict(route.calls.last.request.url.params) == {
        "track": TRACK, "fmt": "json", "inc": "release-groups",
    }


@respx.mock
async def test_track_release_year_is_none_without_releases(client):
    respx.get(f"{BASE}/release").respond(json={"releases": []})
    assert await client.track_release_year(TRACK) is None
    respx.get(f"{BASE}/release").respond(404, json={"error": "Not Found"})
    assert await client.track_release_year(TRACK) is None


@respx.mock
async def test_a_503_is_reported_as_rate_limiting(client):
    respx.get(f"{BASE}/release/{RELEASE}").respond(503, json={"error": "rate limited"})
    with pytest.raises(MusicBrainzRateLimited):
        await client.release_year(RELEASE)


@respx.mock
async def test_other_failures_raise(client):
    respx.get(f"{BASE}/release/{RELEASE}").respond(500)
    with pytest.raises(httpx.HTTPStatusError):
        await client.release_year(RELEASE)


@respx.mock
async def test_requests_keep_the_minimum_interval(monkeypatch):
    respx.get(f"{BASE}/release/{RELEASE}").respond(json={"date": "1998"})
    clock = {"now": 100.0}
    slept: list[float] = []

    async def fake_sleep(seconds):
        slept.append(seconds)
        clock["now"] += seconds

    monkeypatch.setattr("tidalwave.musicbrainz.client.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("tidalwave.musicbrainz.client.time.monotonic", lambda: clock["now"])
    async with httpx.AsyncClient() as http:
        client = MusicBrainzClient(http, base_url=BASE, min_interval=1.1)
        await client.release_year(RELEASE)
        clock["now"] += 0.4
        await client.release_year(RELEASE)
    assert slept == [pytest.approx(0.7)]
