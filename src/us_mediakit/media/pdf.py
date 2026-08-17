"""PDF-Seiten-Rendering via pdftoppm (poppler-utils).

Portierung des PDF-Zweigs aus SimpleImageLibrary3::thumbnailFromString.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from us_mediakit.core.security import SubprocessError, run_subprocess

DEFAULT_DPI = 150
DEFAULT_JPEG_QUALITY = 100


def render_page(
    data: bytes,
    *,
    page: int = 1,
    dpi: int = DEFAULT_DPI,
    jpeg_quality: int = DEFAULT_JPEG_QUALITY,
    timeout_seconds: float = 30.0,
) -> bytes:
    """Rendert eine PDF-Seite als JPEG."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pdf_path = Path(tmp_dir) / "input.pdf"
        out_prefix = Path(tmp_dir) / "page"
        pdf_path.write_bytes(data)

        result = run_subprocess(
            [
                "pdftoppm",
                "-f",
                str(page),
                "-l",
                str(page),
                "-jpeg",
                "-r",  # PHP-Original nutzt "-dpi" — ein Alias, den aktuelle poppler-utils-
                # Versionen nicht mehr kennen (getestet mit 26.08.0). "-r" ist der seit
                # Langem stabile, dokumentierte Parameter für die Auflösung.
                str(dpi),
                "-jpegopt",
                f"quality={jpeg_quality}",
                str(pdf_path),
                str(out_prefix),
            ],
            timeout_seconds=timeout_seconds,
        )

        # pdftoppm haengt bei mehrseitigen Dokumenten "-<seite>" an, bei genau einer
        # gerenderten Seite je nach Version ggf. ohne Suffix — beide Fälle abdecken.
        candidates = [
            out_prefix.with_name(f"{out_prefix.name}-{page}.jpg"),
            out_prefix.with_name(f"{out_prefix.name}.jpg"),
        ]
        rendered = next((p for p in candidates if p.exists()), None)

        if result.returncode != 0 or rendered is None:
            raise SubprocessError(
                f"PDF-Rendering fehlgeschlagen: {result.stderr.decode(errors='replace')}"
            )
        return rendered.read_bytes()
