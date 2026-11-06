from datetime import UTC, date, datetime

import pytest
from fastapi import HTTPException

from tidalwave.stats.scope import intersect, resolve_range


def test_resolve_range_local_midnights_across_dst():
    got = resolve_range(
        "Europe/Berlin", since=None, until=None, start=date(2026, 10, 1), end=date(2026, 11, 1)
    )
    assert got == (datetime(2026, 9, 30, 22, tzinfo=UTC), datetime(2026, 10, 31, 23, tzinfo=UTC))


def test_resolve_range_passes_instants_through():
    since = datetime(2026, 1, 1, tzinfo=UTC)
    until = datetime(2026, 2, 1, tzinfo=UTC)
    got = resolve_range("Europe/Berlin", since=since, until=until, start=None, end=None)
    assert got == (since, until)
    assert resolve_range("UTC", since=None, until=None, start=None, end=None) == (None, None)


def test_resolve_range_rejects_mixed_forms():
    with pytest.raises(HTTPException) as exc:
        resolve_range(
            "UTC", since=datetime(2026, 1, 1, tzinfo=UTC), until=None,
            start=date(2026, 1, 1), end=None,
        )
    assert exc.value.status_code == 422


def test_intersect_never_widens():
    floor = datetime(2026, 1, 1, tzinfo=UTC)
    ceiling = datetime(2026, 2, 1, tzinfo=UTC)
    wide = (datetime(2025, 6, 1, tzinfo=UTC), datetime(2027, 1, 1, tzinfo=UTC))
    assert intersect(*wide, floor, ceiling) == (floor, ceiling)
    assert intersect(None, None, floor, ceiling) == (floor, ceiling)
    assert intersect(*wide, None, None) == wide
