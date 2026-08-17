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
