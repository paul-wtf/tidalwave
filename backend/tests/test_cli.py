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
