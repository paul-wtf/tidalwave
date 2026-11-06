from __future__ import annotations

from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tidalwave.auth.registration import RegistrationDenied
from tidalwave.auth.service import upsert_user_from_session
from tidalwave.auth.session import COOKIE_NAME, SessionCodec, current_user
from tidalwave.models.db import User
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
    known = await session.scalar(
        text("SELECT 1 FROM pg_timezone_names WHERE name = :tz"), {"tz": body.timezone}
    )
    if known is None:
        raise HTTPException(status_code=422, detail="Unknown timezone")
    try:
        ZoneInfo(body.timezone)
    except KeyError as e:
        raise HTTPException(status_code=422, detail="Unknown timezone") from e
    user.timezone = body.timezone
    await session.flush()
    return await _me_payload(session, user)
