from datetime import UTC, datetime

from tidalwave.auth.service import upsert_user_from_session
from tidalwave.ingest.repository import upsert_listens
from tidalwave.models.db import AlbumArt
from tidalwave.models.domain import Scrobble
from tidalwave.stats.queries import (
    listening_clock,
    recent_listens,
    listening_weekday,
    listens_over_time,
    metrics_over_time,
    summary_stats,
    top_albums,
    top_artists,
    top_tracks,
    total_listens,
)
from tidalwave.stats.scope import Scope


def _scope(user):
    return Scope(user_id=user.id, tz="UTC", since=None, until=None)


def _sc(artist, title, ts):
    return Scrobble(artist=artist, track_title=title, album=None,
                    played_at=datetime.fromtimestamp(ts, tz=UTC))


async def _seed(db_session):
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    # 2 Daft Punk, 1 Kavinsky; timestamps at hour 0 UTC (ts multiples of 86400)
    await upsert_listens(db_session, user.id, [
        _sc("Daft Punk", "a", 0),
        _sc("Daft Punk", "b", 86400),
        _sc("Kavinsky", "c", 172800),
    ])
    return user


async def test_top_artists_ranks_by_count(db_session):
    user = await _seed(db_session)
    rows = await top_artists(db_session, _scope(user), limit=10)
    assert rows[0] == {"artist": "Daft Punk", "count": 2, "image_url": None}
    assert rows[1] == {"artist": "Kavinsky", "count": 1, "image_url": None}


async def test_top_tracks_includes_artist(db_session):
    user = await _seed(db_session)
    rows = await top_tracks(db_session, _scope(user), limit=10)
    # Each track row carries its artist so the UI can build platform links.
    assert {"track", "artist", "count"} == set(rows[0].keys())
    assert {"Daft Punk"} == {r["artist"] for r in rows if r["track"] in {"a", "b"}}
    assert all(r["count"] == 1 for r in rows)


async def test_total_listens(db_session):
    user = await _seed(db_session)
    assert await total_listens(db_session, _scope(user)) == 3


async def test_summary_stats_counts_distinct(db_session):
    user = await _seed(db_session)  # 2 Daft Punk + 1 Kavinsky, tracks a/b/c, no albums
    stats = await summary_stats(db_session, _scope(user))
    assert stats["total_listens"] == 3
    assert stats["distinct_artists"] == 2
    assert stats["distinct_tracks"] == 3
    assert stats["distinct_albums"] == 0  # all albums NULL
    assert stats["total_seconds"] == 0  # no durations resolved


async def test_metrics_over_time_per_day(db_session):
    user = await upsert_user_from_session(db_session, "metrics", "sk", mode="open", allowlist=[])
    day1 = datetime(2024, 3, 10, 8, tzinfo=UTC)
    day2 = datetime(2024, 3, 12, 20, tzinfo=UTC)
    await upsert_listens(db_session, user.id, [
        Scrobble(artist="X", track_title="t1", album=None, played_at=day1),
        Scrobble(artist="Y", track_title="t2", album=None, played_at=day1),
        Scrobble(artist="X", track_title="t3", album=None, played_at=day2),
    ])
    rows = await metrics_over_time(db_session, _scope(user), bucket="day")
    assert len(rows) == 2
    assert {"period", "listens", "artists", "albums", "seconds"} <= rows[0].keys()
    assert rows[0]["listens"] == 2
    assert rows[0]["artists"] == 2  # X + Y on day1
    assert rows[1]["listens"] == 1
    assert rows[0]["period"] < rows[1]["period"]


async def test_listening_clock_buckets_by_hour(db_session):
    user = await _seed(db_session)
    clock = await listening_clock(db_session, _scope(user))
    assert clock[0] == 3  # all three at UTC hour 0
    assert len(clock) == 24


async def test_top_artists_isolated_per_user(db_session):
    await _seed(db_session)
    bob = await upsert_user_from_session(db_session, "bob", "sk", mode="open", allowlist=[])
    assert await top_artists(db_session, _scope(bob), limit=10) == []


async def test_listening_weekday_buckets_by_iso_weekday(db_session):
    user = await upsert_user_from_session(db_session, "carol", "sk2", mode="open", allowlist=[])
    monday = datetime(2024, 6, 17, 12, tzinfo=UTC)    # 2024-06-17 is a Monday
    wednesday = datetime(2024, 6, 19, 9, tzinfo=UTC)  # Wednesday
    await upsert_listens(db_session, user.id, [
        Scrobble(artist="A", track_title="mon1", album=None, played_at=monday),
        Scrobble(artist="A", track_title="mon2", album=None, played_at=monday),
        Scrobble(artist="A", track_title="wed1", album=None, played_at=wednesday),
    ])
    result = await listening_weekday(db_session, _scope(user))
    assert len(result) == 7
    assert result[0] == 2  # Monday (isodow 1 → index 0)
    assert result[2] == 1  # Wednesday (isodow 3 → index 2)
    assert sum(result) == 3


async def test_listens_over_time_buckets_by_day(db_session):
    user = await upsert_user_from_session(db_session, "dave", "sk3", mode="open", allowlist=[])
    day1 = datetime(2024, 3, 10, 8, tzinfo=UTC)
    day2 = datetime(2024, 3, 12, 20, tzinfo=UTC)
    await upsert_listens(db_session, user.id, [
        Scrobble(artist="X", track_title="t1", album=None, played_at=day1),
        Scrobble(artist="X", track_title="t2", album=None, played_at=day1),
        Scrobble(artist="X", track_title="t3", album=None, played_at=day2),
    ])
    result = await listens_over_time(db_session, _scope(user), bucket="day")
    assert len(result) == 2
    assert {"period", "count"} <= result[0].keys()
    assert result[0]["count"] == 2
    assert result[1]["count"] == 1
    # chronological order: day1 before day2
    assert result[0]["period"] < result[1]["period"]


