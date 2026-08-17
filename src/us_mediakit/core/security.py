"""Sicherheits-Grundhärtung: Größenlimits vor dem Decode, sichere Subprozess-Aufrufe.

Pillow hat mit `Image.MAX_IMAGE_PIXELS` bereits einen eingebauten Dekompressionsschutz
(Standard ~89 Megapixel, wirft `Image.DecompressionBombError`). Die Prüfungen hier sind
zusätzlich, konfigurierbar und laufen bewusst *vor* dem vollen Decode (nur Header-Lesen),
damit ein Instanzbetreiber eigene, ggf. strengere Limits setzen kann.
"""

from __future__ import annotations

import io
import subprocess
from dataclasses import dataclass

from PIL import Image

DEFAULT_MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB
DEFAULT_MAX_PIXELS = 60_000_000  # ~60 Megapixel


class SecurityLimitExceeded(ValueError):
    """Eingabedatei überschreitet ein konfiguriertes Sicherheitslimit."""


def check_file_size(data: bytes, *, max_file_size_bytes: int = DEFAULT_MAX_FILE_SIZE_BYTES) -> None:
    """Reine Größenprüfung, auch für Nicht-Rasterformate wie SVG anwendbar."""
    if len(data) > max_file_size_bytes:
        raise SecurityLimitExceeded(
            f"Datei ist {len(data)} Bytes groß, Limit liegt bei {max_file_size_bytes} Bytes."
        )


def check_image_size(
    data: bytes,
    *,
    max_file_size_bytes: int = DEFAULT_MAX_FILE_SIZE_BYTES,
    max_pixels: int = DEFAULT_MAX_PIXELS,
) -> None:
    """Prüft Dateigröße und (aus dem Header, ohne vollen Decode) Pixelanzahl.

    Muss vor jedem `Image.open(...).load()` aufgerufen werden — `Image.open()` allein
    liest nur den Header und ist damit für diese Prüfung sicher, auch bei präparierten
    Dateien mit riesigen behaupteten Abmessungen.
    """
    check_file_size(data, max_file_size_bytes=max_file_size_bytes)
    with Image.open(io.BytesIO(data)) as img:
        pixels = img.size[0] * img.size[1]
        if pixels > max_pixels:
            raise SecurityLimitExceeded(
                f"Bild hat {pixels} Pixel ({img.size[0]}x{img.size[1]}), "
                f"Limit liegt bei {max_pixels} Pixeln."
            )


@dataclass
class SubprocessResult:
    stdout: bytes
    stderr: bytes
    returncode: int


class SubprocessError(RuntimeError):
    pass


class SubprocessTimeout(SubprocessError):
    pass


def run_subprocess(
    args: list[str],
    *,
    timeout_seconds: float,
    input_bytes: bytes | None = None,
) -> SubprocessResult:
    """Sicherer Subprozess-Wrapper: ausschließlich Argument-Arrays, nie `shell=True`.

    `args` muss eine Liste sein (kein zusammengesetzter Shell-String) — das ist die
    zentrale Absicherung gegen Command-Injection über Dateinamen/Nutzereingaben, die an
    `exiftool`/`ffmpeg`/`pdftoppm` weitergereicht werden.
    """
    if isinstance(args, str):
        raise TypeError("args muss eine Liste von Argumenten sein, kein String (keine Shell).")
    try:
        proc = subprocess.run(
            args,
            input=input_bytes,
            capture_output=True,
            timeout=timeout_seconds,
            shell=False,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise SubprocessTimeout(
            f"Subprozess {args[0]!r} hat das Timeout von {timeout_seconds}s überschritten."
        ) from exc

    return SubprocessResult(stdout=proc.stdout, stderr=proc.stderr, returncode=proc.returncode)
