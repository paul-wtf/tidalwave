from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from html import escape
from urllib.parse import quote
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tidalwave.config import Settings
from tidalwave.deps import get_session, get_settings
from tidalwave.models.db import Share, User
from tidalwave.stats import queries
from tidalwave.stats.scope import Scope, share_bounds, user_tz

log = logging.getLogger(__name__)

router = APIRouter(tags=["share"])

_SHELL_TTL_SECONDS = 60
# The frontend answers from the same cluster; a slow one should cost a visitor
# a moment, not the HTTP client's 15 seconds.
_SHELL_TIMEOUT_SECONDS = 5.0
_COVER_CANDIDATES = 5
_MOVING_LABELS = {
    "rolling_7d": "Last 7 days",
    "rolling_30d": "Last 30 days",
    "rolling_365d": "Last 365 days",
    "this_week": "This week",
    "this_month": "This month",
    "this_year": "This year",
}


def _clock() -> float:
    return time.monotonic()


async def _frontend_shell(request: Request, settings: Settings) -> str | None:
    if not settings.frontend_url:
        return None
    cached: tuple[float, str] | None = getattr(request.app.state, "frontend_shell", None)
    if cached is not None and _clock() - cached[0] < _SHELL_TTL_SECONDS:
        return cached[1]
    try:
        resp = await request.app.state.http.get(
            f"{settings.frontend_url.rstrip('/')}/index.html", timeout=_SHELL_TIMEOUT_SECONDS
        )
        resp.raise_for_status()
    except Exception:
        # A stale shell still boots the app; no shell at all means the fallback page.
        return cached[1] if cached is not None else None
    request.app.state.frontend_shell = (_clock(), resp.text)
    return resp.text


def _day(moment: datetime, tz: str) -> str:
    local = moment.astimezone(ZoneInfo(tz))
    return f"{local.day} {local:%b %Y}"


def _range_text(share: Share, tz: str) -> str:
    if share.range_key is not None:
        return _MOVING_LABELS.get(share.range_key, share.range_key)
    first = _day(share.range_from, tz) if share.range_from is not None else None
    # range_to is exclusive, so the last day shown is the one just before it.
    last = (
        _day(share.range_to - timedelta(microseconds=1), tz)
        if share.range_to is not None else None
    )
    if first and last:
        return f"{first} to {last}"
    if first:
        return f"Since {first}"
    if last:
        return f"Until {last}"
    return "All time"


async def _preview_tags(
    session: AsyncSession, share: Share, owner: User, page_url: str
) -> tuple[str, str]:
    tz = user_tz(owner)
    floor, ceiling = share_bounds(share, tz)
    scope = Scope(
        user_id=share.user_id, tz=tz, since=floor, until=ceiling,
        floor=floor, ceiling=ceiling, shared=True,
    )
    listens = await queries.total_listens(session, scope)
    artists = await queries.top_artists(session, scope, limit=1)
    albums = await queries.top_albums(session, scope, limit=_COVER_CANDIDATES)

    title = " · ".join(filter(None, [f"{owner.lastfm_username}'s listening", share.label]))
    description = [_range_text(share, tz), f"{listens:,} {'listen' if listens == 1 else 'listens'}"]
    if artists:
        description.append(f"Top artist: {artists[0]['artist']}")
    tags = {
        "og:site_name": "tidalwave",
        "og:type": "website",
        "og:title": title,
        "og:description": " · ".join(description),
        "og:url": page_url,
    }
    cover = next((a["image_url"] for a in albums if a["image_url"]), None)
    if cover:
        tags["og:image"] = cover
    html = "".join(
        f'<meta property="{name}" content="{escape(value, quote=True)}" />'
        for name, value in tags.items()
    )
    html += '<meta name="twitter:card" content="summary" />'
    return escape(title, quote=True), html


def _forward_target(token: str, rest: str, query: str) -> str:
    target = f"/?share={quote(token, safe='')}"
    if rest:
        target += f"&page={quote(rest, safe='')}"
    if query:
        target += f"&{query}"
    return escape(target, quote=True)


def _fallback(tags: str, title: str, target: str) -> str:
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8" />'
        f"<title>{title}</title>{tags}"
        f'<meta http-equiv="refresh" content="0; url={target}" /></head>'
        f'<body><a href="{target}">tidalwave</a></body></html>'
    )


def _page(html: str, status_code: int = 200) -> HTMLResponse:
    return HTMLResponse(html, status_code=status_code, headers={"Cache-Control": "no-cache"})


@router.get("/s/{token}", include_in_schema=False, response_class=HTMLResponse)
@router.get("/s/{token}/{rest:path}", include_in_schema=False, response_class=HTMLResponse)
async def share_page(
    token: str,
    request: Request,
    rest: str = "",
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> HTMLResponse:
    shell = await _frontend_shell(request, settings)
    target = _forward_target(token, rest, request.url.query)
    plain = shell if shell is not None else _fallback("", "tidalwave", target)

    share = (
        await session.execute(
            select(Share).where(Share.share_token == token, Share.revoked_at.is_(None))
        )
    ).scalar_one_or_none()
    owner = await session.get(User, share.user_id) if share is not None else None
    if share is None or owner is None:
        return _page(plain, status_code=404)

    page_url = f"{settings.public_base_url.rstrip('/')}{request.url.path}"
    if request.url.query:
        page_url += f"?{request.url.query}"
    try:
        title, tags = await _preview_tags(session, share, owner, page_url)
    except Exception:
        # The preview is a courtesy to link unfurlers; the app shows the real error.
        log.exception("share preview failed")
        return _page(plain)

    title = f"{title} · tidalwave"
    if shell is None:
        return _page(_fallback(tags, title, target))
    html = shell.replace("<title>tidalwave</title>", f"<title>{title}</title>", 1)
    return _page(html.replace("</head>", f"{tags}</head>", 1))
