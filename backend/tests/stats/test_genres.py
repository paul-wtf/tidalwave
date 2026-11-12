from datetime import UTC, datetime

from tidalwave.auth.service import upsert_user_from_session
from tidalwave.ingest.repository import upsert_listens
from tidalwave.models.db import ArtistTags
from tidalwave.models.domain import Scrobble
from tidalwave.stats.genres import genre_detail, genres
from tidalwave.stats.queries import metrics_over_time, top_artists
from tidalwave.stats.scope import Scope


def _d(*args):
    return datetime(*args, tzinfo=UTC)


def _scope(user, **kw):
    return Scope(user_id=user.id, tz="UTC", since=kw.get("since"), until=kw.get("until"),
                 floor=kw.get("floor"), ceiling=kw.get("ceiling"), shared=kw.get("shared", False))


async def _seed(db_session):
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    other = await upsert_user_from_session(db_session, "bob", "sk2", mode="open", allowlist=[])
    listens = [
        *[("Daft Punk", _d(2024, 6, d)) for d in (1, 2, 3)],
        *[("Justice", _d(2024, 6, d)) for d in (4, 5)],
        ("Kavinsky", _d(2024, 6, 6)),
        ("Untagged", _d(2024, 6, 7)),
        ("Tagless", _d(2024, 6, 8)),
        ("Daft Punk", _d(2023, 1, 1)),
    ]
    await upsert_listens(db_session, user.id, [
        Scrobble(artist=a, track_title="t", album=None, played_at=when) for a, when in listens
    ])
    await upsert_listens(db_session, other.id, [
        Scrobble(artist="Slayer", track_title="t", album=None, played_at=_d(2024, 6, 1)),
    ])
    db_session.add_all([
        ArtistTags(artist="Daft Punk", tags=["electronic", "house", "french house", "dance"]),
        ArtistTags(artist="Justice", tags=["electronic", "house"]),
        ArtistTags(artist="Kavinsky", tags=["synthwave"]),
        ArtistTags(artist="Tagless", tags=[]),
        ArtistTags(artist="Slayer", tags=["thrash metal"]),
    ])
    await db_session.flush()
    return user


JUNE = {"since": _d(2024, 6, 1), "until": _d(2024, 7, 1)}


async def test_genres_count_an_artists_listens_for_each_of_its_top_three_tags(db_session):
    user = await _seed(db_session)
    result = await genres(db_session, _scope(user, **JUNE))
    assert result["genres"] == [
        {"genre": "electronic", "listens": 5, "artists": 2},
        {"genre": "house", "listens": 5, "artists": 2},
        {"genre": "french house", "listens": 3, "artists": 1},
        {"genre": "synthwave", "listens": 1, "artists": 1},
    ]


async def test_genres_report_how_many_artists_in_range_have_been_looked_up(db_session):
    user = await _seed(db_session)
    result = await genres(db_session, _scope(user, **JUNE))
    assert (result["artists"], result["tagged_artists"]) == (5, 4)
    earlier = await genres(db_session, _scope(user, since=_d(2023, 1, 1), until=_d(2023, 2, 1)))
    assert earlier == {
        "genres": [{"genre": "electronic", "listens": 1, "artists": 1},
                   {"genre": "french house", "listens": 1, "artists": 1},
                   {"genre": "house", "listens": 1, "artists": 1}],
        "artists": 1, "tagged_artists": 1,
    }


async def test_genres_limit(db_session):
    user = await _seed(db_session)
    result = await genres(db_session, _scope(user, **JUNE), limit=1)
    assert [g["genre"] for g in result["genres"]] == ["electronic"]


async def test_genre_detail_totals_follow_the_range(db_session):
    user = await _seed(db_session)
    assert await genre_detail(db_session, _scope(user, **JUNE), "House") == {
        "genre": "house", "listens": 5, "seconds": 0, "artists": 2,
    }
    assert await genre_detail(db_session, _scope(user), "house") == {
        "genre": "house", "listens": 6, "seconds": 0, "artists": 2,
    }


async def test_genre_detail_is_none_for_a_tag_outside_the_top_three_or_the_bounds(db_session):
    user = await _seed(db_session)
    assert await genre_detail(db_session, _scope(user), "dance") is None
    assert await genre_detail(db_session, _scope(user), "thrash metal") is None
    shared = _scope(user, since=_d(2023, 1, 1), until=_d(2023, 2, 1),
                    floor=_d(2023, 1, 1), ceiling=_d(2023, 2, 1), shared=True)
    assert await genre_detail(db_session, shared, "synthwave") is None
    assert (await genre_detail(db_session, shared, "house"))["listens"] == 1


async def test_top_artists_and_metrics_filter_by_genre(db_session):
    user = await _seed(db_session)
    scope = _scope(user, **JUNE)
    rows = await top_artists(db_session, scope, genre="house")
    assert [(r["artist"], r["count"]) for r in rows] == [("Daft Punk", 3), ("Justice", 2)]
    assert await top_artists(db_session, scope, genre="dance") == []
    points = await metrics_over_time(db_session, scope, bucket="month", genre="house")
    assert [(p["listens"], p["artists"]) for p in points] == [(5, 2)]
