import io

import pytest
from PIL import Image, ImageOps

from us_mediakit.core import transform


def test_php_round_half_away_from_zero():
    assert transform.php_round(0.5) == 1
    assert transform.php_round(1.5) == 2
    assert transform.php_round(2.4) == 2
    assert transform.php_round(-0.5) == -1
    assert transform.php_round(-1.5) == -2


@pytest.mark.parametrize(
    ("zoom", "default", "expected"),
    [
        (None, None, 1.0),
        ("1.5", None, 1.5),  # Faktor < 10 -> *100 -> 150 -> /100
        ("150", None, 1.5),  # bereits Prozent
        ("50", None, 1.0),  # unter 100 % geklemmt
        ("50000", None, 5.0),  # über 500 % geklemmt
        (None, "2", 2.0),  # Fallback auf Preset-Default
    ],
)
def test_parse_zoom(zoom, default, expected):
    assert transform.parse_zoom(zoom, default) == expected


def test_parse_aspect_ratio_fraction():
    assert transform.parse_aspect_ratio("16-9") == pytest.approx(16 / 9)


def test_parse_aspect_ratio_single_value():
    assert transform.parse_aspect_ratio("1.5") == 1.5


def test_parse_aspect_ratio_invalid_returns_none():
    assert transform.parse_aspect_ratio(None) is None
    assert transform.parse_aspect_ratio("bogus") is None
    assert transform.parse_aspect_ratio("16-0") is None


@pytest.mark.parametrize(
    ("shift", "max_val", "target", "expected"),
    [
        ("left", 100, 20, 0),
        ("top", 100, 20, 0),
        ("right", 100, 20, 80),
        ("bottom", 100, 20, 80),
        (50, 100, 20, 40),
        ("center", 100, 20, 40),  # weder numerisch noch left/right -> Default 50 %
        (0, 100, 20, 0),
        (100, 100, 20, 80),
    ],
)
def test_get_fractional_shift(shift, max_val, target, expected):
    assert transform.get_fractional_shift(shift, max_val, target) == expected


def test_get_xy_alignment_centered_default():
    mode = {"w": 50, "h": 50}
    assert transform.get_xy_alignment(mode, 100, 100) == (25, 25)


def test_get_xy_alignment_left_top():
    mode = {"w": 50, "h": 50, "xalign": "left", "yalign": "top"}
    assert transform.get_xy_alignment(mode, 100, 100) == (0, 0)


def test_get_xy_alignment_right_bottom():
    mode = {"w": 50, "h": 50, "xalign": "right", "yalign": "bottom"}
    assert transform.get_xy_alignment(mode, 100, 100) == (50, 50)


def _make_image(w: int, h: int, color=(200, 50, 50)) -> Image.Image:
    return Image.new("RGB", (w, h), color)


def test_apply_fit_crop_mode_returns_exact_target_size():
    img = _make_image(200, 100)
    mode = {"w": 50, "h": 50, "fit": "crop", "xalign": "center", "yalign": "center"}
    result = transform.apply_fit(img, mode)
    assert result.image.size == (50, 50)
    assert (result.target_width, result.target_height) == (50, 50)


def test_apply_fit_greedycrop_returns_exact_target_size():
    img = _make_image(200, 100)
    mode = {"w": 50, "h": 50, "fit": "greedycrop", "xalign": "center", "yalign": "center"}
    result = transform.apply_fit(img, mode)
    assert result.image.size == (50, 50)


def test_apply_fit_full_mode_matches_target_size():
    img = _make_image(200, 100)
    mode = {"w": 100, "h": 100, "fit": "full", "xalign": "center", "yalign": "center"}
    result = transform.apply_fit(img, mode)
    assert result.image.size == (100, 100)
    assert (result.target_width, result.target_height) == (100, 100)


def test_apply_fit_crop_override_forces_mode(monkeypatch=None):
    img = _make_image(200, 100)
    mode = {"w": 50, "h": 50, "fit": "full"}
    result = transform.apply_fit(img, mode, crop="crop")
    # Bei fit="crop" wird ohne Skalierung direkt zugeschnitten.
    assert result.image.size == (50, 50)


def test_apply_fit_zoom_forces_greedyscalecrop_and_keeps_target_size():
    img = _make_image(200, 100)
    mode = {"w": 50, "h": 50, "fit": "crop"}
    result = transform.apply_fit(img, mode, zoom="2")
    assert result.image.size == (50, 50)


def test_apply_fit_does_not_upscale_without_ai_provider():
    """Dokumentiertes Bestandsverhalten: ohne ai-Provider wird bei scale > 1 nicht
    vergrößert — das Bild bleibt kleiner als die Zielgröße, nur target_width/height
    berichten die eigentlich gewünschte Zielgröße."""
    img = _make_image(100, 100)
    mode = {"w": 500, "h": 500, "fit": "full"}
    result = transform.apply_fit(img, mode)
    assert (result.target_width, result.target_height) == (500, 500)
    assert result.image.size != (500, 500)
    assert result.scale > 1
    assert result.ai_pending is False


def test_apply_fit_marks_ai_pending_when_ai_requested_and_upscaling():
    img = _make_image(100, 100)
    mode = {"w": 500, "h": 500, "fit": "full"}
    result = transform.apply_fit(img, mode, ai="real-esrgan")
    assert result.ai_pending is True
    # Ohne tatsächlichen KI-Aufruf (Phase 5) bleibt das Bild an der Zwischengröße.
    assert result.image.size == (100, 100)


def test_apply_fit_corrects_exif_orientation_before_measuring():
    base = Image.new("RGB", (100, 50), "blue")
    exif = base.getexif()
    exif[0x0112] = 6  # "rotate 90 CW", siehe EXIF-Orientation-Tag
    buf = io.BytesIO()
    base.save(buf, format="JPEG", exif=exif)
    buf.seek(0)
    loaded = Image.open(buf)

    assert loaded.size == (100, 50)
    assert ImageOps.exif_transpose(loaded).size == (50, 100)

    mode = {"w": 50, "h": 100, "fit": "full"}
    result = transform.apply_fit(loaded, mode)
    assert result.image.size == (50, 100)


def test_apply_fit_unknown_fit_mode_raises():
    img = _make_image(10, 10)
    with pytest.raises(ValueError):
        transform.apply_fit(img, {"w": 5, "h": 5, "fit": "nonsense"})
