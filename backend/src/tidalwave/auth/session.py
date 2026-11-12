from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from itsdangerous import BadSignature, URLSafeSerializer
from sqlalchemy.ext.asyncio import AsyncSession

from tidalwave.deps import get_session, get_settings
from tidalwave.models.db import User

COOKIE_NAME = "tw_session"


class SessionCodec:
    def __init__(self, secret: str) -> None:
        self._s = URLSafeSerializer(secret, salt="tidalwave-session")

    def encode(self, user_id: int) -> str:
        return self._s.dumps({"uid": user_id})

    def decode(self, token: str) -> int | None:
        try:
            data = self._s.loads(token)
        except BadSignature:
            return None
        uid = data.get("uid")
        return uid if isinstance(uid, int) else None


async def current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
    settings=Depends(get_settings),
) -> User:
    token = request.cookies.get(COOKIE_NAME)
    uid = SessionCodec(settings.session_secret).decode(token) if token else None
    user = await session.get(User, uid) if uid is not None else None
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


async def admin_user(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admins only")
    return user
