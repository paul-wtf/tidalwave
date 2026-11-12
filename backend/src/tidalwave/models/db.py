from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lastfm_username: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    lastfm_session_key: Mapped[str] = mapped_column(Text, nullable=False)
    is_admin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    disconnected: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    timezone: Mapped[str | None] = mapped_column(String(64))


class Listen(Base):
    __tablename__ = "listens"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "artist", "track_title", "played_at", name="uq_listen_dedup"
        ),
        Index("ix_listens_user_artist_played", "user_id", "artist", "played_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    track_title: Mapped[str] = mapped_column(Text, nullable=False)
    artist: Mapped[str] = mapped_column(Text, nullable=False)
    album: Mapped[str | None] = mapped_column(Text)
    played_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    track_mbid: Mapped[str | None] = mapped_column(String(36))
    artist_mbid: Mapped[str | None] = mapped_column(String(36))
    album_mbid: Mapped[str | None] = mapped_column(String(36))
    # Track length in seconds, resolved from Last.fm track.getInfo. NULL = not
    # yet resolved or unknown; "time listened" sums this column.
    duration_sec: Mapped[int | None] = mapped_column(Integer)


class TrackDuration(Base):
    """Per-track duration cache so each unique (artist, track) is fetched once.

    ``duration_sec`` is NULL when Last.fm has no duration for the track; the row
    still exists so we don't keep re-requesting it.
    """

    __tablename__ = "track_durations"
    __table_args__ = (
        UniqueConstraint("artist", "track_title", name="uq_track_duration"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    artist: Mapped[str] = mapped_column(Text, nullable=False)
    track_title: Mapped[str] = mapped_column(Text, nullable=False)
    duration_sec: Mapped[int | None] = mapped_column(Integer)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AlbumArt(Base):
    __tablename__ = "album_art"
    __table_args__ = (UniqueConstraint("artist", "album", name="uq_album_art"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    artist: Mapped[str] = mapped_column(Text, nullable=False)
    album: Mapped[str] = mapped_column(Text, nullable=False)
    image_url: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AlbumYear(Base):
    """Release year of an album from MusicBrainz. NULL means MusicBrainz was
    asked and has no date for it."""

    __tablename__ = "album_years"
    __table_args__ = (UniqueConstraint("artist", "album", name="uq_album_year"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    artist: Mapped[str] = mapped_column(Text, nullable=False)
    album: Mapped[str] = mapped_column(Text, nullable=False)
    year: Mapped[int | None] = mapped_column(Integer)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ArtistTags(Base):
    """An artist's genre tags from Last.fm, strongest first.

    An empty list means Last.fm has no usable tag for the artist; the row still
    exists so the artist is not asked for again.
    """

    __tablename__ = "artist_tags"
    __table_args__ = (UniqueConstraint("artist", name="uq_artist_tags"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    artist: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SyncState(Base):
    __tablename__ = "sync_state"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    last_played_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Share(Base):
    __tablename__ = "shares"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    share_token: Mapped[str] = mapped_column(String(43), nullable=False, unique=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    range_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    range_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    label: Mapped[str | None] = mapped_column(Text)
    range_key: Mapped[str | None] = mapped_column(String(16))
