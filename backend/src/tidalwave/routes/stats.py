from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from tidalwave.deps import get_session
from tidalwave.stats import queries
from tidalwave.stats.scope import Scope, previous_range


def make_stats_router(scope_dep) -> APIRouter:
    router = APIRouter(tags=["stats"])

    @router.get("/top-artists")
    async def top_artists(
        limit: int = Query(20, ge=1, le=500),
        scope: Scope = Depends(scope_dep),
        session: AsyncSession = Depends(get_session),
    ) -> list[dict]:
        return await queries.top_artists(session, scope, limit=limit)

    @router.get("/top-tracks")
    async def top_tracks(
        limit: int = Query(20, ge=1, le=500),
        scope: Scope = Depends(scope_dep),
        session: AsyncSession = Depends(get_session),
    ) -> list[dict]:
        return await queries.top_tracks(session, scope, limit=limit)

    @router.get("/top-albums")
    async def top_albums(
        limit: int = Query(20, ge=1, le=500),
        scope: Scope = Depends(scope_dep),
        session: AsyncSession = Depends(get_session),
    ) -> list[dict]:
        return await queries.top_albums(session, scope, limit=limit)

    @router.get("/clock")
    async def clock(
        scope: Scope = Depends(scope_dep),
        session: AsyncSession = Depends(get_session),
    ) -> list[int]:
        return await queries.listening_clock(session, scope)

    @router.get("/weekday")
    async def weekday(
        scope: Scope = Depends(scope_dep),
        session: AsyncSession = Depends(get_session),
    ) -> list[int]:
        return await queries.listening_weekday(session, scope)

    @router.get("/history")
    async def history(
        bucket: Literal["day", "week", "month"] = "day",
        scope: Scope = Depends(scope_dep),
        session: AsyncSession = Depends(get_session),
    ) -> list[dict]:
        return await queries.listens_over_time(session, scope, bucket=bucket)

    @router.get("/recent")
    async def recent(
        limit: int = Query(50, ge=1, le=500),
        scope: Scope = Depends(scope_dep),
        session: AsyncSession = Depends(get_session),
    ) -> list[dict]:
        return await queries.recent_listens(session, scope, limit=limit)

    @router.get("/metrics-over-time")
    async def metrics_over_time(
        bucket: Literal["day", "week", "month"] = "day",
        scope: Scope = Depends(scope_dep),
        session: AsyncSession = Depends(get_session),
    ) -> list[dict]:
        return await queries.metrics_over_time(session, scope, bucket=bucket)

    @router.get("/summary")
    async def summary(
        compare: bool = False,
        calendar: Literal["week", "month", "year"] | None = None,
        scope: Scope = Depends(scope_dep),
        session: AsyncSession = Depends(get_session),
    ) -> dict:
        current = await queries.summary_stats(session, scope)
        if not compare:
            return current
        previous = None
        if scope.since is not None and not scope.shared:
            since, until = previous_range(
                scope.tz, scope.since, scope.until, calendar, datetime.now(UTC)
            )
            previous = await queries.summary_stats(
                session, replace(scope, since=since, until=until)
            )
        return {**current, "previous": previous}

    return router
