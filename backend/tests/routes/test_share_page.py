from datetime import UTC, datetime, timedelta

import pytest
import respx

from tidalwave.auth.service import upsert_user_from_session
from tidalwave.deps import get_settings
from tidalwave.ingest.repository import upsert_listens
from tidalwave.models.db import AlbumArt, Share
from tidalwave.models.domain import Scrobble
from tidalwave.routes import share_page as share_page_module

FRONTEND = "http://frontend.test"
INDEX = (
    '<!doctype html><html lang="en"><head><meta charset="utf-8" /><title>tidalwave</title>'
    '<link href="/_app/immutable/entry/start.js" rel="modulepreload"></head>'
    '<body><div id="app" style="display: contents"></div></body></html>'
)
TOKEN = "T" * 43


@pytest.fixture
async def site(api, monkeypatch):
    monkeypatch.setenv("TIDALWAVE_FRONTEND_URL", FRONTEND)
    monkeypatch.setenv("TIDALWAVE_PUBLIC_BASE_URL", "https://tidalwave.example")
    get_settings.cache_clear()
    client, _ = api
    return client


def _listen(artist, track, album, when):
    return Scrobble(artist=artist, track_title=track, album=album, played_at=when)


async def _october_share(db_session, **share_fields):
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    await upsert_listens(db_session, user.id, [
        _listen("Kavinsky", "Nightcall", "OutRun", datetime(2026, 10, 2, 12, tzinfo=UTC)),
        _listen("Kavinsky", "Roadgame", "OutRun", datetime(2026, 10, 3, 12, tzinfo=UTC)),
        _listen("Daft Punk", "Aerodynamic", "Discovery", datetime(2026, 10, 4, 12, tzinfo=UTC)),
        # Outside October: more plays than anything inside it.
        *[_listen("Secret Band", f"hidden {i}", "Hidden Album", datetime(2026, 9, 1, i, tzinfo=UTC))
          for i in range(5)],
    ])
    db_session.add_all([
        AlbumArt(artist="Kavinsky", album="OutRun", image_url="https://img.test/outrun.jpg?a=1&b=2"),
        AlbumArt(artist="Secret Band", album="Hidden Album", image_url="https://img.test/hidden.jpg"),
    ])
    fields = {
        "range_from": datetime(2026, 10, 1, tzinfo=UTC),
        "range_to": datetime(2026, 11, 1, tzinfo=UTC),
        **share_fields,
    }
    db_session.add(Share(share_token=TOKEN, user_id=user.id, **fields))
    await db_session.flush()
    return user


@respx.mock
async def test_share_page_is_the_frontend_shell_with_preview_tags(site, db_session):
    respx.get(f"{FRONTEND}/index.html").respond(text=INDEX)
    await _october_share(db_session, label='Trip "2026" <b>')

    resp = await site.get(f"/s/{TOKEN}")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert resp.headers["cache-control"] == "no-cache"
    html = resp.text
    assert '<div id="app" style="display: contents"></div>' in html
    assert '<link href="/_app/immutable/entry/start.js" rel="modulepreload">' in html
    title = "alice&#x27;s listening · Trip &quot;2026&quot; &lt;b&gt;"
    assert f"<title>{title} · tidalwave</title>" in html
    assert "<title>tidalwave</title>" not in html
    assert f'<meta property="og:title" content="{title}" />' in html
    assert (
        '<meta property="og:description" '
        'content="1 Oct 2026 to 31 Oct 2026 · 3 listens · Top artist: Kavinsky" />'
    ) in html
    assert '<meta property="og:image" content="https://img.test/outrun.jpg?a=1&amp;b=2" />' in html
    assert f'<meta property="og:url" content="https://tidalwave.example/s/{TOKEN}" />' in html
    assert '<meta property="og:site_name" content="tidalwave" />' in html
    assert '<meta property="og:type" content="website" />' in html
    assert html.index("og:title") < html.index("</head>")


