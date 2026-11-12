from __future__ import annotations

import asyncpg
from sqlalchemy.engine import make_url


def derive_test_url(url: str) -> str:
    parsed = make_url(url)
    name = parsed.database or ""
    if name.endswith("_test"):
        return url
    return parsed.set(database=f"{name}_test").render_as_string(hide_password=False)


async def ensure_database(url: str) -> None:
    parsed = make_url(url)
    conn = await asyncpg.connect(
        host=parsed.host, port=parsed.port, user=parsed.username,
        password=parsed.password, database="postgres",
    )
    try:
        if await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", parsed.database):
            return
        try:
            await conn.execute(f'CREATE DATABASE "{parsed.database}"')
        except asyncpg.InsufficientPrivilegeError as e:
            raise RuntimeError(
                f"The test database {parsed.database} does not exist and "
                f"{parsed.username} may not create it. Create it once, for example "
                f"with: createdb -O {parsed.username} {parsed.database}"
            ) from e
    finally:
        await conn.close()
