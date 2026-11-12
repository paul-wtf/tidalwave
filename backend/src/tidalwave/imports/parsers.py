from __future__ import annotations

import io
import json
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import PurePosixPath
from typing import IO, Any

MIN_PLAYED_MS = 30_000
ENOUGH_PLAYED_MS = 240_000
_CHUNK = 64 * 1024
# One record is a few hundred bytes. A piece this large that still does not
# parse is a broken file, not a record cut off by the read.
_MAX_RECORD_CHARS = 1024 * 1024
_IGNORED_MEMBERS = {"user.json", "feedback.jsonl", "pinned_recording.jsonl"}


class ImportFileError(ValueError):
    pass


class Skip(Enum):
    NOT_MUSIC = "not_music"
    PRIVATE = "private"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Play:
    source: str
    artist: str
    track: str
    album: str | None
    played_at: datetime
    played_ms: int | None = None
    duration_ms: int | None = None
    track_mbid: str | None = None
    artist_mbid: str | None = None
    album_mbid: str | None = None


def iter_json(stream: IO[str], *, chunk_size: int = _CHUNK) -> Iterator[dict[str, Any]]:
    """Yield the objects of a JSON array, or of a file with one object per line,
    without reading the whole file at once."""
    decoder = json.JSONDecoder()
    buf = ""
    pos = 0
    array: bool | None = None
    eof = False

    def more() -> bool:
        nonlocal buf, pos, eof
        if eof:
            return False
        chunk = stream.read(chunk_size)
        if not chunk:
            eof = True
            return False
        buf = buf[pos:] + chunk
        pos = 0
        return True

    while True:
        while pos < len(buf) and (buf[pos].isspace() or (array and buf[pos] == ",")):
            pos += 1
        if pos >= len(buf):
            if more():
                continue
            if array:
                raise ImportFileError("The file ends in the middle of the list")
            return
        char = buf[pos]
        if array is None and char == "[":
            array = True
            pos += 1
            continue
        if array and char == "]":
            return
        if array is None:
            array = False
        try:
            value, end = decoder.raw_decode(buf, pos)
        except json.JSONDecodeError as e:
            if len(buf) - pos < _MAX_RECORD_CHARS and more():
                continue
            raise ImportFileError(f"The file is not valid JSON ({e.msg})") from e
        if not isinstance(value, dict):
            raise ImportFileError("The file does not hold listening history")
        pos = end
        yield value


class _Counted(io.RawIOBase):
    def __init__(self, inner: IO[bytes], budget: list[int]) -> None:
        self.inner = inner
        self.budget = budget

    def readable(self) -> bool:
        return True

    def readinto(self, b: Any) -> int:
        data = self.inner.read(len(b))
        self.budget[0] -= len(data)
        if self.budget[0] < 0:
            raise ImportFileError("The archive unpacks to more than the import size allows; "
                                  "upload its history files one by one")
        b[: len(data)] = data
        return len(data)


def _wanted(name: str) -> bool:
    member = PurePosixPath(name)
    if member.name in _IGNORED_MEMBERS or member.name.startswith("."):
        return False
    if member.suffix not in {".json", ".jsonl"}:
        return False
    return "Video" not in member.name and "__MACOSX" not in member.parts


def _text(raw: IO[bytes]) -> IO[str]:
    return io.TextIOWrapper(raw, encoding="utf-8-sig")


def read_records(path: Any, *, max_bytes: int) -> Iterator[dict[str, Any]]:
    """Every record of an uploaded file: a JSON or JSONL file, or a zip of them
    as Spotify and ListenBrainz send it. ``max_bytes`` bounds what a zip may
    unpack to."""
    if zipfile.is_zipfile(path):
        budget = [max_bytes]
        with zipfile.ZipFile(path) as archive:
            members = sorted(m.filename for m in archive.infolist() if _wanted(m.filename))
            if not members:
                raise ImportFileError("The archive holds no listening history")
            for name in members:
                with archive.open(name) as member:
                    counted = io.BufferedReader(_Counted(member, budget))
                    yield from iter_json(_text(counted))
        return
    with open(path, "rb") as file:
        try:
            yield from iter_json(_text(file))
        except UnicodeDecodeError as e:
            raise ImportFileError("The file is neither JSON nor a zip archive") from e


