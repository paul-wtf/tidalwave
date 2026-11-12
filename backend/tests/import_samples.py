import zipfile
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[0] / "fixtures" / "imports"
SPOTIFY = FIXTURES / "Streaming_History_Audio_2021_0.json"
LISTENBRAINZ = FIXTURES / "listenbrainz"


def spotify_zip(tmp_path: Path) -> Path:
    path = tmp_path / "my_spotify_data.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        folder = "Spotify Extended Streaming History/"
        z.write(SPOTIFY, folder + SPOTIFY.name)
        z.write(FIXTURES / "Streaming_History_Video_2021.json",
                folder + "Streaming_History_Video_2021.json")
        z.writestr(folder + "ReadMeFirst_ExtendedStreamingHistory.pdf", b"%PDF-1.4 not really")
    return path


def listenbrainz_zip(tmp_path: Path) -> Path:
    path = tmp_path / "listenbrainz_listener_1731400000.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for file in LISTENBRAINZ.rglob("*"):
            if file.is_file():
                z.write(file, file.relative_to(LISTENBRAINZ).as_posix())
    return path
