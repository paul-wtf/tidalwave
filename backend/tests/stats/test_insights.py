from datetime import UTC, datetime, timedelta

from sqlalchemy import update

from tidalwave.auth.service import upsert_user_from_session
from tidalwave.ingest.repository import upsert_listens
from tidalwave.models.db import Listen
from tidalwave.models.domain import Scrobble
from tidalwave.stats.insights import discoveries, heatmap, on_this_day, records
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


async def _seed(db_session, user, whens):
    await upsert_listens(db_session, user.id, [_s("A", f"t{i}", w) for i, w in enumerate(whens)])


async def test_longest_streak(db_session):
    user = await _user(db_session)
    await _seed(db_session, user, [
        _d(2024, 6, 1, 12), _d(2024, 6, 1, 13), _d(2024, 6, 2, 12),
        _d(2024, 6, 4, 12), _d(2024, 6, 5, 12), _d(2024, 6, 6, 12),
        _d(2024, 6, 8, 12),
    ])
    r = await records(db_session, _scope(user), now=_d(2025, 1, 1))
    assert r["longest_streak"] == {"days": 3, "start": "2024-06-04", "end": "2024-06-06"}


async def test_current_streak_may_end_yesterday(db_session):
    user = await _user(db_session)
    await _seed(db_session, user, [_d(2024, 6, 3, 12), _d(2024, 6, 4, 12), _d(2024, 6, 5, 12)])
    r = await records(db_session, _scope(user), now=_d(2024, 6, 6, 9))
    assert r["current_streak"] == {"days": 3, "start": "2024-06-03"}
    r = await records(db_session, _scope(user), now=_d(2024, 6, 7, 9))
    assert r["current_streak"] is None


async def test_current_streak_uses_user_tz(db_session):
    user = await _user(db_session)
    await _seed(db_session, user, [_d(2024, 6, 4, 12), _d(2024, 6, 5, 12)])
    now = _d(2024, 6, 6, 22, 30)
    utc = await records(db_session, _scope(user), now=now)
    berlin = await records(db_session, _scope(user, tz="Europe/Berlin"), now=now)
    assert utc["current_streak"] == {"days": 2, "start": "2024-06-04"}
    assert berlin["current_streak"] is None


async def test_current_streak_absent_when_range_excludes_today(db_session):
    user = await _user(db_session)
    await _seed(db_session, user, [_d(2024, 6, 4, 12), _d(2024, 6, 5, 12)])
    now = _d(2024, 6, 6, 9)
    scope = _scope(user, since=_d(2024, 6, 1), until=_d(2024, 6, 6))
    assert (await records(db_session, scope, now=now))["current_streak"] is None
    scope = _scope(user, since=_d(2024, 6, 1), until=_d(2024, 6, 7))
    assert (await records(db_session, scope, now=now))["current_streak"] is not None
    scope = _scope(user, since=_d(2024, 6, 7))
    assert (await records(db_session, scope, now=now))["current_streak"] is None


async def test_current_streak_is_not_cut_at_the_range_start(db_session):
    user = await _user(db_session)
    await _seed(db_session, user, [_d(2024, 6, day, 12) for day in range(1, 11)])
    now = _d(2024, 6, 10, 15)
    scope = _scope(user, since=_d(2024, 6, 9))
    r = await records(db_session, scope, now=now)
    assert r["current_streak"] == {"days": 10, "start": "2024-06-01"}


async def test_current_streak_in_a_share_stops_at_the_share_floor(db_session):
    user = await _user(db_session)
    await _seed(db_session, user, [_d(2024, 6, day, 12) for day in range(1, 11)])
    now = _d(2024, 6, 10, 15)
    floor = _d(2024, 6, 8)
    scope = _scope(user, since=floor, floor=floor, shared=True)
    r = await records(db_session, scope, now=now)
    assert r["current_streak"] == {"days": 3, "start": "2024-06-08"}


async def test_busiest_day_in_user_tz(db_session):
    user = await _user(db_session)
    await _seed(db_session, user, [
        _d(2024, 6, 1, 12),
        _d(2024, 6, 2, 21, 30), _d(2024, 6, 2, 22, 30), _d(2024, 6, 2, 23, 30),
    ])
    utc = await records(db_session, _scope(user), now=_d(2025, 1, 1))
    assert utc["busiest_day"] == {"date": "2024-06-02", "listens": 3}
    berlin = await records(db_session, _scope(user, tz="Europe/Berlin"), now=_d(2025, 1, 1))
    assert berlin["busiest_day"] == {"date": "2024-06-03", "listens": 2}


