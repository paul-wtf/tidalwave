from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from tidalwave.auth.service import upsert_user_from_session
from tidalwave.ingest.repository import upsert_listens
from tidalwave.models.db import AlbumArt, AlbumYear, ArtistTags, Listen, TrackDuration
from tidalwave.models.domain import Scrobble
from tidalwave.spellings.service import (
    MergeError,
    alias_map,
    list_merges,
    merge_spellings,
    suggestions,
    unmerge,
)

T0 = datetime(2024, 3, 1, 12, tzinfo=UTC)


def _s(artist: str, track: str, minutes: int, album: str | None = "Boxer") -> Scrobble:
    return Scrobble(
        artist=artist, track_title=track, album=album, played_at=T0 + timedelta(minutes=minutes)
    )


async def _user(session, name="alice"):
    return await upsert_user_from_session(session, name, f"sk-{name}", mode="open", allowlist=[])


async def _artists(session, user_id) -> list[tuple[str, str]]:
    rows = await session.execute(
        select(Listen.artist, Listen.artist_raw)
        .where(Listen.user_id == user_id)
        .order_by(Listen.played_at)
    )
    return [tuple(r) for r in rows.all()]


async def test_a_new_listen_keeps_its_spelling_as_the_original(db_session):
    user = await _user(db_session)
    await upsert_listens(db_session, user.id, [_s("National", "Fake Empire", 0)])

    assert await _artists(db_session, user.id) == [("National", "National")]


async def test_merging_rewrites_the_artist_and_keeps_the_original(db_session):
    user = await _user(db_session)
    await upsert_listens(db_session, user.id, [
        _s("The National", "Fake Empire", 0),
        _s("National", "Mistaken for Strangers", 5),
        _s("the national", "Apartment Story", 10),
    ])

    await merge_spellings(db_session, user.id, "The National", ["National", "the national"])

    assert await _artists(db_session, user.id) == [
        ("The National", "The National"),
        ("The National", "National"),
        ("The National", "the national"),
    ]


async def test_merges_belong_to_one_user(db_session):
    alice = await _user(db_session, "alice")
    bob = await _user(db_session, "bob")
    await upsert_listens(db_session, alice.id, [_s("National", "Fake Empire", 0)])
    await upsert_listens(db_session, bob.id, [_s("National", "Fake Empire", 0)])

    await merge_spellings(db_session, alice.id, "The National", ["National"])

    assert await _artists(db_session, alice.id) == [("The National", "National")]
    assert await _artists(db_session, bob.id) == [("National", "National")]
    assert await alias_map(db_session, bob.id) == {}


async def test_new_listens_in_a_merged_spelling_arrive_under_the_canonical_name(db_session):
    user = await _user(db_session)
    await merge_spellings(db_session, user.id, "Sigur Rós", ["Sigur Ros"])

    inserted = await upsert_listens(
        db_session, user.id, [_s("Sigur Ros", "Hoppípolla", 0)],
        aliases=await alias_map(db_session, user.id),
    )

    assert inserted == 1
    assert await _artists(db_session, user.id) == [("Sigur Rós", "Sigur Ros")]


async def test_a_listen_seen_again_after_a_merge_is_not_stored_twice(db_session):
    user = await _user(db_session)
    scrobble = _s("National", "Fake Empire", 0)
    await upsert_listens(db_session, user.id, [scrobble])
    await merge_spellings(db_session, user.id, "The National", ["National"])

    again = await upsert_listens(
        db_session, user.id, [scrobble], aliases=await alias_map(db_session, user.id)
    )

    assert again == 0


async def test_two_spellings_of_the_same_listen_can_both_be_merged(db_session):
    user = await _user(db_session)
    await upsert_listens(db_session, user.id, [
        _s("The National", "Fake Empire", 0),
        _s("National", "Fake Empire", 0),
    ])

    await merge_spellings(db_session, user.id, "The National", ["National"])

    assert len(await _artists(db_session, user.id)) == 2


