"""EXIF/IPTC/XMP lesen. C2PA-Daten kommen in Phase 3 hinzu (siehe `us_mediakit.c2pa`)."""

from __future__ import annotations

import tempfile
from typing import Any

from us_mediakit.core.formats import get_extension, get_image_type_from_bytes
from us_mediakit.metadata.exiftool_client import ExifToolClient


def read_metadata(data: bytes, *, client: ExifToolClient | None = None) -> dict[str, Any]:
    """Liest alle von exiftool erkannten Metadaten-Gruppen (EXIF/IPTC/XMP/File/...)."""
    owns_client = client is None
    active_client = client or ExifToolClient()
    suffix = get_extension(get_image_type_from_bytes(data))
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix) as tmp:
            tmp.write(data)
            tmp.flush()
            return active_client.read_tags(tmp.name)
    finally:
        if owns_client:
            active_client.close()
