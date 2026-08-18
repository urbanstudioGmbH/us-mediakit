"""CLI-Ebene: Dinge, die nur über argparse-Wiring kaputtgehen können, nicht über die
darunterliegenden Bibliotheksfunktionen (die schon anderswo getestet sind)."""

from __future__ import annotations

import base64
import io
import shutil
import subprocess
import sys

import pytest
from PIL import Image

from tests.integration._helpers import video_b64 as _video_b64

requires_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg nicht installiert")


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "us_mediakit.cli", *args],
        capture_output=True,
        timeout=30,
        check=False,
    )


@requires_ffmpeg
def test_thumbnail_video_seek_seconds_flag_changes_extracted_frame(tmp_path):
    """Ohne das Flag wird immer bei DEFAULT_SEEK_SECONDS (8s, hier geklemmt auf die
    Videodauer) extrahiert -- mit dem Flag muss ein anderer, expliziter Zeitpunkt
    greifen. Getestet über zwei tatsächlich unterschiedliche Standbilder desselben
    ffmpeg-testsrc-Videos (die eingeblendete Regenbogen-Zeitleiste bewegt sich)."""
    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(base64.b64decode(_video_b64(4)))

    early = tmp_path / "early.png"
    late = tmp_path / "late.png"

    result_early = _run_cli(
        "thumbnail", str(video_path), "--mode", "showcase_medium", "--video",
        "--video-seek-seconds", "0.2", "--format", "png", "-o", str(early),
    )
    assert result_early.returncode == 0, result_early.stderr

    result_late = _run_cli(
        "thumbnail", str(video_path), "--mode", "showcase_medium", "--video",
        "--video-seek-seconds", "3.8", "--format", "png", "-o", str(late),
    )
    assert result_late.returncode == 0, result_late.stderr

    with Image.open(early) as img_early, Image.open(late) as img_late:
        assert img_early.tobytes() != img_late.tobytes()


@requires_ffmpeg
def test_thumbnail_video_seek_seconds_default_matches_library_default(tmp_path):
    """Ohne --video-seek-seconds muss weiterhin exakt das bisherige Verhalten gelten
    (DEFAULT_SEEK_SECONDS, geklemmt auf die Videodauer) -- Regressionsschutz für die
    neue CLI-Option."""
    from us_mediakit.media.video import DEFAULT_SEEK_SECONDS

    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(base64.b64decode(_video_b64(4)))

    without_flag = tmp_path / "without_flag.png"
    with_explicit_default = tmp_path / "with_explicit_default.png"

    r1 = _run_cli(
        "thumbnail", str(video_path), "--mode", "showcase_medium", "--video",
        "--format", "png", "-o", str(without_flag),
    )
    assert r1.returncode == 0, r1.stderr

    r2 = _run_cli(
        "thumbnail", str(video_path), "--mode", "showcase_medium", "--video",
        "--video-seek-seconds", str(DEFAULT_SEEK_SECONDS), "--format", "png", "-o", str(with_explicit_default),
    )
    assert r2.returncode == 0, r2.stderr

    with Image.open(without_flag) as a, Image.open(with_explicit_default) as b:
        assert a.tobytes() == b.tobytes()


def test_watermark_invisible_format_flag_controls_actual_encoding(tmp_path):
    """Ohne --format kodiert embed() intern immer JPEG (Default), unabhängig von der
    Dateiendung -- ein reales Verwechslungsrisiko bei Robustheitstests, siehe
    invisible.py. Mit --format PNG muss die tatsächlich geschriebene Datei auch
    PNG-Bytes enthalten, nicht nur einen passenden Dateinamen."""
    buf = io.BytesIO()
    Image.new("RGB", (300, 300), (60, 90, 40)).save(buf, format="PNG")
    source = tmp_path / "photo.png"
    source.write_bytes(buf.getvalue())

    result = _run_cli(
        "watermark", "invisible", str(source), "--reference-id", "01020304", "--format", "PNG",
    )
    assert result.returncode == 0, result.stderr

    with Image.open(source) as img:
        assert img.format == "PNG"


