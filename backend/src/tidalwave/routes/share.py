from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends
from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncSession

from tidalwave.auth.session import current_user
from tidalwave.deps import get_session
from tidalwave.models.db import Share, User

router = APIRouter(tags=["share"])


@router.post("/shares", status_code=201)
async def create_share(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    token = secrets.token_urlsafe(32)
    session.add(Share(share_token=token, user_id=user.id))
    await session.flush()
    return {"share_token": token}


@router.delete("/shares/{token}", status_code=204)
async def revoke_share(
    token: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    await session.execute(
        update(Share)
        .where(Share.share_token == token, Share.user_id == user.id, Share.revoked_at.is_(None))
        .values(revoked_at=func.now())
    )
