import traceback

import httpx
import pytest
import respx

from tidalwave.lastfm.client import LastfmClient

API = "https://ws.audioscrobbler.com/2.0/"


@pytest.fixture
async def client():
    async with httpx.AsyncClient() as http:
        yield LastfmClient(http, api_key="API-KEY-1", api_secret="SECRET-1")


def _printed(exc: BaseException | None) -> str:
    messages = []
    while exc is not None:
        messages += traceback.format_exception_only(exc)
        exc = exc.__cause__ or (None if exc.__suppress_context__ else exc.__context__)
    return "".join(messages)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(502, text="<html>Bad Gateway</html>"),
        httpx.Response(500, json={"message": "try again"}),
    ],
    ids=["html", "json"],
)
@respx.mock
async def test_a_server_error_names_no_key(client, response):
    respx.get(API).mock(return_value=response)

    with pytest.raises(httpx.HTTPStatusError) as info:
        await client.get_recent_tracks("alice", session_key="SESSION-KEY-1")

    printed = _printed(info.value)
    assert str(response.status_code) in printed
    assert "API-KEY-1" not in printed
    assert "SESSION-KEY-1" not in printed
