from __future__ import annotations

from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from tidalwave.db import make_engine, make_session_factory
from tidalwave.deps import get_settings
from tidalwave.routes import auth, health, share
from tidalwave.routes.stats import make_stats_router
from tidalwave.stats.scope import own_scope, shared_scope


def create_app() -> FastAPI:
    settings = get_settings()
    engine = make_engine(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Resources are created eagerly below (so ASGITransport tests work without
        # lifespan events). Lifespan only disposes them on shutdown.
        yield
        await engine.dispose()
        await app.state.http.aclose()

    app = FastAPI(title="tidalwave", lifespan=lifespan)
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    app.state.http = httpx.AsyncClient(timeout=15.0)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(make_stats_router(own_scope), prefix="/stats")
    app.include_router(make_stats_router(shared_scope), prefix="/shared/{token}")
    app.include_router(share.router)
    return app


app = create_app()