def test_watermark_invisible_without_format_flag_defaults_to_jpeg(tmp_path):
    buf = io.BytesIO()
    Image.new("RGB", (300, 300), (60, 90, 40)).save(buf, format="PNG")
    source = tmp_path / "photo.png"
    source.write_bytes(buf.getvalue())

    result = _run_cli("watermark", "invisible", str(source), "--reference-id", "01020304")
    assert result.returncode == 0, result.stderr

    with Image.open(source) as img:
        assert img.format == "JPEG"


def _quadrant_image(path, w=800, h=400):
    from PIL import ImageDraw

    img = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)
    hw, hh = w // 2, h // 2
    draw.rectangle([0, 0, hw, hh], fill=(200, 80, 70))
    draw.rectangle([hw, 0, w, hh], fill=(70, 130, 160))
    draw.rectangle([0, hh, hw, h], fill=(210, 170, 60))
    draw.rectangle([hw, hh, w, h], fill=(90, 150, 100))
    img.save(path, format="PNG")


def test_thumbnail_width_height_without_mode_builds_ad_hoc_preset(tmp_path):
    source = tmp_path / "photo.png"
    _quadrant_image(source)
    out = tmp_path / "out.png"

    result = _run_cli(
        "thumbnail", str(source), "--width", "200", "--height", "100", "--format", "png", "-o", str(out),
    )
    assert result.returncode == 0, result.stderr
    with Image.open(out) as img:
        assert img.size == (200, 100)


def test_thumbnail_without_mode_or_width_height_fails_clearly(tmp_path):
    source = tmp_path / "photo.png"
    _quadrant_image(source)

    result = _run_cli("thumbnail", str(source))
    assert result.returncode == 1
    assert b"--mode" in result.stderr and b"--width" in result.stderr


def test_thumbnail_align_x_align_y_change_which_region_is_kept(tmp_path):
    """800x400-Quadrantenbild auf ein schmales 100x100-Zielformat zugeschnitten --
    align-x/align-y muss steuern, welche Ecke im Ergebnis landet."""
    source = tmp_path / "photo.png"
    _quadrant_image(source)

    top_left = tmp_path / "top_left.png"
    bottom_right = tmp_path / "bottom_right.png"

    r1 = _run_cli(
        "thumbnail", str(source), "--width", "100", "--height", "100", "--fit", "full",
        "--align-x", "left", "--align-y", "top", "--format", "png", "-o", str(top_left),
    )
    assert r1.returncode == 0, r1.stderr

    r2 = _run_cli(
        "thumbnail", str(source), "--width", "100", "--height", "100", "--fit", "full",
        "--align-x", "right", "--align-y", "bottom", "--format", "png", "-o", str(bottom_right),
    )
    assert r2.returncode == 0, r2.stderr

    with Image.open(top_left) as a, Image.open(bottom_right) as b:
        # oben-links muss die rote Ecke treffen, unten-rechts die gruene
        assert a.getpixel((5, 5))[:3] == (200, 80, 70)
        assert b.getpixel((94, 94))[:3] == (90, 150, 100)


def test_thumbnail_max_upscale_factor_allows_capped_simple_upscale(tmp_path):
    source = tmp_path / "photo.png"
    _quadrant_image(source, w=100, h=100)
    without_cap = tmp_path / "without_cap.png"
    with_cap = tmp_path / "with_cap.png"

    r1 = _run_cli(
        "thumbnail", str(source), "--width", "500", "--height", "500", "--format", "png", "-o", str(without_cap),
    )
    assert r1.returncode == 0, r1.stderr
    with Image.open(without_cap) as img:
        assert img.size != (500, 500)  # bisheriges Verhalten unveraendert: keine Vergroesserung

    r2 = _run_cli(
        "thumbnail", str(source), "--width", "500", "--height", "500",
        "--max-upscale-factor", "2.0", "--format", "png", "-o", str(with_cap),
    )
    assert r2.returncode == 0, r2.stderr
    with Image.open(with_cap) as img:
        assert img.size == (200, 200)  # gedeckelt bei Faktor 2, nicht die vollen 500x500
