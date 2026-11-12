import io
import os
from pathlib import Path

import asyncpg
import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.engine import make_url

from tidalwave.models.db import Base

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"


def _config(buffer: io.StringIO | None = None) -> Config:
    # Without an ini file, env.py leaves the logging setup of pytest alone.
    config = Config(output_buffer=buffer)
    config.set_main_option("script_location", str(MIGRATIONS))
    return config


def _chain() -> list[tuple[str, str]]:
    """(down revision or "base", revision) for every step, oldest first."""
    script = ScriptDirectory.from_config(_config())
    assert len(script.get_heads()) == 1, "the migrations have more than one head"
    steps = []
    for rev in reversed(list(script.walk_revisions("base", "heads"))):
        down = rev.down_revision
        assert down is None or isinstance(down, str), f"{rev.revision} is a merge"
        steps.append((down or "base", rev.revision))
    return steps


def _sql(direction: str, revisions: str) -> str:
    # Offline mode prints the DDL instead of running it, so the test can run it
    # inside a scratch schema. The role of the test database may not create
    # databases, and alembic's online mode has no way to pick a schema.
    buffer = io.StringIO()
    getattr(command, direction)(_config(buffer), revisions, sql=True)
    return buffer.getvalue()


@pytest.fixture
async def scratch(test_database):
    url = make_url(test_database)
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


async def _schema(conn, schema: str) -> dict[str, list]:
    columns = await conn.fetch(
        "SELECT table_name, column_name, data_type, character_maximum_length, is_nullable, "
        "column_default FROM information_schema.columns "
        "WHERE table_schema = $1 AND table_name <> 'alembic_version' ORDER BY 1, 2",
        schema,
    )
    indexes = await conn.fetch(
        "SELECT indexname, indexdef FROM pg_indexes "
        "WHERE schemaname = $1 AND tablename <> 'alembic_version' ORDER BY 1",
        schema,
    )
    constraints = await conn.fetch(
        "SELECT c.conrelid::regclass::text, c.conname, pg_get_constraintdef(c.oid) "
        "FROM pg_constraint c JOIN pg_namespace n ON n.oid = c.connamespace "
        "WHERE n.nspname = $1 AND c.conrelid::regclass::text <> 'alembic_version' ORDER BY 1, 2",
        schema,
    )
    return {
        "columns": [tuple(r) for r in columns],
        "indexes": [tuple(r) for r in indexes],
        "constraints": [tuple(r) for r in constraints],
    }


async def test_every_migration_downgrades_and_upgrades_again(scratch):
    conn, schema = scratch
    for down, rev in _chain():
        before = await _schema(conn, schema)
        upgrade = _sql("upgrade", f"{down}:{rev}" if down != "base" else rev)
        await conn.execute(upgrade)
        after = await _schema(conn, schema)

        await conn.execute(_sql("downgrade", f"{rev}:{down}"))
        assert await _schema(conn, schema) == before, f"downgrade of {rev}"

        await conn.execute(upgrade)
        assert await _schema(conn, schema) == after, f"second upgrade to {rev}"
        assert await conn.fetchval("SELECT version_num FROM alembic_version") == rev


async def _columns(conn, schema: str, table: str) -> set[str]:
    rows = await conn.fetch(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = $1 AND table_name = $2",
        schema, table,
    )
    return {r["column_name"] for r in rows}


async def _assert_listen_kept(conn, schema: str, rev: str) -> None:
    assert await conn.fetchval("SELECT count(*) FROM users") == 1, rev
    assert await conn.fetchval("SELECT count(*) FROM listens") == 1, rev
    listen = await conn.fetchrow("SELECT * FROM listens")
    assert (listen["artist"], listen["track_title"]) == ("Kavinsky", "Nightcall"), rev
    columns = await _columns(conn, schema, "listens")
    if "artist_raw" in columns:
        assert listen["artist_raw"] == "Kavinsky", rev
    if "source" in columns:
        assert listen["source"] == "lastfm", rev


async def test_a_listen_from_the_first_schema_survives_every_step(scratch):
    conn, schema = scratch
    chain = _chain()
    first = chain[0][1]
    await conn.execute(_sql("upgrade", first))
    await conn.execute(
        "INSERT INTO users (lastfm_username, lastfm_session_key) VALUES ('alice', 'sk')"
    )
    await conn.execute(
        "INSERT INTO listens (user_id, track_title, artist, played_at) "
        "SELECT id, 'Nightcall', 'Kavinsky', '2026-10-01T00:00:00Z' FROM users"
    )

    for down, rev in chain[1:]:
        await conn.execute(_sql("upgrade", f"{down}:{rev}"))
        await _assert_listen_kept(conn, schema, rev)
    for down, rev in reversed(chain[1:]):
        await conn.execute(_sql("downgrade", f"{rev}:{down}"))
        await _assert_listen_kept(conn, schema, down)


async def test_migrations_create_the_columns_the_models_declare(scratch):
    conn, schema = scratch
    await conn.execute(_sql("upgrade", "head"))
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
