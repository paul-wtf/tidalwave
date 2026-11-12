import csv
import io
import json
from datetime import UTC, datetime

from sqlalchemy import func, select

from tidalwave.auth.service import upsert_user_from_session
from tidalwave.auth.session import COOKIE_NAME, SessionCodec
from tidalwave.ingest.repository import mark_synced, upsert_listens
from tidalwave.models.db import (
    AlbumArt,
    ArtistMerge,
    Listen,
    Share,
    SyncState,
    TrackDuration,
    User,
)
from tidalwave.models.domain import Scrobble


def _auth(user_id: int) -> dict:
    return {"Cookie": f"{COOKIE_NAME}={SessionCodec('test-secret').encode(user_id)}"}


async def _count(db_session, model) -> int:
    return (await db_session.execute(select(func.count()).select_from(model))).scalar_one()


async def _seed(db_session):
    alice = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    bob = await upsert_user_from_session(db_session, "bob", "sk", mode="open", allowlist=[])
    await upsert_listens(db_session, alice.id, [
        Scrobble(artist="Kavinsky", track_title="Nightcall", album="OutRun",
                 played_at=datetime(2026, 10, 2, 20, 15, tzinfo=UTC),
                 track_mbid="11111111-1111-1111-1111-111111111111",
                 artist_mbid="22222222-2222-2222-2222-222222222222",
                 album_mbid="33333333-3333-3333-3333-333333333333"),
        Scrobble(artist='Sigur Rós', track_title='Say "hi", twice', album=None,
                 played_at=datetime(2026, 10, 1, 8, 0, tzinfo=UTC)),
    ])
    await upsert_listens(db_session, bob.id, [
        Scrobble(artist="Bob's band", track_title="private", album=None,
                 played_at=datetime(2026, 10, 3, tzinfo=UTC)),
    ])
    night = (await db_session.execute(
        select(Listen).where(Listen.track_title == "Nightcall")
    )).scalar_one()
    night.duration_sec = 258
    imported = (await db_session.execute(
        select(Listen).where(Listen.track_title == 'Say "hi", twice')
    )).scalar_one()
    imported.artist_raw = "Sigur Ros"
    imported.source = "spotify"
    await db_session.flush()
    return alice, bob


async def test_export_requires_login(api):
    client, _ = api
    assert (await client.get("/auth/export?format=csv")).status_code == 401


async def test_export_rejects_unknown_format(api, db_session):
    client, _ = api
    alice, _ = await _seed(db_session)
    assert (await client.get("/auth/export?format=xml", headers=_auth(alice.id))).status_code == 422


async def test_export_csv_has_every_own_listen_in_time_order(api, db_session):
    client, _ = api
    alice, _ = await _seed(db_session)
    resp = await client.get("/auth/export?format=csv", headers=_auth(alice.id))
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert resp.headers["content-disposition"] == 'attachment; filename="tidalwave-alice.csv"'
    rows = list(csv.reader(io.StringIO(resp.text)))
    assert rows == [
        ["played_at", "artist", "track", "album", "track_mbid", "artist_mbid", "album_mbid",
         "duration_sec", "artist_raw", "source"],
        ["2026-10-01T08:00:00+00:00", "Sigur Rós", 'Say "hi", twice', "", "", "", "", "",
         "Sigur Ros", "spotify"],
        ["2026-10-02T20:15:00+00:00", "Kavinsky", "Nightcall", "OutRun",
         "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222",
         "33333333-3333-3333-3333-333333333333", "258", "Kavinsky", "lastfm"],
    ]


async def test_export_json_has_every_own_listen_in_time_order(api, db_session):
    client, _ = api
    alice, _ = await _seed(db_session)
    resp = await client.get("/auth/export?format=json", headers=_auth(alice.id))
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/json"
    assert resp.headers["content-disposition"] == 'attachment; filename="tidalwave-alice.json"'
    assert json.loads(resp.text)["listens"] == [
        {"played_at": "2026-10-01T08:00:00+00:00", "artist": "Sigur Rós",
         "track": 'Say "hi", twice', "album": None, "track_mbid": None, "artist_mbid": None,
         "album_mbid": None, "duration_sec": None, "artist_raw": "Sigur Ros",
         "source": "spotify"},
        {"played_at": "2026-10-02T20:15:00+00:00", "artist": "Kavinsky", "track": "Nightcall",
         "album": "OutRun", "track_mbid": "11111111-1111-1111-1111-111111111111",
         "artist_mbid": "22222222-2222-2222-2222-222222222222",
         "album_mbid": "33333333-3333-3333-3333-333333333333", "duration_sec": 258,
         "artist_raw": "Kavinsky", "source": "lastfm"},
    ]


async def test_export_of_an_empty_history(api, db_session):
    client, _ = api
    user = await upsert_user_from_session(db_session, "empty", "sk", mode="open", allowlist=[])
    assert json.loads((await client.get("/auth/export?format=json", headers=_auth(user.id))).text) == {
        "listens": [], "merges": [],
    }
    csv_text = (await client.get("/auth/export?format=csv", headers=_auth(user.id))).text
    assert len(csv_text.splitlines()) == 1


