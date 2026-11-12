import os
import subprocess
import sys
from pathlib import Path

import asyncpg
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from conftest import TEST_DB_URL
from sqlalchemy.engine import make_url

from tidalwave.models.db import Base

BACKEND = Path(__file__).resolve().parents[1]


def _upgrade_sql(revisions: str) -> str:
    # Offline mode prints the DDL instead of running it, so the test can run it
    # inside a scratch schema. The role of the test database may not create
    # databases, and alembic's online mode has no way to pick a schema.
    return subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", revisions, "--sql"],
        cwd=BACKEND, check=True, capture_output=True, text=True,
    ).stdout


def _revisions() -> tuple[str, str]:
    script = ScriptDirectory.from_config(Config(str(BACKEND / "alembic.ini")))
    head = script.get_current_head()
    assert head is not None
    previous = script.get_revision(head).down_revision
    assert isinstance(previous, str)
    return previous, head


@pytest.fixture
async def scratch():
    url = make_url(TEST_DB_URL)
    schema = f"migration_test_{os.getpid()}"
    conn = await asyncpg.connect(
        host=url.host, port=url.port, user=url.username, password=url.password,
        database=url.database,
    )
    await conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
    await conn.execute(f'CREATE SCHEMA "{schema}"')
    await conn.execute(f'SET search_path TO "{schema}"')
    try:
        yield conn, schema
    finally:
        await conn.execute(f'DROP SCHEMA "{schema}" CASCADE')
        await conn.close()


async def test_head_upgrades_a_database_at_the_previous_revision(scratch):
    conn, _ = scratch
    previous, head = _revisions()
    await conn.execute(_upgrade_sql(previous))
    await conn.execute(
        "INSERT INTO users (lastfm_username, lastfm_session_key) VALUES ('alice', 'sk')"
    )
    await conn.execute(
        "INSERT INTO listens (user_id, track_title, artist, played_at) "
        "SELECT id, 'Nightcall', 'Kavinsky', '2026-10-01T00:00:00Z' FROM users"
    )

    await conn.execute(_upgrade_sql(f"{previous}:{head}"))

    assert await conn.fetchval("SELECT version_num FROM alembic_version") == head
    assert await conn.fetchval("SELECT count(*) FROM listens") == 1
    await conn.execute(
        "INSERT INTO users (lastfm_username, lastfm_session_key) VALUES ('bob', 'sk')"
    )
    await conn.execute(
        "INSERT INTO compare_pairs (low_user_id, high_user_id) "
        "SELECT min(id), max(id) FROM users"
    )
    assert await conn.fetchval("SELECT count(*) FROM compare_pairs") == 1
    with pytest.raises(asyncpg.CheckViolationError):
        await conn.execute(
            "INSERT INTO compare_pairs (low_user_id, high_user_id) "
            "SELECT max(id), min(id) FROM users"
        )


async def test_migrations_create_the_columns_the_models_declare(scratch):
    conn, schema = scratch
    await conn.execute(_upgrade_sql("head"))
    rows = await conn.fetch(
        "SELECT table_name, column_name FROM information_schema.columns "
        "WHERE table_schema = $1 AND table_name <> 'alembic_version'",
        schema,
    )
    migrated = {(r["table_name"], r["column_name"]) for r in rows}
    declared = {
        (table.name, column.name)
        for table in Base.metadata.tables.values()
        for column in table.columns
    }
    assert migrated == declared
