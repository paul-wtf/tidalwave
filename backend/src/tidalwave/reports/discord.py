from __future__ import annotations

import re

import httpx

_WEBHOOK = re.compile(
    r"https://(?P<host>discord\.com|discordapp\.com)/api/webhooks/"
    r"(?P<id>[0-9]+)/(?P<token>[A-Za-z0-9_-]+)"
)
_MARKDOWN = re.compile(r"([\\*_~`|>\[\]])")


class WebhookFailed(Exception):
    pass


def valid_webhook(url: str) -> str | None:
    url = url.strip()
    return url if _WEBHOOK.fullmatch(url) else None


def mask(url: str) -> str:
    match = _WEBHOOK.fullmatch(url)
    if match is None:
        return "…"
    return (
        f"https://{match['host']}/api/webhooks/{match['id'][:4]}…/…{match['token'][-4:]}"
    )


def escape(text: str) -> str:
    return _MARKDOWN.sub(r"\\\1", text)


async def post(http: httpx.AsyncClient, url: str, embed: dict) -> None:
    payload = {
        "username": "tidalwave",
        "embeds": [embed],
        # Artist names are user data; "@everyone" in one must not ping a server.
        "allowed_mentions": {"parse": []},
    }
    try:
        resp = await http.post(url, json=payload, timeout=10.0)
    except httpx.HTTPError as e:
        raise WebhookFailed(f"Discord unreachable: {type(e).__name__}") from e
    if not resp.is_success:
        raise WebhookFailed(f"Discord answered {resp.status_code}")
