from contextlib import asynccontextmanager

import pytest
from import_samples import SPOTIFY, listenbrainz_zip

from tidalwave.auth.service import upsert_user_from_session
from tidalwave.auth.session import COOKIE_NAME, SessionCodec
from tidalwave.deps import get_session_factory
from tidalwave.imports.service import start_import


@pytest.fixture
def imports(api, db_session, monkeypatch, tmp_path):
    client, app = api
    monkeypatch.setenv("TIDALWAVE_IMPORT_DIR", str(tmp_path))

    @asynccontextmanager
    async def same():
        yield db_session

    app.dependency_overrides[get_session_factory] = lambda: same
    return client


async def _login(db_session, name="alice"):
    user = await upsert_user_from_session(db_session, name, f"sk-{name}", mode="open", allowlist=[])
    cookie = SessionCodec("test-secret").encode(user.id)
    return user, {"Cookie": f"{COOKIE_NAME}={cookie}"}


async def _upload(client, headers, body: bytes, name="Streaming_History_Audio_2021_0.json"):
    return await client.post("/imports", params={"filename": name}, content=body, headers=headers)


async def test_imports_need_a_login(imports):
    assert (await imports.get("/imports")).status_code == 401
    assert (await _upload(imports, {}, b"[]")).status_code == 401
    assert (await imports.delete("/imports/1")).status_code == 401


async def test_an_upload_is_imported_in_the_background(imports, db_session, tmp_path):
    _, headers = await _login(db_session)

    resp = await _upload(imports, headers, SPOTIFY.read_bytes())

    assert resp.status_code == 202
    started = resp.json()
    assert started["status"] == "pending"
    assert started["filename"] == "Streaming_History_Audio_2021_0.json"
    done = (await imports.get(f"/imports/{started['id']}", headers=headers)).json()
    assert done["status"] == "done"
    assert {k: done[k] for k in ("read", "skipped", "too_short", "duplicates", "added")} == {
        "read": 8, "skipped": 3, "too_short": 1, "duplicates": 0, "added": 4,
    }
    assert done["first_played_at"] == "2021-04-15T18:00:00+00:00"
    assert list(tmp_path.iterdir()) == []
    top = (await imports.get("/stats/top-artists", headers=headers)).json()
    assert {a["artist"] for a in top} == {"The National", "National", "Kavinsky"}


async def test_uploading_the_same_file_twice_adds_nothing_the_second_time(imports, db_session):
    _, headers = await _login(db_session)
    await _upload(imports, headers, SPOTIFY.read_bytes())

    again = await _upload(imports, headers, SPOTIFY.read_bytes())

    done = (await imports.get(f"/imports/{again.json()['id']}", headers=headers)).json()
    assert (done["added"], done["duplicates"]) == (0, 4)


async def test_a_listenbrainz_zip_is_imported(imports, db_session, tmp_path):
    _, headers = await _login(db_session)

    resp = await _upload(
        imports, headers, listenbrainz_zip(tmp_path).read_bytes(), "listenbrainz_listener.zip"
    )

    done = (await imports.get(f"/imports/{resp.json()['id']}", headers=headers)).json()
    assert (done["source"], done["added"]) == ("listenbrainz", 3)


async def test_imports_are_listed_newest_first(imports, db_session):
    _, headers = await _login(db_session)
    first = (await _upload(imports, headers, SPOTIFY.read_bytes(), "a.json")).json()
    second = (await _upload(imports, headers, b"nonsense", "b.json")).json()

    listed = (await imports.get("/imports", headers=headers)).json()

    assert [i["id"] for i in listed] == [second["id"], first["id"]]
    assert listed[0]["status"] == "failed"
    assert listed[0]["error"]


async def test_an_upload_over_the_limit_is_refused(imports, db_session, monkeypatch, tmp_path):
    monkeypatch.setenv("TIDALWAVE_IMPORT_MAX_BYTES", "100")
    from tidalwave.deps import get_settings

    get_settings.cache_clear()
    _, headers = await _login(db_session)

    sized = await _upload(imports, headers, b"[" + b" " * 200 + b"]")

    async def chunks():
        for _ in range(10):
            yield b" " * 50

    streamed = await imports.post(
        "/imports", params={"filename": "x.json"}, content=chunks(), headers=headers
    )
    assert sized.status_code == 413
    assert streamed.status_code == 413
    assert (await imports.get("/imports", headers=headers)).json() == []
    assert list(tmp_path.iterdir()) == []


async def test_an_empty_upload_is_refused(imports, db_session):
    _, headers = await _login(db_session)

    assert (await _upload(imports, headers, b"")).status_code == 422


async def test_a_second_import_while_one_runs_is_refused(imports, db_session):
    user, headers = await _login(db_session)
    await start_import(db_session, user.id, "running.json")

    resp = await _upload(imports, headers, SPOTIFY.read_bytes())

    assert resp.status_code == 409


async def test_undo_removes_the_listens_of_an_import(imports, db_session):
    _, headers = await _login(db_session)
    started = (await _upload(imports, headers, SPOTIFY.read_bytes())).json()

    resp = await imports.delete(f"/imports/{started['id']}", headers=headers)

    assert resp.status_code == 200
    assert resp.json()["status"] == "undone"
    assert (await imports.get("/stats/top-artists", headers=headers)).json() == []


async def test_another_users_import_is_not_found(imports, db_session):
    _, alice = await _login(db_session, "alice")
    _, bob = await _login(db_session, "bob")
    started = (await _upload(imports, alice, SPOTIFY.read_bytes())).json()

    assert (await imports.get(f"/imports/{started['id']}", headers=bob)).status_code == 404
    assert (await imports.delete(f"/imports/{started['id']}", headers=bob)).status_code == 404


async def test_a_running_import_cannot_be_undone(imports, db_session):
    user, headers = await _login(db_session)
    running = await start_import(db_session, user.id, "running.json")

    assert (await imports.delete(f"/imports/{running.id}", headers=headers)).status_code == 409


async def test_sources_tell_how_many_listens_came_from_imports(imports, db_session):
    _, headers = await _login(db_session)
    await _upload(imports, headers, SPOTIFY.read_bytes())

    resp = await imports.get("/stats/sources", headers=headers)

    assert resp.status_code == 200
    assert resp.json()["imported"] == 4
    assert resp.json()["sources"] == [{"source": "spotify", "listens": 4}]
