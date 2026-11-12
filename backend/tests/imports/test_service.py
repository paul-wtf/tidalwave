import json
import shutil
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from import_samples import SPOTIFY, listenbrainz_zip, spotify_zip
from sqlalchemy import select, update

from tidalwave.auth.service import upsert_user_from_session
from tidalwave.imports.service import (
    ImportBusy,
    run_import,
    source_summary,
    start_import,
    undo_import,
)
from tidalwave.ingest.repository import upsert_listens
from tidalwave.models.db import Import, Listen, TrackDuration
from tidalwave.models.domain import Scrobble
from tidalwave.spellings.service import merge_spellings
from tidalwave.stats.scope import Scope

LIMIT = 10_000_000


@pytest.fixture
def factory(db_session):
    @asynccontextmanager
    async def same():
        yield db_session

    return same


async def _user(session, name="alice"):
    return await upsert_user_from_session(session, name, f"sk-{name}", mode="open", allowlist=[])


def _copy(src: Path, tmp_path: Path) -> Path:
    dst = tmp_path / f"upload-{len(list(tmp_path.iterdir()))}"
    shutil.copy(src, dst)
    return dst


async def _run(session, factory, user, path: Path, name="history.json") -> Import:
    started = await start_import(session, user.id, name)
    await run_import(factory, started.id, path, max_bytes=LIMIT)
    imp = await session.get(Import, started.id)
    await session.refresh(imp)
    return imp


def _counts(imp: Import) -> dict:
    return {
        "read": imp.read, "skipped": imp.skipped, "too_short": imp.too_short,
        "duplicates": imp.duplicates, "added": imp.added,
    }


async def _listens(session, user_id):
    rows = await session.execute(
        select(Listen).where(Listen.user_id == user_id).order_by(Listen.played_at)
    )
    return rows.scalars().all()


async def test_a_spotify_history_adds_the_plays_last_fm_would_have_scrobbled(
    db_session, factory, tmp_path
):
    user = await _user(db_session)

    imp = await _run(db_session, factory, user, _copy(SPOTIFY, tmp_path))

    assert imp.status == "done"
    assert imp.source == "spotify"
    assert _counts(imp) == {
        "read": 8, "skipped": 3, "too_short": 1, "duplicates": 0, "added": 4,
    }
    listens = await _listens(db_session, user.id)
    assert [(listen.artist, listen.track_title) for listen in listens] == [
        ("The National", "Fake Empire"),
        ("National", "Mistaken for Strangers"),
        ("Kavinsky", "Nightcall"),
        ("Kavinsky", "Nightcall"),
    ]
    assert {(listen.source, listen.import_id) for listen in listens} == {("spotify", imp.id)}
    assert imp.first_played_at == datetime(2021, 4, 15, 18, 0, tzinfo=UTC)
    assert imp.last_played_at == datetime(2021, 4, 16, 8, 5, 42, tzinfo=UTC)
    assert imp.finished_at is not None


async def test_the_uploaded_file_is_removed_afterwards(db_session, factory, tmp_path):
    user = await _user(db_session)
    path = _copy(SPOTIFY, tmp_path)

    await _run(db_session, factory, user, path)

    assert not path.exists()


async def test_a_known_track_length_applies_the_half_or_four_minutes_rule(
    db_session, factory, tmp_path
):
    user = await _user(db_session)
    db_session.add(TrackDuration(artist="Kavinsky", track_title="Nightcall", duration_sec=258))
    await db_session.flush()

    imp = await _run(db_session, factory, user, _copy(SPOTIFY, tmp_path))

    assert (imp.too_short, imp.added) == (2, 3)
    nightcall = [x for x in await _listens(db_session, user.id) if x.track_title == "Nightcall"]
    assert [x.duration_sec for x in nightcall] == [258]


async def test_importing_the_same_file_again_adds_nothing(db_session, factory, tmp_path):
    user = await _user(db_session)
    await _run(db_session, factory, user, _copy(SPOTIFY, tmp_path))

    again = await _run(db_session, factory, user, _copy(SPOTIFY, tmp_path))

    assert (again.added, again.duplicates) == (0, 4)
    assert len(await _listens(db_session, user.id)) == 4


async def test_a_zip_imports_like_the_file_inside(db_session, factory, tmp_path):
    user = await _user(db_session)
    await _run(db_session, factory, user, _copy(SPOTIFY, tmp_path))

    again = await _run(db_session, factory, user, spotify_zip(tmp_path), "my_spotify_data.zip")

    assert again.status == "done"
    assert (again.read, again.added, again.duplicates) == (8, 0, 4)


