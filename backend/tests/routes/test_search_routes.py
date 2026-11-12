from datetime import UTC, datetime

from tidalwave.auth.service import upsert_user_from_session
from tidalwave.auth.session import COOKIE_NAME, SessionCodec
from tidalwave.ingest.repository import upsert_listens
from tidalwave.models.db import AlbumArt, Share
from tidalwave.models.domain import Scrobble


def _auth(user_id: int) -> dict:
    return {"Cookie": f"{COOKIE_NAME}={SessionCodec('test-secret').encode(user_id)}"}


def _listen(artist: str, track: str, album: str | None, day: int, hour: int = 12) -> Scrobble:
    return Scrobble(artist=artist, track_title=track, album=album,
                    played_at=datetime(2026, 10, day, hour, tzinfo=UTC))


async def _seed(db_session):
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    await upsert_listens(db_session, user.id, [
        _listen("Daft Punk", "Around the World", "Homework", 1),
        _listen("Daft Punk", "Around the World", "Homework", 2),
        _listen("Daft Punk", "Da Funk", "Homework", 3),
        _listen("Daftside", "Worldwide", "Planet", 20),
        _listen("Kavinsky", "Nightcall", "OutRun", 21),
        _listen("100% Fun", "50%_off", None, 22),
    ])
    db_session.add(AlbumArt(artist="Daft Punk", album="Homework", image_url="https://img/homework.jpg"))
    await db_session.flush()
    return user


async def test_search_requires_auth(api):
    client, _ = api
    assert (await client.get("/stats/search?q=daft")).status_code == 401


async def test_search_matches_substrings_case_insensitively(api, db_session):
    client, _ = api
    user = await _seed(db_session)
    body = (await client.get("/stats/search?q=DAFT", headers=_auth(user.id))).json()
    assert body["artists"] == [
        {"artist": "Daft Punk", "count": 3, "image_url": "https://img/homework.jpg"},
        {"artist": "Daftside", "count": 1, "image_url": None},
    ]
    assert body["albums"] == []
    assert body["tracks"] == []

    body = (await client.get("/stats/search?q=world", headers=_auth(user.id))).json()
    assert body["artists"] == []
    assert body["tracks"] == [
        {"track": "Around the World", "artist": "Daft Punk", "count": 2},
        {"track": "Worldwide", "artist": "Daftside", "count": 1},
    ]

    body = (await client.get("/stats/search?q=homew", headers=_auth(user.id))).json()
    assert body["albums"] == [
        {"album": "Homework", "artist": "Daft Punk", "count": 3,
         "image_url": "https://img/homework.jpg"},
    ]


async def test_search_orders_by_listens_in_range_then_all_time(api, db_session):
    client, _ = api
    user = await _seed(db_session)
    body = (await client.get(
        "/stats/search?q=daft&since=2026-10-15T00:00:00Z", headers=_auth(user.id)
    )).json()
    assert body["artists"] == [
        {"artist": "Daftside", "count": 1, "image_url": None},
        {"artist": "Daft Punk", "count": 0, "image_url": "https://img/homework.jpg"},
    ]


async def test_search_treats_like_wildcards_literally(api, db_session):
    client, _ = api
    user = await _seed(db_session)
    body = (await client.get("/stats/search", params={"q": "%"}, headers=_auth(user.id))).json()
    assert [a["artist"] for a in body["artists"]] == ["100% Fun"]
    assert [t["track"] for t in body["tracks"]] == ["50%_off"]
    body = (await client.get("/stats/search", params={"q": "_"}, headers=_auth(user.id))).json()
    assert body["artists"] == []
    assert [t["track"] for t in body["tracks"]] == ["50%_off"]


async def test_search_returns_at_most_five_per_kind(api, db_session):
    client, _ = api
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    await upsert_listens(db_session, user.id, [
        _listen(f"Band {i}", f"Song {i}", f"Record {i}", 1 + i) for i in range(7)
    ])
    body = (await client.get("/stats/search?q=band", headers=_auth(user.id))).json()
    assert len(body["artists"]) == 5
    assert len((await client.get("/stats/search?q=song", headers=_auth(user.id))).json()["tracks"]) == 5
    assert len((await client.get("/stats/search?q=record", headers=_auth(user.id))).json()["albums"]) == 5


async def test_blank_query_returns_nothing(api, db_session):
    client, _ = api
    user = await _seed(db_session)
    body = (await client.get("/stats/search", params={"q": "  "}, headers=_auth(user.id))).json()
    assert body == {"artists": [], "albums": [], "tracks": []}


async def test_shared_search_never_leaves_the_share_range(api, db_session):
    client, _ = api
    user = await _seed(db_session)
    share = Share(share_token="T" * 43, user_id=user.id,
                  range_from=datetime(2026, 10, 15, tzinfo=UTC),
                  range_to=datetime(2026, 10, 22, tzinfo=UTC))
    db_session.add(share)
    await db_session.flush()
    base = f"/shared/{share.share_token}/search"

    body = (await client.get(base, params={"q": "daft"})).json()
    assert body["artists"] == [{"artist": "Daftside", "count": 1, "image_url": None}]
    assert (await client.get(base, params={"q": "homework"})).json()["albums"] == []
    assert (await client.get(base, params={"q": "around"})).json()["tracks"] == []
    # 100% Fun was played on the 22nd, the first instant outside the share.
    assert (await client.get(base, params={"q": "fun"})).json()["artists"] == []

    widened = (await client.get(
        base, params={"q": "daft", "since": "2026-01-01T00:00:00Z"}
    )).json()
    assert [a["artist"] for a in widened["artists"]] == ["Daftside"]
