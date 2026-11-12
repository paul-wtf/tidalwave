from datetime import UTC, datetime

import httpx
from sqlalchemy import select, text

from tidalwave.auth.service import upsert_user_from_session
from tidalwave.ingest.repository import upsert_listens
from tidalwave.ingest.years import fill_missing_album_years
from tidalwave.models.db import AlbumYear
from tidalwave.models.domain import Scrobble
from tidalwave.musicbrainz.client import MusicBrainzRateLimited


class FakeMusicBrainz:
    def __init__(self, releases=None, tracks=None, errors=None):
        self.releases = releases or {}
        self.tracks = tracks or {}
        self.errors = errors or {}
        self.calls: list[tuple[str, str]] = []

    async def release_year(self, mbid):
        self.calls.append(("release", mbid))
        if mbid in self.errors:
            raise self.errors[mbid]
        return self.releases.get(mbid)

    async def track_release_year(self, mbid):
        self.calls.append(("track", mbid))
        if mbid in self.errors:
            raise self.errors[mbid]
        return self.tracks.get(mbid)


def _sc(artist, album, ts, *, album_mbid=None, track_mbid=None, title="t"):
    return Scrobble(artist=artist, track_title=title, album=album,
                    played_at=datetime.fromtimestamp(ts, tz=UTC),
                    album_mbid=album_mbid, track_mbid=track_mbid)


async def _seed(db_session, scrobbles):
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    await upsert_listens(db_session, user.id, scrobbles)
    return user


async def _rows(db_session):
    rows = (await db_session.execute(select(AlbumYear))).scalars().all()
    return {(r.artist, r.album): r.year for r in rows}


async def test_years_come_from_the_album_id_and_unknown_ones_are_remembered(db_session):
    await _seed(db_session, [
        _sc("A", "One", 0, album_mbid="rel-1"),
        _sc("A", "One", 10, album_mbid="rel-1"),
        _sc("B", "Two", 20, album_mbid="rel-2"),
        _sc("C", "No ids", 30),
        _sc("D", None, 40, track_mbid="trk-0"),
    ])
    client = FakeMusicBrainz(releases={"rel-1": 1998})

    assert await fill_missing_album_years(db_session, client) == 2
    assert await _rows(db_session) == {("A", "One"): 1998, ("B", "Two"): None}
    assert sorted(client.calls) == [("release", "rel-1"), ("release", "rel-2")]

    assert await fill_missing_album_years(db_session, client) == 0
    assert len(client.calls) == 2


async def test_the_most_frequent_album_id_is_asked(db_session):
    await _seed(db_session, [
        _sc("A", "One", 0, album_mbid="rare"),
        _sc("A", "One", 10, album_mbid="common"),
        _sc("A", "One", 20, album_mbid="common"),
        _sc("A", "One", 30),
    ])
    client = FakeMusicBrainz(releases={"common": 2001, "rare": 1990})
    await fill_missing_album_years(db_session, client)
    assert client.calls == [("release", "common")]
    assert await _rows(db_session) == {("A", "One"): 2001}


async def test_track_id_is_the_fallback(db_session):
    await _seed(db_session, [
        _sc("A", "Only track ids", 0, track_mbid="trk-1"),
        _sc("B", "Unknown release", 10, album_mbid="rel-x", track_mbid="trk-2"),
        _sc("C", "Nothing found", 20, album_mbid="rel-y", track_mbid="trk-3"),
    ])
    client = FakeMusicBrainz(tracks={"trk-1": 1977, "trk-2": 2011})

    assert await fill_missing_album_years(db_session, client) == 3
    assert await _rows(db_session) == {
        ("A", "Only track ids"): 1977, ("B", "Unknown release"): 2011, ("C", "Nothing found"): None,
    }
    assert ("release", "trk-1") not in client.calls


async def test_budget_limits_the_albums_per_run(db_session):
    await _seed(db_session, [_sc(f"A{i}", "Album", i, album_mbid=f"rel-{i}") for i in range(4)])
    client = FakeMusicBrainz()
    assert await fill_missing_album_years(db_session, client, max_albums=3) == 3
    assert len(await _rows(db_session)) == 3
    assert await fill_missing_album_years(db_session, client, max_albums=0) == 0


async def test_failed_lookup_writes_no_row_and_is_retried(db_session):
    await _seed(db_session, [
        _sc("A", "One", 0, album_mbid="rel-1"), _sc("B", "Two", 10, album_mbid="rel-2"),
    ])
    client = FakeMusicBrainz(
        releases={"rel-1": 1998, "rel-2": 2004}, errors={"rel-1": httpx.ConnectError("down")}
    )

    assert await fill_missing_album_years(db_session, client) == 1
    assert await _rows(db_session) == {("B", "Two"): 2004}

    client.errors.clear()
    assert await fill_missing_album_years(db_session, client) == 1
    assert (await _rows(db_session))[("A", "One")] == 1998


async def test_rate_limiting_stops_the_run(db_session):
    await _seed(db_session, [_sc(f"A{i}", "Album", i, album_mbid=f"rel-{i}") for i in range(3)])
    client = FakeMusicBrainz(errors={f"rel-{i}": MusicBrainzRateLimited() for i in range(3)})
    assert await fill_missing_album_years(db_session, client) == 0
    assert len(client.calls) == 1
    assert await _rows(db_session) == {}


async def test_budgeted_pick_rotates_past_albums_that_keep_failing(db_session):
    await _seed(db_session, [
        *[_sc("Bad", f"Broken {i}", i, album_mbid=f"bad-{i}") for i in range(30)],
        _sc("Good", "Fine", 100, album_mbid="good"),
    ])
    client = FakeMusicBrainz(
        releases={"good": 1999},
        errors={f"bad-{i}": httpx.ConnectError("down") for i in range(30)},
    )
    await db_session.execute(text("SELECT setseed(0.42)"))
    for _ in range(300):
        if await fill_missing_album_years(db_session, client, max_albums=3):
            break
    else:
        raise AssertionError("the good album was never picked")
