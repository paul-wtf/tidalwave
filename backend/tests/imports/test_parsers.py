import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from import_samples import FIXTURES, LISTENBRAINZ, SPOTIFY, listenbrainz_zip, spotify_zip

from tidalwave.imports.parsers import (
    ImportFileError,
    Play,
    Skip,
    iter_json,
    parse_record,
    read_records,
    scrobblable,
)


def _plays(path: Path) -> list[Play | Skip]:
    return [parse_record(r) for r in read_records(path, max_bytes=10_000_000)]


def test_iter_json_reads_an_array_in_small_pieces():
    text = json.dumps([{"a": i, "s": "x" * 50} for i in range(500)])
    values = list(iter_json(io.StringIO(text), chunk_size=64))
    assert [v["a"] for v in values] == list(range(500))


def test_iter_json_reads_one_object_per_line():
    text = '{"a": 1}\n{"a": 2}\n\n{"a": 3}\n'
    assert [v["a"] for v in iter_json(io.StringIO(text), chunk_size=5)] == [1, 2, 3]


@pytest.mark.parametrize("text", ['[{"a": 1}, {"a": ', '{"a": 1}\n{"a" 2}\n', "[1, 2]", "nonsense"])
def test_iter_json_refuses_broken_files(text):
    with pytest.raises(ImportFileError):
        list(iter_json(io.StringIO(text), chunk_size=4))


def test_spotify_entries_become_plays_that_started_ms_played_before_ts():
    plays = _plays(SPOTIFY)

    assert plays[0] == Play(
        source="spotify", artist="The National", track="Fake Empire", album="Boxer",
        played_at=datetime(2021, 4, 15, 18, 0, 0, tzinfo=UTC), played_ms=200_000,
    )
    assert plays[1].played_at == datetime(2021, 4, 15, 18, 3, 25, tzinfo=UTC)
    assert plays[7].played_at == datetime(2021, 4, 16, 8, 5, 42, tzinfo=UTC)


def test_spotify_podcasts_private_sessions_and_empty_entries_are_skipped():
    plays = _plays(SPOTIFY)

    assert plays[3] == Skip.NOT_MUSIC
    assert plays[4] == Skip.PRIVATE
    assert plays[5] == Skip.NOT_MUSIC


def test_a_spotify_zip_reads_the_audio_history_and_leaves_videos_and_the_readme_out(tmp_path):
    plays = _plays(spotify_zip(tmp_path))

    assert len(plays) == 8
    assert plays[0].track == "Fake Empire"


def test_listenbrainz_export_zip_reads_the_monthly_listen_files(tmp_path):
    plays = _plays(listenbrainz_zip(tmp_path))

    assert len(plays) == 6
    assert plays[0] == Play(
        source="listenbrainz", artist="Röyksopp", track="Some Resolve",
        album="Profound Mysteries II",
        played_at=datetime(2021, 4, 15, 15, 23, 20, tzinfo=UTC),
        duration_ms=402_390,
        track_mbid="30d08f4c-d825-4ae1-b79c-44242cddd7c0",
        artist_mbid="1c70a3fc-fa3c-4be1-8b55-c3192db8a884",
        album_mbid="f1418001-7f1e-46af-bfdb-95faeded8841",
    )
    assert plays[1].duration_ms == 375_000
    assert plays[3] == Skip.NOT_MUSIC
    assert plays[4].played_ms == 60_000
    assert plays[5].album == "Boxer"


def test_a_single_listenbrainz_listen_file_is_read_too():
    plays = _plays(LISTENBRAINZ / "listens" / "2021" / "4.jsonl")
    assert len(plays) == 6


def test_an_older_listenbrainz_export_as_one_json_array_is_read():
    plays = _plays(FIXTURES / "listenbrainz_listener_legacy.json")

    assert [p.track for p in plays] == ["Some Resolve", "Glósóli"]
    assert plays[0].played_at == datetime(2021, 4, 15, 15, 23, 20, tzinfo=UTC)


def test_records_of_neither_format_are_skipped():
    assert parse_record({"endTime": "2021-04-15 18:03", "artistName": "A"}) == Skip.UNKNOWN


def test_a_zip_without_listening_history_says_so(tmp_path):
    path = tmp_path / "other.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("notes.txt", "hello")
    with pytest.raises(ImportFileError, match="no listening history"):
        list(read_records(path, max_bytes=1000))


def test_a_zip_that_unpacks_beyond_the_limit_is_refused(tmp_path):
    path = tmp_path / "big.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("Streaming_History_Audio_2021_0.json", "[" + " " * 5000 + "]")
    with pytest.raises(ImportFileError, match="unpacks to more"):
        list(read_records(path, max_bytes=1000))


def test_a_file_that_is_neither_zip_nor_json_is_refused(tmp_path):
    path = tmp_path / "x.json"
    path.write_bytes(b"\x89PNG\r\n")
    with pytest.raises(ImportFileError):
        list(read_records(path, max_bytes=1000))


def _play(**over) -> Play:
    base = dict(source="spotify", artist="A", track="T", album=None,
                played_at=datetime(2021, 1, 1, tzinfo=UTC))
    return Play(**(base | over))


@pytest.mark.parametrize(
    ("played_ms", "duration_ms", "expected"),
    [
        (29_999, None, False),
        (30_000, None, True),
        (95_000, 258_000, False),
        (129_000, 258_000, True),
        (240_000, 600_000, True),
        (239_000, 600_000, False),
        (None, 21_000, False),
        (None, 402_390, True),
        (None, None, True),
        (40_000, 45_000, True),
    ],
)
def test_only_plays_last_fm_would_scrobble_count(played_ms, duration_ms, expected):
    assert scrobblable(_play(played_ms=played_ms), duration_ms) is expected
