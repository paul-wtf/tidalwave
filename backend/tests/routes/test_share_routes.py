from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from tidalwave.auth.service import upsert_user_from_session
from tidalwave.auth.session import COOKIE_NAME, SessionCodec
from tidalwave.ingest.repository import upsert_listens
from tidalwave.models.db import Share
from tidalwave.models.domain import Scrobble


def _auth_header(user_id: int) -> dict:
    cookie = SessionCodec("test-secret").encode(user_id)
    return {"Cookie": f"{COOKIE_NAME}={cookie}"}


async def test_share_create_then_public_view(api, db_session):
    client, app = api
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    await upsert_listens(db_session, user.id, [
        Scrobble(artist="Kavinsky", track_title="Nightcall", album=None,
                 played_at=datetime.fromtimestamp(0, tz=UTC)),
    ])

    created = await client.post("/shares", headers=_auth_header(user.id))
    assert created.status_code == 201
    token = created.json()["share_token"]

    view = await client.get(f"/shared/{token}/top-artists")  # public, no cookie
    assert view.status_code == 200
    assert view.json()[0] == {"artist": "Kavinsky", "count": 1, "image_url": None}


async def test_revoked_share_returns_404(api, db_session):
    client, app = api
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    token = (await client.post("/shares", headers=_auth_header(user.id))).json()["share_token"]

    await client.delete(f"/shares/{token}", headers=_auth_header(user.id))
    view = await client.get(f"/shared/{token}/top-artists")
    assert view.status_code == 404


async def test_shared_full_dashboard_endpoints(api, db_session):
    from datetime import UTC, datetime
    from tidalwave.auth.service import upsert_user_from_session
    from tidalwave.auth.session import COOKIE_NAME, SessionCodec
    from tidalwave.ingest.repository import upsert_listens
    from tidalwave.models.domain import Scrobble

    client, app = api
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    await upsert_listens(db_session, user.id, [
        Scrobble(artist="Kavinsky", track_title="Nightcall", album="OutRun",
                 played_at=datetime(2024, 6, 17, 12, tzinfo=UTC)),
    ])
    cookie = SessionCodec("test-secret").encode(user.id)
    token = (await client.post("/shares", headers={"Cookie": f"{COOKIE_NAME}={cookie}"})).json()["share_token"]

    assert (await client.get(f"/shared/{token}/top-tracks")).json()[0]["track"] == "Nightcall"
    assert (await client.get(f"/shared/{token}/top-albums")).json()[0]["album"] == "OutRun"
    assert (await client.get(f"/shared/{token}/clock")).json()[12] == 1   # hour 12 UTC
    assert (await client.get(f"/shared/{token}/weekday")).json()[0] == 1  # Monday
    assert (await client.get(f"/shared/{token}/history?bucket=day")).json()[0]["count"] == 1
    assert (await client.get(f"/shared/{token}/recent")).json()[0]["track"] == "Nightcall"


async def test_shared_endpoints_404_when_revoked(api, db_session):
    from tidalwave.auth.service import upsert_user_from_session
    from tidalwave.auth.session import COOKIE_NAME, SessionCodec

    client, app = api
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    auth = {"Cookie": f"{COOKIE_NAME}={SessionCodec('test-secret').encode(user.id)}"}
    token = (await client.post("/shares", headers=auth)).json()["share_token"]
    await client.delete(f"/shares/{token}", headers=auth)
    assert (await client.get(f"/shared/{token}/top-tracks")).status_code == 404
    assert (await client.get(f"/shared/{token}/clock")).status_code == 404


async def test_shared_view_cannot_widen_share_range(api, db_session):
    from tidalwave.models.db import Share

    client, app = api
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    await upsert_listens(db_session, user.id, [
        Scrobble(artist="A", track_title="dec", album=None,
                 played_at=datetime(2025, 12, 15, tzinfo=UTC)),
        Scrobble(artist="A", track_title="jan", album=None,
                 played_at=datetime(2026, 1, 15, tzinfo=UTC)),
    ])
    db_session.add(Share(
        share_token="ranged", user_id=user.id,
        range_from=datetime(2026, 1, 1, tzinfo=UTC), range_to=datetime(2026, 2, 1, tzinfo=UTC),
    ))
    await db_session.flush()

    resp = await client.get("/shared/ranged/summary?since=2025-01-01T00:00:00Z")
    assert resp.status_code == 200
    assert resp.json()["total_listens"] == 1


async def test_shared_paths_unchanged(api, db_session):
    client, app = api
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    token = (await client.post("/shares", headers=_auth_header(user.id))).json()["share_token"]
    for path in ("top-artists", "top-tracks", "top-albums", "clock", "weekday", "history",
                 "metrics-over-time", "recent", "summary"):
        assert (await client.get(f"/shared/{token}/{path}")).status_code == 200, path


