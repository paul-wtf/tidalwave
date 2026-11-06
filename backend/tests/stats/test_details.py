from datetime import UTC, datetime

from tidalwave.auth.service import upsert_user_from_session
from tidalwave.ingest.repository import upsert_listens
from tidalwave.models.db import AlbumArt
from tidalwave.models.domain import Scrobble
from tidalwave.stats.details import album_detail, artist_detail, track_detail
from tidalwave.stats.queries import top_artists, top_tracks
from tidalwave.stats.scope import Scope


def _s(artist, title, when, album=None):
    return Scrobble(artist=artist, track_title=title, album=album, played_at=when)


def _scope(user, **kw):
    return Scope(user_id=user.id, tz="UTC", since=kw.get("since"), until=kw.get("until"),
                 floor=kw.get("floor"), ceiling=kw.get("ceiling"), shared=kw.get("shared", False))


async def _user(db_session, name="alice"):
    return await upsert_user_from_session(db_session, name, "sk", mode="open", allowlist=[])


async def test_artist_detail_counts_range_but_first_listen_all_time(db_session):
    user = await _user(db_session)
    await upsert_listens(db_session, user.id, [
        _s("A", "t", datetime(2024, 1, 1, tzinfo=UTC)),
        _s("A", "t", datetime(2024, 6, 1, tzinfo=UTC)),
        _s("A", "t", datetime(2024, 9, 1, tzinfo=UTC)),
    ])
    scope = _scope(user, since=datetime(2024, 5, 1, tzinfo=UTC), until=datetime(2024, 7, 1, tzinfo=UTC))
    d = await artist_detail(db_session, scope, "A")
    assert d["listens"] == 1
    assert d["rank"] == 1
    assert d["first_listen"] == datetime(2024, 1, 1, tzinfo=UTC).isoformat()
    assert d["last_listen"] == datetime(2024, 9, 1, tzinfo=UTC).isoformat()


async def test_artist_detail_rank_matches_top_list(db_session):
    user = await _user(db_session)
    t = datetime(2024, 1, 1, tzinfo=UTC)
    rows = []
    for artist, n in [("B", 3), ("A", 2), ("C", 2), ("D", 1)]:
        rows += [_s(artist, f"t{i}", t.replace(day=i + 1)) for i in range(n)]
    await upsert_listens(db_session, user.id, rows)
    scope = _scope(user)
    order = [r["artist"] for r in await top_artists(db_session, scope, limit=10)]
    for position, artist in enumerate(order, start=1):
        assert (await artist_detail(db_session, scope, artist))["rank"] == position


async def test_artist_with_listens_only_outside_range_has_zero_counts(db_session):
    user = await _user(db_session)
    await upsert_listens(db_session, user.id, [_s("A", "t", datetime(2024, 1, 1, tzinfo=UTC))])
    scope = _scope(user, since=datetime(2025, 1, 1, tzinfo=UTC))
    d = await artist_detail(db_session, scope, "A")
    assert d["listens"] == 0
    assert d["seconds"] == 0
    assert d["rank"] is None
    assert d["first_listen"] == datetime(2024, 1, 1, tzinfo=UTC).isoformat()


async def test_detail_first_listen_clamped_to_share(db_session):
    user = await _user(db_session)
    await upsert_listens(db_session, user.id, [
        _s("A", "t", datetime(2024, 1, 1, tzinfo=UTC), "Al"),
        _s("A", "t", datetime(2024, 6, 1, tzinfo=UTC), "Al"),
        _s("A", "t", datetime(2024, 12, 1, tzinfo=UTC), "Al"),
        _s("Hidden", "h", datetime(2024, 1, 1, tzinfo=UTC), "HA"),
    ])
    floor, ceiling = datetime(2024, 3, 1, tzinfo=UTC), datetime(2024, 9, 1, tzinfo=UTC)
    scope = _scope(user, since=floor, until=ceiling, floor=floor, ceiling=ceiling, shared=True)
    june = datetime(2024, 6, 1, tzinfo=UTC).isoformat()
    for d in (
        await artist_detail(db_session, scope, "A"),
        await album_detail(db_session, scope, "A", "Al"),
        await track_detail(db_session, scope, "A", "t"),
    ):
        assert d["first_listen"] == june
        assert d["last_listen"] == june
        assert d["listens"] == 1
    assert await artist_detail(db_session, scope, "Hidden") is None


async def test_track_detail_album_is_most_listened(db_session):
    user = await _user(db_session)
    t = datetime(2024, 1, 1, tzinfo=UTC)
    await upsert_listens(db_session, user.id, [
        _s("A", "t", t.replace(day=1), "Single"),
        _s("A", "t", t.replace(day=2), "Compilation"),
        _s("A", "t", t.replace(day=3), "Compilation"),
        _s("A", "u", t.replace(day=4)),
    ])
    db_session.add(AlbumArt(artist="A", album="Compilation", image_url="http://img/c"))
    await db_session.flush()
    d = await track_detail(db_session, _scope(user), "A", "t")
    assert d["album"] == "Compilation"
    assert d["image_url"] == "http://img/c"
    assert d["listens"] == 3
    out = await track_detail(db_session, _scope(user, since=datetime(2024, 1, 1, 12, tzinfo=UTC),
                                                until=datetime(2024, 1, 2, 12, tzinfo=UTC)), "A", "t")
    assert out["album"] == "Compilation"
    assert (await track_detail(db_session, _scope(user), "A", "u"))["album"] is None


