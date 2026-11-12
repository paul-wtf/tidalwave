import pytest

from tidalwave.stats.compare import compare


def test_overlap_sums_the_smaller_share_of_every_artist():
    you = {"A": 6, "B": 3, "C": 1}
    partner = {"A": 2, "B": 2, "D": 4}

    result = compare(you, partner, limit=10)

    assert result["overlap"] == pytest.approx(0.5)
    assert result["listens"] == {"you": 10, "partner": 8}
    assert result["shared_artists"] == 2


def test_overlap_is_symmetric_and_one_for_the_same_taste():
    a = {"A": 4, "B": 2}
    b = {"A": 2, "B": 1, "C": 0}
    assert compare(a, b, limit=10)["overlap"] == pytest.approx(1.0)
    x, y = {"A": 5, "B": 1}, {"B": 3, "C": 3}
    assert compare(x, y, limit=10)["overlap"] == pytest.approx(compare(y, x, limit=10)["overlap"])


def test_no_common_artist_is_zero_overlap():
    assert compare({"A": 3}, {"B": 3}, limit=10)["overlap"] == 0


def test_overlap_is_undefined_when_one_side_has_no_listens():
    result = compare({"A": 3}, {}, limit=10)
    assert result["overlap"] is None
    assert result["shared"] == []
    assert result["only_you"] == [{"artist": "A", "count": 3}]
    assert result["only_partner"] == []


def test_shared_artists_come_by_their_common_share_with_both_counts():
    you = {"A": 6, "B": 3, "C": 1, "E": 10}
    partner = {"A": 2, "B": 2, "D": 4, "E": 1}

    shared = compare(you, partner, limit=10)["shared"]

    assert shared == [
        {"artist": "A", "you": 6, "partner": 2},
        {"artist": "B", "you": 3, "partner": 2},
        {"artist": "E", "you": 10, "partner": 1},
    ]


def test_each_side_lists_what_the_other_did_not_hear_most_played_first():
    you = {"A": 1, "X": 2, "Y": 5, "Z": 2}
    partner = {"A": 1, "P": 7}

    result = compare(you, partner, limit=2)

    assert result["only_you"] == [{"artist": "Y", "count": 5}, {"artist": "X", "count": 2}]
    assert result["only_partner"] == [{"artist": "P", "count": 7}]


def test_spellings_of_one_artist_match_across_the_pair():
    you = {"The National": 4, "Beyonce": 1}
    partner = {"National": 2, "Beyoncé": 3}

    result = compare(you, partner, limit=10)

    assert result["shared_artists"] == 2
    assert result["overlap"] == pytest.approx(0.4 + 0.2)
    assert result["shared"] == [
        {"artist": "The National", "you": 4, "partner": 2},
        {"artist": "Beyonce", "you": 1, "partner": 3},
    ]
    assert result["only_you"] == [] and result["only_partner"] == []
    assert [s["artist"] for s in compare(partner, you, limit=10)["shared"]] == [
        "National", "Beyoncé",
    ]


def test_an_artist_only_one_side_played_keeps_that_sides_spelling():
    result = compare({"Sigur Ros": 2}, {"Sigur Rós": 1, "The xx": 4}, limit=10)

    assert result["shared"] == [{"artist": "Sigur Ros", "you": 2, "partner": 1}]
    assert result["only_partner"] == [{"artist": "The xx", "count": 4}]


def test_unmerged_spellings_on_one_side_count_together_under_the_most_played():
    you = {"The National": 3, "National": 1, "Muse": 2}
    partner = {"the national": 2, "Muse": 2}

    result = compare(you, partner, limit=10)

    assert result["shared_artists"] == 2
    assert result["listens"] == {"you": 6, "partner": 4}
    assert result["shared"][0] == {"artist": "The National", "you": 4, "partner": 2}
    assert result["only_you"] == []
