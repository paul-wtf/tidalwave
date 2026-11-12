from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from tidalwave.auth.session import current_user
from tidalwave.deps import get_session
from tidalwave.models.db import User
from tidalwave.spellings.service import (
    MergeError,
    list_merges,
    merge_spellings,
    suggestions,
    unmerge,
)

router = APIRouter(prefix="/merges", tags=["merges"])


class MergeCreate(BaseModel):
    canonical: str = Field(max_length=500)
    variants: list[str] = Field(max_length=50)


async def _overview(session: AsyncSession, user_id: int) -> dict:
    return {
        "suggestions": await suggestions(session, user_id),
        "merges": await list_merges(session, user_id),
    }


@router.get("")
async def spellings(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await _overview(session, user.id)


@router.post("", status_code=201)
async def create_merge(
    body: MergeCreate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        await merge_spellings(session, user.id, body.canonical, body.variants)
    except MergeError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return await _overview(session, user.id)


@router.delete("")
async def remove_merge(
    canonical: str,
    variant: str | None = None,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if await unmerge(session, user.id, canonical, variant) == 0:
        raise HTTPException(status_code=404, detail="No such merge")
    return await _overview(session, user.id)
