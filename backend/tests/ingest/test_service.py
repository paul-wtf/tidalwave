from datetime import UTC, datetime

from sqlalchemy import select

from tidalwave.auth.service import upsert_user_from_session
from tidalwave.ingest.repository import get_sync_state
from tidalwave.ingest.service import ingest_user
from tidalwave.lastfm.client import RecentTracksPage
from tidalwave.models.db import Listen
from tidalwave.models.domain import Scrobble


class FakeClient:
    """Returns preconfigured pages keyed by requested page number."""

    def __init__(self, pages: dict[int, RecentTracksPage]) -> None:
        self.pages = pages
        self.calls: list[tuple[str, int | None, int]] = []
        self.session_keys: list[str | None] = []

    async def get_recent_tracks(self, username, *, from_ts=None, page=1, limit=200, session_key=None):
        self.calls.append((username, from_ts, page))
        self.session_keys.append(session_key)
        return self.pages[page]


def _sc(title: str, ts: int) -> Scrobble:
    return Scrobble(artist="A", track_title=title, album=None,
                    played_at=datetime.fromtimestamp(ts, tz=UTC))


async def test_ingest_walks_all_pages_and_advances_state(db_session):
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    client = FakeClient({
        1: RecentTracksPage((_sc("t3", 3000), _sc("t2", 2000)), page=1, total_pages=2),
        2: RecentTracksPage((_sc("t1", 1000),), page=2, total_pages=2),
    })

    inserted = await ingest_user(db_session, client, user)

    assert inserted == 3
    listens = (await db_session.execute(select(Listen))).scalars().all()
    assert {listen.track_title for listen in listens} == {"t1", "t2", "t3"}
    state = await get_sync_state(db_session, user.id)
    assert state.last_played_at == datetime.fromtimestamp(3000, tz=UTC)  # newest
    # session key must be forwarded on every page fetch
    assert all(sk == "sk" for sk in client.session_keys)


async def test_ingest_uses_from_ts_after_first_run(db_session):
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    client = FakeClient({1: RecentTracksPage((_sc("t1", 1000),), page=1, total_pages=1)})
    await ingest_user(db_session, client, user)

    client2 = FakeClient({1: RecentTracksPage((_sc("t2", 2000),), page=1, total_pages=1)})
    await ingest_user(db_session, client2, user)
    # second run should request from just after the last stored timestamp (1000 + 1)
    assert client2.calls[0][1] == 1001


async def test_ingest_without_new_scrobbles_still_marks_synced(db_session):
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    client = FakeClient({1: RecentTracksPage((), page=1, total_pages=1)})

    inserted = await ingest_user(db_session, client, user)

    assert inserted == 0
    state = await get_sync_state(db_session, user.id)
    assert state is not None
    assert state.last_synced_at is not None
    assert state.last_played_at is None


async def test_ingest_stores_merged_spellings_under_their_canonical_name(db_session):
    from tidalwave.models.db import AlbumArt
    from tidalwave.spellings.service import merge_spellings

    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    await merge_spellings(db_session, user.id, "The National", ["National"])
    scrobble = Scrobble(
        artist="National", track_title="Fake Empire", album="Boxer",
        played_at=datetime.fromtimestamp(1000, tz=UTC), image_url="http://img/boxer.jpg",
    )
    client = FakeClient({1: RecentTracksPage((scrobble,), page=1, total_pages=1)})

    await ingest_user(db_session, client, user)

    listen = (await db_session.execute(select(Listen))).scalar_one()
    assert (listen.artist, listen.artist_raw) == ("The National", "National")
    covers = (await db_session.execute(
        select(AlbumArt.artist).where(AlbumArt.album == "Boxer").order_by(AlbumArt.artist)
    )).scalars().all()
    assert covers == ["National", "The National"]
