from datetime import UTC, datetime

from sqlalchemy import select, text

from tidalwave.auth.service import upsert_user_from_session
from tidalwave.ingest.repository import upsert_listens
from tidalwave.ingest.tags import fill_missing_artist_tags, pick_genres
from tidalwave.lastfm.client import LastfmError
from tidalwave.models.db import ArtistTags
from tidalwave.models.domain import Scrobble


def test_pick_genres_keeps_weighty_tags_lower_cased_in_order():
    raw = [("Industrial Metal", 100), ("metal", 71), ("industrial", 66), ("rock", 37),
           ("hard rock", 12), ("heavy metal", 10)]
    assert pick_genres("Rammstein", raw) == ["industrial metal", "metal", "industrial", "rock"]


def test_pick_genres_drops_non_genre_tags():
    raw = [("pop", 100), ("female vocalists", 71), ("80s", 52), ("seen live", 50),
           ("Cher", 45), ("favorites", 44), ("1998", 43), ("2010s", 42), ("american", 41),
           ("dance", 40)]
    assert pick_genres("Cher", raw) == ["pop", "dance"]


def test_pick_genres_matches_the_artist_name_loosely():
    assert pick_genres("Daft Punk", [("daftpunk", 100), ("DAFT PUNK", 90), ("house", 80)]) == [
        "house"
    ]


def test_pick_genres_caps_the_list_and_skips_duplicates():
    raw = [("a", 100), ("A", 99), ("b", 98), ("c", 97), ("d", 96), ("e", 95), ("f", 94)]
    assert pick_genres("X", raw) == ["a", "b", "c", "d", "e"]


class FakeTagClient:
    def __init__(self, tags, errors=None):
        self.tags = tags
        self.errors = errors or {}
        self.calls: list[str] = []

    async def get_artist_top_tags(self, artist):
        self.calls.append(artist)
        if artist in self.errors:
            raise self.errors[artist]
        return self.tags.get(artist, [])


async def _seed(db_session, artists):
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    await upsert_listens(db_session, user.id, [
        Scrobble(artist=a, track_title="t", album=None,
                 played_at=datetime.fromtimestamp(i * 10, tz=UTC))
        for i, a in enumerate(artists)
    ])
    return user


async def _rows(db_session):
    rows = (await db_session.execute(select(ArtistTags))).scalars().all()
    return {r.artist: r.tags for r in rows}


async def test_fill_missing_artist_tags_remembers_artists_without_tags(db_session, monkeypatch):
    await _seed(db_session, ["Daft Punk", "Daft Punk", "Nobody"])
    client = FakeTagClient({"Daft Punk": [("electronic", 100), ("House", 53), ("seen live", 30)]})

    assert await fill_missing_artist_tags(db_session, client) == 2
    assert await _rows(db_session) == {"Daft Punk": ["electronic", "house"], "Nobody": []}

    assert await fill_missing_artist_tags(db_session, client) == 0
    assert sorted(client.calls) == ["Daft Punk", "Nobody"]


async def test_fill_missing_artist_tags_respects_the_budget(db_session):
    await _seed(db_session, ["A", "B", "C"])
    client = FakeTagClient({})
    assert await fill_missing_artist_tags(db_session, client, max_artists=2) == 2
    assert len(client.calls) == 2
    assert len(await _rows(db_session)) == 2


async def test_failed_lookup_writes_no_row_and_is_retried(db_session):
    await _seed(db_session, ["A", "B"])
    client = FakeTagClient({"A": [("rock", 100)]}, {"A": LastfmError(11, "Service offline")})

    assert await fill_missing_artist_tags(db_session, client) == 1
    assert await _rows(db_session) == {"B": []}

    client.errors.clear()
    client.calls.clear()
    assert await fill_missing_artist_tags(db_session, client) == 1
    assert client.calls == ["A"]
    assert (await _rows(db_session))["A"] == ["rock"]


async def test_rate_limit_stops_the_run(db_session):
    await _seed(db_session, ["A", "B", "C"])
    client = FakeTagClient({})
    seen: list[str] = []

    async def limited(artist):
        seen.append(artist)
        if len(seen) == 1:
            return [("rock", 100)]
        raise LastfmError(29, "Rate limit exceeded")

    client.get_artist_top_tags = limited  # type: ignore[method-assign]
    assert await fill_missing_artist_tags(db_session, client) == 1
    assert len(seen) == 2
    assert len(await _rows(db_session)) == 1


async def test_budgeted_pick_rotates_past_artists_that_keep_failing(db_session, monkeypatch):
    async def no_sleep(_):
        return None

    monkeypatch.setattr("tidalwave.ingest.tags.asyncio.sleep", no_sleep)
    await _seed(db_session, [*[f"Bad {i}" for i in range(30)], "Good"])

    class Client:
        async def get_artist_top_tags(self, artist):
            if artist.startswith("Bad"):
                raise LastfmError(7, "boom")
            return [("rock", 100)]

    await db_session.execute(text("SELECT setseed(0.42)"))
    for _ in range(300):
        if await fill_missing_artist_tags(db_session, Client(), max_artists=3):
            break
    else:
        raise AssertionError("the good artist was never picked")
