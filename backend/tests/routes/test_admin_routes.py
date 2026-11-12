from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from tidalwave.auth.service import upsert_user_from_session
from tidalwave.auth.session import COOKIE_NAME, SessionCodec
from tidalwave.deps import get_settings
from tidalwave.ingest.repository import advance_sync_state, upsert_listens
from tidalwave.models.db import Listen, Share, SyncState, User
from tidalwave.models.domain import Scrobble


def _auth(user_id: int) -> dict:
    return {"Cookie": f"{COOKIE_NAME}={SessionCodec('test-secret').encode(user_id)}"}


async def _users(db_session):
    admin = await upsert_user_from_session(db_session, "paul", "sk", mode="open", allowlist=[])
    bob = await upsert_user_from_session(db_session, "bob", "sk", mode="open", allowlist=[])
    return admin, bob


@pytest.fixture
def env_allowlist(monkeypatch):
    monkeypatch.setenv("TIDALWAVE_REGISTRATION_MODE", "allowlist")
    monkeypatch.setenv("TIDALWAVE_REGISTRATION_ALLOWLIST", "Dave, erin")
    get_settings.cache_clear()


ADMIN_REQUESTS = [
    ("GET", "/auth/admin/users", None),
    ("DELETE", "/auth/admin/users/1", None),
    ("GET", "/auth/admin/allowlist", None),
    ("POST", "/auth/admin/allowlist", {"username": "carol"}),
    ("DELETE", "/auth/admin/allowlist/carol", None),
]


@pytest.mark.parametrize(("method", "path", "body"), ADMIN_REQUESTS)
async def test_admin_routes_need_a_session(api, method, path, body):
    client, _ = api
    resp = await client.request(method, path, json=body)
    assert resp.status_code == 401


@pytest.mark.parametrize(("method", "path", "body"), ADMIN_REQUESTS)
async def test_admin_routes_refuse_users_who_are_not_admins(api, db_session, method, path, body):
    client, _ = api
    _, bob = await _users(db_session)
    resp = await client.request(method, path, json=body, headers=_auth(bob.id))
    assert resp.status_code == 403


async def test_users_lists_everyone_with_listens_and_last_poll(api, db_session):
    client, _ = api
    admin, bob = await _users(db_session)
    await upsert_listens(db_session, bob.id, [
        Scrobble(artist="Kavinsky", track_title="Nightcall", album=None,
                 played_at=datetime(2026, 11, 1, 12, tzinfo=UTC)),
        Scrobble(artist="Kavinsky", track_title="Roadgame", album=None,
                 played_at=datetime(2026, 11, 1, 13, tzinfo=UTC)),
    ])
    await advance_sync_state(
        db_session, bob.id, last_played_at=datetime(2026, 11, 1, 13, tzinfo=UTC)
    )
    await db_session.flush()

    resp = await client.get("/auth/admin/users", headers=_auth(admin.id))

    assert resp.status_code == 200
    rows = {row["username"]: row for row in resp.json()}
    assert set(rows) == {"paul", "bob"}
    assert rows["paul"]["is_admin"] is True
    assert rows["paul"]["listens"] == 0
    assert rows["paul"]["last_synced_at"] is None
    assert rows["bob"]["is_admin"] is False
    assert rows["bob"]["listens"] == 2
    assert rows["bob"]["last_synced_at"] is not None
    assert rows["bob"]["id"] == bob.id
    assert datetime.fromisoformat(rows["bob"]["created_at"]).tzinfo is not None
    assert rows["bob"]["disconnected"] is False


async def test_admin_deletes_another_user_with_all_their_data(api, db_session):
    client, _ = api
    admin, bob = await _users(db_session)
    await upsert_listens(db_session, bob.id, [
        Scrobble(artist="Kavinsky", track_title="Nightcall", album=None,
                 played_at=datetime(2026, 11, 1, 12, tzinfo=UTC)),
    ])
    await upsert_listens(db_session, admin.id, [
        Scrobble(artist="Kavinsky", track_title="Nightcall", album=None,
                 played_at=datetime(2026, 11, 1, 12, tzinfo=UTC)),
    ])
    await advance_sync_state(
        db_session, bob.id, last_played_at=datetime(2026, 11, 1, 12, tzinfo=UTC)
    )
    db_session.add(Share(share_token="t" * 43, user_id=bob.id))
    await db_session.flush()
    bob_id, admin_id = bob.id, admin.id

    resp = await client.delete(f"/auth/admin/users/{bob_id}", headers=_auth(admin.id))

    assert resp.status_code == 204
    db_session.expire_all()
    assert await db_session.get(User, bob_id) is None
    assert await db_session.scalar(
        select(func.count()).select_from(Listen).where(Listen.user_id == bob_id)
    ) == 0
    assert await db_session.scalar(select(func.count()).select_from(Share)) == 0
    assert await db_session.get(SyncState, bob_id) is None
    assert await db_session.scalar(
        select(func.count()).select_from(Listen).where(Listen.user_id == admin_id)
    ) == 1
    assert COOKIE_NAME not in resp.headers.get("set-cookie", "")


