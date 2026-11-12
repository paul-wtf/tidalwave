import json

import httpx
import pytest
import respx

from tidalwave.auth.service import upsert_user_from_session
from tidalwave.auth.session import COOKIE_NAME, SessionCodec

HOOK = "https://discord.com/api/webhooks/123456789012345678/secretTOKENvalue_wxyz"


async def _login(db_session):
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    cookie = SessionCodec("test-secret").encode(user.id)
    return user, {"Cookie": f"{COOKIE_NAME}={cookie}"}


@pytest.mark.parametrize(("method", "path"), [
    ("PUT", "/auth/me/webhook"), ("DELETE", "/auth/me/webhook"), ("POST", "/auth/me/webhook/test"),
])
async def test_webhook_routes_need_a_session(api, method, path):
    client, _ = api
    resp = await client.request(method, path, json={"url": HOOK})
    assert resp.status_code == 401


async def test_saving_a_webhook_stores_it_and_answers_only_with_the_mask(api, db_session):
    client, _ = api
    user, headers = await _login(db_session)

    resp = await client.put("/auth/me/webhook", json={"url": HOOK}, headers=headers)

    assert resp.status_code == 200
    assert resp.json()["weekly_report_webhook"] == "https://discord.com/api/webhooks/1234…/…wxyz"
    assert "secretTOKEN" not in resp.text
    await db_session.refresh(user)
    assert user.discord_webhook_url == HOOK
    me = await client.get("/auth/me", headers=headers)
    assert me.json()["weekly_report_webhook"] == "https://discord.com/api/webhooks/1234…/…wxyz"
    assert "secretTOKEN" not in me.text


@pytest.mark.parametrize("url", [
    "https://example.com/api/webhooks/1/t", "http://discord.com/api/webhooks/1/t", "",
])
async def test_other_addresses_are_refused(api, db_session, url):
    client, _ = api
    user, headers = await _login(db_session)

    resp = await client.put("/auth/me/webhook", json={"url": url}, headers=headers)

    assert resp.status_code == 422
    await db_session.refresh(user)
    assert user.discord_webhook_url is None


async def test_clearing_the_webhook(api, db_session):
    client, _ = api
    user, headers = await _login(db_session)
    await client.put("/auth/me/webhook", json={"url": HOOK}, headers=headers)

    resp = await client.delete("/auth/me/webhook", headers=headers)

    assert resp.status_code == 200
    assert resp.json()["weekly_report_webhook"] is None
    await db_session.refresh(user)
    assert user.discord_webhook_url is None


async def test_test_message_needs_a_webhook(api, db_session):
    client, _ = api
    _, headers = await _login(db_session)
    assert (await client.post("/auth/me/webhook/test", headers=headers)).status_code == 409


@respx.mock
async def test_test_message_goes_to_the_saved_webhook(api, db_session):
    client, _ = api
    _, headers = await _login(db_session)
    await client.put("/auth/me/webhook", json={"url": HOOK}, headers=headers)
    route = respx.post(HOOK).respond(204)

    resp = await client.post("/auth/me/webhook/test", headers=headers)

    assert resp.status_code == 204
    embed = json.loads(route.calls.last.request.content)["embeds"][0]
    assert embed["title"] == "tidalwave is connected"
    assert "alice" in embed["description"]


@respx.mock
@pytest.mark.parametrize("failure", [
    {"return_value": httpx.Response(404, json={"code": 10015})},
    {"side_effect": httpx.ConnectError("down")},
])
async def test_a_failing_test_message_is_reported_as_bad_gateway(api, db_session, failure):
    client, _ = api
    _, headers = await _login(db_session)
    await client.put("/auth/me/webhook", json={"url": HOOK}, headers=headers)
    respx.post(HOOK).mock(**failure)

    resp = await client.post("/auth/me/webhook/test", headers=headers)

    assert resp.status_code == 502
    assert "secretTOKEN" not in resp.text
