import base64
import io
import shutil

import pytest
from PIL import Image

from tests.integration._helpers import video_b64 as _video_b64
from us_mediakit.media import animated_webp as animated_webp_media
from us_mediakit.media import pdf as pdf_media
from us_mediakit.media import video as video_media

requires_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg nicht installiert")
requires_pdftoppm = pytest.mark.skipif(
    shutil.which("pdftoppm") is None, reason="pdftoppm (poppler-utils) nicht installiert"
)


def _make_test_video(duration_seconds: int = 3) -> bytes:
    return base64.b64decode(_video_b64(duration_seconds))


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
    # statt fehlzuschlagen.
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


@requires_ffmpeg
def test_extract_animated_webp_produces_multi_frame_webp():
    data = _make_test_video(duration_seconds=3)
    result = animated_webp_media.extract_animated_webp(
        data, start_seconds=0.0, duration_seconds=1.0, fps=8
    )
    with Image.open(io.BytesIO(result)) as img:
        assert img.format == "WEBP"
        assert getattr(img, "n_frames", 1) > 1
        assert img.size == (64, 64)


@requires_ffmpeg
def test_extract_animated_webp_scales_width():
    data = _make_test_video(duration_seconds=2)
    result = animated_webp_media.extract_animated_webp(
        data, start_seconds=0.0, duration_seconds=1.0, fps=8, width=32
    )
    with Image.open(io.BytesIO(result)) as img:
        assert img.size[0] == 32


def test_extract_animated_webp_rejects_duration_over_limit():
    with pytest.raises(animated_webp_media.AnimatedWebpError, match="duration_seconds"):
        animated_webp_media.extract_animated_webp(b"not-a-real-video", duration_seconds=999)


def test_extract_animated_webp_rejects_fps_over_limit():
    with pytest.raises(animated_webp_media.AnimatedWebpError, match="fps"):
        animated_webp_media.extract_animated_webp(b"not-a-real-video", fps=999)


def test_extract_animated_webp_rejects_frame_count_over_limit():
    with pytest.raises(animated_webp_media.AnimatedWebpError, match="Frames"):
        animated_webp_media.extract_animated_webp(
            b"not-a-real-video", duration_seconds=10, fps=24
        )


def test_extract_animated_webp_rejects_width_over_limit():
    with pytest.raises(animated_webp_media.AnimatedWebpError, match="width"):
        animated_webp_media.extract_animated_webp(b"not-a-real-video", width=9999)