async def test_admin_cannot_delete_themselves_here(api, db_session):
    client, _ = api
    admin, _ = await _users(db_session)
    admin_id = admin.id

    resp = await client.delete(f"/auth/admin/users/{admin_id}", headers=_auth(admin_id))

    assert resp.status_code == 409
    db_session.expire_all()
    assert await db_session.get(User, admin_id) is not None


async def test_deleting_an_unknown_user_is_404(api, db_session):
    client, _ = api
    admin, _ = await _users(db_session)
    resp = await client.delete("/auth/admin/users/999999", headers=_auth(admin.id))
    assert resp.status_code == 404


async def test_allowlist_shows_env_entries_as_fixed(api, db_session, env_allowlist):
    client, _ = api
    admin, _ = await _users(db_session)

    resp = await client.get("/auth/admin/allowlist", headers=_auth(admin.id))

    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "allowlist"
    assert [(e["username"], e["fixed"]) for e in body["entries"]] == [
        ("Dave", True), ("erin", True),
    ]


async def test_added_entries_show_up_and_can_be_removed(api, db_session, env_allowlist):
    client, _ = api
    admin, _ = await _users(db_session)
    headers = _auth(admin.id)

    added = await client.post("/auth/admin/allowlist", json={"username": " Carol "},
                              headers=headers)
    assert added.status_code == 201
    assert added.json()["username"] == "Carol"
    assert added.json()["fixed"] is False
    assert added.json()["added_at"] is not None

    listed = (await client.get("/auth/admin/allowlist", headers=headers)).json()["entries"]
    assert [(e["username"], e["fixed"]) for e in listed] == [
        ("Carol", False), ("Dave", True), ("erin", True),
    ]

    removed = await client.delete("/auth/admin/allowlist/carol", headers=headers)
    assert removed.status_code == 204
    listed = (await client.get("/auth/admin/allowlist", headers=headers)).json()["entries"]
    assert [e["username"] for e in listed] == ["Dave", "erin"]


@pytest.mark.parametrize("name", ["carol", "CAROL", "dave", "ERIN"])
async def test_an_entry_cannot_be_added_twice_in_any_case(api, db_session, env_allowlist, name):
    client, _ = api
    admin, _ = await _users(db_session)
    headers = _auth(admin.id)
    assert (await client.post("/auth/admin/allowlist", json={"username": "Carol"},
                              headers=headers)).status_code == 201

    resp = await client.post("/auth/admin/allowlist", json={"username": name}, headers=headers)

    assert resp.status_code == 409


@pytest.mark.parametrize("name", ["", "   ", "a b", "x" * 65, "al,ice"])
async def test_allowlist_rejects_names_that_cannot_be_usernames(
    api, db_session, env_allowlist, name
):
    client, _ = api
    admin, _ = await _users(db_session)
    resp = await client.post("/auth/admin/allowlist", json={"username": name},
                             headers=_auth(admin.id))
    assert resp.status_code == 422


async def test_env_entries_cannot_be_removed(api, db_session, env_allowlist):
    client, _ = api
    admin, _ = await _users(db_session)
    resp = await client.delete("/auth/admin/allowlist/DAVE", headers=_auth(admin.id))
    assert resp.status_code == 409


async def test_removing_an_unknown_entry_is_404(api, db_session, env_allowlist):
    client, _ = api
    admin, _ = await _users(db_session)
    resp = await client.delete("/auth/admin/allowlist/nobody", headers=_auth(admin.id))
    assert resp.status_code == 404


async def test_a_user_added_at_runtime_can_register(api, db_session, env_allowlist, monkeypatch):
    from tidalwave.deps import get_lastfm_client
    from tidalwave.routes import auth as auth_module

    client, app = api
    admin, _ = await _users(db_session)

    async def _noop(*args, **kwargs):
        pass

    monkeypatch.setattr(auth_module, "ingest_user_now", _noop)

    class FakeLastfm:
        async def get_session(self, token):
            return ("carol", "SESS")

    app.dependency_overrides[get_lastfm_client] = lambda: FakeLastfm()

    denied = await client.get("/auth/callback?token=TOK", follow_redirects=False)
    assert denied.status_code == 403

    await client.post("/auth/admin/allowlist", json={"username": "Carol"},
                      headers=_auth(admin.id))
    allowed = await client.get("/auth/callback?token=TOK", follow_redirects=False)
    assert allowed.status_code == 307
