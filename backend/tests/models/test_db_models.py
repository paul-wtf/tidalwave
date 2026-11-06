import pytest
from sqlalchemy.exc import IntegrityError

from tidalwave.models.db import AlbumArt, Base, Listen, User


def test_tables_registered():
    names = set(Base.metadata.tables)
    assert names == {"users", "listens", "sync_state", "shares", "track_durations", "album_art"}


def test_listen_dedup_constraint_present():
    cols = {c.name for c in Listen.__table__.columns}
    assert {"user_id", "artist", "track_title", "played_at"} <= cols
    uniques = [c for c in Listen.__table__.constraints if c.__class__.__name__ == "UniqueConstraint"]
    assert any(
        {col.name for col in u.columns} == {"user_id", "artist", "track_title", "played_at"}
        for u in uniques
    )


def test_user_username_unique():
    assert User.__table__.columns["lastfm_username"].unique is True


async def test_album_art_unique_per_artist_album(db_session):
    db_session.add(AlbumArt(artist="A", album="X", image_url=None))
    await db_session.flush()
    db_session.add(AlbumArt(artist="B", album="X", image_url="u"))
    await db_session.flush()
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            db_session.add(AlbumArt(artist="A", album="X", image_url="v"))


async def test_user_timezone_defaults_to_null(db_session):
    user = User(lastfm_username="tz", lastfm_session_key="k")
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    assert user.timezone is None
