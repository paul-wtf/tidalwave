from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from tidalwave.auth.service import upsert_user_from_session
from tidalwave.auth.session import COOKIE_NAME, SessionCodec
from tidalwave.ingest.repository import upsert_listens
from tidalwave.models.db import AlbumArt, AlbumYear, ArtistTags
from tidalwave.models.domain import Scrobble

BERLIN = ZoneInfo("Europe/Berlin")


def _at(*parts: int) -> datetime:
    return datetime(*parts, tzinfo=BERLIN).astimezone(UTC)


def _s(artist: str, track: str, when: datetime, album: str | None = None) -> Scrobble:
    return Scrobble(artist=artist, track_title=track, album=album, played_at=when)


async def _owner(db_session):
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    user.timezone = "Europe/Berlin"
    cookie = SessionCodec("test-secret").encode(user.id)
    return user, {"Cookie": f"{COOKIE_NAME}={cookie}"}


async def _history(db_session, user):
    run = [
        _s("Boards of Canada", f"Track {i}", _at(2025, 6, 7, 20, 0) + timedelta(minutes=5 * i),
           "Music Has the Right to Children")
        for i in range(6)
    ]
    await upsert_listens(db_session, user.id, [
        _s("Radiohead", "Reckoner", _at(2024, 12, 31, 23, 30), "In Rainbows"),
        _s("Kavinsky", "Nightcall", _at(2025, 1, 1, 0, 15), "OutRun"),
        _s("Kavinsky", "Nightcall", _at(2025, 1, 2, 9, 0), "OutRun"),
        _s("Radiohead", "Reckoner", _at(2025, 1, 3, 9, 0), "In Rainbows"),
        _s("Kavinsky", "Odd Look", _at(2025, 3, 10, 18, 0), "OutRun"),
        _s("Kavinsky", "Nightcall", _at(2025, 3, 10, 18, 5), "OutRun"),
        _s("Sigur Rós", "Hoppípolla", _at(2025, 3, 10, 18, 10), "Takk..."),
        *run,
        _s("Radiohead", "Nude", _at(2025, 12, 31, 23, 50), "In Rainbows"),
        _s("Kavinsky", "Nightcall", _at(2026, 1, 1, 0, 5), "OutRun"),
    ])
    db_session.add_all([
        AlbumArt(artist="Kavinsky", album="OutRun", image_url="http://img/outrun.jpg"),
        AlbumYear(artist="Kavinsky", album="OutRun", year=2013),
        AlbumYear(artist="Radiohead", album="In Rainbows", year=2007),
        ArtistTags(artist="Kavinsky", tags=["synthwave", "electronic"]),
        ArtistTags(artist="Radiohead", tags=["alternative", "rock"]),
    ])
    await db_session.flush()


async def test_a_year_comes_in_one_request_in_the_owners_timezone(api, db_session):
    client, _ = api
    user, headers = await _owner(db_session)
    await _history(db_session, user)

    resp = await client.get("/stats/year/2025", headers=headers)

    assert resp.status_code == 200
    year = resp.json()
    assert year["year"] == 2025
    assert year["summary"]["total_listens"] == 13
    assert year["previous"]["total_listens"] == 1
    assert [a["artist"] for a in year["top_artists"]][:2] == ["Boards of Canada", "Kavinsky"]
    assert year["top_artists"][1]["image_url"] == "http://img/outrun.jpg"
    assert year["top_tracks"][0] == {"track": "Nightcall", "artist": "Kavinsky", "count": 3}
    assert year["top_albums"][0]["album"] == "Music Has the Right to Children"


async def test_the_year_has_twelve_months_with_their_top_artist(api, db_session):
    client, _ = api
    user, headers = await _owner(db_session)
    await _history(db_session, user)

    months = (await client.get("/stats/year/2025", headers=headers)).json()["months"]

    assert [m["month"] for m in months] == list(range(1, 13))
    assert [m["listens"] for m in months] == [3, 0, 3, 0, 0, 6, 0, 0, 0, 0, 0, 1]
    assert months[0]["top_artist"] == "Kavinsky"
    assert months[1]["top_artist"] is None
    assert months[5]["top_artist"] == "Boards of Canada"