async def test_removing_a_merge_restores_the_original_spelling(db_session):
    user = await _user(db_session)
    await upsert_listens(db_session, user.id, [
        _s("The National", "Fake Empire", 0),
        _s("National", "Mistaken for Strangers", 5),
        _s("the national", "Apartment Story", 10),
    ])
    await merge_spellings(db_session, user.id, "The National", ["National", "the national"])

    removed = await unmerge(db_session, user.id, "The National", "National")

    assert removed == 1
    assert await _artists(db_session, user.id) == [
        ("The National", "The National"),
        ("National", "National"),
        ("The National", "the national"),
    ]
    assert await alias_map(db_session, user.id) == {"the national": "The National"}


async def test_removing_a_whole_merge_restores_every_variant(db_session):
    user = await _user(db_session)
    await upsert_listens(db_session, user.id, [
        _s("National", "Mistaken for Strangers", 5),
        _s("the national", "Apartment Story", 10),
    ])
    await merge_spellings(db_session, user.id, "The National", ["National", "the national"])

    assert await unmerge(db_session, user.id, "The National") == 2

    assert await _artists(db_session, user.id) == [
        ("National", "National"),
        ("the national", "the national"),
    ]
    assert await list_merges(db_session, user.id) == []


async def test_merging_into_a_name_that_is_a_variant_is_refused(db_session):
    user = await _user(db_session)
    await merge_spellings(db_session, user.id, "The National", ["National"])

    with pytest.raises(MergeError):
        await merge_spellings(db_session, user.id, "National", ["NATIONAL"])


@pytest.mark.parametrize("variants", [[], ["The National"], ["  "]])
async def test_a_merge_needs_a_variant_other_than_the_canonical_name(db_session, variants):
    user = await _user(db_session)

    with pytest.raises(MergeError):
        await merge_spellings(db_session, user.id, "The National", variants)


async def test_a_blank_canonical_name_is_refused(db_session):
    user = await _user(db_session)

    with pytest.raises(MergeError):
        await merge_spellings(db_session, user.id, " ", ["National"])


async def test_merging_a_canonical_name_moves_its_variants_along(db_session):
    user = await _user(db_session)
    await upsert_listens(db_session, user.id, [
        _s("Natl", "Fake Empire", 0),
        _s("National", "Mistaken for Strangers", 5),
    ])
    await merge_spellings(db_session, user.id, "National", ["Natl"])

    await merge_spellings(db_session, user.id, "The National", ["National"])

    assert await alias_map(db_session, user.id) == {
        "Natl": "The National", "National": "The National",
    }
    assert [a for a, _ in await _artists(db_session, user.id)] == ["The National"] * 2


async def test_a_variant_can_move_to_another_canonical_name(db_session):
    user = await _user(db_session)
    await upsert_listens(db_session, user.id, [_s("Kraftklub", "Songs für Liam", 0)])
    await merge_spellings(db_session, user.id, "KRAFTKLUB", ["Kraftklub"])

    await merge_spellings(db_session, user.id, "Kraft Klub", ["Kraftklub"])

    assert await alias_map(db_session, user.id) == {"Kraftklub": "Kraft Klub"}
    assert await _artists(db_session, user.id) == [("Kraft Klub", "Kraftklub")]


async def test_merges_are_listed_with_the_listens_of_each_spelling(db_session):
    user = await _user(db_session)
    await upsert_listens(db_session, user.id, [
        _s("The National", "Fake Empire", 0),
        _s("National", "Mistaken for Strangers", 5),
        _s("National", "Apartment Story", 10),
        _s("the national", "Slow Show", 15),
    ])
    await merge_spellings(db_session, user.id, "The National", ["National", "the national"])

    assert await list_merges(db_session, user.id) == [
        {
            "canonical": "The National",
            "listens": 4,
            "variants": [
                {"artist": "National", "listens": 2},
                {"artist": "the national", "listens": 1},
            ],
        }
    ]


