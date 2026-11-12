import os

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from testdb import derive_test_url, ensure_database

from tidalwave.models.db import Base

TEST_DB_URL = derive_test_url(
    os.environ.get(
        "TIDALWAVE_TEST_DATABASE_URL",
        "postgresql+asyncpg://tidalwave:tidalwave@localhost:5432/tidalwave",
    )
)


@pytest.fixture(autouse=True)
def _isolate_env_file(tmp_path, monkeypatch):
    # pydantic-settings reads .env from CWD; keep tests from seeing local secrets.
    monkeypatch.chdir(tmp_path)


@pytest_asyncio.fixture(scope="session")
async def test_database() -> str:
    await ensure_database(TEST_DB_URL)
    return TEST_DB_URL


@pytest_asyncio.fixture(scope="session")
async def _engine(test_database):
    engine = create_async_engine(test_database, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(_engine):
    # Each test runs in a transaction rolled back at teardown — full isolation.
    connection = await _engine.connect()
    trans = await connection.begin()
    factory = async_sessionmaker(bind=connection, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        await session.close()
        await trans.rollback()
        await connection.close()


@pytest_asyncio.fixture
async def api(db_session, monkeypatch):
    monkeypatch.setenv("TIDALWAVE_LASTFM_API_KEY", "KEY")
    monkeypatch.setenv("TIDALWAVE_LASTFM_API_SECRET", "SECRET")
    monkeypatch.setenv("TIDALWAVE_SESSION_SECRET", "test-secret")
    monkeypatch.setenv("TIDALWAVE_REGISTRATION_MODE", "open")
    monkeypatch.setenv("TIDALWAVE_PUBLIC_BASE_URL", "http://test")
    monkeypatch.setenv("TIDALWAVE_DATABASE_URL", TEST_DB_URL)
    from tidalwave.deps import get_session, get_settings
    from tidalwave.main import create_app

    get_settings.cache_clear()
    app = create_app()

    async def _use_test_session():
        yield db_session

    app.dependency_overrides[get_session] = _use_test_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, app
    get_settings.cache_clear()
