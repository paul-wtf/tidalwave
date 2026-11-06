from tidalwave import cli


def test_cli_exposes_poll_and_backfill_entrypoints():
    assert callable(cli.poll)
    assert callable(cli.backfill)


def test_backfill_covers_cli_registered():
    import tomllib
    from pathlib import Path

    assert callable(cli.backfill_covers)
    scripts = tomllib.loads(
        (Path(__file__).parent.parent / "pyproject.toml").read_text()
    )["project"]["scripts"]
    assert scripts["tidalwave-backfill-covers"] == "tidalwave.cli:backfill_covers"
