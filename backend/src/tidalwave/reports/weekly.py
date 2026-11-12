from __future__ import annotations

import logging
from dataclasses import replace
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tidalwave.models.db import User
from tidalwave.reports.discord import WebhookFailed, escape, post
from tidalwave.stats import insights, queries
from tidalwave.stats.scope import Scope, last_full_week, previous_range, user_tz

__all__ = ["last_full_week", "send_weekly_reports", "weekly_embed"]

log = logging.getLogger(__name__)

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_ACCENT = 0xCBA6F7
_NAMED_DISCOVERIES = 5
# Only a first import brings more new artists into one week.
_DISCOVERY_CAP = 500


def _week_label(first: date, last: date) -> str:
    start = f"{_MONTHS[first.month - 1]} {first.day}"
    if first.year != last.year:
        start += f", {first.year}"
    end = str(last.day) if first.month == last.month else f"{_MONTHS[last.month - 1]} {last.day}"
    return f"{start} – {end}, {last.year}"


def _listens(n: int) -> str:
    return f"{n} listen" if n == 1 else f"{n} listens"


def _duration(seconds: int) -> str:
    hours, minutes = divmod(round(seconds / 60), 60)
    return f"{hours}h {minutes}m" if hours else f"{minutes}m"


def _change(current: int, previous: int) -> str:
    if previous == 0:
        return "none the week before"
    pct = round((current - previous) / previous * 100)
    if pct == 0:
        return "same as the week before"
    return f"{pct:+d}% on the week before"


def _names(names: list[str], total: int) -> str:
    if not names:
        return "None this week"
    shown = [escape(n) for n in names[:_NAMED_DISCOVERIES]]
    rest = total - len(shown)
    if rest > 0:
        return f"{', '.join(shown)} and {rest} more"
    if len(shown) == 1:
        return shown[0]
    return f"{', '.join(shown[:-1])} and {shown[-1]}"


async def weekly_embed(
    session: AsyncSession, user: User, *, now: datetime, base_url: str
) -> dict | None:
    tz = user_tz(user)
    since, until = last_full_week(tz, now)
    scope = Scope(user_id=user.id, tz=tz, since=since, until=until)
    current = await queries.summary_stats(session, scope)
    if current["total_listens"] == 0:
        return None
    lo, hi = previous_range(tz, since, until, "week", now)
    previous = await queries.summary_stats(session, replace(scope, since=lo, until=hi))
    artist = (await queries.top_artists(session, scope, limit=1))[0]
    track = (await queries.top_tracks(session, scope, limit=1))[0]
    new = (await insights.discoveries(session, scope, limit=_DISCOVERY_CAP))["new_artists"]

    first = since.astimezone(ZoneInfo(tz)).date()
    last = until.astimezone(ZoneInfo(tz)).date() - timedelta(days=1)
    seconds = current["total_seconds"]
    listens = current["total_listens"]
    return {
        "title": "Your week in music",
        "description": _week_label(first, last),
        "url": base_url,
        "color": _ACCENT,
        "timestamp": until.isoformat(),
        "footer": {"text": f"tidalwave · week {first.isocalendar().week}"},
        "fields": [
            {
                "name": "Listening time",
                "value": (
                    f"{_duration(seconds)} ({_change(seconds, previous['total_seconds'])})"
                    if seconds else "Not known yet"
                ),
                "inline": True,
            },
            {
                "name": "Listens",
                "value": f"{listens} ({_change(listens, previous['total_listens'])})",
                "inline": True,
            },
            {
                "name": "Top artist",
                "value": f"{escape(artist['artist'])}, {_listens(artist['count'])}",
                "inline": False,
            },
            {
                "name": "Top track",
                "value": (
                    f"{escape(track['track'])} by {escape(track['artist'])}, "
                    f"{_listens(track['count'])}"
                ),
                "inline": False,
            },
            {
                "name": "New discoveries",
                "value": _names([a["artist"] for a in new], len(new)),
                "inline": False,
            },
        ],
    }


def connected_embed(user: User, base_url: str) -> dict:
    return {
        "title": "tidalwave is connected",
        "description": (
            f"Weekly reports for {escape(user.lastfm_username)} arrive here on Monday mornings."
        ),
        "url": base_url,
        "color": _ACCENT,
    }


async def send_weekly_reports(
    session: AsyncSession, http: httpx.AsyncClient, *, now: datetime, base_url: str
) -> dict[str, str]:
    users = (await session.execute(
        select(User).where(User.discord_webhook_url.is_not(None)).order_by(User.id)
    )).scalars().all()
    report: dict[str, str] = {}
    for user in users:
        name = user.lastfm_username
        url = user.discord_webhook_url
        try:
            embed = await weekly_embed(session, user, now=now, base_url=base_url)
            if embed is None or url is None:
                report[name] = "empty"
                continue
            await post(http, url, embed)
            report[name] = "sent"
        except WebhookFailed as e:
            log.warning("weekly report for %s not delivered: %s", name, e)
            report[name] = "failed"
        except Exception:
            log.exception("weekly report for %s failed", name)
            report[name] = "failed"
    return report