async def test_a_play_last_fm_already_has_counts_as_a_duplicate(db_session, factory, tmp_path):
    user = await _user(db_session)
    await upsert_listens(db_session, user.id, [
        Scrobble(artist="The National", track_title="Fake Empire", album="Boxer",
                 played_at=datetime(2021, 4, 15, 18, 1, 10, tzinfo=UTC)),
        Scrobble(artist="The National", track_title="Mistaken For Strangers", album="Boxer",
                 played_at=datetime(2021, 4, 15, 18, 3, 0, tzinfo=UTC)),
    ])

    imp = await _run(db_session, factory, user, _copy(SPOTIFY, tmp_path))

    assert (imp.duplicates, imp.added) == (2, 2)
    sources = [x.source for x in await _listens(db_session, user.id)]
    assert sources == ["lastfm", "lastfm", "spotify", "spotify"]


def _spotify_entry(track: str, artist: str, ended: datetime, ms: int) -> dict:
    return {
        "ts": ended.strftime("%Y-%m-%dT%H:%M:%SZ"), "ms_played": ms,
        "master_metadata_track_name": track, "master_metadata_album_artist_name": artist,
        "master_metadata_album_album_name": None, "spotify_track_uri": "spotify:track:x",
        "episode_name": None, "incognito_mode": False,
    }


async def test_one_last_fm_listen_absorbs_only_one_imported_play(db_session, factory, tmp_path):
    user = await _user(db_session)
    start = datetime(2022, 5, 1, 20, 0, tzinfo=UTC)
    await upsert_listens(db_session, user.id, [
        Scrobble(artist="Kavinsky", track_title="Nightcall", album=None,
                 played_at=start + timedelta(minutes=4, seconds=30)),
    ])
    path = tmp_path / "repeat.json"
    path.write_text(json.dumps([
        _spotify_entry("Nightcall", "Kavinsky", start + timedelta(minutes=4), 240_000),
        _spotify_entry("Nightcall", "Kavinsky", start + timedelta(minutes=8, seconds=20), 250_000),
    ]))

    imp = await _run(db_session, factory, user, path)

    assert (imp.duplicates, imp.added) == (1, 1)
    assert len(await _listens(db_session, user.id)) == 2


async def test_a_play_outside_the_window_is_not_a_duplicate(db_session, factory, tmp_path):
    user = await _user(db_session)
    start = datetime(2022, 5, 1, 20, 0, tzinfo=UTC)
    await upsert_listens(db_session, user.id, [
        Scrobble(artist="Kavinsky", track_title="Nightcall", album=None,
                 played_at=start + timedelta(minutes=11)),
    ])
    path = tmp_path / "far.json"
    path.write_text(json.dumps([_spotify_entry("Nightcall", "Kavinsky", start + timedelta(minutes=4), 240_000)]))

    imp = await _run(db_session, factory, user, path)

    assert (imp.duplicates, imp.added) == (0, 1)


async def test_plays_of_another_user_are_no_duplicates(db_session, factory, tmp_path):
    alice = await _user(db_session, "alice")
    bob = await _user(db_session, "bob")
    await _run(db_session, factory, bob, _copy(SPOTIFY, tmp_path))

    imp = await _run(db_session, factory, alice, _copy(SPOTIFY, tmp_path))

    assert imp.added == 4


async def test_merged_spellings_apply_to_imported_plays(db_session, factory, tmp_path):
    user = await _user(db_session)
    await merge_spellings(db_session, user.id, "The National", ["National"])

    await _run(db_session, factory, user, _copy(SPOTIFY, tmp_path))

    rows = [(x.artist, x.artist_raw) for x in await _listens(db_session, user.id)][:2]
    assert rows == [("The National", "The National"), ("The National", "National")]


async def test_a_listenbrainz_export_is_imported(db_session, factory, tmp_path):
    user = await _user(db_session)

    imp = await _run(db_session, factory, user, listenbrainz_zip(tmp_path), "lb.zip")

    assert imp.status == "done"
    assert imp.source == "listenbrainz"
    assert _counts(imp) == {
        "read": 6, "skipped": 1, "too_short": 2, "duplicates": 0, "added": 3,
    }
    listens = await _listens(db_session, user.id)
    assert [(x.artist, x.duration_sec, x.track_mbid) for x in listens] == [
        ("Röyksopp", 402, "30d08f4c-d825-4ae1-b79c-44242cddd7c0"),
        ("Sigur Ros", 375, None),
        ("The National", None, None),
    ]


