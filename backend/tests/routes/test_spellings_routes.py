from datetime import UTC, datetime, timedelta

from tidalwave.auth.service import upsert_user_from_session
from tidalwave.auth.session import COOKIE_NAME, SessionCodec
from tidalwave.ingest.repository import upsert_listens
from tidalwave.models.domain import Scrobble

T0 = datetime(2024, 3, 1, 12, tzinfo=UTC)


async def _login(db_session, name="alice"):
    user = await upsert_user_from_session(db_session, name, f"sk-{name}", mode="open", allowlist=[])
    cookie = SessionCodec("test-secret").encode(user.id)
    return user, {"Cookie": f"{COOKIE_NAME}={cookie}"}


async def _listen(db_session, user, *artists):
    await upsert_listens(db_session, user.id, [
        Scrobble(artist=a, track_title=f"t{i}", album=None, played_at=T0 + timedelta(minutes=i))
        for i, a in enumerate(artists)
    ])


async def test_spellings_need_a_login(api):
    client, _ = api
    assert (await client.get("/merges")).status_code == 401
    assert (await client.post("/merges", json={})).status_code == 401
    assert (await client.delete("/merges?canonical=x")).status_code == 401


async def test_spellings_list_suggestions_and_merges(api, db_session):
    client, _ = api
    user, headers = await _login(db_session)
    await _listen(db_session, user, "The National", "The National", "National", "Sigur Ros", "Sigur Rós")

    resp = await client.get("/merges", headers=headers)

    assert resp.status_code == 200
    assert resp.json() == {
        "suggestions": [
            {"names": [{"artist": "The National", "listens": 2},
                       {"artist": "National", "listens": 1}], "listens": 3},
            {"names": [{"artist": "Sigur Ros", "listens": 1},
                       {"artist": "Sigur Rós", "listens": 1}], "listens": 2},
        ],
        "merges": [],
    }


async def test_accepting_a_suggestion_merges_and_the_stats_follow(api, db_session):
    client, _ = api
    user, headers = await _login(db_session)
    await _listen(db_session, user, "The National", "The National", "National")

    resp = await client.post(
        "/merges",
        json={"canonical": "The National", "variants": ["National"]},
        headers=headers,
    )

    assert resp.status_code == 201
    assert resp.json()["merges"] == [{
        "canonical": "The National", "listens": 3,
        "variants": [{"artist": "National", "listens": 1}],
    }]
    assert resp.json()["suggestions"] == []
    top = (await client.get("/stats/top-artists", headers=headers)).json()
    assert [(a["artist"], a["count"]) for a in top] == [("The National", 3)]


async def test_an_invalid_merge_is_answered_with_422(api, db_session):
    client, _ = api
    _, headers = await _login(db_session)

    resp = await client.post(
        "/merges",
        json={"canonical": "The National", "variants": ["The National"]},
        headers=headers,
    )

    assert resp.status_code == 422
    assert resp.json()["detail"] == "Pick at least one other spelling"


async def test_undoing_a_merge_restores_the_spellings(api, db_session):
    client, _ = api
    user, headers = await _login(db_session)
    await _listen(db_session, user, "The National", "National", "the national")
    await client.post(
        "/merges",
        json={"canonical": "The National", "variants": ["National", "the national"]},
        headers=headers,
    )

    one = await client.delete(
        "/merges", params={"canonical": "The National", "variant": "National"},
        headers=headers,
    )
    assert one.status_code == 200
    assert one.json()["merges"][0]["variants"] == [{"artist": "the national", "listens": 1}]

    rest = await client.delete(
        "/merges", params={"canonical": "The National"}, headers=headers
    )
    assert rest.json()["merges"] == []
    top = (await client.get("/stats/top-artists", headers=headers)).json()
    assert sorted(a["artist"] for a in top) == ["National", "The National", "the national"]


async def test_undoing_a_merge_that_does_not_exist_is_404(api, db_session):
    client, _ = api
    _, headers = await _login(db_session)

    resp = await client.delete(
        "/merges", params={"canonical": "Nobody"}, headers=headers
    )

    assert resp.status_code == 404


async def test_one_user_cannot_undo_another_users_merge(api, db_session):
    client, _ = api
    alice, alice_headers = await _login(db_session, "alice")
    _, bob_headers = await _login(db_session, "bob")
    await _listen(db_session, alice, "The National", "National")
    await client.post(
        "/merges",
        json={"canonical": "The National", "variants": ["National"]},
        headers=alice_headers,
    )

    resp = await client.delete(
        "/merges", params={"canonical": "The National"}, headers=bob_headers
    )

    assert resp.status_code == 404
    still = (await client.get("/merges", headers=alice_headers)).json()["merges"]
    assert len(still) == 1
