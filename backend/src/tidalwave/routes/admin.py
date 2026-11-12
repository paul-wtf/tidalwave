from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tidalwave.auth import allowlist
from tidalwave.auth.service import delete_account
from tidalwave.auth.session import admin_user
from tidalwave.config import Settings
from tidalwave.deps import get_session, get_settings
from tidalwave.models.db import Listen, SyncState, User

router = APIRouter(prefix="/auth/admin", tags=["admin"])

_USERNAME = re.compile(r"[A-Za-z0-9_.-]{1,64}")


class AllowlistAdd(BaseModel):
    username: str

    @field_validator("username")
    @classmethod
    def _username(cls, value: str) -> str:
        value = value.strip()
        if not _USERNAME.fullmatch(value):
            raise ValueError("Not a Last.fm username")
        return value


def _entry(entry: allowlist.Entry) -> dict:
    return {"username": entry.username, "fixed": entry.fixed, "added_at": entry.added_at}


@router.get("/users")
async def list_users(
    _: User = Depends(admin_user), session: AsyncSession = Depends(get_session)
) -> list[dict]:
    listens = (
        select(Listen.user_id, func.count().label("n")).group_by(Listen.user_id).subquery()
    )
    rows = await session.execute(
        select(User, func.coalesce(listens.c.n, 0), SyncState.last_synced_at)
        .outerjoin(listens, listens.c.user_id == User.id)
        .outerjoin(SyncState, SyncState.user_id == User.id)
        .order_by(User.created_at, User.id)
    )
    return [
        {
            "id": user.id,
            "username": user.lastfm_username,
            "is_admin": user.is_admin,
            "disconnected": user.disconnected,
            "created_at": user.created_at,
            "listens": int(count),
            "last_synced_at": synced,
        }
        for user, count, synced in rows.all()
    ]


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: int,
    admin: User = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    if user_id == admin.id:
        raise HTTPException(status_code=409, detail="Delete your own account from the user menu")
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="No such user")
    await delete_account(session, user)
    return Response(status_code=204)


@router.get("/allowlist")
async def list_allowlist(
    _: User = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    found = await allowlist.entries(session, settings.registration_allowlist)
    return {"mode": settings.registration_mode, "entries": [_entry(e) for e in found]}


@router.post("/allowlist", status_code=201)
async def add_allowlist_entry(
    body: AllowlistAdd,
    _: User = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    try:
        entry = await allowlist.add(session, settings.registration_allowlist, body.username)
    except allowlist.AlreadyListed as e:
        raise HTTPException(status_code=409, detail="Already on the allowlist") from e
    return _entry(entry)


@router.delete("/allowlist/{username}", status_code=204)
async def remove_allowlist_entry(
    username: str,
    _: User = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> Response:
    try:
        removed = await allowlist.remove(session, settings.registration_allowlist, username)
    except allowlist.FixedEntry as e:
        raise HTTPException(
            status_code=409, detail="Set in TIDALWAVE_REGISTRATION_ALLOWLIST"
        ) from e
    if not removed:
        raise HTTPException(status_code=404, detail="Not on the allowlist")
    return Response(status_code=204)