async def test_longest_session_breaks_after_30_minutes(db_session):
    user = await _user(db_session)
    first = [_d(2024, 6, 1, 10) + timedelta(minutes=30 * i) for i in range(4)]
    second = [_d(2024, 6, 1, 20) + timedelta(minutes=31 * i) for i in range(5)]
    await _seed(db_session, user, first + second)
    await db_session.execute(update(Listen).where(Listen.track_title == "t0").values(duration_sec=100))
    await db_session.execute(update(Listen).where(Listen.track_title == "t2").values(duration_sec=50))
    r = await records(db_session, _scope(user), now=_d(2025, 1, 1))
    assert r["longest_session"] == {"start": first[0].isoformat(), "listens": 4, "seconds": 150}
    await _seed(db_session, user, [first[-1] + timedelta(minutes=30)])
    r = await records(db_session, _scope(user), now=_d(2025, 1, 1))
    assert r["longest_session"]["listens"] == 5


async def test_streak_across_month_boundary_and_dst_in_berlin(db_session):
    user = await _user(db_session)
    await _seed(db_session, user, [_d(2024, 3, 30, 12), _d(2024, 3, 31, 12), _d(2024, 4, 1, 12)])
    r = await records(db_session, _scope(user, tz="Europe/Berlin"), now=_d(2025, 1, 1))
    assert r["longest_streak"] == {"days": 3, "start": "2024-03-30", "end": "2024-04-01"}


async def test_heatmap_366_day_boundary(db_session):
    user = await _user(db_session)
    now = _d(2025, 6, 1)
    h = await heatmap(db_session, _scope(user, since=_d(2024, 1, 1), until=_d(2025, 1, 1)), now=now)
    assert (h["start"], h["end"]) == ("2024-01-01", "2024-12-31")
    h = await heatmap(db_session, _scope(user, since=_d(2024, 1, 1), until=_d(2025, 1, 2)), now=now)
    assert (h["start"], h["end"]) == ("2024-01-03", "2025-01-01")


async def test_heatmap_future_since_is_empty_window(db_session):
    user = await _user(db_session)
    h = await heatmap(db_session, _scope(user, since=_d(2025, 6, 10)), now=_d(2025, 6, 1))
    assert (h["start"], h["end"], h["days"]) == ("2025-06-01", "2025-06-01", [])


async def test_heatmap_window_caps_at_365_days(db_session):
    user = await _user(db_session)
    await _seed(db_session, user, [_d(2023, 1, 1, 12), _d(2024, 1, 1, 12), _d(2024, 1, 1, 13)])
    now = _d(2024, 6, 1, 9)
    h = await heatmap(db_session, _scope(user), now=now)
    assert (h["start"], h["end"]) == ("2023-06-03", "2024-06-01")
    assert h["days"] == [{"date": "2024-01-01", "listens": 2}]
    h = await heatmap(db_session, _scope(user, since=_d(2024, 1, 1), until=_d(2024, 2, 1)), now=now)
    assert (h["start"], h["end"]) == ("2024-01-01", "2024-01-31")
    h = await heatmap(db_session, _scope(user, since=_d(2022, 1, 1), until=_d(2024, 2, 1)), now=now)
    assert (h["start"], h["end"]) == ("2023-02-01", "2024-01-31")


async def test_records_empty_user(db_session):
    user = await _user(db_session)
    now = _d(2024, 6, 1)
    assert await records(db_session, _scope(user), now=now) == {
        "longest_streak": None, "current_streak": None,
        "busiest_day": None, "longest_session": None,
    }
    h = await heatmap(db_session, _scope(user), now=now)
    assert h["days"] == []


async def test_discovery_and_session_instants_carry_the_owner_offset(db_session):
    user = await _user(db_session)
    await _seed(db_session, user, [_d(2024, 1, 10, 23, 30), _d(2024, 7, 10, 23, 30)])
    scope = _scope(user, tz="Europe/Berlin", since=_d(2024, 1, 1), until=_d(2025, 1, 1))
    d = await discoveries(db_session, scope)
    assert d["new_artists"][0]["first_listen"] == "2024-01-11T00:30:00+01:00"
    assert d["new_tracks"][0]["first_listen"].endswith("+01:00")
    r = await records(db_session, scope, now=_d(2025, 1, 1))
    assert r["longest_session"]["start"] == "2024-01-11T00:30:00+01:00"


async def test_rediscovery_previous_listen_carries_the_owner_offset(db_session):
    user = await _user(db_session)
    since = _d(2024, 7, 1)
    await upsert_listens(db_session, user.id, [
        _s("Gap", "t", _d(2023, 12, 1, 23, 30)),
        _s("Gap", "t", since),
    ])
    d = await discoveries(
        db_session, _scope(user, tz="Europe/Berlin", since=since, until=_d(2024, 8, 1))
    )
    assert d["rediscoveries"][0]["previous_listen"] == "2023-12-02T00:30:00+01:00"
