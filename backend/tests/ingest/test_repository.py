from datetime import UTC, datetime

from sqlalchemy import func, select

from tidalwave.auth.service import upsert_user_from_session
from tidalwave.ingest.repository import (
    advance_sync_state,
    get_sync_state,
    upsert_album_art,
    upsert_listens,
)
from tidalwave.models.db import AlbumArt, Listen
from tidalwave.models.domain import Scrobble


def _scrobble(title: str, ts: int) -> Scrobble:
    return Scrobble(
        artist="A", track_title=title, album="Alb",
        played_at=datetime.fromtimestamp(ts, tz=UTC),
    )


async def test_upsert_inserts_and_dedups(db_session):
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    s = [_scrobble("t1", 1000), _scrobble("t2", 2000)]

    inserted = await upsert_listens(db_session, user.id, s)
    assert inserted == 2

    inserted2 = await upsert_listens(db_session, user.id, [*s, _scrobble("t3", 3000)])
    assert inserted2 == 1

    total = (
        await db_session.execute(select(func.count()).select_from(Listen))
    ).scalar_one()
    assert total == 3


async def test_upsert_handles_more_rows_than_the_bind_parameter_limit(db_session):
    # Postgres allows at most 32767 bind parameters per statement, and a listen row
    # binds 8 columns — so a single INSERT tops out at 4095 rows. A first backfill of
    # a long history easily exceeds that, so the insert has to be split into chunks.
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    many = [_scrobble(f"t{i}", 1000 + i) for i in range(5000)]

    inserted = await upsert_listens(db_session, user.id, many)

    assert inserted == 5000
    total = (
        await db_session.execute(select(func.count()).select_from(Listen))
    ).scalar_one()
    assert total == 5000


async def test_upsert_dedups_across_chunk_boundaries(db_session):
    # Re-importing the same oversized history must stay idempotent, not just within
    # one chunk — the dedup constraint has to hold for every chunk of the second run.
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    many = [_scrobble(f"t{i}", 1000 + i) for i in range(5000)]
    await upsert_listens(db_session, user.id, many)

    reinserted = await upsert_listens(db_session, user.id, [*many, _scrobble("new", 90000)])

    assert reinserted == 1
    total = (
        await db_session.execute(select(func.count()).select_from(Listen))
    ).scalar_one()
    assert total == 5001


async def test_now_playing_scrobbles_are_skipped(db_session):
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    np = Scrobble(artist="A", track_title="np", album=None, played_at=None, now_playing=True)
    inserted = await upsert_listens(db_session, user.id, [np])
    assert inserted == 0


async def test_dateless_finished_scrobbles_are_skipped(db_session):
    # A finished track (now_playing=False) that lacks a timestamp cannot be stored.
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    dateless = Scrobble(artist="A", track_title="x", album=None, played_at=None, now_playing=False)
    inserted = await upsert_listens(db_session, user.id, [dateless])
    assert inserted == 0


async def test_sync_state_roundtrip(db_session):
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    assert await get_sync_state(db_session, user.id) is None

    ts = datetime.fromtimestamp(5000, tz=UTC)
    await advance_sync_state(db_session, user.id, last_played_at=ts)
    state = await get_sync_state(db_session, user.id)
    assert state is not None and state.last_played_at == ts


def _cover(album: str | None, url: str | None, artist: str = "A") -> Scrobble:
    return Scrobble(
        artist=artist, track_title="t", album=album,
        played_at=datetime.fromtimestamp(1000, tz=UTC), image_url=url,
    )


async def _art(db_session) -> dict[tuple[str, str], str | None]:
    rows = (await db_session.execute(select(AlbumArt))).scalars().all()
    return {(r.artist, r.album): r.image_url for r in rows}


async def test_upsert_album_art_url_wins_over_null(db_session):
    await upsert_album_art(db_session, [_cover("Alb", "https://img/1.jpg"), _cover(None, "x")])
    assert await _art(db_session) == {("A", "Alb"): "https://img/1.jpg"}

    await upsert_album_art(db_session, [_cover("Alb", None)])
    assert await _art(db_session) == {("A", "Alb"): "https://img/1.jpg"}

    await upsert_album_art(db_session, [_cover("Other", None)])
    assert await _art(db_session) == {("A", "Alb"): "https://img/1.jpg", ("A", "Other"): None}


async def test_upsert_album_art_newer_url_replaces_older(db_session):
    await upsert_album_art(db_session, [_cover("Alb", "https://img/old.jpg")])
    await upsert_album_art(
        db_session,
        [_cover("Alb", "https://img/mid.jpg"), _cover("Alb", "https://img/new.jpg"), _cover("Alb", None)],
    )
    assert await _art(db_session) == {("A", "Alb"): "https://img/new.jpg"}
