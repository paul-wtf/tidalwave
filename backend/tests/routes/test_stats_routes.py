from datetime import UTC, datetime, timedelta

from tidalwave.auth.service import upsert_user_from_session
from tidalwave.auth.session import COOKIE_NAME, SessionCodec
from tidalwave.ingest.repository import upsert_listens
from tidalwave.models.db import ArtistTags
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
    assert resp.json()[0] == {"artist": "Daft Punk", "count": 1, "image_url": None}


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


async def test_hour_weekday_uses_user_timezone(api, db_session):
    client, app = api
    user = await upsert_user_from_session(db_session, "grid_user", "sk_grid", mode="open", allowlist=[])
    user.timezone = "Europe/Berlin"
    await db_session.flush()
    await upsert_listens(db_session, user.id, [
        Scrobble(artist="A", track_title="t", album=None,
                 played_at=datetime(2026, 7, 5, 22, 30, tzinfo=UTC)),
    ])
    cookie = SessionCodec("test-secret").encode(user.id)
    resp = await client.get("/stats/hour-weekday", headers={"Cookie": f"{COOKIE_NAME}={cookie}"})
    assert resp.status_code == 200
    grid = resp.json()
    assert len(grid) == 7
    assert grid[0][0] == 1
    assert sum(map(sum, grid)) == 1


async def test_milestones_report_the_1000th_listen_for_any_selected_range(api, db_session):
    client, app = api
    user = await upsert_user_from_session(db_session, "ms_user", "sk_ms", mode="open", allowlist=[])
    start = datetime(2024, 1, 1, tzinfo=UTC)
    await upsert_listens(db_session, user.id, [
        Scrobble(artist="A", track_title=f"t{i}", album=None, played_at=start + timedelta(hours=i))
        for i in range(1, 1003)
    ])
    cookie = SessionCodec("test-secret").encode(user.id)
    resp = await client.get(
        "/stats/milestones?since=2030-01-01T00:00:00Z", headers={"Cookie": f"{COOKIE_NAME}={cookie}"}
    )
    assert resp.status_code == 200
    assert resp.json() == {
        "total": 1002,
        "reached": [{
            "count": 1000, "played_at": (start + timedelta(hours=1000)).isoformat(),
            "track": "t1000", "artist": "A", "album": None,
        }],
        "next": {"count": 5000, "remaining": 3998},
    }


async def test_limit_capped_at_500(api, db_session):
    client, app = api
    user = await upsert_user_from_session(db_session, "cap_user", "sk_cap", mode="open", allowlist=[])
    headers = {"Cookie": f"{COOKIE_NAME}={SessionCodec('test-secret').encode(user.id)}"}
    assert (await client.get("/stats/top-artists?limit=501", headers=headers)).status_code == 422
    assert (await client.get("/stats/top-artists?limit=0", headers=headers)).status_code == 422
    assert (await client.get("/stats/top-artists?limit=500", headers=headers)).status_code == 200


async def test_summary_compare_omitted_for_all_time_and_shares(api, db_session):
    client, app = api
    user = await upsert_user_from_session(db_session, "cmp", "sk_cmp", mode="open", allowlist=[])
    await upsert_listens(db_session, user.id, [
        Scrobble(artist="A", track_title="old", album=None,
                 played_at=datetime(2024, 1, 15, tzinfo=UTC)),
        Scrobble(artist="A", track_title="new", album=None,
                 played_at=datetime(2024, 2, 15, tzinfo=UTC)),
    ])
    headers = {"Cookie": f"{COOKIE_NAME}={SessionCodec('test-secret').encode(user.id)}"}

    all_time = await client.get("/stats/summary?compare=true", headers=headers)
    assert all_time.json()["previous"] is None

    plain = await client.get("/stats/summary", headers=headers)
    assert "previous" not in plain.json()

    ranged = await client.get(
        "/stats/summary?compare=true&since=2024-02-01T00:00:00Z&until=2024-03-01T00:00:00Z",
        headers=headers,
    )
    body = ranged.json()
    assert body["total_listens"] == 1
    assert body["previous"]["total_listens"] == 1

    token = (await client.post("/shares", headers=headers)).json()["share_token"]
    shared = await client.get(f"/shared/{token}/summary?compare=true&since=2024-02-01T00:00:00Z")
    assert shared.status_code == 200
    assert shared.json()["previous"] is None


NASTY = 'AC/DC & "Friends" #1 ?+ Ünïcode'


