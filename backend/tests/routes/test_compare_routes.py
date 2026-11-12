from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from tidalwave.auth.service import upsert_user_from_session
from tidalwave.auth.session import COOKIE_NAME, SessionCodec
from tidalwave.ingest.repository import upsert_listens
from tidalwave.models.db import ComparePair, User
from tidalwave.models.domain import Scrobble


def _auth(user_id: int) -> dict:
    return {"Cookie": f"{COOKIE_NAME}={SessionCodec('test-secret').encode(user_id)}"}


async def _users(db_session):
    names = ("alice", "bob", "carol")
    return [
        await upsert_user_from_session(db_session, n, "sk", mode="open", allowlist=[])
        for n in names
    ]


async def _invite(client, user: User) -> str:
    resp = await client.post("/comparisons/invites", headers=_auth(user.id))
    assert resp.status_code == 201
    return resp.json()["token"]


async def _pair(client, inviter: User, guest: User) -> int:
    token = await _invite(client, inviter)
    resp = await client.post(f"/comparisons/invites/{token}/accept", headers=_auth(guest.id))
    assert resp.status_code == 201
    return resp.json()["id"]


def _listens(artist_counts: dict[str, int], day: int = 5):
    return [
        Scrobble(artist=artist, track_title=f"{artist} {i}", album=None,
                 played_at=datetime(2026, 11, day, 10, i, tzinfo=UTC))
        for artist, n in artist_counts.items()
        for i in range(n)
    ]


@pytest.mark.parametrize(("method", "path"), [
    ("GET", "/comparisons"),
    ("POST", "/comparisons/invites"),
    ("GET", "/comparisons/invites/x"),
    ("POST", "/comparisons/invites/x/accept"),
    ("DELETE", "/comparisons/invites/x"),
    ("GET", "/comparisons/1"),
    ("DELETE", "/comparisons/1"),
])
async def test_comparisons_need_a_session(api, method, path):
    client, _ = api
    assert (await client.request(method, path)).status_code == 401


async def test_an_invite_is_listed_until_it_is_used(api, db_session):
    client, _ = api
    alice, bob, _ = await _users(db_session)

    token = await _invite(client, alice)

    assert len(token) == 43
    listed = (await client.get("/comparisons", headers=_auth(alice.id))).json()
    assert [i["token"] for i in listed["invites"]] == [token]
    assert listed["pairs"] == []

    opened = await client.get(f"/comparisons/invites/{token}", headers=_auth(bob.id))
    assert opened.status_code == 200
    assert opened.json() == {"inviter": "alice", "own": False}

    accepted = await client.post(f"/comparisons/invites/{token}/accept", headers=_auth(bob.id))
    assert accepted.status_code == 201
    assert accepted.json()["partner"] == "alice"

    listed = (await client.get("/comparisons", headers=_auth(alice.id))).json()
    assert listed["invites"] == []
    assert [p["partner"] for p in listed["pairs"]] == ["bob"]
    bob_side = (await client.get("/comparisons", headers=_auth(bob.id))).json()
    assert [p["partner"] for p in bob_side["pairs"]] == ["alice"]


async def test_an_invite_works_only_once(api, db_session):
    client, _ = api
    alice, bob, carol = await _users(db_session)
    token = await _invite(client, alice)
    assert (await client.post(f"/comparisons/invites/{token}/accept",
                              headers=_auth(bob.id))).status_code == 201

    again = await client.post(f"/comparisons/invites/{token}/accept", headers=_auth(carol.id))

    assert again.status_code == 404
    assert (await client.get(f"/comparisons/invites/{token}",
                             headers=_auth(carol.id))).status_code == 404


async def test_a_revoked_invite_cannot_be_accepted(api, db_session):
    client, _ = api
    alice, bob, _ = await _users(db_session)
    token = await _invite(client, alice)

    assert (await client.delete(f"/comparisons/invites/{token}",
                                headers=_auth(alice.id))).status_code == 204

    resp = await client.post(f"/comparisons/invites/{token}/accept", headers=_auth(bob.id))
    assert resp.status_code == 404
    assert (await client.get("/comparisons", headers=_auth(alice.id))).json()["invites"] == []


async def test_only_the_inviter_can_revoke(api, db_session):
    client, _ = api
    alice, bob, _ = await _users(db_session)
    token = await _invite(client, alice)

    assert (await client.delete(f"/comparisons/invites/{token}",
                                headers=_auth(bob.id))).status_code == 404
    assert (await client.post(f"/comparisons/invites/{token}/accept",
                              headers=_auth(bob.id))).status_code == 201