async def test_create_share_with_label_and_range(api, db_session):
    client, app = api
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    resp = await client.post(
        "/shares",
        headers=_auth_header(user.id),
        json={
            "label": "Summer",
            "range_from": "2026-06-01T00:00:00Z",
            "range_to": "2026-09-01T00:00:00Z",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["label"] == "Summer"
    assert body["range_from"].startswith("2026-06-01T00:00:00")
    assert body["range_to"].startswith("2026-09-01T00:00:00")
    assert body["created_at"]
    assert len(body["share_token"]) > 20


async def test_create_share_from_local_dates_uses_owner_timezone(api, db_session):
    client, app = api
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    user.timezone = "Europe/Berlin"
    await db_session.flush()
    resp = await client.post(
        "/shares",
        headers=_auth_header(user.id),
        json={"start": "2026-10-01", "end": "2026-11-01"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert datetime.fromisoformat(body["range_from"]) == datetime(2026, 9, 30, 22, tzinfo=UTC)
    assert datetime.fromisoformat(body["range_to"]) == datetime(2026, 10, 31, 23, tzinfo=UTC)


async def test_create_share_start_without_end_freezes_end_at_now(api, db_session):
    client, app = api
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    before = datetime.now(UTC)
    resp = await client.post(
        "/shares", headers=_auth_header(user.id), json={"start": "2026-01-01"}
    )
    assert resp.status_code == 201
    end = datetime.fromisoformat(resp.json()["range_to"])
    assert before <= end <= datetime.now(UTC)


async def test_create_share_without_body_still_works(api, db_session):
    client, app = api
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    resp = await client.post("/shares", headers=_auth_header(user.id))
    assert resp.status_code == 201
    body = resp.json()
    assert body["label"] is None
    assert body["range_from"] is None
    assert body["range_to"] is None
    assert body["share_token"]


async def test_create_share_rejects_inverted_range(api, db_session):
    client, app = api
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    for payload in (
        {"range_from": "2026-02-01T00:00:00Z", "range_to": "2026-01-01T00:00:00Z"},
        {"range_from": "2026-02-01T00:00:00Z", "range_to": "2026-02-01T00:00:00Z"},
        {"start": "2026-02-01", "end": "2026-01-01"},
    ):
        resp = await client.post("/shares", headers=_auth_header(user.id), json=payload)
        assert resp.status_code == 422, payload


async def test_create_share_rejects_mixed_forms(api, db_session):
    client, app = api
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    resp = await client.post(
        "/shares",
        headers=_auth_header(user.id),
        json={"range_from": "2026-01-01T00:00:00Z", "start": "2026-01-01"},
    )
    assert resp.status_code == 422


async def test_list_shares_excludes_revoked_and_other_users(api, db_session):
    client, app = api
    alice = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    bob = await upsert_user_from_session(db_session, "bob", "sk2", mode="open", allowlist=[])
    first = (await client.post(
        "/shares", headers=_auth_header(alice.id), json={"label": "first"}
    )).json()
    second = (await client.post(
        "/shares", headers=_auth_header(alice.id), json={"label": "second"}
    )).json()
    revoked = (await client.post(
        "/shares", headers=_auth_header(alice.id), json={"label": "gone"}
    )).json()
    await client.delete(f"/shares/{revoked['share_token']}", headers=_auth_header(alice.id))
    await client.post("/shares", headers=_auth_header(bob.id), json={"label": "bobs"})

    resp = await client.get("/shares", headers=_auth_header(alice.id))
    assert resp.status_code == 200
    assert [s["share_token"] for s in resp.json()] == [
        second["share_token"], first["share_token"],
    ]
    assert set(resp.json()[0]) == {
        "share_token", "label", "range_from", "range_to", "created_at",
    }


async def test_list_shares_requires_login(api):
    client, app = api
    assert (await client.get("/shares")).status_code == 401


def _clamp_listens() -> list[Scrobble]:
    def at(*args):
        return datetime(*args, tzinfo=UTC)

    return [
        Scrobble(artist="Ana", track_title="T-before", album="Rec", played_at=at(2026, 2, 28, 22, 30)),
        Scrobble(artist="Ana", track_title="T-in1", album="Rec", played_at=at(2026, 3, 10, 12)),
        Scrobble(artist="Ana", track_title="T-in2", album="Rec", played_at=at(2026, 4, 15, 22, 30)),
        Scrobble(artist="Ana", track_title="T-after", album="Rec", played_at=at(2026, 4, 30, 22, 30)),
        Scrobble(artist="Ghost", track_title="G-before", album="Boo", played_at=at(2026, 1, 5, 12)),
        Scrobble(artist="Ghost", track_title="G-after", album="Boo", played_at=at(2026, 7, 5, 12)),
    ]


async def _clamped_share(api, db_session) -> str:
    client, _ = api
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    user.timezone = "Europe/Berlin"
    await upsert_listens(db_session, user.id, _clamp_listens())
    db_session.add(Share(
        share_token="clamped", user_id=user.id,
        range_from=datetime(2026, 2, 28, 23, tzinfo=UTC),
        range_to=datetime(2026, 4, 30, 22, tzinfo=UTC),
    ))
    await db_session.flush()
    return "clamped"


LEAKS = ("T-before", "T-after", "G-before", "G-after", "Ghost", "2026-02-28", "2026-05-01", "2026-01-05", "2026-07-05")

CLAMP_CASES = {
    "artist": ("artist?artist=Ana", lambda b: b["listens"] == 2),
    "album": ("album?artist=Ana&album=Rec", lambda b: b["listens"] == 2),
    "track": ("track?artist=Ana&track=T-in1", lambda b: b["listens"] == 1),
    "discoveries": ("discoveries", lambda b: [a["artist"] for a in b["new_artists"]] == ["Ana"]
                    and b["new_tracks_count"] == 2),
    "records": ("records", lambda b: b["longest_streak"]["days"] == 1
                and b["current_streak"] is None and b["longest_session"]["listens"] == 1),
    "heatmap": ("heatmap", lambda b: [d["date"] for d in b["days"]] == ["2026-03-10", "2026-04-16"]),
    "summary-compare": ("summary?compare=true&calendar=month", lambda b: b["total_listens"] == 2
                        and b["previous"] is None),
    "top-albums": ("top-albums", lambda b: [(a["album"], a["count"]) for a in b] == [("Rec", 2)]),
    "top-albums-filtered": ("top-albums?artist=Ana", lambda b: [a["count"] for a in b] == [2]),
    "metrics-over-time": ("metrics-over-time?bucket=month&artist=Ana&album=Rec",
                          lambda b: sum(p["listens"] for p in b) == 2),
    "metrics-over-time-track": ("metrics-over-time?track=T-after", lambda b: b == []),
    "recent-filtered": ("recent?artist=Ana", lambda b: sorted(r["track"] for r in b) == ["T-in1", "T-in2"]),
    "clock": ("clock", lambda b: b[13] == 1 and b[0] == 1 and sum(b) == 2),
    "summary-start-end": ("summary?start=2026-01-01&end=2026-12-31", lambda b: b["total_listens"] == 2),
    "summary-owner-day": ("summary?start=2026-04-16&end=2026-04-17", lambda b: b["total_listens"] == 1),
    "summary-since-until": ("summary?since=2025-01-01T00:00:00Z&until=2027-01-01T00:00:00Z",
                            lambda b: b["total_listens"] == 2),
}


@pytest.mark.parametrize("path,check", list(CLAMP_CASES.values()), ids=list(CLAMP_CASES))
async def test_shared_endpoints_never_leak_outside_the_share_range(api, db_session, path, check):
    client, _ = api
    token = await _clamped_share(api, db_session)
    resp = await client.get(f"/shared/{token}/{path}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert check(body), body
    for leak in LEAKS:
        assert leak not in resp.text, (leak, resp.text)


@pytest.mark.parametrize("path", [
    "artist?artist=Ghost", "album?artist=Ghost&album=Boo", "track?artist=Ghost&track=G-before",
    "track?artist=Ana&track=T-after",
])
async def test_shared_details_outside_the_range_are_404(api, db_session, path):
    client, _ = api
    token = await _clamped_share(api, db_session)
    assert (await client.get(f"/shared/{token}/{path}")).status_code == 404


async def test_shared_on_this_day_ignores_listens_outside_the_range(api, db_session):
    client, _ = api
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    user.timezone = "Europe/Berlin"
    today = datetime.now(ZoneInfo("Europe/Berlin")).date()
    if (today.month, today.day) == (2, 29):
        pytest.skip("no same calendar day in other years")

    def noon(year: int) -> datetime:
        return datetime(year, today.month, today.day, 12, tzinfo=ZoneInfo("Europe/Berlin"))

    await upsert_listens(db_session, user.id, [
        Scrobble(artist="A", track_title="in", album=None, played_at=noon(today.year - 2)),
        Scrobble(artist="A", track_title="after", album=None, played_at=noon(today.year - 1)),
        Scrobble(artist="A", track_title="before", album=None, played_at=noon(today.year - 4)),
    ])
    db_session.add(Share(
        share_token="otd", user_id=user.id,
        range_from=datetime(today.year - 3, 1, 1, tzinfo=UTC),
        range_to=datetime(today.year - 1, 1, 1, tzinfo=UTC),
    ))
    await db_session.flush()

    resp = await client.get("/shared/otd/on-this-day")
    assert resp.status_code == 200
    assert [(y["year"], [t["track"] for t in y["top_tracks"]]) for y in resp.json()] == [
        (today.year - 2, ["in"])
    ]