async def test_a_broken_file_fails_with_a_reason(db_session, factory, tmp_path):
    user = await _user(db_session)
    path = tmp_path / "broken.json"
    path.write_text('[{"ts": "2021-04-15T18:03:20Z", "ms_played": 1')

    imp = await _run(db_session, factory, user, path)

    assert imp.status == "failed"
    assert "JSON" in imp.error
    assert not path.exists()


async def test_a_file_without_any_listen_fails(db_session, factory, tmp_path):
    user = await _user(db_session)
    path = tmp_path / "other.json"
    path.write_text('[{"endTime": "2021-04-15 18:03", "artistName": "A", "msPlayed": 1}]')

    imp = await _run(db_session, factory, user, path)

    assert imp.status == "failed"
    assert "Extended streaming history" in imp.error


async def test_only_one_import_runs_per_user(db_session):
    alice = await _user(db_session, "alice")
    bob = await _user(db_session, "bob")
    await start_import(db_session, alice.id, "a.json")

    with pytest.raises(ImportBusy):
        await start_import(db_session, alice.id, "b.json")
    await start_import(db_session, bob.id, "c.json")


async def test_an_import_that_stopped_updating_no_longer_blocks(db_session):
    user = await _user(db_session)
    stale = await start_import(db_session, user.id, "a.json")
    await db_session.execute(
        update(Import).where(Import.id == stale.id)
        .values(status="running", updated_at=datetime.now(UTC) - timedelta(hours=1))
    )

    fresh = await start_import(db_session, user.id, "b.json")

    await db_session.refresh(stale)
    assert stale.status == "failed"
    assert fresh.status == "pending"


async def test_undo_removes_exactly_the_listens_an_import_added(db_session, factory, tmp_path):
    user = await _user(db_session)
    await upsert_listens(db_session, user.id, [
        Scrobble(artist="The National", track_title="Fake Empire", album="Boxer",
                 played_at=datetime(2021, 4, 15, 18, 1, 10, tzinfo=UTC)),
    ])
    first = await _run(db_session, factory, user, _copy(SPOTIFY, tmp_path))
    second = await _run(db_session, factory, user, listenbrainz_zip(tmp_path), "lb.zip")

    undone = await undo_import(db_session, user.id, first.id)

    assert undone is not None and undone.status == "undone"
    listens = await _listens(db_session, user.id)
    assert {x.source for x in listens} == {"lastfm", "listenbrainz"}
    assert len(listens) == 1 + second.added


async def test_a_running_import_cannot_be_undone(db_session):
    user = await _user(db_session)
    running = await start_import(db_session, user.id, "a.json")

    with pytest.raises(ImportBusy):
        await undo_import(db_session, user.id, running.id)


async def test_undo_of_another_users_import_finds_nothing(db_session, factory, tmp_path):
    alice = await _user(db_session, "alice")
    bob = await _user(db_session, "bob")
    imp = await _run(db_session, factory, alice, _copy(SPOTIFY, tmp_path))

    assert await undo_import(db_session, bob.id, imp.id) is None
    assert len(await _listens(db_session, alice.id)) == 4


async def test_the_summary_counts_imported_listens_before_the_first_scrobble(
    db_session, factory, tmp_path
):
    user = await _user(db_session)
    await upsert_listens(db_session, user.id, [
        Scrobble(artist="Parquet Courts", track_title="Wide Awake", album=None,
                 played_at=datetime(2021, 4, 16, 8, 0, tzinfo=UTC)),
    ])
    await _run(db_session, factory, user, _copy(SPOTIFY, tmp_path))
    scope = Scope(user_id=user.id, tz="UTC", since=None, until=None)

    summary = await source_summary(db_session, scope)

    assert summary == {
        "imported": 4,
        "imported_before_lastfm": 3,
        "lastfm_first": "2021-04-16T08:00:00+00:00",
        "sources": [{"source": "spotify", "listens": 4}],
    }


async def test_the_summary_is_empty_without_imports(db_session):
    user = await _user(db_session)
    scope = Scope(user_id=user.id, tz="UTC", since=None, until=None)

    assert await source_summary(db_session, scope) == {
        "imported": 0, "imported_before_lastfm": 0, "lastfm_first": None, "sources": [],
    }