async def test_the_year_names_its_busiest_day_and_first_and_last_listen(api, db_session):
    client, _ = api
    user, headers = await _owner(db_session)
    await _history(db_session, user)

    year = (await client.get("/stats/year/2025", headers=headers)).json()

    assert year["busiest_day"] == {
        "date": "2025-06-07", "listens": 6, "top_artist": "Boards of Canada",
    }
    first, last = year["first_listen"], year["last_listen"]
    assert (first["track"], first["played_at"]) == ("Nightcall", "2025-01-01T00:15:00+01:00")
    assert first["image_url"] == "http://img/outrun.jpg"
    assert (last["track"], last["played_at"]) == ("Nude", "2025-12-31T23:50:00+01:00")


async def test_the_year_counts_artists_heard_for_the_first_time(api, db_session):
    client, _ = api
    user, headers = await _owner(db_session)
    await _history(db_session, user)

    new = (await client.get("/stats/year/2025", headers=headers)).json()["new_artists"]

    assert new["count"] == 3
    assert [a["artist"] for a in new["top"]] == ["Boards of Canada", "Kavinsky", "Sigur Rós"]


async def test_the_year_brings_genres_decades_streak_and_album_runs(api, db_session):
    client, _ = api
    user, headers = await _owner(db_session)
    await _history(db_session, user)

    year = (await client.get("/stats/year/2025", headers=headers)).json()

    assert [g["genre"] for g in year["genres"]["genres"]] == [
        "electronic", "synthwave", "alternative", "rock",
    ]
    assert {d["decade"]: d["listens"] for d in year["decades"]["decades"]}[2010] == 4
    assert year["longest_streak"] == {"days": 3, "start": "2025-01-01", "end": "2025-01-03"}
    assert year["album_runs"]["total"] == 1
    assert year["album_runs"]["runs"][0]["album"] == "Music Has the Right to Children"


async def test_a_year_without_listens_is_empty_not_missing(api, db_session):
    client, _ = api
    user, headers = await _owner(db_session)
    await _history(db_session, user)

    year = (await client.get("/stats/year/2019", headers=headers)).json()

    assert year["summary"]["total_listens"] == 0
    assert year["first_listen"] is None
    assert year["busiest_day"] is None


@pytest.mark.parametrize("bad", ["1899", "3000", "abc"])
async def test_an_unreasonable_year_is_refused(api, db_session, bad):
    client, _ = api
    _, headers = await _owner(db_session)

    assert (await client.get(f"/stats/year/{bad}", headers=headers)).status_code == 422


async def test_years_lists_every_year_with_listens(api, db_session):
    client, _ = api
    user, headers = await _owner(db_session)
    await _history(db_session, user)

    resp = await client.get("/stats/years", headers=headers)

    assert resp.json() == [
        {"year": 2026, "listens": 1}, {"year": 2025, "listens": 13}, {"year": 2024, "listens": 1},
    ]


async def test_a_share_of_the_year_shows_its_review(api, db_session):
    client, _ = api
    user, headers = await _owner(db_session)
    await _history(db_session, user)
    token = (await client.post(
        "/shares", json={"start": "2025-01-01", "end": "2026-01-01", "label": "2025"},
        headers=headers,
    )).json()["share_token"]

    year = await client.get(f"/shared/{token}/year/2025")
    years = await client.get(f"/shared/{token}/years")

    assert year.status_code == 200
    assert year.json()["summary"]["total_listens"] == 13
    assert year.json()["previous"] is None
    assert years.json() == [{"year": 2025, "listens": 13}]


async def test_a_share_does_not_open_years_outside_its_range(api, db_session):
    client, _ = api
    user, headers = await _owner(db_session)
    await _history(db_session, user)
    token = (await client.post(
        "/shares", json={"start": "2025-03-01", "end": "2026-01-01"}, headers=headers,
    )).json()["share_token"]

    assert (await client.get(f"/shared/{token}/year/2025")).status_code == 404
    assert (await client.get(f"/shared/{token}/year/2024")).status_code == 404
    assert (await client.get(f"/shared/{token}/years")).json() == []


async def test_an_all_time_share_opens_every_year(api, db_session):
    client, _ = api
    user, headers = await _owner(db_session)
    await _history(db_session, user)
    token = (await client.post("/shares", headers=headers)).json()["share_token"]

    assert (await client.get(f"/shared/{token}/year/2024")).status_code == 200
    assert len((await client.get(f"/shared/{token}/years")).json()) == 3
