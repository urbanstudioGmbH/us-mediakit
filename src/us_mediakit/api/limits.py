"""Geteilte Prozesslimits über Endpunkte hinweg.

`video_pdf_limiter` ist eine einzige Instanz für `/v1/thumbnail` (Video-/PDF-Zweig) und
`/v1/animated_webp` gemeinsam — beide starten CPU-teure ffmpeg/pdftoppm-Prozesse, die
Schwelle soll deshalb für alle zusammen gelten, nicht pro Endpunkt getrennt gezählt werden.
"""

from __future__ import annotations

import os

from us_mediakit.billing.rate_limit import ConcurrencyLimiter

video_pdf_limiter = ConcurrencyLimiter(
    max_concurrent=int(os.environ.get("USMEDIAKIT_MAX_CONCURRENT_VIDEO_PDF_JOBS", "4"))
)
