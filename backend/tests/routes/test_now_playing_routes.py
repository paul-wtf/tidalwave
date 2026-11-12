import httpx
import pytest

from tidalwave.auth.service import upsert_user_from_session
from tidalwave.auth.session import COOKIE_NAME, SessionCodec
from tidalwave.deps import get_lastfm_client
from tidalwave.lastfm.client import LastfmError, RecentTracksPage
from tidalwave.models.db import AlbumArt, Share
from tidalwave.models.domain import Scrobble
from tidalwave.stats import now_playing as now_playing_module


def _auth(user_id: int) -> dict:
    return {"Cookie": f"{COOKIE_NAME}={SessionCodec('test-secret').encode(user_id)}"}


PLAYING = Scrobble(artist="Kavinsky", track_title="Nightcall", album="OutRun", played_at=None,
                   now_playing=True, image_url="https://img/outrun.jpg")
FINISHED = Scrobble(artist="Daft Punk", track_title="Aerodynamic", album="Discovery",
                    played_at=None)


class FakeLastfm:
    def __init__(self, *scrobbles, error: Exception | None = None):
        self.scrobbles = scrobbles
        self.error = error
        self.calls: list[dict] = []

    async def get_recent_tracks(self, username, **kwargs):
        self.calls.append({"username": username, **kwargs})
        if self.error is not None:
            raise self.error
        return RecentTracksPage(tuple(self.scrobbles), page=1, total_pages=1)


@pytest.fixture
async def alice(db_session):
    return await upsert_user_from_session(db_session, "alice", "SESSION", mode="open", allowlist=[])


def _use(app, fake: FakeLastfm) -> FakeLastfm:
    app.dependency_overrides[get_lastfm_client] = lambda: fake
    return fake


async def test_now_playing_requires_login(api):
    client, _ = api
    assert (await client.get("/stats/now-playing")).status_code == 401


async def test_now_playing_returns_the_track_last_fm_reports_as_playing(api, alice):
    client, app = api
    fake = _use(app, FakeLastfm(PLAYING, FINISHED))
    resp = await client.get("/stats/now-playing", headers=_auth(alice.id))
    assert resp.status_code == 200
    assert resp.json() == {
        "track": "Nightcall", "artist": "Kavinsky", "album": "OutRun",
        "image_url": "https://img/outrun.jpg",
    }
    assert fake.calls == [{"username": "alice", "limit": 1, "session_key": "SESSION"}]


@pytest.mark.parametrize("scrobbles", [(), (FINISHED,)])
async def test_now_playing_is_null_when_nothing_plays(api, alice, scrobbles):
    client, app = api
    _use(app, FakeLastfm(*scrobbles))
    resp = await client.get("/stats/now-playing", headers=_auth(alice.id))
    assert resp.status_code == 200
    assert resp.json() is None


async def test_now_playing_falls_back_to_the_stored_cover(api, alice, db_session):
    client, app = api
    db_session.add(AlbumArt(artist="Kavinsky", album="OutRun", image_url="https://img/stored.jpg"))
    await db_session.flush()
    _use(app, FakeLastfm(Scrobble(artist="Kavinsky", track_title="Nightcall", album="OutRun",
                                  played_at=None, now_playing=True)))
    body = (await client.get("/stats/now-playing", headers=_auth(alice.id))).json()
    assert body["image_url"] == "https://img/stored.jpg"


async def test_now_playing_asks_last_fm_once_per_user_within_the_cache_window(
    api, alice, db_session, monkeypatch
):
    client, app = api
    bob = await upsert_user_from_session(db_session, "bob", "sk", mode="open", allowlist=[])
    fake = _use(app, FakeLastfm(PLAYING))
    clock = [1000.0]
    monkeypatch.setattr(now_playing_module, "_clock", lambda: clock[0])

    for _ in range(3):
        assert (await client.get("/stats/now-playing", headers=_auth(alice.id))).json()["track"] == "Nightcall"
    assert len(fake.calls) == 1

    await client.get("/stats/now-playing", headers=_auth(bob.id))
    assert [c["username"] for c in fake.calls] == ["alice", "bob"]

    clock[0] += now_playing_module.NOW_PLAYING_TTL - 0.1
    fake.scrobbles = ()
    assert (await client.get("/stats/now-playing", headers=_auth(alice.id))).json() is not None
    clock[0] += 0.2
    assert (await client.get("/stats/now-playing", headers=_auth(alice.id))).json() is None
    assert [c["username"] for c in fake.calls] == ["alice", "bob", "alice"]


@pytest.mark.parametrize("error", [
    LastfmError(8, "operation failed"),
    LastfmError(9, "Invalid session key"),
    httpx.ConnectError("down"),
    httpx.ReadTimeout("slow"),
])
async def test_now_playing_is_null_when_last_fm_fails(api, alice, error):
    client, app = api
    fake = _use(app, FakeLastfm(error=error))
    resp = await client.get("/stats/now-playing", headers=_auth(alice.id))
    assert resp.status_code == 200
    assert resp.json() is None
    await client.get("/stats/now-playing", headers=_auth(alice.id))
    assert len(fake.calls) == 1


async def test_now_playing_skips_disconnected_users(api, alice, db_session):
    client, app = api
    alice.disconnected = True
    await db_session.flush()
    fake = _use(app, FakeLastfm(PLAYING))
    assert (await client.get("/stats/now-playing", headers=_auth(alice.id))).json() is None
    assert fake.calls == []


async def test_shared_now_playing_is_always_null_and_never_asks_last_fm(api, alice, db_session):
    client, app = api
    db_session.add(Share(share_token="S" * 43, user_id=alice.id))
    await db_session.flush()
    fake = _use(app, FakeLastfm(PLAYING))
    resp = await client.get(f"/shared/{'S' * 43}/now-playing")
    assert resp.status_code == 200
    assert resp.json() is None
    assert fake.calls == []
