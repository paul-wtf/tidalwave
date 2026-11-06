from datetime import UTC, datetime

from sqlalchemy import select

from tidalwave.auth.service import upsert_user_from_session
from tidalwave.ingest.covers import fill_missing_covers
from tidalwave.ingest.repository import upsert_listens
from tidalwave.models.db import AlbumArt
from tidalwave.models.domain import Scrobble


class FakeAlbumClient:
    def __init__(self, covers):
        self.covers = covers
        self.calls: list[tuple[str, str]] = []

    async def get_album_info(self, artist, album):
        self.calls.append((artist, album))
        return self.covers.get((artist, album))


def _sc(artist, album, ts):
    return Scrobble(artist=artist, track_title="t", album=album,
                    played_at=datetime.fromtimestamp(ts, tz=UTC))


async def test_fill_missing_covers_writes_null_rows_and_respects_budget(db_session):
    user = await upsert_user_from_session(db_session, "alice", "sk", mode="open", allowlist=[])
    await upsert_listens(db_session, user.id, [
        _sc("A", "One", 0),
        _sc("A", "One", 10),
        _sc("B", "Two", 20),
        _sc("C", None, 30),
    ])
    client = FakeAlbumClient({("A", "One"): "https://img/one.jpg"})

    written = await fill_missing_covers(db_session, client)

    assert written == 2
    assert sorted(client.calls) == [("A", "One"), ("B", "Two")]
    rows = (await db_session.execute(select(AlbumArt))).scalars().all()
    assert {(r.artist, r.album): r.image_url for r in rows} == {
        ("A", "One"): "https://img/one.jpg",
        ("B", "Two"): None,
    }

    again = await fill_missing_covers(db_session, client)
    assert again == 0
    assert len(client.calls) == 2

    await upsert_listens(db_session, user.id, [_sc("D", "Three", 40), _sc("E", "Four", 50)])
    limited = await fill_missing_covers(db_session, client, max_albums=1)
    assert limited == 1
    assert len(client.calls) == 3
