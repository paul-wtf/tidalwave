from __future__ import annotations

import tempfile
from pathlib import Path, PurePath

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tidalwave.auth.session import current_user
from tidalwave.config import Settings
from tidalwave.deps import get_session, get_session_factory, get_settings
from tidalwave.imports.service import (
    ImportBusy,
    active_import,
    run_import,
    serialize,
    start_import,
    undo_import,
)
from tidalwave.models.db import Import, User
from tidalwave.stats.scope import user_tz

router = APIRouter(prefix="/imports", tags=["imports"])

_BUSY = "An import is already running"


def _too_large(limit: int) -> HTTPException:
    return HTTPException(
        status_code=413, detail=f"The file is larger than {limit // (1024 * 1024)} MB"
    )


@router.post("", status_code=202)
async def upload(
    request: Request,
    background: BackgroundTasks,
    filename: str = Query(min_length=1, max_length=255),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
) -> dict:
    limit = settings.import_max_bytes
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > limit:
        raise _too_large(limit)
    if await active_import(session, user.id) is not None:
        raise HTTPException(status_code=409, detail=_BUSY)
    file = tempfile.NamedTemporaryFile(
        dir=settings.import_dir or None, prefix="tidalwave-import-", delete=False
    )
    path = Path(file.name)
    try:
        size = 0
        with file:
            async for chunk in request.stream():
                size += len(chunk)
                if size > limit:
                    raise _too_large(limit)
                file.write(chunk)
        if size == 0:
            raise HTTPException(status_code=422, detail="The file is empty")
        try:
            imp = await start_import(session, user.id, PurePath(filename).name or "upload")
        except ImportBusy as e:
            raise HTTPException(status_code=409, detail=_BUSY) from e
        await session.commit()
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    background.add_task(run_import, factory, imp.id, path, max_bytes=limit)
    return serialize(imp, user_tz(user))


@router.get("")
async def list_imports(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    await active_import(session, user.id)
    rows = await session.execute(
        select(Import)
        .where(Import.user_id == user.id)
        .order_by(Import.created_at.desc(), Import.id.desc())
    )
    return [serialize(imp, user_tz(user)) for imp in rows.scalars()]


@router.get("/{import_id}")
async def get_import(
    import_id: int,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    await active_import(session, user.id)
    imp = (await session.execute(
        select(Import).where(Import.id == import_id, Import.user_id == user.id)
    )).scalar_one_or_none()
    if imp is None:
        raise HTTPException(status_code=404, detail="Import not found")
    return serialize(imp, user_tz(user))


@router.delete("/{import_id}")
async def undo(
    import_id: int,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        imp = await undo_import(session, user.id, import_id)
    except ImportBusy as e:
        raise HTTPException(status_code=409, detail="The import is still running") from e
    if imp is None:
        raise HTTPException(status_code=404, detail="Import not found")
    return serialize(imp, user_tz(user))
