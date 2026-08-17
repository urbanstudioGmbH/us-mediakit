"""EXIF/IPTC/XMP schreiben und von einer Quelle auf ein Derivat übertragen.

`copy_metadata_from` ist der Baustein, den `core.pipeline` fest verdrahtet: jede
erzeugte Bildvariante bekommt die Metadaten des Originals per exiftools
`-tagsFromFile` zurückgeschrieben, bevor sie ausgeliefert wird.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from us_mediakit.core.formats import get_extension, get_image_type_from_bytes
from us_mediakit.metadata.exiftool_client import ExifToolClient, ExifToolError


def write_tags(data: bytes, tags: dict[str, str], *, client: ExifToolClient | None = None) -> bytes:
    """Setzt einzelne Tags (z. B. `{"IPTC:ObjectName": "..."}`) und gibt die geänderte Datei zurück."""
    owns_client = client is None
    active_client = client or ExifToolClient()
    suffix = get_extension(get_image_type_from_bytes(data))
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix) as tmp:
            tmp.write(data)
            tmp.flush()
            active_client.write_tags(tmp.name, tags)
            return Path(tmp.name).read_bytes()
    finally:
        if owns_client:
            active_client.close()


def copy_metadata_from(
    source_data: bytes,
    target_data: bytes,
    *,
    exclude_groups: list[str] | None = None,
    client: ExifToolClient | None = None,
) -> bytes:
    """Kopiert alle Metadaten von `source_data` auf `target_data` (per `-tagsFromFile`).

    `exclude_groups` (z. B. `["GPS"]`) schließt einzelne Tag-Gruppen von der Übernahme aus
    — genutzt von `strip_gps`, damit ein Derivat den Standort des Originals nicht erbt.
    """
    owns_client = client is None
    active_client = client or ExifToolClient()

    source_suffix = get_extension(get_image_type_from_bytes(source_data))
    target_suffix = get_extension(get_image_type_from_bytes(target_data))

    try:
        with (
            tempfile.NamedTemporaryFile(suffix=source_suffix) as source_tmp,
            tempfile.NamedTemporaryFile(suffix=target_suffix) as target_tmp,
        ):
            source_tmp.write(source_data)
            source_tmp.flush()
            target_tmp.write(target_data)
            target_tmp.flush()

            # Die naheliegende Exclude-Syntax "--GROUP:all" wird von -tagsFromFile beim
            # Kopieren nicht respektiert (mit exiftool 13.55 nachgestellt) — stattdessen
            # erst alles kopieren und die auszuschließenden Gruppen danach explizit
            # löschen. Reihenfolge ist entscheidend: der Löschbefehl muss nach dem
            # Kopierbefehl stehen, damit er ihn überschreibt.
            args = ["-tagsFromFile", source_tmp.name, "-all:all"]
            args.extend(f"-{group}:all=" for group in exclude_groups or [])
            args.append("-overwrite_original")
            args.append(target_tmp.name)

            raw = active_client.run_raw(args)
            if b"error" in raw.lower() and b"0 image files updated" not in raw.lower():
                raise ExifToolError(f"Metadaten-Übernahme fehlgeschlagen: {raw!r}")

            return Path(target_tmp.name).read_bytes()
    finally:
        if owns_client:
            active_client.close()