@respx.mock
async def test_share_page_shows_nothing_from_outside_the_range(site, db_session):
    respx.get(f"{FRONTEND}/index.html").respond(text=INDEX)
    await _october_share(db_session)
    html = (await site.get(f"/s/{TOKEN}")).text
    assert "Secret Band" not in html
    assert "hidden" not in html.lower()
    assert "8 listens" not in html
    assert '<meta property="og:title" content="alice&#x27;s listening" />' in html


@respx.mock
async def test_share_page_names_the_range_of_each_kind_of_share(site, db_session, monkeypatch):
    respx.get(f"{FRONTEND}/index.html").respond(text=INDEX)
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    user.timezone = "Europe/Berlin"
    now = datetime.now(UTC)
    await upsert_listens(db_session, user.id, [
        _listen("Recent", "a", None, now - timedelta(days=2)),
        _listen("Old", "b", None, now - timedelta(days=400)),
        _listen("Old", "c", None, now - timedelta(days=401)),
    ])
    shares = {
        "A" * 43: {},
        "B" * 43: {"range_key": "rolling_30d"},
        "C" * 43: {"range_key": "this_year"},
        "D" * 43: {"range_from": datetime(2026, 9, 30, 22, tzinfo=UTC)},
        "E" * 43: {"range_to": datetime(2026, 10, 31, 23, tzinfo=UTC)},
    }
    for token, fields in shares.items():
        db_session.add(Share(share_token=token, user_id=user.id, **fields))
    await db_session.flush()

    async def description(token: str) -> str:
        html = (await site.get(f"/s/{token}")).text
        start = html.index('og:description" content="') + len('og:description" content="')
        return html[start:html.index('"', start)]

    assert await description("A" * 43) == "All time · 3 listens · Top artist: Old"
    assert await description("B" * 43) == "Last 30 days · 1 listen · Top artist: Recent"
    assert (await description("C" * 43)).startswith("This year · ")
    assert (await description("D" * 43)).startswith("Since 1 Oct 2026 · ")
    assert (await description("E" * 43)).startswith("Until 31 Oct 2026 · ")


@respx.mock
async def test_share_page_without_listens_has_no_image_and_no_top_artist(site, db_session):
    respx.get(f"{FRONTEND}/index.html").respond(text=INDEX)
    await _october_share(
        db_session,
        range_from=datetime(2026, 12, 1, tzinfo=UTC), range_to=datetime(2027, 1, 1, tzinfo=UTC),
    )
    html = (await site.get(f"/s/{TOKEN}")).text
    assert 'content="1 Dec 2026 to 31 Dec 2026 · 0 listens" />' in html
    assert "og:image" not in html
    assert "Top artist" not in html


@respx.mock
async def test_share_page_takes_the_cover_of_the_best_ranked_album_that_has_one(site, db_session):
    respx.get(f"{FRONTEND}/index.html").respond(text=INDEX)
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    await upsert_listens(db_session, user.id, [
        _listen("A", "1", "Coverless", datetime(2026, 10, 2, 1, tzinfo=UTC)),
        _listen("A", "2", "Coverless", datetime(2026, 10, 2, 2, tzinfo=UTC)),
        _listen("B", "3", "Covered", datetime(2026, 10, 2, 3, tzinfo=UTC)),
    ])
    db_session.add_all([
        AlbumArt(artist="A", album="Coverless", image_url=None),
        AlbumArt(artist="B", album="Covered", image_url="https://img.test/covered.jpg"),
        Share(share_token=TOKEN, user_id=user.id),
    ])
    await db_session.flush()
    html = (await site.get(f"/s/{TOKEN}")).text
    assert '<meta property="og:image" content="https://img.test/covered.jpg" />' in html


