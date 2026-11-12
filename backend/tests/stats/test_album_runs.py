from datetime import UTC, datetime, timedelta

from sqlalchemy import update

from tidalwave.auth.service import upsert_user_from_session
from tidalwave.ingest.repository import upsert_listens
from tidalwave.models.db import AlbumArt, Listen
from tidalwave.models.domain import Scrobble
from tidalwave.stats.album_runs import RUN_MAX_GAP, RUN_MIN_TRACKS, album_runs
from tidalwave.stats.scope import Scope

START = datetime(2024, 6, 1, 20, tzinfo=UTC)


def _scope(user, **kw):
    return Scope(user_id=user.id, tz="UTC", since=kw.get("since"), until=kw.get("until"))


def _play(artist, album, start, tracks, *, every=timedelta(minutes=4), prefix="t"):
    names = tracks if isinstance(tracks, list) else [f"{prefix}{i}" for i in range(tracks)]
    return [
        Scrobble(artist=artist, track_title=name, album=album, played_at=start + i * every)
        for i, name in enumerate(names)
    ]


async def _user(db_session, listens):
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    await upsert_listens(db_session, user.id, listens)
    return user


def test_the_heuristic_is_six_tracks_and_ten_minutes():
    assert (RUN_MIN_TRACKS, RUN_MAX_GAP) == (6, timedelta(minutes=10))


async def test_six_different_tracks_in_a_row_are_a_run_and_five_are_not(db_session):
    user = await _user(db_session, [
        *_play("Daft Punk", "Discovery", START, 6),
        *_play("Kavinsky", "OutRun", START + timedelta(days=1), 5),
    ])
    await db_session.execute(update(Listen).where(Listen.artist == "Daft Punk").values(duration_sec=200))
    db_session.add(AlbumArt(artist="Daft Punk", album="Discovery", image_url="https://img/d.jpg"))
    await db_session.flush()

    assert await album_runs(db_session, _scope(user)) == {
        "total": 1,
        "runs": [{
            "artist": "Daft Punk", "album": "Discovery", "started_at": START.isoformat(),
            "tracks": 6, "listens": 6, "seconds": 1200, "image_url": "https://img/d.jpg",
        }],
    }


async def test_a_repeated_track_does_not_count_twice(db_session):
    user = await _user(db_session, _play("A", "Album", START, ["a", "b", "c", "d", "e", "a2"]))
    await db_session.execute(update(Listen).where(Listen.track_title == "a2").values(track_title="a"))
    assert (await album_runs(db_session, _scope(user)))["total"] == 0


async def test_a_pause_of_more_than_ten_minutes_ends_the_run(db_session):
    first = _play("A", "Album", START, 3)
    exact = _play("A", "Album", START + timedelta(minutes=18), 3, prefix="u")
    late = _play("B", "Other", START + timedelta(days=1), 3)
    later = _play("B", "Other", START + timedelta(days=1, minutes=18, seconds=1), 3, prefix="u")
    user = await _user(db_session, [*first, *exact, *late, *later])
    result = await album_runs(db_session, _scope(user))
    assert [(r["album"], r["tracks"]) for r in result["runs"]] == [("Album", 6)]


async def test_the_pause_is_measured_from_the_end_of_the_previous_track(db_session):
    user = await _user(db_session, [
        *_play("Long", "Epics", START, 6, every=timedelta(minutes=15)),
        *_play("Unknown", "Lengths", START + timedelta(days=1), 6, every=timedelta(minutes=15)),
    ])
    await db_session.execute(update(Listen).where(Listen.artist == "Long").values(duration_sec=900))
    result = await album_runs(db_session, _scope(user))
    assert [r["album"] for r in result["runs"]] == ["Epics"]


async def test_another_album_in_between_ends_the_run(db_session):
    user = await _user(db_session, [
        *_play("A", "Album", START, 3),
        Scrobble(artist="B", track_title="x", album="Else", played_at=START + timedelta(minutes=12)),
        *_play("A", "Album", START + timedelta(minutes=16), 3, prefix="u"),
        *_play("C", "Same name", START + timedelta(days=1), 3),
        *_play("D", "Same name", START + timedelta(days=1, minutes=12), 3, prefix="u"),
        *_play("E", None, START + timedelta(days=2), 8),
    ])
    assert await album_runs(db_session, _scope(user)) == {"total": 0, "runs": []}


async def test_runs_come_newest_first_with_limit_filter_and_range(db_session):
    user = await _user(db_session, [
        *_play("A", "One", START, 6),
        *_play("A", "One", START + timedelta(days=2), 7),
        *_play("B", "Two", START + timedelta(days=4), 6),
    ])
    other = await upsert_user_from_session(db_session, "bob", "sk2", mode="open", allowlist=[])
    await upsert_listens(db_session, other.id, _play("Z", "Theirs", START, 6))

    everything = await album_runs(db_session, _scope(user))
    assert [(r["album"], r["tracks"]) for r in everything["runs"]] == [("Two", 6), ("One", 7), ("One", 6)]
    limited = await album_runs(db_session, _scope(user), limit=1)
    assert (limited["total"], [r["album"] for r in limited["runs"]]) == (3, ["Two"])
    one = await album_runs(db_session, _scope(user), artist="A", album="One")
    assert (one["total"], [r["tracks"] for r in one["runs"]]) == (2, [7, 6])
    ranged = await album_runs(
        db_session, _scope(user, since=START + timedelta(days=1), until=START + timedelta(days=3))
    )
    assert [(r["album"], r["tracks"]) for r in ranged["runs"]] == [("One", 7)]
    cut = await album_runs(db_session, _scope(user, since=START + timedelta(minutes=6)))
    assert [r["tracks"] for r in cut["runs"]] == [6, 7]
