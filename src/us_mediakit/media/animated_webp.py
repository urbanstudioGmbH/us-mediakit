"""Animierter WebP-Ausschnitt aus einem Video.

ffmpeg extrahiert nur die Einzelframes (PNG-Sequenz, `image2`-Muxer, jede ffmpeg-Wheel
kann das) — die Animation selbst kodiert Pillow (`save_all=True`). Nicht über ffmpegs
eigenen `libwebp`-Encoder gelöst, weil der nur in mit `--enable-libwebp` gebauten
ffmpeg-Paketen vorhanden ist (z. B. der Standard-Homebrew-Build hat ihn nicht) — Pillows
WebP-Unterstützung bringt libwebp dagegen bereits selbst mit (dieselbe Lehre wie bei der
AVIF/HEIC-Ausgabe, siehe `core/formats.py`).

Eigene Operation, keine Variante von `core.pipeline.generate_thumbnail`: ein Zeitausschnitt
mit Mehrbild-Ausgabe ist fachlich etwas anderes als ein Zuschnitt/Resize eines Einzelbilds
(siehe `watermark`-Modul für dieselbe Trennung sichtbar/unsichtbar/Erkennung als Vorbild).
"""

from __future__ import annotations

import io
import tempfile
from pathlib import Path

from PIL import Image

from us_mediakit.core.security import SubprocessError, run_subprocess
from us_mediakit.media.video import get_duration_seconds

MAX_DURATION_SECONDS = 12.0
MAX_FPS = 24
MAX_FRAMES = 200
MAX_WIDTH = 1280

DEFAULT_FPS = 12
DEFAULT_QUALITY = 75


class AnimatedWebpError(ValueError):
    """Ungültige Eingabeparameter oder gescheiterte Frame-Extraktion."""


def extract_animated_webp(
    data: bytes,
    *,
    start_seconds: float = 0.0,
    duration_seconds: float = 3.0,
    width: int | None = None,
    fps: int = DEFAULT_FPS,
    quality: int = DEFAULT_QUALITY,
    timeout_seconds: float = 60.0,
) -> bytes:
    """Schneidet `[start_seconds, start_seconds + duration_seconds)` aus dem Video und
    liefert den Ausschnitt als animiertes, endlos-loopendes WebP.

    Alle Limits werfen `AnimatedWebpError` (Eingabefehler des Aufrufers), *bevor* ffmpeg
    überhaupt aufgerufen wird — verhindert überlange/CPU-teure Jobs statt sie erst
    nachträglich per Timeout abzubrechen.
    """
    if start_seconds < 0:
        raise AnimatedWebpError("start_seconds darf nicht negativ sein.")
    if duration_seconds <= 0:
        raise AnimatedWebpError("duration_seconds muss größer als 0 sein.")
    if duration_seconds > MAX_DURATION_SECONDS:
        raise AnimatedWebpError(
            f"duration_seconds={duration_seconds} überschreitet das Limit von {MAX_DURATION_SECONDS}s."
        )
    if fps <= 0:
        raise AnimatedWebpError("fps muss größer als 0 sein.")
    if fps > MAX_FPS:
        raise AnimatedWebpError(f"fps={fps} überschreitet das Limit von {MAX_FPS}.")
    if duration_seconds * fps > MAX_FRAMES:
        raise AnimatedWebpError(
            f"duration_seconds * fps ergibt {duration_seconds * fps:.0f} Frames, "
            f"Limit liegt bei {MAX_FRAMES}."
        )
    if width is not None and (width <= 0 or width > MAX_WIDTH):
        raise AnimatedWebpError(f"width muss zwischen 1 und {MAX_WIDTH} liegen.")
    if not (0 <= quality <= 100):
        raise AnimatedWebpError("quality muss zwischen 0 und 100 liegen.")

    total_duration = get_duration_seconds(data, timeout_seconds=timeout_seconds)
    if total_duration is not None and total_duration > 0:
        start_seconds = min(start_seconds, max(0.0, total_duration - 0.1))
        duration_seconds = min(duration_seconds, total_duration - start_seconds)

    scale_filter = f"scale={width}:-1:flags=lanczos" if width else "scale=trunc(iw/2)*2:trunc(ih/2)*2"

    with tempfile.TemporaryDirectory() as tmp_dir:
        video_path = Path(tmp_dir) / "input.mp4"
        video_path.write_bytes(data)
        frame_pattern = Path(tmp_dir) / "frame_%04d.png"

        result = run_subprocess(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                str(start_seconds),
                "-i",
                str(video_path),
                "-t",
                str(duration_seconds),
                "-vf",
                f"fps={fps},{scale_filter}",
                "-f",
                "image2",
                str(frame_pattern),
            ],
            timeout_seconds=timeout_seconds,
        )
        frame_paths = sorted(Path(tmp_dir).glob("frame_*.png"))
        if result.returncode != 0 or not frame_paths:
            raise SubprocessError(
                f"Frame-Extraktion für animiertes WebP fehlgeschlagen: "
                f"{result.stderr.decode(errors='replace')}"
            )

        frames = [Image.open(path) for path in frame_paths]
        try:
            buffer = io.BytesIO()
            frames[0].save(
                buffer,
                format="WEBP",
                save_all=True,
                append_images=frames[1:],
                duration=int(1000 / fps),
                loop=0,
                quality=quality,
            )
        finally:
            for frame in frames:
                frame.close()
        return buffer.getvalue()
