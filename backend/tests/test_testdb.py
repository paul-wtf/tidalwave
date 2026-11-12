from conftest import TEST_DB_URL
from sqlalchemy.engine import make_url

from tidalwave.config import Settings

DEV = "postgresql+asyncpg://tidalwave:tidalwave@localhost:5432/tidalwave"


def test_the_suite_never_runs_on_the_development_database():
    assert make_url(TEST_DB_URL).database != make_url(Settings().database_url).database
    assert str(make_url(TEST_DB_URL).database).endswith("_test")


def test_the_test_database_is_named_after_the_configured_one():
    from testdb import derive_test_url

    assert derive_test_url(DEV) == DEV + "_test"
    assert derive_test_url(
        "postgresql+asyncpg://ci:secret@db.example:6543/tracker"
    ) == "postgresql+asyncpg://ci:secret@db.example:6543/tracker_test"


def test_a_url_that_already_names_a_test_database_is_kept():
    from testdb import derive_test_url

    assert derive_test_url(DEV + "_test") == DEV + "_test"
