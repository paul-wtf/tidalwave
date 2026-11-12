import httpx
import pytest
import respx

from tidalwave.reports.discord import WebhookFailed, mask, post, valid_webhook

GOOD = "https://discord.com/api/webhooks/123456789012345678/abc-DEF_ghi123wxyz"


@pytest.mark.parametrize("url", [
    GOOD,
    "https://discordapp.com/api/webhooks/123456789012345678/abc-DEF_ghi123wxyz",
    "  https://discord.com/api/webhooks/1/t  ",
])
def test_discord_webhooks_are_accepted(url):
    assert valid_webhook(url) == url.strip()


@pytest.mark.parametrize("url", [
    "http://discord.com/api/webhooks/1/t",
    "https://discord.com.evil.example/api/webhooks/1/t",
    "https://evil.example/https://discord.com/api/webhooks/1/t",
    "https://user@discord.com/api/webhooks/1/t",
    "https://discord.com:8443/api/webhooks/1/t",
    "https://ptb.discord.com/api/webhooks/1/t",
    "https://discord.com/api/webhooks/1",
    "https://discord.com/api/webhooks/abc/t",
    "https://discord.com/api/webhooks/1/t/slack",
    "https://discord.com/api/webhooks/1/t?wait=true",
    "https://discord.com/api/webhooks/1/t#x",
    "https://discord.com/api/v10/webhooks/1/t",
    "",
])
def test_anything_else_is_refused(url):
    assert valid_webhook(url) is None


def test_mask_keeps_the_host_and_hides_the_token():
    masked = mask(GOOD)
    assert masked == "https://discord.com/api/webhooks/1234…/…wxyz"
    assert "abc-DEF" not in masked


@respx.mock
async def test_post_sends_embeds_without_pinging_anyone():
    route = respx.post(GOOD).respond(204)
    async with httpx.AsyncClient() as http:
        await post(http, GOOD, {"title": "hi"})
    body = route.calls.last.request.content
    import json

    assert json.loads(body) == {
        "username": "tidalwave",
        "embeds": [{"title": "hi"}],
        "allowed_mentions": {"parse": []},
    }


@respx.mock
@pytest.mark.parametrize("response", [
    httpx.Response(404, json={"message": "Unknown Webhook", "code": 10015}),
    httpx.Response(429, json={"retry_after": 1.5}),
    httpx.Response(500),
])
async def test_post_raises_when_discord_refuses(response):
    respx.post(GOOD).mock(return_value=response)
    async with httpx.AsyncClient() as http:
        with pytest.raises(WebhookFailed) as caught:
            await post(http, GOOD, {"title": "hi"})
    assert str(response.status_code) in str(caught.value)


@respx.mock
async def test_post_raises_when_discord_is_unreachable():
    respx.post(GOOD).mock(side_effect=httpx.ConnectError("down"))
    async with httpx.AsyncClient() as http:
        with pytest.raises(WebhookFailed):
            await post(http, GOOD, {"title": "hi"})
