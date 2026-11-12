from datetime import UTC, datetime

from tidalwave.auth.service import upsert_user_from_session
from tidalwave.ingest.repository import upsert_listens
from tidalwave.models.db import AlbumYear
from tidalwave.models.domain import Scrobble
from tidalwave.stats.decades import decades
from tidalwave.stats.scope import Scope


def _d(*args):
    return datetime(*args, tzinfo=UTC)


def _scope(user, **kw):
    return Scope(user_id=user.id, tz="UTC", since=kw.get("since"), until=kw.get("until"))


async def _seed(db_session):
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    other = await upsert_user_from_session(db_session, "bob", "sk2", mode="open", allowlist=[])
    rows = [
        ("Bonnie Raitt", "Streetlights", _d(2024, 6, 1), None),
        ("Bonnie Raitt", "Streetlights", _d(2024, 6, 2), None),
        ("Morcheeba", "Big Calm", _d(2024, 6, 3), None),
        ("Aphex Twin", "Drukqs", _d(2024, 6, 4), None),
        ("Asked", "No date", _d(2024, 6, 5), "rel-asked"),
        ("Waiting", "Has an id", _d(2024, 6, 6), "rel-waiting"),
        ("Plain", "No id", _d(2024, 6, 7), None),
        ("Single", None, _d(2024, 6, 8), None),
        ("Morcheeba", "Big Calm", _d(2023, 1, 1), None),
    ]
    await upsert_listens(db_session, user.id, [
        Scrobble(artist=a, track_title="t", album=al, played_at=when, album_mbid=mbid)
        for a, al, when, mbid in rows
    ])
    await upsert_listens(db_session, other.id, [
        Scrobble(artist="Morcheeba", track_title="t", album="Big Calm", played_at=_d(2024, 6, 1)),
    ])
    db_session.add_all([
        AlbumYear(artist="Bonnie Raitt", album="Streetlights", year=1974),
        AlbumYear(artist="Morcheeba", album="Big Calm", year=1998),
        AlbumYear(artist="Aphex Twin", album="Drukqs", year=2001),
        AlbumYear(artist="Asked", album="No date", year=None),
    ])
    await db_session.flush()
    return user


async def test_decades_count_listens_by_release_decade_without_gaps(db_session):
    user = await _seed(db_session)
    result = await decades(db_session, _scope(user, since=_d(2024, 6, 1), until=_d(2024, 7, 1)))
    assert result == {
        "decades": [
            {"decade": 1970, "listens": 2},
            {"decade": 1980, "listens": 0},
            {"decade": 1990, "listens": 1},
            {"decade": 2000, "listens": 1},
        ],
        "known": 4,
        "unknown": 4,
        "pending": 1,
    }


async def test_decades_follow_the_range(db_session):
    user = await _seed(db_session)
    result = await decades(db_session, _scope(user, since=_d(2023, 1, 1), until=_d(2023, 2, 1)))
    assert result == {
        "decades": [{"decade": 1990, "listens": 1}], "known": 1, "unknown": 0, "pending": 0,
    }


async def test_decades_without_listens(db_session):
    user = await _seed(db_session)
    result = await decades(db_session, _scope(user, since=_d(2020, 1, 1), until=_d(2020, 2, 1)))
    assert result == {"decades": [], "known": 0, "unknown": 0, "pending": 0}
