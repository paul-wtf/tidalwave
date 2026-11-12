import logging

import respx

from tidalwave import cli


def test_cli_exposes_poll_and_backfill_entrypoints():
    assert callable(cli.poll)
    assert callable(cli.backfill)


def _scripts() -> dict[str, str]:
    import tomllib
    from pathlib import Path

    return tomllib.loads(
        (Path(__file__).parent.parent / "pyproject.toml").read_text()
    )["project"]["scripts"]


def test_backfill_covers_cli_registered():
    assert callable(cli.backfill_covers)
    assert _scripts()["tidalwave-backfill-covers"] == "tidalwave.cli:backfill_covers"


def test_backfill_tags_cli_registered():
    assert callable(cli.backfill_tags)
    assert _scripts()["tidalwave-backfill-tags"] == "tidalwave.cli:backfill_tags"


def test_backfill_years_cli_registered():
    assert callable(cli.backfill_years)
    assert _scripts()["tidalwave-backfill-years"] == "tidalwave.cli:backfill_years"


def test_weekly_report_cli_registered():
    assert callable(cli.weekly_report)
    assert _scripts()["tidalwave-weekly-report"] == "tidalwave.cli:weekly_report"


async def test_poll_saves_the_lastfm_work_before_it_asks_musicbrainz(monkeypatch):
    events: list[object] = []

    class Session:
        async def commit(self):
            events.append("commit")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

    def step(name, result=0):
        async def run(session, client, **kwargs):
            events.append((name, kwargs) if name == "years" else name)
            if name == "years":
                events.append(client._base)
            return result

        return run

    monkeypatch.setenv("TIDALWAVE_MUSICBRAINZ_URL", "http://mirror.test/ws/2")
    monkeypatch.setenv("TIDALWAVE_MUSICBRAINZ_BUDGET", "7")
    monkeypatch.setattr(cli, "make_engine", lambda settings: None)
    monkeypatch.setattr(cli, "make_session_factory", lambda engine: Session)
    monkeypatch.setattr(cli, "poll_all_users", step("poll", {}))
    monkeypatch.setattr(cli, "fill_missing_durations", step("durations"))
    monkeypatch.setattr(cli, "fill_missing_covers", step("covers"))
    monkeypatch.setattr(cli, "fill_missing_artist_tags", step("tags"))
    monkeypatch.setattr(cli, "fill_missing_album_years", step("years"))

    await cli._poll()

    assert events == [
        "poll", "durations", "covers", "tags", "commit",
        ("years", {"max_albums": 7}), "http://mirror.test/ws/2", "commit",
    ]


@respx.mock
async def test_poll_keeps_request_urls_with_keys_out_of_the_log(monkeypatch, caplog):
    respx.get("https://ws.audioscrobbler.com/2.0/").respond(json={})

    class Session:
        async def commit(self):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

    async def poll(session, client, **kwargs):
        await client._http.get(
            "https://ws.audioscrobbler.com/2.0/", params={"api_key": "API-KEY-1", "sk": "SESSION-KEY-1"}
        )
        return {"alice": 1}

    async def nothing(session, client, **kwargs):
        return 0

    monkeypatch.setattr(cli, "make_engine", lambda settings: None)
    monkeypatch.setattr(cli, "make_session_factory", lambda engine: Session)
    monkeypatch.setattr(cli, "poll_all_users", poll)
    for step in ("fill_missing_durations", "fill_missing_covers", "fill_missing_artist_tags",
                 "fill_missing_album_years"):
        monkeypatch.setattr(cli, step, nothing)
    caplog.set_level(logging.INFO)

    await cli._poll()

    assert "poll report: {'alice': 1}" in caplog.text
    assert "API-KEY-1" not in caplog.text
    assert "SESSION-KEY-1" not in caplog.text
