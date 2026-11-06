from datetime import UTC, datetime, timedelta

from tidalwave.auth.service import upsert_user_from_session
from tidalwave.ingest.repository import upsert_listens
from tidalwave.models.domain import Scrobble
from tidalwave.stats.insights import discoveries, on_this_day
from tidalwave.stats.scope import Scope


def _s(artist, title, when, album=None):
    return Scrobble(artist=artist, track_title=title, album=album, played_at=when)


def _scope(user, tz="UTC", **kw):
    return Scope(user_id=user.id, tz=tz, since=kw.get("since"), until=kw.get("until"),
                 floor=kw.get("floor"), ceiling=kw.get("ceiling"), shared=kw.get("shared", False))


async def _user(db_session, name="alice"):
    return await upsert_user_from_session(db_session, name, "sk", mode="open", allowlist=[])


def _d(*args):
    return datetime(*args, tzinfo=UTC)


async def test_new_artists_first_listen_inside_range(db_session):
    user = await _user(db_session)
    await upsert_listens(db_session, user.id, [
        _s("Old", "o", _d(2024, 1, 1)),
        _s("Old", "o", _d(2024, 6, 10)),
        _s("New", "n", _d(2024, 6, 5)),
        _s("New", "n2", _d(2024, 6, 6)),
        _s("New", "n", _d(2024, 6, 7)),
    ])
    scope = _scope(user, since=_d(2024, 6, 1), until=_d(2024, 7, 1))
    d = await discoveries(db_session, scope)
    assert d["new_artists"] == [
        {"artist": "New", "first_listen": _d(2024, 6, 5).isoformat(), "listens": 3, "image_url": None}
    ]
    assert d["new_tracks_count"] == 2
    assert {t["track"] for t in d["new_tracks"]} == {"n", "n2"}
    assert d["new_tracks"][0] == {
        "track": "n", "artist": "New", "first_listen": _d(2024, 6, 5).isoformat(), "listens": 2
    }


async def test_discoveries_empty_for_all_time(db_session):
    user = await _user(db_session)
    await upsert_listens(db_session, user.id, [_s("A", "t", _d(2024, 1, 1))])
    d = await discoveries(db_session, _scope(user))
    assert d == {"new_artists": [], "new_tracks_count": 0, "new_tracks": [], "rediscoveries": []}


async def test_rediscovery_requires_180_day_gap(db_session):
    user = await _user(db_session)
    since = _d(2024, 7, 1)
    await upsert_listens(db_session, user.id, [
        _s("Gap179", "t", since - timedelta(days=179)),
        _s("Gap179", "t", since),
        _s("Gap180", "t", since - timedelta(days=180)),
        _s("Gap180", "t", since),
        _s("Gap180", "t", since + timedelta(days=1)),
    ])
    d = await discoveries(db_session, _scope(user, since=since, until=_d(2024, 8, 1)))
    assert d["rediscoveries"] == [
        {"artist": "Gap180", "previous_listen": (since - timedelta(days=180)).isoformat(),
         "gap_days": 180, "listens": 2}
    ]


async def test_share_floor_hides_earlier_listens_from_discoveries(db_session):
    user = await _user(db_session)
    await upsert_listens(db_session, user.id, [
        _s("Early", "t", _d(2023, 1, 1)),
        _s("Early", "t", _d(2024, 6, 5)),
        _s("Early", "u", _d(2023, 1, 1)),
        _s("Early", "u", _d(2024, 6, 6)),
    ])
    floor, ceiling = _d(2024, 6, 1), _d(2024, 7, 1)
    own = await discoveries(db_session, _scope(user, since=floor, until=ceiling))
    assert own["new_artists"] == []
    assert own["new_tracks_count"] == 0
    assert [r["artist"] for r in own["rediscoveries"]] == ["Early"]
    shared = await discoveries(
        db_session, _scope(user, since=floor, until=ceiling, floor=floor, ceiling=ceiling, shared=True)
    )
    assert [a["artist"] for a in shared["new_artists"]] == ["Early"]
    assert shared["new_tracks_count"] == 2
    assert shared["rediscoveries"] == []


async def test_on_this_day_groups_previous_years_in_user_tz(db_session):
    user = await _user(db_session)
    await upsert_listens(db_session, user.id, [
        _s("A", "t", datetime(2025, 11, 5, 23, 30, tzinfo=UTC)),
        _s("A", "t", datetime(2025, 11, 6, 12, 0, tzinfo=UTC)),
        _s("B", "u", datetime(2025, 11, 6, 13, 0, tzinfo=UTC)),
        _s("A", "t", datetime(2023, 11, 6, 8, 0, tzinfo=UTC)),
        _s("A", "t", datetime(2025, 11, 5, 12, 0, tzinfo=UTC)),
        _s("A", "t", datetime(2026, 11, 6, 8, 0, tzinfo=UTC)),
    ])
    now = datetime(2026, 11, 6, 9, 0, tzinfo=UTC)
    result = await on_this_day(db_session, _scope(user, tz="Europe/Berlin"), now=now)
    assert [y["year"] for y in result] == [2025, 2023]
    assert result[0]["listens"] == 3
    assert result[0]["top_tracks"][0] == {"track": "t", "artist": "A", "count": 2}
    assert len(result[0]["top_tracks"]) == 2
    utc = await on_this_day(db_session, _scope(user), now=now)
    assert utc[0]["listens"] == 2


async def test_on_this_day_respects_share_range(db_session):
    user = await _user(db_session)
    await upsert_listens(db_session, user.id, [
        _s("A", "t", _d(2022, 11, 6)),
        _s("A", "t", _d(2024, 11, 6)),
        _s("A", "t", _d(2025, 11, 6)),
    ])
    now = _d(2026, 11, 6)
    scope = _scope(user, floor=_d(2024, 1, 1), ceiling=_d(2025, 1, 1), shared=True)
    result = await on_this_day(db_session, scope, now=now)
    assert [y["year"] for y in result] == [2024]


async def test_insights_empty_user_returns_empty(db_session):
    user = await _user(db_session)
    scope = _scope(user, since=_d(2024, 1, 1), until=_d(2024, 2, 1))
    assert await discoveries(db_session, scope) == {
        "new_artists": [], "new_tracks_count": 0, "new_tracks": [], "rediscoveries": []
    }
    assert await on_this_day(db_session, scope, now=_d(2026, 11, 6)) == []