@respx.mock
@pytest.mark.parametrize("path,query", [
    ("/artists", ""),
    ("/insights", ""),
    ("/artist", "?artist=Daft+Punk"),
])
async def test_pages_below_the_share_get_the_same_shell_and_tags(site, db_session, path, query):
    respx.get(f"{FRONTEND}/index.html").respond(text=INDEX)
    await _october_share(db_session, label="October")
    html = (await site.get(f"/s/{TOKEN}{path}{query}")).text
    assert '<div id="app" style="display: contents"></div>' in html
    assert '<meta property="og:title" content="alice&#x27;s listening · October" />' in html
    expected = f"https://tidalwave.example/s/{TOKEN}{path}{query}".replace("&", "&amp;")
    assert f'<meta property="og:url" content="{expected}" />' in html


@respx.mock
async def test_unknown_and_revoked_tokens_get_the_plain_shell(site, db_session):
    respx.get(f"{FRONTEND}/index.html").respond(text=INDEX)
    await _october_share(db_session, revoked_at=datetime(2026, 11, 2, tzinfo=UTC))
    for token in (TOKEN, "nothere"):
        resp = await site.get(f"/s/{token}")
        assert resp.status_code == 404
        assert resp.text == INDEX


@respx.mock
async def test_share_page_fetches_the_shell_once_while_it_is_fresh(site, db_session, monkeypatch):
    route = respx.get(f"{FRONTEND}/index.html").respond(text=INDEX)
    await _october_share(db_session)
    clock = [50.0]
    monkeypatch.setattr(share_page_module, "_clock", lambda: clock[0])
    await site.get(f"/s/{TOKEN}")
    clock[0] += 59
    await site.get(f"/s/{TOKEN}/artists")
    assert route.call_count == 1
    clock[0] += 2
    await site.get(f"/s/{TOKEN}")
    assert route.call_count == 2


@respx.mock
async def test_a_stale_shell_is_served_while_the_frontend_is_down(site, db_session, monkeypatch):
    route = respx.get(f"{FRONTEND}/index.html").respond(text=INDEX)
    await _october_share(db_session)
    clock = [50.0]
    monkeypatch.setattr(share_page_module, "_clock", lambda: clock[0])
    await site.get(f"/s/{TOKEN}")
    route.respond(status_code=502)
    clock[0] += 120
    html = (await site.get(f"/s/{TOKEN}")).text
    assert '<div id="app" style="display: contents"></div>' in html
    assert 'property="og:title"' in html


@respx.mock
async def test_without_a_reachable_frontend_the_page_previews_and_forwards(site, db_session):
    respx.get(f"{FRONTEND}/index.html").respond(status_code=502)
    await _october_share(db_session, label="October")

    resp = await site.get(f"/s/{TOKEN}")
    assert resp.status_code == 200
    assert 'property="og:title" content="alice&#x27;s listening · October"' in resp.text
    assert f'<meta http-equiv="refresh" content="0; url=/?share={TOKEN}" />' in resp.text
    assert f'<a href="/?share={TOKEN}">' in resp.text

    deep = (await site.get(f"/s/{TOKEN}/artist?artist=Daft+Punk&x=1")).text
    assert f'url=/?share={TOKEN}&amp;page=artist&amp;artist=Daft+Punk&amp;x=1"' in deep

    unknown = await site.get("/s/nothere")
    assert unknown.status_code == 404
    assert "og:title" not in unknown.text
    assert 'url=/?share=nothere"' in unknown.text


@respx.mock
async def test_without_a_configured_frontend_nothing_is_fetched(api, db_session, monkeypatch):
    route = respx.get(url__regex=r".*index\.html").respond(text=INDEX)
    monkeypatch.delenv("TIDALWAVE_FRONTEND_URL", raising=False)
    get_settings.cache_clear()
    client, _ = api
    await _october_share(db_session)
    resp = await client.get(f"/s/{TOKEN}")
    assert resp.status_code == 200
    assert f"url=/?share={TOKEN}" in resp.text
    assert route.call_count == 0
