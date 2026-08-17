"""Testet das unsichtbare Wasserzeichen (Embedding + Erkennung) gegen die reale
`invisible-watermark`-Bibliothek. Alle Robustheits-Zahlen hier sind selbst gemessen
(siehe `us_mediakit/watermark/invisible.py`), nicht aus der Bibliotheks-Doku übernommen.
"""

from __future__ import annotations

import importlib.util
import io
from pathlib import Path

import pytest
from PIL import Image

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("imwatermark") is None,
    reason="invisible-watermark nicht installiert ([watermark]-Extra)",
)

from us_mediakit.watermark.detect import detect
from us_mediakit.watermark.invisible import WatermarkError, embed

_REAL_PHOTO = Path(__file__).parent.parent.parent / "docs" / "images" / "source.png"


def _real_photo_bytes() -> bytes:
    with Image.open(_REAL_PHOTO) as img:
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="PNG")
        return buf.getvalue()


def _solid_bytes(w: int, h: int, fmt: str = "JPEG") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (40, 100, 180)).save(buf, format=fmt)
    return buf.getvalue()


def test_embed_rejects_wrong_reference_id_length():
    with pytest.raises(WatermarkError):
        embed(_real_photo_bytes(), b"too-long")


def test_embed_rejects_images_below_minimum_size():
    with pytest.raises(WatermarkError):
        embed(_solid_bytes(200, 200), b"\x01\x02\x03\x04")


def test_embed_then_detect_roundtrip_recovers_reference_id():
    reference_id = b"\xaa\xbb\xcc\xdd"
    watermarked = embed(_real_photo_bytes(), reference_id, output_format="PNG")

    result = detect(watermarked)

    assert result.detected is True
    assert result.reference_id == reference_id


def test_detect_on_never_watermarked_image_reports_not_detected():
    result = detect(_real_photo_bytes())
    assert result.detected is False
    assert result.reference_id is None


def test_detect_on_too_small_image_reports_not_detected_without_error():
    result = detect(_solid_bytes(100, 100))
    assert result.detected is False


def test_watermark_survives_moderate_jpeg_recompression():
    """Eigener Messwert: bei Qualität >= 90 wird auf echten Fotos sowohl der Marker
    erkannt als auch die Referenz-ID bitgenau wiederhergestellt. Näher an der
    Überlebensgrenze (eigener Test bei Qualität 85 mit einer anderen Referenz-ID)
    erkennt der Marker zwar noch zuverlässig, aber einzelne Bits der Referenz-ID
    können bereits kippen — ein Grund, den Zielwert klar oberhalb der reinen
    "noch erkannt"-Schwelle zu dokumentieren, nicht direkt an ihr."""
    reference_id = b"\x01\x02\x03\x04"
    watermarked_png = embed(_real_photo_bytes(), reference_id, output_format="PNG")

    with Image.open(io.BytesIO(watermarked_png)) as img:
        recompressed_buf = io.BytesIO()
        img.convert("RGB").save(recompressed_buf, format="JPEG", quality=90)
        recompressed = recompressed_buf.getvalue()

    result = detect(recompressed)
    assert result.detected is True
    assert result.reference_id == reference_id


def test_watermark_does_not_reliably_survive_resize():
    """Dokumentiert eine echte Grenze (siehe invisible.py-Docstring): ein nachträgliches
    Verkleinern zerstört das Signal typischerweise — deshalb ist das Wasserzeichen eine
    eigenständige, nach der finalen Größenänderung anzuwendende Operation, nicht
    automatisch an `thumbnail` gekoppelt."""
    reference_id = b"\x01\x02\x03\x04"
    watermarked_png = embed(_real_photo_bytes(), reference_id, output_format="PNG")

    with Image.open(io.BytesIO(watermarked_png)) as img:
        half_size = (img.width // 2, img.height // 2)
        resized = img.resize(half_size, Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        resized.save(buf, format="PNG")
        resized_bytes = buf.getvalue()

    result = detect(resized_bytes)
    assert result.detected is False
