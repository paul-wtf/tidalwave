from datetime import UTC, datetime

from tidalwave.auth.service import upsert_user_from_session
from tidalwave.ingest.repository import upsert_listens
from tidalwave.models.db import AlbumArt
from tidalwave.models.domain import Scrobble
from tidalwave.stats.race import artist_race
from tidalwave.stats.scope import Scope


def _d(*args):
    return datetime(*args, tzinfo=UTC)


def _scope(user, tz="UTC", **kw):
    return Scope(user_id=user.id, tz=tz, since=kw.get("since"), until=kw.get("until"))


async def _user(db_session, plays):
    """plays: (artist, day of June 2024, listens that day)."""
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    await upsert_listens(db_session, user.id, [
        Scrobble(artist=artist, track_title="t", album="LP", played_at=_d(2024, 6, day, 12, i))
        for artist, day, n in plays
        for i in range(n)
    ])
    return user


PLAYS = [
    ("Early", 1, 3), ("Steady", 1, 2), ("Late", 1, 1),
    ("Steady", 2, 2), ("Late", 2, 2),
    ("Late", 4, 4), ("Never", 4, 1),
]


async def test_race_has_the_running_totals_of_every_artist_that_was_ever_in_the_top(db_session):
    user = await _user(db_session, PLAYS)
    result = await artist_race(db_session, _scope(user), bucket="day", limit=2)
    assert result == {
        "bucket": "day",
        "periods": ["2024-06-01T00:00:00", "2024-06-02T00:00:00", "2024-06-04T00:00:00"],
        "artists": [
            {"artist": "Late", "image_url": None, "totals": [1, 3, 7]},
            {"artist": "Steady", "image_url": None, "totals": [2, 4, 4]},
            {"artist": "Early", "image_url": None, "totals": [3, 3, 3]},
        ],
    }


async def test_race_breaks_ties_by_name_like_the_top_list(db_session):
    user = await _user(db_session, [("B", 1, 2), ("A", 1, 2), ("C", 1, 2), ("C", 2, 1)])
    result = await artist_race(db_session, _scope(user), bucket="day", limit=2)
    assert [a["artist"] for a in result["artists"]] == ["C", "A", "B"]
    assert [a["totals"] for a in result["artists"]] == [[2, 3], [2, 2], [2, 2]]


async def test_race_starts_counting_at_the_range_and_carries_covers(db_session):
    user = await _user(db_session, PLAYS)
    db_session.add(AlbumArt(artist="Late", album="LP", image_url="https://img/late.jpg"))
    await db_session.flush()
    result = await artist_race(
        db_session, _scope(user, since=_d(2024, 6, 2), until=_d(2024, 6, 5)), bucket="day", limit=1
    )
    assert result["periods"] == ["2024-06-02T00:00:00", "2024-06-04T00:00:00"]
    assert result["artists"] == [
        {"artist": "Late", "image_url": "https://img/late.jpg", "totals": [2, 6]},
    ]


async def test_race_buckets_in_the_users_timezone_and_by_month(db_session):
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    await upsert_listens(db_session, user.id, [
        Scrobble(artist="A", track_title="t", album=None, played_at=_d(2024, 6, 30, 23, 30)),
        Scrobble(artist="A", track_title="t", album=None, played_at=_d(2024, 7, 15)),
    ])
    berlin = await artist_race(db_session, _scope(user, tz="Europe/Berlin"), bucket="month")
    assert berlin["periods"] == ["2024-07-01T00:00:00"]
    utc = await artist_race(db_session, _scope(user), bucket="month")
    assert utc["periods"] == ["2024-06-01T00:00:00", "2024-07-01T00:00:00"]


async def test_race_picks_the_bucket_from_the_span_when_none_is_given(db_session):
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    await upsert_listens(db_session, user.id, [
        Scrobble(artist="A", track_title="t", album=None, played_at=_d(2024, 1, 1)),
        Scrobble(artist="A", track_title="t", album=None, played_at=_d(2024, 3, 1)),
        Scrobble(artist="A", track_title="t", album=None, played_at=_d(2024, 6, 1)),
    ])
    assert (await artist_race(db_session, _scope(user)))["bucket"] == "month"
    short = _scope(user, since=_d(2024, 1, 1), until=_d(2024, 4, 1))
    assert (await artist_race(db_session, short))["bucket"] == "day"
    open_end = _scope(user, since=_d(2024, 2, 15))
    assert (await artist_race(db_session, open_end))["bucket"] == "month"
    assert (await artist_race(db_session, _scope(user, since=_d(2024, 5, 1))))["bucket"] == "day"


async def test_race_without_listens(db_session):
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    assert await artist_race(db_session, _scope(user)) == {
        "bucket": "day", "periods": [], "artists": [],
    }
