from __future__ import annotations

import secrets
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from tidalwave.auth.session import current_user
from tidalwave.deps import get_session
from tidalwave.models.db import Share, User
from tidalwave.stats.scope import resolve_range, user_tz

router = APIRouter(tags=["share"])


class ShareCreate(BaseModel):
    label: str | None = None
    range_from: datetime | None = None
    range_to: datetime | None = None
    start: date | None = None
    end: date | None = None


def _serialize(share: Share) -> dict:
    return {
        "share_token": share.share_token,
        "label": share.label,
        "range_from": share.range_from,
        "range_to": share.range_to,
        "created_at": share.created_at,
    }


@router.post("/shares", status_code=201)
async def create_share(
    body: ShareCreate | None = None,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    body = body or ShareCreate()
    lo, hi = resolve_range(
        user_tz(user),
        since=body.range_from,
        until=body.range_to,
        start=body.start,
        end=body.end,
    )
    if body.start is not None and hi is None:
        hi = datetime.now(UTC)
    if lo is not None and hi is not None and lo >= hi:
        raise HTTPException(status_code=422, detail="Range start must be before its end")
    share = Share(
        share_token=secrets.token_urlsafe(32),
        user_id=user.id,
        label=body.label,
        range_from=lo,
        range_to=hi,
    )
    session.add(share)
    await session.flush()
    await session.refresh(share)
    return _serialize(share)


@router.get("/shares")
async def list_shares(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    rows = await session.execute(
        select(Share)
        .where(Share.user_id == user.id, Share.revoked_at.is_(None))
        .order_by(Share.created_at.desc(), Share.id.desc())
    )
    return [_serialize(share) for share in rows.scalars()]


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
