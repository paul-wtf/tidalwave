from datetime import UTC, datetime

from tidalwave.auth.service import upsert_user_from_session
from tidalwave.auth.session import COOKIE_NAME, SessionCodec
from tidalwave.ingest.repository import upsert_listens
from tidalwave.models.domain import Scrobble


async def test_stats_requires_auth(api):
    client, app = api
    resp = await client.get("/stats/top-artists")
    assert resp.status_code == 401


async def test_stats_returns_own_data(api, db_session):
    client, app = api
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    await upsert_listens(db_session, user.id, [
        Scrobble(artist="Daft Punk", track_title="a", album=None,
                 played_at=datetime.fromtimestamp(0, tz=UTC)),
    ])
    cookie = SessionCodec("test-secret").encode(user.id)
    resp = await client.get(
        "/stats/top-artists", headers={"Cookie": f"{COOKIE_NAME}={cookie}"}
    )
    assert resp.status_code == 200
    assert resp.json()[0] == {"artist": "Daft Punk", "count": 1}


async def test_weekday_returns_7_element_list(api, db_session):
    client, app = api
    user = await upsert_user_from_session(db_session, "weekday_user", "sk_wd", mode="open", allowlist=[])
    # 2024-06-17 is a Monday (isodow=1 → index 0)
    monday = datetime(2024, 6, 17, 10, tzinfo=UTC)
    await upsert_listens(db_session, user.id, [
        Scrobble(artist="A", track_title="mon_track", album=None, played_at=monday),
    ])
    cookie = SessionCodec("test-secret").encode(user.id)
    resp = await client.get("/stats/weekday", headers={"Cookie": f"{COOKIE_NAME}={cookie}"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 7
    assert data[0] == 1   # Monday bucket
    assert sum(data) == 1


async def test_history_buckets_by_day(api, db_session):
    client, app = api
    user = await upsert_user_from_session(db_session, "history_user", "sk_hist", mode="open", allowlist=[])
    day1 = datetime(2024, 5, 1, 6, tzinfo=UTC)
    day2 = datetime(2024, 5, 3, 14, tzinfo=UTC)
    await upsert_listens(db_session, user.id, [
        Scrobble(artist="B", track_title="h1", album=None, played_at=day1),
        Scrobble(artist="B", track_title="h2", album=None, played_at=day1),
        Scrobble(artist="B", track_title="h3", album=None, played_at=day2),
    ])
    cookie = SessionCodec("test-secret").encode(user.id)
    resp = await client.get(
        "/stats/history?bucket=day", headers={"Cookie": f"{COOKIE_NAME}={cookie}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["count"] == 2
    assert data[1]["count"] == 1
    assert data[0]["period"] < data[1]["period"]


async def test_history_invalid_bucket_returns_422(api, db_session):
    client, app = api
    user = await upsert_user_from_session(db_session, "history_422_user", "sk_422", mode="open", allowlist=[])
    cookie = SessionCodec("test-secret").encode(user.id)
    resp = await client.get(
        "/stats/history?bucket=nonsense", headers={"Cookie": f"{COOKIE_NAME}={cookie}"}
    )
    assert resp.status_code == 422


async def test_summary_since_filters_listens(api, db_session):
    client, app = api
    user = await upsert_user_from_session(db_session, "bob", "sk2", mode="open", allowlist=[])
    await upsert_listens(db_session, user.id, [
        Scrobble(artist="Artist A", track_title="old", album=None,
                 played_at=datetime(2024, 1, 1, tzinfo=UTC)),
        Scrobble(artist="Artist A", track_title="new1", album=None,
                 played_at=datetime(2024, 6, 1, tzinfo=UTC)),
        Scrobble(artist="Artist B", track_title="new2", album=None,
                 played_at=datetime(2024, 7, 1, tzinfo=UTC)),
    ])
    cookie = SessionCodec("test-secret").encode(user.id)
    # only listens at or after 2024-06-01 should be counted (2 of 3)
    resp = await client.get(
        "/stats/summary?since=2024-06-01T00:00:00",
        headers={"Cookie": f"{COOKIE_NAME}={cookie}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_listens"] == 2
    assert body["distinct_artists"] == 2  # Artist A + Artist B in the window
    assert body["distinct_tracks"] == 2
    assert body["total_seconds"] == 0  # no durations resolved in this test


async def test_clock_uses_user_timezone(api, db_session):
    client, app = api
    user = await upsert_user_from_session(db_session, "tz_user", "sk_tz", mode="open", allowlist=[])
    user.timezone = "Europe/Berlin"
    await db_session.flush()
    await upsert_listens(db_session, user.id, [
        Scrobble(artist="A", track_title="t", album=None,
                 played_at=datetime(2026, 7, 1, 10, tzinfo=UTC)),
    ])
    cookie = SessionCodec("test-secret").encode(user.id)
    resp = await client.get("/stats/clock", headers={"Cookie": f"{COOKIE_NAME}={cookie}"})
    assert resp.status_code == 200
    assert resp.json()[12] == 1


async def test_limit_capped_at_500(api, db_session):
    client, app = api
    user = await upsert_user_from_session(db_session, "cap_user", "sk_cap", mode="open", allowlist=[])
    headers = {"Cookie": f"{COOKIE_NAME}={SessionCodec('test-secret').encode(user.id)}"}
    assert (await client.get("/stats/top-artists?limit=501", headers=headers)).status_code == 422
    assert (await client.get("/stats/top-artists?limit=0", headers=headers)).status_code == 422
    assert (await client.get("/stats/top-artists?limit=500", headers=headers)).status_code == 200
