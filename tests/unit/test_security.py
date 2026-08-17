import io

import pytest
from PIL import Image

from us_mediakit.core import security


def _png_bytes(w: int, h: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), "white").save(buf, format="PNG")
    return buf.getvalue()


def test_check_image_size_accepts_normal_image():
    security.check_image_size(_png_bytes(100, 100))


def test_check_image_size_rejects_oversized_file():
    data = _png_bytes(10, 10)
    with pytest.raises(security.SecurityLimitExceeded):
        security.check_image_size(data, max_file_size_bytes=1)


def test_check_image_size_rejects_too_many_pixels_from_header_alone():
    """Header behauptet riesige Abmessungen — Prüfung muss vor dem vollen Decode greifen."""
    data = _png_bytes(5000, 5000)
    with pytest.raises(security.SecurityLimitExceeded):
        security.check_image_size(data, max_pixels=1000)


def test_run_subprocess_rejects_shell_string():
    with pytest.raises(TypeError):
        security.run_subprocess("echo hi", timeout_seconds=1)  # type: ignore[arg-type]


def test_run_subprocess_runs_argument_array():
    result = security.run_subprocess(["echo", "-n", "hallo"], timeout_seconds=5)
    assert result.returncode == 0
    assert result.stdout == b"hallo"


def test_run_subprocess_times_out():
    with pytest.raises(security.SubprocessTimeout):
        security.run_subprocess(["sleep", "5"], timeout_seconds=0.1)
