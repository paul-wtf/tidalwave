from datetime import UTC, datetime

from sqlalchemy import select

from tidalwave.auth.service import upsert_user_from_session
from tidalwave.lastfm.client import LastfmError
from tidalwave.ingest.covers import fill_missing_covers
from tidalwave.ingest.repository import upsert_listens
from tidalwave.models.db import AlbumArt
from tidalwave.models.domain import Scrobble


class FakeAlbumClient:
    def __init__(self, covers):
        self.covers = covers
        self.calls: list[tuple[str, str]] = []

    async def get_album_info(self, artist, album):
        self.calls.append((artist, album))
        return self.covers.get((artist, album))


def _sc(artist, album, ts):
    return Scrobble(artist=artist, track_title="t", album=album,
                    played_at=datetime.fromtimestamp(ts, tz=UTC))


async def test_fill_missing_covers_writes_null_rows_and_respects_budget(db_session):
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    await upsert_listens(db_session, user.id, [
        _sc("A", "One", 0),
        _sc("A", "One", 10),
        _sc("B", "Two", 20),
        _sc("C", None, 30),
    ])
    client = FakeAlbumClient({("A", "One"): "https://img/one.jpg"})

    written = await fill_missing_covers(db_session, client)

    assert written == 2
    assert sorted(client.calls) == [("A", "One"), ("B", "Two")]
    rows = (await db_session.execute(select(AlbumArt))).scalars().all()
    assert {(r.artist, r.album): r.image_url for r in rows} == {
        ("A", "One"): "https://img/one.jpg",
        ("B", "Two"): None,
    }

    again = await fill_missing_covers(db_session, client)
    assert again == 0
    assert len(client.calls) == 2

    await upsert_listens(db_session, user.id, [_sc("D", "Three", 40), _sc("E", "Four", 50)])
    limited = await fill_missing_covers(db_session, client, max_albums=1)
    assert limited == 1
    assert len(client.calls) == 3


class FlakyClient:
    def __init__(self, errors):
        self.errors = errors
        self.calls: list[tuple[str, str]] = []

    async def get_album_info(self, artist, album):
        self.calls.append((artist, album))
        err = self.errors.get((artist, album))
        if err is not None:
            raise err
        return "https://img/ok.jpg"


async def _seed(db_session, pairs):
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    await upsert_listens(
        db_session, user.id, [_sc(a, b, i * 10) for i, (a, b) in enumerate(pairs)]
    )


async def test_transient_error_writes_no_row_and_is_retried(db_session):
    await _seed(db_session, [("A", "One"), ("B", "Two")])
    client = FlakyClient({("A", "One"): RuntimeError("boom")})

    assert await fill_missing_covers(db_session, client) == 1
    rows = (await db_session.execute(select(AlbumArt))).scalars().all()
    assert [(r.artist, r.album) for r in rows] == [("B", "Two")]

    client.errors.clear()
    client.calls.clear()
    assert await fill_missing_covers(db_session, client) == 1
    assert client.calls == [("A", "One")]


async def test_lastfm_error_other_than_rate_limit_is_skipped(db_session):
    await _seed(db_session, [("A", "One"), ("B", "Two")])
    client = FlakyClient({("A", "One"): LastfmError(11, "Service offline")})
    client.errors[("A", "One")] = LastfmError(11, "Service offline")

    assert await fill_missing_covers(db_session, client) == 1
    assert len(client.calls) == 2


async def test_rate_limit_stops_the_run(db_session):
    await _seed(db_session, [("A", "One"), ("B", "Two"), ("C", "Three")])
    client = FlakyClient({})
    first = None

    async def limited(artist, album):
        nonlocal first
        client.calls.append((artist, album))
        if first is None:
            first = (artist, album)
            return "https://img/ok.jpg"
        raise LastfmError(29, "Rate limit exceeded")

    client.get_album_info = limited  # type: ignore[method-assign]
    assert await fill_missing_covers(db_session, client) == 1
    assert len(client.calls) == 2
    assert len((await db_session.execute(select(AlbumArt))).scalars().all()) == 1


async def test_budgeted_pick_rotates_past_albums_that_keep_failing(db_session, monkeypatch):
    async def no_sleep(_):
        return None

    monkeypatch.setattr("tidalwave.ingest.covers.asyncio.sleep", no_sleep)
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    await upsert_listens(db_session, user.id, [
        *[_sc("Bad", f"Broken {i}", i) for i in range(30)],
        _sc("Good", "Fine", 100),
    ])

    class Client:
        async def get_album_info(self, artist, album):
            if artist == "Bad":
                raise LastfmError(7, "boom")
            return "https://img/fine.jpg"

    for _ in range(300):
        if await fill_missing_covers(db_session, Client(), max_albums=3):
            break
    else:
        raise AssertionError("the good album was never picked")