async def test_export_spans_more_than_one_batch(api, db_session, monkeypatch):
    from tidalwave.routes import auth as auth_module

    monkeypatch.setattr(auth_module, "EXPORT_BATCH", 2)
    client, _ = api
    user = await upsert_user_from_session(db_session, "many", "sk", mode="open", allowlist=[])
    await upsert_listens(db_session, user.id, [
        Scrobble(artist="A", track_title=f"t{i}", album=None,
                 played_at=datetime(2026, 10, 1, 0, i, tzinfo=UTC))
        for i in range(5)
    ])
    body = json.loads((await client.get("/auth/export?format=json", headers=_auth(user.id))).text)
    assert [row["track"] for row in body["listens"]] == ["t0", "t1", "t2", "t3", "t4"]
    rows = list(csv.reader(io.StringIO(
        (await client.get("/auth/export?format=csv", headers=_auth(user.id))).text
    )))
    assert [row[2] for row in rows[1:]] == ["t0", "t1", "t2", "t3", "t4"]


async def test_delete_account_requires_login(api):
    client, _ = api
    assert (await client.delete("/auth/me")).status_code == 401


async def test_delete_account_removes_everything_of_that_user_only(api, db_session):
    client, _ = api
    alice, bob = await _seed(db_session)
    await mark_synced(db_session, alice.id)
    await mark_synced(db_session, bob.id)
    db_session.add_all([
        Share(share_token="A" * 43, user_id=alice.id),
        Share(share_token="B" * 43, user_id=bob.id),
        AlbumArt(artist="Kavinsky", album="OutRun", image_url="https://img/outrun.jpg"),
        TrackDuration(artist="Kavinsky", track_title="Nightcall", duration_sec=258),
    ])
    await db_session.flush()
    alice_id, bob_id = alice.id, bob.id

    resp = await client.delete("/auth/me", headers=_auth(alice_id))

    assert resp.status_code == 204
    assert f'{COOKIE_NAME}=""' in resp.headers["set-cookie"]
    db_session.expire_all()
    assert [u.lastfm_username for u in (await db_session.execute(select(User))).scalars()] == ["bob"]
    for model in (Listen, Share, SyncState):
        owners = (await db_session.execute(select(model.user_id))).scalars().all()
        assert owners == [bob_id], model.__name__
    assert await _count(db_session, AlbumArt) == 1
    assert await _count(db_session, TrackDuration) == 1

    assert (await client.get("/auth/me", headers=_auth(alice_id))).status_code == 401
    assert (await client.get(f"/shared/{'A' * 43}/summary")).status_code == 404
    assert (await client.get(f"/shared/{'B' * 43}/summary")).status_code == 200


async def _merge(db_session, user, variant: str, canonical: str, at: datetime) -> None:
    db_session.add(ArtistMerge(user_id=user.id, variant=variant, canonical=canonical, created_at=at))
    await db_session.flush()


async def test_export_json_carries_the_merged_spellings(api, db_session):
    client, _ = api
    alice, bob = await _seed(db_session)
    await _merge(db_session, alice, "Sigur Ros", "Sigur Rós", datetime(2026, 10, 5, 9, tzinfo=UTC))
    await _merge(db_session, alice, "Kavinksy", "Kavinsky", datetime(2026, 10, 6, 9, tzinfo=UTC))
    await _merge(db_session, bob, "Bobs band", "Bob's band", datetime(2026, 10, 6, 9, tzinfo=UTC))

    body = json.loads((await client.get("/auth/export?format=json", headers=_auth(alice.id))).text)

    assert list(body) == ["listens", "merges"]
    assert len(body["listens"]) == 2
    assert body["merges"] == [
        {"variant": "Kavinksy", "canonical": "Kavinsky", "merged_at": "2026-10-06T09:00:00+00:00"},
        {"variant": "Sigur Ros", "canonical": "Sigur Rós", "merged_at": "2026-10-05T09:00:00+00:00"},
    ]


async def test_export_csv_of_the_merged_spellings_is_a_file_of_its_own(api, db_session):
    client, _ = api
    alice, bob = await _seed(db_session)
    await _merge(db_session, alice, "Sigur Ros", "Sigur Rós", datetime(2026, 10, 5, 9, tzinfo=UTC))
    await _merge(db_session, bob, "Bobs band", "Bob's band", datetime(2026, 10, 6, 9, tzinfo=UTC))

    resp = await client.get("/auth/export?format=csv&part=merges", headers=_auth(alice.id))

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert resp.headers["content-disposition"] == (
        'attachment; filename="tidalwave-alice-merges.csv"'
    )
    assert list(csv.reader(io.StringIO(resp.text))) == [
        ["variant", "canonical", "merged_at"],
        ["Sigur Ros", "Sigur Rós", "2026-10-05T09:00:00+00:00"],
    ]
    listens = (await client.get("/auth/export?format=csv", headers=_auth(alice.id))).text
    assert listens.splitlines()[0].startswith("played_at,artist,track,")


async def test_the_merges_part_comes_only_as_csv(api, db_session):
    client, _ = api
    alice, _ = await _seed(db_session)
    resp = await client.get("/auth/export?format=json&part=merges", headers=_auth(alice.id))
    assert resp.status_code == 422