async def test_nobody_can_accept_their_own_invite(api, db_session):
    client, _ = api
    alice, _, _ = await _users(db_session)
    token = await _invite(client, alice)

    opened = await client.get(f"/comparisons/invites/{token}", headers=_auth(alice.id))
    assert opened.json() == {"inviter": "alice", "own": True}
    resp = await client.post(f"/comparisons/invites/{token}/accept", headers=_auth(alice.id))

    assert resp.status_code == 409
    assert await db_session.scalar(select(func.count()).select_from(ComparePair)) == 0


async def test_a_second_invite_between_the_same_two_is_refused_and_stays_open(api, db_session):
    client, _ = api
    alice, bob, _ = await _users(db_session)
    await _pair(client, alice, bob)
    token = await _invite(client, bob)

    resp = await client.post(f"/comparisons/invites/{token}/accept", headers=_auth(alice.id))

    assert resp.status_code == 409
    listed = (await client.get("/comparisons", headers=_auth(bob.id))).json()
    assert [i["token"] for i in listed["invites"]] == [token]


async def test_either_side_can_end_a_pair(api, db_session):
    client, _ = api
    alice, bob, carol = await _users(db_session)
    first = await _pair(client, alice, bob)
    second = await _pair(client, carol, alice)

    assert (await client.delete(f"/comparisons/{first}", headers=_auth(carol.id))).status_code == 404
    assert (await client.delete(f"/comparisons/{first}", headers=_auth(alice.id))).status_code == 204
    assert (await client.delete(f"/comparisons/{second}", headers=_auth(carol.id))).status_code == 204

    assert (await client.get(f"/comparisons/{first}", headers=_auth(bob.id))).status_code == 404
    assert (await client.get("/comparisons", headers=_auth(alice.id))).json()["pairs"] == []


async def test_comparison_data_needs_the_pair(api, db_session):
    client, _ = api
    alice, bob, carol = await _users(db_session)
    pair = await _pair(client, alice, bob)

    assert (await client.get(f"/comparisons/{pair}", headers=_auth(carol.id))).status_code == 404
    assert (await client.get("/comparisons/999999", headers=_auth(alice.id))).status_code == 404


async def test_comparison_counts_artists_of_both_inside_the_range(api, db_session):
    client, _ = api
    alice, bob, _ = await _users(db_session)
    await upsert_listens(db_session, alice.id, _listens({"A": 6, "B": 3, "C": 1}))
    await upsert_listens(db_session, bob.id, _listens({"A": 2, "B": 2, "D": 4}))
    await upsert_listens(db_session, bob.id, _listens({"C": 5}, day=1))
    await db_session.flush()
    pair = await _pair(client, bob, alice)
    query = "since=2026-11-03T00:00:00Z&until=2026-11-10T00:00:00Z"

    resp = await client.get(f"/comparisons/{pair}?{query}", headers=_auth(alice.id))

    assert resp.status_code == 200
    body = resp.json()
    assert body["partner"] == "bob"
    assert body["overlap"] == pytest.approx(0.5)
    assert body["listens"] == {"you": 10, "partner": 8}
    assert body["shared"] == [
        {"artist": "A", "you": 6, "partner": 2},
        {"artist": "B", "you": 3, "partner": 2},
    ]
    assert body["only_you"] == [{"artist": "C", "count": 1}]
    assert body["only_partner"] == [{"artist": "D", "count": 4}]

    other = (await client.get(f"/comparisons/{pair}?{query}", headers=_auth(bob.id))).json()
    assert other["partner"] == "alice"
    assert other["listens"] == {"you": 8, "partner": 10}
    assert other["only_you"] == [{"artist": "D", "count": 4}]

    everything = (await client.get(f"/comparisons/{pair}", headers=_auth(alice.id))).json()
    assert everything["only_you"] == []
    assert everything["shared_artists"] == 3


async def test_comparison_resolves_days_in_the_viewers_timezone(api, db_session):
    client, _ = api
    alice, bob, _ = await _users(db_session)
    alice.timezone = "Europe/Berlin"
    await upsert_listens(db_session, bob.id, [
        Scrobble(artist="Late", track_title="t", album=None,
                 played_at=datetime(2026, 11, 4, 23, 30, tzinfo=UTC)),
    ])
    await db_session.flush()
    pair = await _pair(client, alice, bob)

    body = (await client.get(f"/comparisons/{pair}?start=2026-11-05&end=2026-11-06",
                             headers=_auth(alice.id))).json()

    assert body["only_partner"] == [{"artist": "Late", "count": 1}]
    assert body["overlap"] is None


async def test_deleting_an_account_ends_its_pairs_and_invites(api, db_session):
    client, _ = api
    alice, bob, _ = await _users(db_session)
    await _pair(client, alice, bob)
    await _invite(client, bob)

    assert (await client.delete("/auth/me", headers=_auth(bob.id))).status_code == 204

    assert (await client.get("/comparisons", headers=_auth(alice.id))).json()["pairs"] == []
