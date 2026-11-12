from __future__ import annotations

from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from tidalwave.db import make_engine, make_session_factory
from tidalwave.deps import get_settings
from tidalwave.routes import auth, health, share
from tidalwave.routes.stats import make_stats_router
from tidalwave.stats.scope import own_scope, shared_scope


class SharedCors:
    """CORS for /shared/ only: a share is public by its token, so any origin may
    read it. Everything else is tied to the session cookie and stays same-origin."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.cors = CORSMiddleware(app, allow_origins=["*"], allow_methods=["GET"])

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        shared = scope["type"] == "http" and scope["path"].startswith("/shared/")
        await (self.cors if shared else self.app)(scope, receive, send)


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
    app.add_middleware(SharedCors)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(make_stats_router(own_scope), prefix="/stats")
    app.include_router(make_stats_router(shared_scope), prefix="/shared/{token}")
    app.include_router(share.router)
    return app


app = create_app()
