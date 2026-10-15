from datetime import UTC, datetime

import httpx
from sqlalchemy import select

from tidalwave.auth.service import upsert_user_from_session
from tidalwave.ingest.poller import poll_all_users
from tidalwave.lastfm.client import LastfmError, RecentTracksPage
from tidalwave.models.db import User
from tidalwave.models.domain import Scrobble


class FakeClient:
    """Fake Last.fm client for tests.

    ``by_user`` maps username -> RecentTracksPage to return on success.
    ``errors`` maps username -> exception to raise instead (optional).
    """

    def __init__(self, by_user, errors=None):
        self.by_user = by_user
        self.errors: dict[str, Exception] = errors or {}

    async def get_recent_tracks(self, username, *, from_ts=None, page=1, limit=200, session_key=None):
        if username in self.errors:
            raise self.errors[username]
        return self.by_user[username]


def _page(ts):
    return RecentTracksPage(
        (Scrobble(artist="A", track_title="t", album=None,
                  played_at=datetime.fromtimestamp(ts, tz=UTC)),),
        page=1, total_pages=1,
    )


async def test_poll_processes_every_connected_user_and_isolates_failures(db_session):
    await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    boom = await upsert_user_from_session(db_session, "boom", "sk", mode="open", allowlist=[])
    boom.disconnected = False
    skipped = await upsert_user_from_session(db_session, "carol", "sk", mode="open", allowlist=[])
    skipped.disconnected = True
    await db_session.flush()

    client = FakeClient(
        {"alice": _page(1000), "carol": _page(1000)},
        errors={"boom": LastfmError(8, "operation failed")},
    )
    report = await poll_all_users(db_session, client)

    assert report["alice"] == 1
    assert report["boom"] == "error"   # failure isolated, not raised
    assert "carol" not in report        # disconnected users skipped


async def test_poll_marks_user_disconnected_on_auth_error(db_session):
    """Auth errors (codes 4 and 9) must set user.disconnected=True; transient errors must not."""
    await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    boom = await upsert_user_from_session(db_session, "boom", "sk", mode="open", allowlist=[])
    boom.disconnected = False
    stale = await upsert_user_from_session(db_session, "stale", "sk", mode="open", allowlist=[])
    stale.disconnected = False
    await db_session.flush()

    client = FakeClient(
        {"alice": _page(1000)},
        errors={
            "boom": LastfmError(8, "operation failed"),
            "stale": LastfmError(9, "Invalid session key"),
        },
    )
    report = await poll_all_users(db_session, client)

    # Success path unchanged
    assert report["alice"] == 1

    # Transient error: report "error", user stays connected
    assert report["boom"] == "error"
    boom_row = (
        await db_session.execute(select(User).where(User.lastfm_username == "boom"))
    ).scalar_one()
    assert boom_row.disconnected is False

    # Auth error: report "disconnected", user is marked disconnected
    assert report["stale"] == "disconnected"
    stale_row = (
        await db_session.execute(select(User).where(User.lastfm_username == "stale"))
    ).scalar_one()
    assert stale_row.disconnected is True


async def test_ingest_one_user_disconnects_on_auth_error(db_session):
    from tidalwave.ingest.poller import ingest_one_user

    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    await db_session.flush()

    client = FakeClient({}, errors={"alice": LastfmError(9, "Invalid session key")})
    result = await ingest_one_user(db_session, client, user)

    assert result == "disconnected"
    assert user.disconnected is True


async def test_ingest_one_user_returns_inserted_count(db_session):
    from tidalwave.ingest.poller import ingest_one_user

    user = await upsert_user_from_session(db_session, "bob", "sk", mode="open", allowlist=[])
    await db_session.flush()

    result = await ingest_one_user(db_session, FakeClient({"bob": _page(1000)}), user)
    assert result == 1


async def test_ingest_one_user_logs_auth_error_as_warning_without_traceback(db_session, caplog):
    """Auth errors (codes 4/9) are a normal 'session revoked' state — log at
    WARNING without a stack trace, not log.exception."""
    import logging

    from tidalwave.ingest.poller import ingest_one_user

    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    await db_session.flush()

    client = FakeClient({}, errors={"alice": LastfmError(9, "Invalid session key")})
    with caplog.at_level(logging.INFO, logger="tidalwave.ingest.poller"):
        result = await ingest_one_user(db_session, client, user)

    assert result == "disconnected"
    rec = next(r for r in caplog.records if r.name == "tidalwave.ingest.poller")
    assert rec.levelno == logging.WARNING
    assert rec.exc_info is None  # no traceback for an expected disconnect


async def test_ingest_one_user_logs_transient_error_with_traceback(db_session, caplog):
    """Transient/unexpected Last.fm errors keep the full traceback (log.exception)."""
    import logging

    from tidalwave.ingest.poller import ingest_one_user

    user = await upsert_user_from_session(db_session, "bob", "sk", mode="open", allowlist=[])
    await db_session.flush()

    client = FakeClient({}, errors={"bob": LastfmError(8, "operation failed")})
    with caplog.at_level(logging.INFO, logger="tidalwave.ingest.poller"):
        result = await ingest_one_user(db_session, client, user)

    assert result == "error"
    rec = next(r for r in caplog.records if r.name == "tidalwave.ingest.poller")
    assert rec.levelno == logging.ERROR
    assert rec.exc_info is not None  # traceback retained for unexpected errors


async def test_poll_isolates_lastfm_being_unavailable(db_session):
    await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    await upsert_user_from_session(db_session, "boom", "sk", mode="open", allowlist=[])
    request = httpx.Request("GET", "https://ws.audioscrobbler.com/2.0/")
    unavailable = httpx.HTTPStatusError(
        "503 Service Unavailable", request=request, response=httpx.Response(503, request=request)
    )
    client = FakeClient({"alice": _page(1000)}, errors={"boom": unavailable})

    report = await poll_all_users(db_session, client)

    assert report["alice"] == 1
    assert report["boom"] == "error"
    boom = (await db_session.execute(select(User).where(User.lastfm_username == "boom"))).scalar_one()
    assert boom.disconnected is False
