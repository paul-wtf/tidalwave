import pytest

from tidalwave.spellings.normalize import spelling_key, track_key


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("The National", "National"),
        ("the national", "The National"),
        ("Sigur Ros", "Sigur Rós"),
        ("Kraftklub", "KRAFTKLUB"),
        ("A & B", "A and B"),
        ("Simon & Garfunkel", "Simon and Garfunkel"),
        ("X feat. Y", "X"),
        ("X ft. Y", "X"),
        ("X featuring Y", "X"),
        ("X (feat. Y)", "X"),
        ("AC/DC", "ACDC"),
        ("Sufjan  Stevens", "Sufjan Stevens"),
        ("Röyksopp", "Royksopp"),
        ("Mø", "MO"),
        ("Beyoncé", "Beyonce"),
        ("Tyler, The Creator", "Tyler The Creator"),
    ],
)
def test_spellings_of_one_artist_share_a_key(a, b):
    assert spelling_key(a) == spelling_key(b)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("The National", "The Nationals"),
        ("Low", "Lowe"),
        ("Theatre of Tragedy", "Atre of Tragedy"),
        ("Feathers", "Hers"),
    ],
)
def test_different_artists_keep_different_keys(a, b):
    assert spelling_key(a) != spelling_key(b)


def test_a_name_of_only_punctuation_still_has_a_key():
    assert spelling_key("!!!") == "!!!"
    assert spelling_key("!!!") != spelling_key("???")


def test_non_latin_names_are_kept():
    assert spelling_key("坂本龍一") == "坂本龍一"
    assert spelling_key("Кино") == spelling_key("КИНО")


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("Bloodbuzz Ohio", "bloodbuzz ohio"),
        ("Fake Plastic Trees - Remastered 2009", "Fake Plastic Trees"),
        ("Get Lucky (feat. Pharrell Williams)", "Get Lucky"),
        ("Hoppípolla", "Hoppipolla"),
        ("Song [Live]", "Song"),
    ],
)
def test_track_keys_ignore_versions_and_case(a, b):
    assert track_key(a) == track_key(b)


def test_track_key_keeps_the_leading_the():
    assert track_key("The Rip") != track_key("Rip")
