import subprocess
import sys

from us_mediakit.core import formats


def test_detects_png():
    data = bytes.fromhex("89504E470D0A1A0A") + b"\x00" * 20
    assert formats.get_image_type_from_bytes(data) == "png"


def test_detects_jpg():
    data = bytes.fromhex("FFD8FF") + b"\x00" * 20
    assert formats.get_image_type_from_bytes(data) == "jpg"


def test_detects_webp():
    data = bytes.fromhex("52494646") + b"\x00" * 20
    assert formats.get_image_type_from_bytes(data) == "webp"


def test_detects_svg_doctype():
    data = b"<!DOCTYPE svg PUBLIC ...>"
    assert formats.get_image_type_from_bytes(data) == "svg"


def test_detects_svg_without_doctype():
    """Praxisfall: SVG-Export ohne DOCTYPE/XML-Prolog, den die reine PHP-Signaturliste
    nicht erkennen würde."""
    data = b'<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>'
    assert formats.get_image_type_from_bytes(data) == "svg"


def test_detects_heic_ftyp_box():
    data = b"\x00\x00\x00\x18" + b"ftyp" + b"heic" + b"\x00" * 20
    assert formats.get_image_type_from_bytes(data) == "heic"


def test_detects_avif_ftyp_box():
    data = b"\x00\x00\x00\x18" + b"ftyp" + b"avif" + b"\x00" * 20
    assert formats.get_image_type_from_bytes(data) == "avif"


def test_unknown_returns_none():
    assert formats.get_image_type_from_bytes(b"garbage-data") is None


def test_content_type_lookup():
    assert formats.get_content_type("jpg") == "image/jpeg"
    assert formats.get_content_type("nonexistent") is None


def test_is_write_format_available_for_always_supported_formats():
    assert formats.is_write_format_available("JPEG") is True
    assert formats.is_write_format_available("PNG") is True
    assert formats.is_write_format_available("WEBP") is True


def test_is_write_format_available_for_unknown_format():
    assert formats.is_write_format_available("NOT-A-REAL-FORMAT") is False


def test_is_write_format_available_webp_in_a_fresh_interpreter():
    """Regressionstest: `Image.SAVE` ist in einem komplett frischen Prozess leer, bis
    `Image.init()` läuft (Pillow registriert Format-Plugins lazy) — ein In-Prozess-Test
    im laufenden pytest-Prozess kann das nicht zuverlässig prüfen, weil vorherige Tests
    Pillow bereits "aufgewärmt" haben. Reproduziert den echten Bug: `thumbnail --format
    webp` schlug in einem frisch gestarteten CLI-Aufruf fehl, obwohl WEBP-Unterstützung
    installiert ist."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from us_mediakit.core import formats; print(formats.is_write_format_available('WEBP'))",
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.stdout.strip() == "True", result.stderr


def test_is_write_format_available_heif_after_pillow_heif_registration():
    """us_mediakit registriert pillow-heif beim Paket-Import (siehe __init__.py) —
    ohne das wäre "HEIF" hier nicht in Image.SAVE enthalten."""
    import us_mediakit  # noqa: F401 — Import löst die Registrierung aus

    assert formats.is_write_format_available("HEIF") is True
