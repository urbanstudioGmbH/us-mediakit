import io
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
from PIL import Image

from us_mediakit.media import pdf as pdf_media
from us_mediakit.media import video as video_media

requires_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg nicht installiert")
requires_pdftoppm = pytest.mark.skipif(
    shutil.which("pdftoppm") is None, reason="pdftoppm (poppler-utils) nicht installiert"
)


def _make_test_video(duration_seconds: int = 3) -> bytes:
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_path = Path(tmp_dir) / "test.mp4"
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"testsrc=duration={duration_seconds}:size=64x64:rate=10",
                str(out_path),
            ],
            check=True,
            timeout=30,
        )
        return out_path.read_bytes()


def _make_test_pdf() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (200, 100), "white").save(buf, format="PDF")
    return buf.getvalue()


@requires_ffmpeg
def test_get_duration_seconds():
    data = _make_test_video(duration_seconds=3)
    duration = video_media.get_duration_seconds(data)
    assert duration is not None
    assert 2.5 < duration < 3.5


@requires_ffmpeg
def test_extract_frame_clamps_seek_to_duration():
    data = _make_test_video(duration_seconds=2)
    # Anfrage nach Sekunde 8 auf einem 2-Sekunden-Video -> muss geklemmt werden,
    # statt fehlzuschlagen (Sicherheitsnetz-Anforderung aus dem Programmierplan).
    frame = video_media.extract_frame(data, seek_seconds=8.0, timeout_seconds=15)
    with Image.open(io.BytesIO(frame)) as img:
        assert img.size == (64, 64)


@requires_pdftoppm
def test_render_page_produces_jpeg():
    data = _make_test_pdf()
    rendered = pdf_media.render_page(data, page=1)
    with Image.open(io.BytesIO(rendered)) as img:
        assert img.format == "JPEG"
        assert img.size[0] > 0 and img.size[1] > 0