async def test_detail_roundtrips_special_characters(api, db_session):
    client, app = api
    user = await upsert_user_from_session(db_session, "nasty", "sk_n", mode="open", allowlist=[])
    when = datetime(2024, 1, 1, tzinfo=UTC)
    await upsert_listens(db_session, user.id, [
        Scrobble(artist=NASTY, track_title=NASTY, album=NASTY, played_at=when),
        Scrobble(artist="Other", track_title="o", album="Oalbum", played_at=when.replace(day=2)),
    ])
    cookie = SessionCodec("test-secret").encode(user.id)
    headers = {"Cookie": f"{COOKIE_NAME}={cookie}"}
    resp = await client.get("/stats/artist", params={"artist": NASTY}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["artist"] == NASTY
    resp = await client.get("/stats/album", params={"artist": NASTY, "album": NASTY}, headers=headers)
    assert resp.json()["album"] == NASTY
    resp = await client.get("/stats/track", params={"artist": NASTY, "track": NASTY}, headers=headers)
    assert resp.json()["track"] == NASTY
    assert resp.json()["album"] == NASTY
    recent = await client.get("/stats/recent", params={"artist": NASTY, "album": NASTY}, headers=headers)
    assert [r["artist"] for r in recent.json()] == [NASTY]
    albums = await client.get("/stats/top-albums", params={"artist": NASTY}, headers=headers)
    assert [r["album"] for r in albums.json()] == [NASTY]
    metrics = await client.get("/stats/metrics-over-time", params={"artist": NASTY}, headers=headers)
    assert [r["listens"] for r in metrics.json()] == [1]
    unfiltered = await client.get("/stats/metrics-over-time", headers=headers)
    assert sum(r["listens"] for r in unfiltered.json()) == 2


async def test_detail_404_for_unknown_entity(api, db_session):
    client, app = api
    user = await upsert_user_from_session(db_session, "empty", "sk_e", mode="open", allowlist=[])
    cookie = SessionCodec("test-secret").encode(user.id)
    headers = {"Cookie": f"{COOKIE_NAME}={cookie}"}
    await upsert_listens(db_session, user.id, [
        Scrobble(artist="Known", track_title="k", album=None,
                 played_at=datetime(2024, 1, 1, tzinfo=UTC)),
    ])
    assert (await client.get("/stats/artist", params={"artist": "Known"}, headers=headers)).status_code == 200
    assert (await client.get("/stats/track", params={"artist": "Known", "track": "k"}, headers=headers)).status_code == 200
    assert (await client.get("/stats/artist", params={"artist": "Nobody"}, headers=headers)).status_code == 404
    assert (await client.get("/stats/album", params={"artist": "N", "album": "M"}, headers=headers)).status_code == 404
    assert (await client.get("/stats/track", params={"artist": "N", "track": "M"}, headers=headers)).status_code == 404
    assert (await client.get("/stats/artist", headers=headers)).status_code == 422


async def test_genres_and_genre_page_endpoints(api, db_session):
    client, app = api
    user = await upsert_user_from_session(db_session, "genre_user", "sk_g", mode="open", allowlist=[])
    await upsert_listens(db_session, user.id, [
        Scrobble(artist="Daft Punk", track_title="a", album=None, played_at=datetime(2024, 6, 1, tzinfo=UTC)),
        Scrobble(artist="Daft Punk", track_title="b", album=None, played_at=datetime(2024, 6, 2, tzinfo=UTC)),
        Scrobble(artist="Slayer", track_title="c", album=None, played_at=datetime(2024, 6, 3, tzinfo=UTC)),
    ])
    db_session.add(ArtistTags(artist="Daft Punk", tags=["french house", "electronic"]))
    await db_session.flush()
    headers = {"Cookie": f"{COOKIE_NAME}={SessionCodec('test-secret').encode(user.id)}"}

    ranking = await client.get("/stats/genres", headers=headers)
    assert ranking.status_code == 200
    assert ranking.json() == {
        "genres": [{"genre": "electronic", "listens": 2, "artists": 1},
                   {"genre": "french house", "listens": 2, "artists": 1}],
        "artists": 2, "tagged_artists": 1,
    }
    assert (await client.get("/stats/genres?limit=1", headers=headers)).json()["genres"] == [
        {"genre": "electronic", "listens": 2, "artists": 1}
    ]
    assert (await client.get("/stats/genres?since=2024-06-02T12:00:00Z", headers=headers)).json() == {
        "genres": [], "artists": 1, "tagged_artists": 0,
    }

    detail = await client.get("/stats/genre", params={"genre": " French House "}, headers=headers)
    assert detail.json() == {"genre": "french house", "listens": 2, "seconds": 0, "artists": 1}
    assert (await client.get("/stats/genre", params={"genre": "polka"}, headers=headers)).status_code == 404
    assert (await client.get("/stats/genre", headers=headers)).status_code == 422

    artists = await client.get("/stats/top-artists", params={"genre": "French House"}, headers=headers)
    assert [(a["artist"], a["count"]) for a in artists.json()] == [("Daft Punk", 2)]
    metrics = await client.get(
        "/stats/metrics-over-time", params={"genre": "french house", "bucket": "month"}, headers=headers
    )
    assert [p["listens"] for p in metrics.json()] == [2]
    assert (await client.get("/stats/genres")).status_code == 401