def _text_or_none(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return int(value)


def _spotify(record: dict[str, Any]) -> Play | Skip:
    track = _text_or_none(record.get("master_metadata_track_name"))
    artist = _text_or_none(record.get("master_metadata_album_artist_name"))
    ms_played = _int_or_none(record.get("ms_played"))
    if track is None or artist is None or ms_played is None:
        return Skip.NOT_MUSIC
    if record.get("incognito_mode") is True:
        return Skip.PRIVATE
    try:
        ended = datetime.fromisoformat(str(record["ts"]))
    except ValueError:
        return Skip.UNKNOWN
    if ended.tzinfo is None:
        ended = ended.replace(tzinfo=UTC)
    return Play(
        source="spotify",
        artist=artist,
        track=track,
        album=_text_or_none(record.get("master_metadata_album_album_name")),
        played_at=(ended - timedelta(milliseconds=ms_played)).replace(microsecond=0),
        played_ms=ms_played,
    )


def _ms(info: dict[str, Any], key: str) -> int | None:
    ms = _int_or_none(info.get(f"{key}_ms"))
    if ms is not None:
        return ms
    seconds = _int_or_none(info.get(key))
    return seconds * 1000 if seconds is not None else None


def _mbid(value: Any) -> str | None:
    if isinstance(value, list):
        value = value[0] if value else None
    text = _text_or_none(value)
    return text if text is not None and len(text) == 36 else None


def _listened_at(value: Any) -> datetime | None:
    seconds = _int_or_none(value)
    if seconds is not None:
        return datetime.fromtimestamp(seconds, tz=UTC)
    if isinstance(value, str):
        try:
            moment = datetime.fromisoformat(value)
        except ValueError:
            return None
        return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)
    return None


def _listenbrainz(record: dict[str, Any]) -> Play | Skip:
    meta = record.get("track_metadata")
    if not isinstance(meta, dict):
        return Skip.NOT_MUSIC
    artist = _text_or_none(meta.get("artist_name"))
    track = _text_or_none(meta.get("track_name"))
    played_at = _listened_at(record.get("listened_at"))
    if artist is None or track is None:
        return Skip.NOT_MUSIC
    if played_at is None:
        return Skip.UNKNOWN
    info: dict[str, Any] = meta.get("additional_info") or {}
    mapping: dict[str, Any] = meta.get("mbid_mapping") or {}
    if not isinstance(info, dict) or not isinstance(mapping, dict):
        return Skip.UNKNOWN
    return Play(
        source="listenbrainz",
        artist=artist,
        track=track,
        album=_text_or_none(meta.get("release_name")),
        played_at=played_at,
        played_ms=_ms(info, "duration_played"),
        duration_ms=_ms(info, "duration"),
        track_mbid=_mbid(info.get("recording_mbid") or mapping.get("recording_mbid")),
        artist_mbid=_mbid(info.get("artist_mbids") or mapping.get("artist_mbids")),
        album_mbid=_mbid(info.get("release_mbid") or mapping.get("release_mbid")),
    )


def parse_record(record: dict[str, Any]) -> Play | Skip:
    if "ts" in record and "ms_played" in record:
        return _spotify(record)
    if "listened_at" in record and "track_metadata" in record:
        return _listenbrainz(record)
    return Skip.UNKNOWN


def scrobblable(play: Play, duration_ms: int | None) -> bool:
    """Last.fm's rule: the track is longer than 30 seconds and was played for
    half its length or 4 minutes, whichever comes first. A part that is not
    known is not held against the play."""
    if duration_ms is not None and duration_ms < MIN_PLAYED_MS:
        return False
    if play.played_ms is None:
        return True
    if play.played_ms < MIN_PLAYED_MS:
        return False
    if duration_ms is None:
        return True
    return play.played_ms >= min(duration_ms / 2, ENOUGH_PLAYED_MS)
