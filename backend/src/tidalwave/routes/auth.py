from __future__ import annotations

import csv
import io
import json
import re
from collections.abc import AsyncIterator
from datetime import UTC
from typing import Literal
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, text, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from tidalwave.auth.registration import RegistrationDenied
from tidalwave.auth.service import delete_account, upsert_user_from_session
from tidalwave.auth.session import COOKIE_NAME, SessionCodec, current_user
from tidalwave.models.db import Listen, User
from tidalwave.config import Settings
from tidalwave.deps import get_lastfm_client, get_session, get_settings
from tidalwave.ingest.poller import ingest_user_now
from tidalwave.ingest.repository import get_sync_state
from tidalwave.lastfm.client import LastfmClient, LastfmError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login")
async def login(settings: Settings = Depends(get_settings)) -> RedirectResponse:
    cb = f"{settings.public_base_url}/auth/callback"
    url = "https://www.last.fm/api/auth/?" + urlencode(
        {"api_key": settings.lastfm_api_key, "cb": cb}
    )
    return RedirectResponse(url)


@router.get("/callback")
async def callback(
    token: str,
    background: BackgroundTasks,
    request: Request,
    client: LastfmClient = Depends(get_lastfm_client),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    try:
        username, session_key = await client.get_session(token)
    except LastfmError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    try:
        user = await upsert_user_from_session(
            session, username, session_key,
            mode=settings.registration_mode, allowlist=settings.registration_allowlist,
        )
    except RegistrationDenied as e:
        raise HTTPException(status_code=403, detail="Registration not allowed") from e

    background.add_task(
        ingest_user_now, request.app.state.session_factory, client, user.id
    )

    codec = SessionCodec(settings.session_secret)
    resp = RedirectResponse("/", status_code=307)
    resp.set_cookie(
        COOKIE_NAME, codec.encode(user.id), httponly=True, samesite="lax",
        secure=settings.public_base_url.startswith("https"),
    )
    return resp


@router.post("/logout")
async def logout() -> Response:
    resp = Response(status_code=204)
    resp.delete_cookie(COOKIE_NAME)
    return resp


@router.get("/config")
async def config(settings: Settings = Depends(get_settings)) -> dict:
    """Settings the static frontend needs, readable without a session so that
    share views get them too."""
    return {"linkhop_url": settings.linkhop_url or None}


class MeUpdate(BaseModel):
    timezone: str


async def _me_payload(session: AsyncSession, user: User) -> dict:
    state = await get_sync_state(session, user.id)
    return {
        "username": user.lastfm_username,
        "is_admin": user.is_admin,
        "timezone": user.timezone,
        "disconnected": user.disconnected,
        "last_synced_at": state.last_synced_at.isoformat() if state and state.last_synced_at else None,
        "last_played_at": state.last_played_at.isoformat() if state and state.last_played_at else None,
    }


@router.get("/me")
async def me(
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> dict:
    return await _me_payload(session, user)


@router.patch("/me")
async def update_me(
    body: MeUpdate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        ZoneInfo(body.timezone)
    except (KeyError, ValueError, OSError) as e:
        raise HTTPException(status_code=422, detail="Unknown timezone") from e
    known = await session.scalar(
        text("SELECT 1 FROM pg_timezone_names WHERE name = :tz"), {"tz": body.timezone}
    )
    if known is None:
        raise HTTPException(status_code=422, detail="Unknown timezone")
    user.timezone = body.timezone
    await session.flush()
    return await _me_payload(session, user)


@router.delete("/me", status_code=204)
async def delete_me(
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> Response:
    await delete_account(session, user)
    resp = Response(status_code=204)
    resp.delete_cookie(COOKIE_NAME)
    return resp


EXPORT_BATCH = 5000
_EXPORT_FIELDS = (
    "played_at", "artist", "track", "album", "track_mbid", "artist_mbid", "album_mbid",
    "duration_sec",
)


async def _export_batches(session: AsyncSession, user_id: int) -> AsyncIterator[list[tuple]]:
    after: tuple | None = None
    while True:
        stmt = (
            select(
                Listen.played_at, Listen.artist, Listen.track_title, Listen.album,
                Listen.track_mbid, Listen.artist_mbid, Listen.album_mbid, Listen.duration_sec,
                Listen.id,
            )
            .where(Listen.user_id == user_id)
            .order_by(Listen.played_at, Listen.id)
            .limit(EXPORT_BATCH)
        )
        if after is not None:
            stmt = stmt.where(tuple_(Listen.played_at, Listen.id) > tuple_(*after))
        rows = (await session.execute(stmt)).all()
        if not rows:
            return
        yield [(row[0].astimezone(UTC).isoformat(), *row[1:8]) for row in rows]
        after = (rows[-1][0], rows[-1][8])


async def _export_csv(session: AsyncSession, user_id: int) -> AsyncIterator[str]:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(_EXPORT_FIELDS)
    yield buffer.getvalue()
    async for batch in _export_batches(session, user_id):
        buffer.seek(0)
        buffer.truncate()
        writer.writerows(batch)
        yield buffer.getvalue()


async def _export_json(session: AsyncSession, user_id: int) -> AsyncIterator[str]:
    separator = "[\n"
    async for batch in _export_batches(session, user_id):
        yield separator + ",\n".join(
            json.dumps(dict(zip(_EXPORT_FIELDS, row)), ensure_ascii=False) for row in batch
        )
        separator = ",\n"
    yield "[]\n" if separator == "[\n" else "\n]\n"


@router.get("/export")
async def export(
    format: Literal["csv", "json"],
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    name = re.sub(r"[^A-Za-z0-9_.-]", "_", user.lastfm_username)
    body = _export_csv(session, user.id) if format == "csv" else _export_json(session, user.id)
    return StreamingResponse(
        body,
        media_type="text/csv; charset=utf-8" if format == "csv" else "application/json",
        headers={"Content-Disposition": f'attachment; filename="tidalwave-{name}.{format}"'},
    )
