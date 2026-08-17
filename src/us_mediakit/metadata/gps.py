"""`strip_gps`: gezielt Standortfelder entfernen, ohne den Rest der Metadaten anzufassen.

Deckt die EXIF-GPS-IFD ab (`-gps:all=`, der Normalfall bei Fotos von Kamera/Smartphone)
sowie die gängigen, in XMP gespiegelten Standort-Tags. Exotischere, nicht standardisierte
Standort-Ablagen (z. B. proprietäre XMP-Erweiterungen einzelner Programme) sind damit
nicht abgedeckt — das ist eine bewusste Scope-Grenze, keine übersehene Lücke.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from us_mediakit.core.formats import get_extension, get_image_type_from_bytes
from us_mediakit.metadata.exiftool_client import ExifToolClient, ExifToolError

_STRIP_ARGS = [
    "-gps:all=",
    "-xmp-exif:gpslatitude=",
    "-xmp-exif:gpslongitude=",
    "-xmp-exif:gpsaltitude=",
    "-xmp-iptcext:locationshown=",
    "-xmp-iptcext:locationcreated=",
]


def strip_gps(data: bytes, *, client: ExifToolClient | None = None) -> bytes:
    """Gibt eine Kopie von `data` ohne GPS-/Standortfelder zurück."""
    owns_client = client is None
    active_client = client or ExifToolClient()
    suffix = get_extension(get_image_type_from_bytes(data))
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix) as tmp:
            tmp.write(data)
            tmp.flush()
            raw = active_client.run_raw([*_STRIP_ARGS, "-overwrite_original", tmp.name])
            if b"error" in raw.lower() and b"0 image files updated" not in raw.lower():
                raise ExifToolError(f"GPS-Entfernung fehlgeschlagen: {raw!r}")
            return Path(tmp.name).read_bytes()
    finally:
        if owns_client:
            active_client.close()