def _alb(artist, title, album, ts):
    return Scrobble(artist=artist, track_title=title, album=album,
                    played_at=datetime.fromtimestamp(ts, tz=UTC))


async def _seed_greatest_hits(db_session):
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    await upsert_listens(db_session, user.id, [
        _alb("A", "x", "Greatest Hits", 0),
        _alb("A", "y", "Greatest Hits", 86400),
        _alb("B", "z", "Greatest Hits", 172800),
    ])
    return user


async def test_top_albums_split_same_name_by_artist(db_session):
    user = await _seed_greatest_hits(db_session)
    rows = await top_albums(db_session, _scope(user), limit=10)
    assert rows == [
        {"album": "Greatest Hits", "artist": "A", "count": 2, "image_url": None},
        {"album": "Greatest Hits", "artist": "B", "count": 1, "image_url": None},
    ]


async def test_distinct_albums_counts_artist_album_pairs(db_session):
    user = await _seed_greatest_hits(db_session)
    await upsert_listens(db_session, user.id, [_alb("C", "n", None, 259200)])
    stats = await summary_stats(db_session, _scope(user))
    assert stats["distinct_albums"] == 2
    buckets = await metrics_over_time(db_session, _scope(user), bucket="month")
    assert sum(b["albums"] for b in buckets) == 2


async def test_unknown_album_rows_split_by_artist(db_session):
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    await upsert_listens(db_session, user.id, [
        _alb("A", "x", None, 0),
        _alb("A", "y", None, 86400),
        _alb("B", "z", None, 172800),
    ])
    rows = await top_albums(db_session, _scope(user), limit=10)
    assert rows == [
        {"album": None, "artist": "A", "count": 2, "image_url": None},
        {"album": None, "artist": "B", "count": 1, "image_url": None},
    ]


def _scope_range(user, since, until):
    return Scope(user_id=user.id, tz="UTC", since=since, until=until)


async def _covers(db_session, *rows):
    db_session.add_all([AlbumArt(artist=a, album=b, image_url=u) for a, b, u in rows])
    await db_session.flush()


async def test_top_albums_carry_cover(db_session):
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    await upsert_listens(db_session, user.id, [
        _alb("A", "x", "One", 0), _alb("A", "y", "Two", 86400),
    ])
    await _covers(db_session, ("A", "One", "https://img/one.jpg"))
    rows = await top_albums(db_session, _scope(user), limit=10)
    assert {r["album"]: r["image_url"] for r in rows} == {
        "One": "https://img/one.jpg",
        "Two": None,
    }


async def test_top_artist_cover_is_most_listened_album_in_scope(db_session):
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    await upsert_listens(db_session, user.id, [
        _alb("A", "x1", "X", 0), _alb("A", "x2", "X", 86400), _alb("A", "x3", "X", 172800),
        _alb("A", "y1", "Y", 259200), _alb("A", "y2", "Y", 345600),
    ])
    await _covers(db_session, ("A", "X", "https://img/x.jpg"), ("A", "Y", "https://img/y.jpg"))
    overall = await top_artists(db_session, _scope(user), limit=10)
    assert overall == [{"artist": "A", "count": 5, "image_url": "https://img/x.jpg"}]
    ranged = await top_artists(
        db_session, _scope_range(user, datetime.fromtimestamp(259200, tz=UTC), None), limit=10
    )
    assert ranged == [{"artist": "A", "count": 2, "image_url": "https://img/y.jpg"}]


async def test_top_artist_cover_tie_breaks_by_album_name(db_session):
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    await upsert_listens(db_session, user.id, [_alb("A", "b", "Beta", 0), _alb("A", "a", "Alpha", 86400)])
    await _covers(db_session, ("A", "Alpha", "https://img/alpha.jpg"), ("A", "Beta", "https://img/beta.jpg"))
    rows = await top_artists(db_session, _scope(user), limit=10)
    assert rows[0]["image_url"] == "https://img/alpha.jpg"


async def test_recent_listens_carry_cover(db_session):
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    await upsert_listens(db_session, user.id, [
        _alb("A", "x", "One", 0), _alb("B", "y", None, 86400),
    ])
    await _covers(db_session, ("A", "One", "https://img/one.jpg"))
    rows = await recent_listens(db_session, _scope(user))
    assert [(r["track"], r["image_url"]) for r in rows] == [("y", None), ("x", "https://img/one.jpg")]


async def test_missing_cover_is_null(db_session):
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    await upsert_listens(db_session, user.id, [_alb("A", "x", "One", 0)])
    await _covers(db_session, ("A", "One", None))
    assert (await top_artists(db_session, _scope(user)))[0]["image_url"] is None
    assert (await top_albums(db_session, _scope(user)))[0]["image_url"] is None
    assert (await recent_listens(db_session, _scope(user)))[0]["image_url"] is None


async def test_recent_listens_carry_the_owner_offset(db_session):
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    await upsert_listens(db_session, user.id, [
        Scrobble(artist="A", track_title="t", album=None,
                 played_at=datetime(2024, 7, 10, 23, 30, tzinfo=UTC)),
    ])
    scope = Scope(user_id=user.id, tz="Europe/Berlin", since=None, until=None)
    assert (await recent_listens(db_session, scope))[0]["played_at"] == "2024-07-11T01:30:00+02:00"
