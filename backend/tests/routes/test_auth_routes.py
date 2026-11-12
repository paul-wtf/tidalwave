import pytest
from urllib.parse import parse_qs, urlsplit

from tidalwave.auth.session import COOKIE_NAME, SessionCodec


async def test_login_redirects_to_lastfm(api):
    client, app = api
    resp = await client.get("/auth/login", follow_redirects=False)
    assert resp.status_code == 307
    loc = resp.headers["location"]
    assert loc.startswith("https://www.last.fm/api/auth/")
    q = parse_qs(urlsplit(loc).query)
    assert q["api_key"] == ["KEY"]
    assert q["cb"] == ["http://test/auth/callback"]


async def test_callback_creates_user_and_sets_cookie(api, monkeypatch):
    client, app = api
    from tidalwave.deps import get_lastfm_client
    from tidalwave.routes import auth as auth_module

    async def _noop(*args, **kwargs):
        pass

    monkeypatch.setattr(auth_module, "ingest_user_now", _noop)

    class FakeLastfm:
        async def get_session(self, token):
            assert token == "TOK"
            return ("alice", "SESS")

    app.dependency_overrides[get_lastfm_client] = lambda: FakeLastfm()

    resp = await client.get("/auth/callback?token=TOK", follow_redirects=False)
    assert resp.status_code == 307
    cookie = resp.cookies[COOKIE_NAME]
    assert SessionCodec("test-secret").decode(cookie) is not None


async def test_me_returns_401_when_anonymous(api):
    client, app = api
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


async def test_me_returns_current_user(api, db_session):
    from tidalwave.auth.service import upsert_user_from_session
    from tidalwave.auth.session import COOKIE_NAME, SessionCodec

    client, app = api
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    cookie = SessionCodec("test-secret").encode(user.id)
    resp = await client.get("/auth/me", headers={"Cookie": f"{COOKIE_NAME}={cookie}"})
    assert resp.status_code == 200
    assert resp.json() == {
        "username": "alice",
        "is_admin": True,
        "timezone": None,
        "disconnected": False,
        "last_synced_at": None,
        "last_played_at": None,
        "weekly_report_webhook": None,
    }


async def _login(api, db_session):
    from tidalwave.auth.service import upsert_user_from_session

    client, _ = api
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    cookie = SessionCodec("test-secret").encode(user.id)
    return client, user, {"Cookie": f"{COOKIE_NAME}={cookie}"}


async def test_me_includes_sync_and_timezone(api, db_session):
    from datetime import UTC, datetime

    from tidalwave.ingest.repository import advance_sync_state

    client, user, headers = await _login(api, db_session)
    user.timezone = "Europe/Berlin"
    played = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
    await advance_sync_state(db_session, user.id, last_played_at=played)
    await db_session.flush()

    body = (await client.get("/auth/me", headers=headers)).json()

    assert body["timezone"] == "Europe/Berlin"
    assert body["disconnected"] is False
    assert datetime.fromisoformat(body["last_played_at"]) == played
    assert body["last_synced_at"] is not None


async def test_patch_me_sets_timezone(api, db_session):
    client, user, headers = await _login(api, db_session)

    resp = await client.patch("/auth/me", json={"timezone": "Europe/Berlin"}, headers=headers)

    assert resp.status_code == 200
    assert resp.json()["timezone"] == "Europe/Berlin"
    await db_session.refresh(user)
    assert user.timezone == "Europe/Berlin"


async def test_patch_me_rejects_unknown_timezone(api, db_session):
    client, user, headers = await _login(api, db_session)

    resp = await client.patch("/auth/me", json={"timezone": "Mars/Olympus"}, headers=headers)

    assert resp.status_code == 422
    await db_session.refresh(user)
    assert user.timezone is None


@pytest.mark.parametrize("name", ["", "../etc/passwd", "/etc/passwd", "Europe", "Europe/"])
async def test_patch_me_rejects_malformed_timezone(api, db_session, name):
    client, user, headers = await _login(api, db_session)

    resp = await client.patch("/auth/me", json={"timezone": name}, headers=headers)

    assert resp.status_code == 422
    await db_session.refresh(user)
    assert user.timezone is None


async def test_callback_schedules_immediate_ingest(api, monkeypatch):
    client, app = api
    from tidalwave.deps import get_lastfm_client
    from tidalwave.routes import auth as auth_module

    class FakeLastfm:
        async def get_session(self, token):
            return ("alice", "SESS")

    fake = FakeLastfm()
    app.dependency_overrides[get_lastfm_client] = lambda: fake

    calls = []

    async def spy(session_factory, lastfm_client, user_id):
        calls.append((session_factory, lastfm_client, user_id))

    monkeypatch.setattr(auth_module, "ingest_user_now", spy)

    resp = await client.get("/auth/callback?token=TOK", follow_redirects=False)
    assert resp.status_code == 307

    # FastAPI runs background tasks after the response is sent.
    assert len(calls) == 1
    session_factory, lastfm_client, user_id = calls[0]
    assert session_factory is app.state.session_factory
    assert lastfm_client is fake
    assert isinstance(user_id, int)


async def test_patch_me_rejects_zoneinfo_name_postgres_does_not_know(
    api, db_session, monkeypatch
):
    from tidalwave.routes import auth as auth_module

    monkeypatch.setattr(auth_module, "ZoneInfo", lambda name: None)
    client, user, headers = await _login(api, db_session)

    resp = await client.patch("/auth/me", json={"timezone": "Mars/Olympus_Mons"}, headers=headers)

    assert resp.status_code == 422
    await db_session.refresh(user)
    assert user.timezone is None


async def test_patch_me_rejects_nul_in_timezone_without_a_server_error(api, db_session):
    client, user, headers = await _login(api, db_session)

    for tz in ("Europe/Berlin\x00", "\x00", "../etc/passwd", ""):
        resp = await client.patch("/auth/me", json={"timezone": tz}, headers=headers)
        assert resp.status_code == 422, tz
    await db_session.refresh(user)
    assert user.timezone is None


async def test_config_is_public_and_empty_by_default(api):
    client, app = api
    resp = await client.get("/auth/config")
    assert resp.status_code == 200
    assert resp.json() == {"linkhop_url": None}


async def test_config_reports_the_linkhop_url_without_a_trailing_slash(api, monkeypatch):
    from tidalwave.deps import get_settings

    client, app = api
    monkeypatch.setenv("TIDALWAVE_LINKHOP_URL", "https://linkhop.example/")
    get_settings.cache_clear()
    resp = await client.get("/auth/config")
    assert resp.json() == {"linkhop_url": "https://linkhop.example"}