async def test_album_and_artist_detail_images(db_session):
    user = await _user(db_session)
    await upsert_listens(db_session, user.id, [_s("A", "t", datetime(2024, 1, 1, tzinfo=UTC), "Al")])
    db_session.add(AlbumArt(artist="A", album="Al", image_url="http://img/al"))
    await db_session.flush()
    assert (await album_detail(db_session, _scope(user), "A", "Al"))["image_url"] == "http://img/al"
    assert (await artist_detail(db_session, _scope(user), "A"))["image_url"] == "http://img/al"


async def test_top_tracks_filtered_by_artist(db_session):
    user = await _user(db_session)
    t = datetime(2024, 1, 1, tzinfo=UTC)
    await upsert_listens(db_session, user.id, [
        _s("A", "x", t.replace(day=1)),
        _s("B", "x", t.replace(day=2)),
        _s("B", "y", t.replace(day=3)),
    ])
    rows = await top_tracks(db_session, _scope(user), artist="B")
    assert {(r["artist"], r["track"]) for r in rows} == {("B", "x"), ("B", "y")}
    rows = await top_tracks(db_session, _scope(user), artist="B", track="y")
    assert len(rows) == 1


async def test_track_detail_album_prefers_range_over_all_time(db_session):
    user = await _user(db_session)
    await upsert_listens(db_session, user.id, [
        _s("A", "t", datetime(2024, 1, d, tzinfo=UTC), "Compilation") for d in (1, 2, 3)
    ] + [
        _s("A", "t", datetime(2024, 2, d, tzinfo=UTC), "Single") for d in (1, 2)
    ])
    scope = _scope(user, since=datetime(2024, 2, 1, tzinfo=UTC), until=datetime(2024, 3, 1, tzinfo=UTC))
    assert (await track_detail(db_session, scope, "A", "t"))["album"] == "Single"
    assert (await track_detail(db_session, _scope(user), "A", "t"))["album"] == "Compilation"


async def test_track_detail_album_fallback_stays_inside_share(db_session):
    user = await _user(db_session)
    await upsert_listens(db_session, user.id, [
        _s("A", "t", datetime(2024, 1, d, tzinfo=UTC), "Outside") for d in (1, 2, 3)
    ] + [_s("A", "t", datetime(2024, 6, 1, tzinfo=UTC), "Inside")])
    db_session.add_all([
        AlbumArt(artist="A", album="Outside", image_url="http://img/outside"),
        AlbumArt(artist="A", album="Inside", image_url="http://img/inside"),
    ])
    await db_session.flush()
    scope = _scope(
        user,
        since=datetime(2024, 7, 1, tzinfo=UTC), until=datetime(2024, 8, 1, tzinfo=UTC),
        floor=datetime(2024, 3, 1, tzinfo=UTC), ceiling=datetime(2024, 9, 1, tzinfo=UTC),
        shared=True,
    )
    d = await track_detail(db_session, scope, "A", "t")
    assert d["listens"] == 0
    assert d["album"] == "Inside"
    assert d["image_url"] == "http://img/inside"


async def test_artist_rank_inside_range_differs_from_all_time(db_session):
    user = await _user(db_session)
    await upsert_listens(db_session, user.id, [
        _s("A", f"t{d}", datetime(2024, 1, d, tzinfo=UTC)) for d in (1, 2, 3)
    ] + [
        _s("B", f"t{d}", datetime(2024, 6, d, tzinfo=UTC)) for d in (1, 2)
    ])
    assert (await artist_detail(db_session, _scope(user), "B"))["rank"] == 2
    june = _scope(user, since=datetime(2024, 6, 1, tzinfo=UTC), until=datetime(2024, 7, 1, tzinfo=UTC))
    assert (await artist_detail(db_session, june, "B"))["rank"] == 1
    assert (await artist_detail(db_session, june, "A"))["rank"] is None


async def test_detail_instants_carry_the_owner_offset(db_session):
    user = await _user(db_session)
    await upsert_listens(db_session, user.id, [
        _s("A", "t", datetime(2024, 1, 10, 23, 30, tzinfo=UTC), album="X"),
        _s("A", "t", datetime(2024, 7, 10, 23, 30, tzinfo=UTC), album="X"),
    ])
    scope = Scope(user_id=user.id, tz="Europe/Berlin", since=None, until=None)
    for d in (
        await artist_detail(db_session, scope, "A"),
        await album_detail(db_session, scope, "A", "X"),
        await track_detail(db_session, scope, "A", "t"),
    ):
        assert d["first_listen"] == "2024-01-11T00:30:00+01:00"
        assert d["last_listen"] == "2024-07-11T01:30:00+02:00"
