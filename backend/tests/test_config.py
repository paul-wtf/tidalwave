import pytest

from tidalwave.config import Settings


def test_defaults():
    s = Settings()
    assert s.database_url.startswith("postgresql+asyncpg://")
    assert s.registration_mode == "allowlist"
    assert s.registration_allowlist == []


def test_allowlist_parses_csv(monkeypatch):
    monkeypatch.setenv("TIDALWAVE_REGISTRATION_ALLOWLIST", "alice, bob")
    s = Settings()
    assert s.registration_allowlist == ["alice", "bob"]


def test_invalid_registration_mode_rejected(monkeypatch):
    monkeypatch.setenv("TIDALWAVE_REGISTRATION_MODE", "nonsense")
    with pytest.raises(ValueError):
        Settings()


def test_musicbrainz_defaults_and_overrides(monkeypatch):
    s = Settings()
    assert s.musicbrainz_url == "https://musicbrainz.org/ws/2"
    assert s.musicbrainz_budget == 30
    monkeypatch.setenv("TIDALWAVE_MUSICBRAINZ_URL", "http://mirror.test/ws/2")
    monkeypatch.setenv("TIDALWAVE_MUSICBRAINZ_BUDGET", "0")
    s = Settings()
    assert (s.musicbrainz_url, s.musicbrainz_budget) == ("http://mirror.test/ws/2", 0)
    monkeypatch.setenv("TIDALWAVE_MUSICBRAINZ_BUDGET", "-1")
    with pytest.raises(ValueError):
        Settings()


def test_linkhop_url_is_empty_by_default_and_must_be_a_web_address(monkeypatch):
    assert Settings().linkhop_url == ""
    monkeypatch.setenv("TIDALWAVE_LINKHOP_URL", "https://linkhop.example/app/")
    assert Settings().linkhop_url == "https://linkhop.example/app"
    monkeypatch.setenv("TIDALWAVE_LINKHOP_URL", "javascript:alert(1)")
    with pytest.raises(ValueError):
        Settings()