async def test_merging_carries_covers_tags_years_and_durations_over(db_session):
    user = await _user(db_session)
    await upsert_listens(db_session, user.id, [_s("National", "Fake Empire", 0)])
    db_session.add_all([
        AlbumArt(artist="National", album="Boxer", image_url="http://img/boxer.jpg"),
        AlbumYear(artist="National", album="Boxer", year=2007),
        ArtistTags(artist="National", tags=["indie rock", "indie"]),
        TrackDuration(artist="National", track_title="Fake Empire", duration_sec=205),
    ])
    await db_session.flush()

    await merge_spellings(db_session, user.id, "The National", ["National"])

    art = await db_session.scalar(
        select(AlbumArt.image_url).where(AlbumArt.artist == "The National")
    )
    year = await db_session.scalar(select(AlbumYear.year).where(AlbumYear.artist == "The National"))
    tags = await db_session.scalar(
        select(ArtistTags.tags).where(ArtistTags.artist == "The National")
    )
    duration = await db_session.scalar(
        select(TrackDuration.duration_sec).where(TrackDuration.artist == "The National")
    )
    assert (art, year, tags, duration) == ("http://img/boxer.jpg", 2007, ["indie rock", "indie"], 205)


async def test_known_data_of_the_canonical_name_is_not_overwritten(db_session):
    user = await _user(db_session)
    await upsert_listens(db_session, user.id, [_s("National", "Fake Empire", 0)])
    db_session.add_all([
        AlbumArt(artist="National", album="Boxer", image_url="http://img/other.jpg"),
        AlbumArt(artist="The National", album="Boxer", image_url="http://img/boxer.jpg"),
        ArtistTags(artist="National", tags=["rock"]),
        ArtistTags(artist="The National", tags=[]),
    ])
    await db_session.flush()

    await merge_spellings(db_session, user.id, "The National", ["National"])

    art = await db_session.scalar(
        select(AlbumArt.image_url).where(AlbumArt.artist == "The National")
    )
    tags = await db_session.scalar(
        select(ArtistTags.tags).where(ArtistTags.artist == "The National")
    )
    assert art == "http://img/boxer.jpg"
    assert tags == ["rock"]


async def test_suggestions_group_spellings_by_their_key_with_listen_counts(db_session):
    user = await _user(db_session)
    await upsert_listens(db_session, user.id, [
        _s("The National", "Fake Empire", 0),
        _s("The National", "Slow Show", 1),
        _s("National", "Mistaken for Strangers", 2),
        _s("Sigur Ros", "Hoppípolla", 3),
        _s("Sigur Rós", "Glósóli", 4),
        _s("Sigur Rós", "Svefn-g-englar", 5),
        _s("Radiohead", "Reckoner", 6),
    ])

    assert await suggestions(db_session, user.id) == [
        {
            "names": [
                {"artist": "Sigur Rós", "listens": 2},
                {"artist": "Sigur Ros", "listens": 1},
            ],
            "listens": 3,
        },
        {
            "names": [
                {"artist": "The National", "listens": 2},
                {"artist": "National", "listens": 1},
            ],
            "listens": 3,
        },
    ]


async def test_merged_spellings_are_no_longer_suggested(db_session):
    user = await _user(db_session)
    await upsert_listens(db_session, user.id, [
        _s("The National", "Fake Empire", 0),
        _s("National", "Mistaken for Strangers", 2),
    ])
    await merge_spellings(db_session, user.id, "The National", ["National"])

    assert await suggestions(db_session, user.id) == []


async def test_suggestions_only_look_at_the_users_own_listens(db_session):
    alice = await _user(db_session, "alice")
    bob = await _user(db_session, "bob")
    await upsert_listens(db_session, alice.id, [_s("The National", "Fake Empire", 0)])
    await upsert_listens(db_session, bob.id, [_s("National", "Fake Empire", 0)])

    assert await suggestions(db_session, alice.id) == []
