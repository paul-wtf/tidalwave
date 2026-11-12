from __future__ import annotations

import secrets
from dataclasses import replace

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from tidalwave.auth.session import current_user
from tidalwave.deps import get_session
from tidalwave.models.db import CompareInvite, ComparePair, User
from tidalwave.stats.compare import artist_counts, compare
from tidalwave.stats.scope import Scope, own_scope

router = APIRouter(prefix="/comparisons", tags=["comparisons"])


def _open_invite(token: str):
    return and_(
        CompareInvite.token == token,
        CompareInvite.revoked_at.is_(None),
        CompareInvite.accepted_at.is_(None),
    )


def _member(user_id: int):
    return or_(ComparePair.low_user_id == user_id, ComparePair.high_user_id == user_id)


def _partner_id(pair: ComparePair, user_id: int) -> int:
    return pair.high_user_id if pair.low_user_id == user_id else pair.low_user_id


async def _pair_payload(session: AsyncSession, pair: ComparePair, user_id: int) -> dict:
    partner = await session.get(User, _partner_id(pair, user_id))
    return {
        "id": pair.id,
        "partner": partner.lastfm_username if partner is not None else None,
        "created_at": pair.created_at,
    }


async def _own_pair(session: AsyncSession, pair_id: int, user: User) -> ComparePair:
    pair = await session.scalar(
        select(ComparePair).where(ComparePair.id == pair_id, _member(user.id))
    )
    if pair is None:
        raise HTTPException(status_code=404, detail="No such comparison")
    return pair


@router.get("")
async def overview(
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> dict:
    pairs = (await session.execute(
        select(ComparePair).where(_member(user.id)).order_by(ComparePair.created_at.desc())
    )).scalars().all()
    invites = (await session.execute(
        select(CompareInvite)
        .where(
            CompareInvite.user_id == user.id,
            CompareInvite.revoked_at.is_(None),
            CompareInvite.accepted_at.is_(None),
        )
        .order_by(CompareInvite.created_at.desc(), CompareInvite.id.desc())
    )).scalars().all()
    return {
        "pairs": [await _pair_payload(session, p, user.id) for p in pairs],
        "invites": [{"token": i.token, "created_at": i.created_at} for i in invites],
    }


@router.post("/invites", status_code=201)
async def create_invite(
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> dict:
    invite = CompareInvite(token=secrets.token_urlsafe(32), user_id=user.id)
    session.add(invite)
    await session.flush()
    await session.refresh(invite)
    return {"token": invite.token, "created_at": invite.created_at}


@router.get("/invites/{token}")
async def open_invite(
    token: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    invite = await session.scalar(select(CompareInvite).where(_open_invite(token)))
    inviter = await session.get(User, invite.user_id) if invite is not None else None
    if invite is None or inviter is None:
        raise HTTPException(status_code=404, detail="Invite not found")
    return {"inviter": inviter.lastfm_username, "own": inviter.id == user.id}


@router.post("/invites/{token}/accept", status_code=201)
async def accept_invite(
    token: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    invite = await session.scalar(select(CompareInvite).where(_open_invite(token)))
    if invite is None:
        raise HTTPException(status_code=404, detail="Invite not found")
    if invite.user_id == user.id:
        raise HTTPException(status_code=409, detail="This is your own invite")
    low, high = sorted((invite.user_id, user.id))
    existing = await session.scalar(
        select(ComparePair.id).where(
            ComparePair.low_user_id == low, ComparePair.high_user_id == high
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="You already compare with each other")
    claimed = await session.scalar(
        update(CompareInvite)
        .where(_open_invite(token))
        .values(accepted_at=func.now())
        .returning(CompareInvite.id)
    )
    if claimed is None:
        raise HTTPException(status_code=404, detail="Invite not found")
    pair = ComparePair(low_user_id=low, high_user_id=high)
    session.add(pair)
    await session.flush()
    await session.refresh(pair)
    return await _pair_payload(session, pair, user.id)


@router.delete("/invites/{token}", status_code=204)
async def revoke_invite(
    token: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    revoked = await session.scalar(
        update(CompareInvite)
        .where(_open_invite(token), CompareInvite.user_id == user.id)
        .values(revoked_at=func.now())
        .returning(CompareInvite.id)
    )
    if revoked is None:
        raise HTTPException(status_code=404, detail="Invite not found")
    return Response(status_code=204)


@router.get("/{pair_id}")
async def comparison(
    pair_id: int,
    limit: int = Query(10, ge=1, le=50),
    scope: Scope = Depends(own_scope),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    pair = await _own_pair(session, pair_id, user)
    payload = await _pair_payload(session, pair, user.id)
    you = await artist_counts(session, scope)
    partner = await artist_counts(
        session, replace(scope, user_id=_partner_id(pair, user.id))
    )
    return {**payload, **compare(you, partner, limit=limit)}


@router.delete("/{pair_id}", status_code=204)
async def end_pair(
    pair_id: int,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    pair = await _own_pair(session, pair_id, user)
    await session.delete(pair)
    await session.flush()
    return Response(status_code=204)
