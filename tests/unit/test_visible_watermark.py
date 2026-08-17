import io

import pytest
from PIL import Image

from us_mediakit.watermark.visible import VisibleWatermarkError, apply_logo, apply_text


def _base_jpeg(w=400, h=300) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (30, 90, 160)).save(buf, format="JPEG")
    return buf.getvalue()


def _logo_png(w=100, h=50) -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", (w, h), (255, 0, 0, 200)).save(buf, format="PNG")
    return buf.getvalue()


def test_apply_logo_returns_valid_image_of_same_base_size():
    result = apply_logo(_base_jpeg(400, 300), _logo_png(), position="bottom-right")
    with Image.open(io.BytesIO(result)) as img:
        assert img.size == (400, 300)
        assert img.format == "JPEG"


def test_apply_logo_darkens_pixels_at_target_corner():
    """Der Logo-Bereich muss sich vom reinen Hintergrund unterscheiden — einfache,
    aber echte Prüfung, dass tatsächlich etwas eingeblendet wurde."""
    base = _base_jpeg(400, 300)
    result = apply_logo(base, _logo_png(100, 50), position="bottom-right", opacity=1.0)

    with Image.open(io.BytesIO(base)) as before, Image.open(io.BytesIO(result)) as after:
        before_px = before.convert("RGB").getpixel((380, 280))
        after_px = after.convert("RGB").getpixel((380, 280))
        assert before_px != after_px


@pytest.mark.parametrize("position", ["top-left", "top-right", "bottom-left", "bottom-right", "center"])
def test_apply_logo_all_positions_succeed(position):
    result = apply_logo(_base_jpeg(), _logo_png(), position=position)
    with Image.open(io.BytesIO(result)):
        pass  # dekodiert ohne Fehler


def test_apply_logo_invalid_position_raises():
    with pytest.raises(VisibleWatermarkError):
        apply_logo(_base_jpeg(), _logo_png(), position="nowhere")


def test_apply_logo_invalid_opacity_raises():
    with pytest.raises(VisibleWatermarkError):
        apply_logo(_base_jpeg(), _logo_png(), opacity=1.5)


def test_apply_text_returns_valid_image():
    result = apply_text(_base_jpeg(400, 300), "© urbanstudio", position="bottom-left")
    with Image.open(io.BytesIO(result)) as img:
        assert img.size == (400, 300)


def test_apply_text_changes_pixels_near_position():
    base = _base_jpeg(400, 300)
    result = apply_text(base, "WATERMARK", position="center", opacity=1.0, color=(255, 255, 0))

    with Image.open(io.BytesIO(base)) as before, Image.open(io.BytesIO(result)) as after:
        region_before = before.convert("RGB").crop((150, 130, 250, 170))
        region_after = after.convert("RGB").crop((150, 130, 250, 170))
        assert region_before.tobytes() != region_after.tobytes()
