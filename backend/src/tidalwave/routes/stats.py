from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from tidalwave.deps import get_session
from tidalwave.stats import details, insights, queries
from tidalwave.stats.scope import Scope, previous_range


def _found(detail: dict | None) -> dict:
    if detail is None:
        raise HTTPException(status_code=404, detail="Not found")
    return detail


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
        artist: str | None = None,
        album: str | None = None,
        track: str | None = None,
        scope: Scope = Depends(scope_dep),
        session: AsyncSession = Depends(get_session),
    ) -> list[dict]:
        return await queries.top_tracks(
            session, scope, limit=limit, artist=artist, album=album, track=track
        )

    @router.get("/top-albums")
    async def top_albums(
        limit: int = Query(20, ge=1, le=500),
        artist: str | None = None,
        album: str | None = None,
        track: str | None = None,
        scope: Scope = Depends(scope_dep),
        session: AsyncSession = Depends(get_session),
    ) -> list[dict]:
        return await queries.top_albums(
            session, scope, limit=limit, artist=artist, album=album, track=track
        )

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

    @router.get("/hour-weekday")
    async def hour_weekday(
        scope: Scope = Depends(scope_dep),
        session: AsyncSession = Depends(get_session),
    ) -> list[list[int]]:
        return await queries.listening_hour_weekday(session, scope)

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
        artist: str | None = None,
        album: str | None = None,
        track: str | None = None,
        scope: Scope = Depends(scope_dep),
        session: AsyncSession = Depends(get_session),
    ) -> list[dict]:
        return await queries.recent_listens(
            session, scope, limit=limit, artist=artist, album=album, track=track
        )

    @router.get("/metrics-over-time")
    async def metrics_over_time(
        bucket: Literal["day", "week", "month"] = "day",
        artist: str | None = None,
        album: str | None = None,
        track: str | None = None,
        scope: Scope = Depends(scope_dep),
        session: AsyncSession = Depends(get_session),
    ) -> list[dict]:
        return await queries.metrics_over_time(
            session, scope, bucket=bucket, artist=artist, album=album, track=track
        )

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

    @router.get("/artist")
    async def artist_detail(
        artist: str,
        scope: Scope = Depends(scope_dep),
        session: AsyncSession = Depends(get_session),
    ) -> dict:
        return _found(await details.artist_detail(session, scope, artist))

    @router.get("/album")
    async def album_detail(
        artist: str,
        album: str,
        scope: Scope = Depends(scope_dep),
        session: AsyncSession = Depends(get_session),
    ) -> dict:
        return _found(await details.album_detail(session, scope, artist, album))

    @router.get("/track")
    async def track_detail(
        artist: str,
        track: str,
        scope: Scope = Depends(scope_dep),
        session: AsyncSession = Depends(get_session),
    ) -> dict:
        return _found(await details.track_detail(session, scope, artist, track))

    @router.get("/discoveries")
    async def discoveries(
        limit: int = Query(20, ge=1, le=500),
        scope: Scope = Depends(scope_dep),
        session: AsyncSession = Depends(get_session),
    ) -> dict:
        return await insights.discoveries(session, scope, limit=limit)

    @router.get("/on-this-day")
    async def on_this_day(
        scope: Scope = Depends(scope_dep),
        session: AsyncSession = Depends(get_session),
    ) -> list[dict]:
        return await insights.on_this_day(session, scope)

    @router.get("/records")
    async def records(
        scope: Scope = Depends(scope_dep),
        session: AsyncSession = Depends(get_session),
    ) -> dict:
        return await insights.records(session, scope)

    @router.get("/milestones")
    async def milestones(
        scope: Scope = Depends(scope_dep),
        session: AsyncSession = Depends(get_session),
    ) -> dict:
        return await insights.milestones(session, scope)

    @router.get("/heatmap")
    async def heatmap(
        scope: Scope = Depends(scope_dep),
        session: AsyncSession = Depends(get_session),
    ) -> dict:
        return await insights.heatmap(session, scope)

    return router
