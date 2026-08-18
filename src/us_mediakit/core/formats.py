"""Magic-byte-basierte Bildformaterkennung.

Portierung der Signaturtabelle aus SimpleImageLibrary3::getImageTypeFromString
(PHP), erweitert um HEIC/AVIF (ISO-BMFF "ftyp"-Box), die im PHP-Original fehlten.
"""

from __future__ import annotations

from PIL import Image, features

CONTENT_TYPES: dict[str, str] = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "bmp": "image/bmp",
    "tiff": "image/tiff",
    "tif": "image/tiff",
    "svg": "image/svg+xml",
    "avif": "image/avif",
    "webp": "image/webp",
    "heic": "image/heic",
    "heif": "image/heif",
}

# Einfache Präfix-Signaturen (Byte-Folge am Dateianfang), Reihenfolge wie im
# PHP-Original erhalten, damit bei mehrdeutigen Präfixen dasselbe Ergebnis
# entsteht (z. B. würde "webp" ohne die RIFF-Prüfung fälschlich vor anderen
# RIFF-Containern greifen — hier unverändert wie im Original übernommen).
_PREFIX_MAGICS: dict[str, tuple[bytes, ...]] = {
    "png": (bytes.fromhex("89504E470D0A1A0A"),),
    "jpg": (bytes.fromhex("FFD8FF"),),
    "bmp": (bytes.fromhex("424D"),),
    "tiff": (
        bytes.fromhex("49492A00"),
        bytes.fromhex("4D4D002A"),
        bytes.fromhex("492049"),
        bytes.fromhex("4D4D002B"),
    ),
    "tif": (
        bytes.fromhex("49492A00"),
        bytes.fromhex("4D4D002A"),
        bytes.fromhex("492049"),
        bytes.fromhex("4D4D002B"),
    ),
    "webp": (bytes.fromhex("52494646"),),
    "svg": (
        b"<!DOCTYPE svg",
        b'<?xml version="1.0" standalone="no"?>\n<!DOCTYPE svg',
    ),
}

# ISO-BMFF-Container (HEIC/AVIF): Byte 4-7 == b"ftyp", Subtype in Byte 8-11.
_FTYP_SUBTYPES: dict[str, tuple[bytes, ...]] = {
    "heic": (b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1"),
    "avif": (b"avif", b"avis"),
}


def get_image_type_from_bytes(data: bytes) -> str | None:
    """Erkennt den Bildtyp anhand der ersten Bytes. Gibt None zurück, wenn unbekannt."""
    for image_type, magics in _PREFIX_MAGICS.items():
        for magic in magics:
            if data.startswith(magic):
                return image_type

    # Erweiterung gegenüber SimpleImageLibrary3: dessen Signaturliste erkennt nur SVG
    # mit vorangestelltem "<!DOCTYPE"/XML-Prolog — ein SVG ganz ohne Prolog (in der Praxis
    # der Normalfall bei exportierten SVGs) fiel dort durch und würde als Rasterbild
    # fehlinterpretiert. Hier zusätzlich: ein "<svg" innerhalb der ersten 256 Bytes.
    head = data[:256].lstrip()
    if head.startswith(b"<svg") or (head.startswith(b"<?xml") and b"<svg" in head):
        return "svg"

    if len(data) >= 12 and data[4:8] == b"ftyp":
        subtype = data[8:12]
        for image_type, subtypes in _FTYP_SUBTYPES.items():
            if subtype in subtypes:
                return image_type

    return None


def get_image_type_from_file(path: str) -> str | None:
    with open(path, "rb") as f:
        head = f.read(256)
    return get_image_type_from_bytes(head)


def get_content_type(image_type: str) -> str | None:
    return CONTENT_TYPES.get(image_type)


# Für Subprozess-Aufrufe (exiftool, ffmpeg, pdftoppm), die aus dem Dateinamen auf das
# Format schließen — Bilddaten liegen in der Pipeline sonst nur als Bytes ohne Dateiname vor.
EXTENSION_BY_TYPE: dict[str, str] = {
    "jpg": ".jpg",
    "png": ".png",
    "tiff": ".tiff",
    "tif": ".tiff",
    "webp": ".webp",
    "bmp": ".bmp",
    "heic": ".heic",
    "avif": ".avif",
    "svg": ".svg",
}


def get_extension(image_type: str | None) -> str:
    return EXTENSION_BY_TYPE.get(image_type or "", ".bin")


# Pillow-Save-Formatname pro output_format-String, wie er über CLI/API angefragt wird.
SAVE_FORMAT_BY_TYPE: dict[str, str] = {
    "jpg": "JPEG",
    "jpeg": "JPEG",
    "png": "PNG",
    "webp": "WEBP",
    "gif": "GIF",
    "heic": "HEIF",
    "heif": "HEIF",
    "avif": "AVIF",
}


def is_write_format_available(save_format: str) -> bool:
    """Prüft, ob Pillow (inkl. registrierter Plugins wie pillow-heif) das jeweilige
    Format tatsächlich schreiben kann. AVIF hängt davon ab, ob die installierte
    Pillow-Wheel mit libavif gebaut wurde — nicht bei jedem Build/jeder Plattform
    garantiert, deshalb hier zur Laufzeit geprüft statt vorausgesetzt.

    `Image.init()` ist hier Pflicht, kein Optimierungsdetail: Pillow registriert
    Format-Plugins (auch weit verbreitete wie WEBP) erst lazy bei erstem Gebrauch —
    `Image.SAVE` ist in einem frischen Prozess ohne vorherigen `Image.init()`-Aufruf
    schlicht leer, auch wenn das Format tatsächlich verfügbar wäre (in-process
    reproduziert durch `python -c "from PIL import Image; print(Image.SAVE)"` direkt
    nach dem Import: leeres Dict)."""
    if save_format == "AVIF":
        return bool(features.check("avif"))
    Image.init()
    return save_format in Image.SAVE
