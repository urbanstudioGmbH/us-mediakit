"""Video-Frame-Extraktion via ffmpeg, Dauer-Check via ffprobe.

Nutzt `tempfile`-Context-Manager statt manueller Temp-Datei-Verwaltung — Aufräumen ist
damit auch bei einer Exception garantiert.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from us_mediakit.core.security import SubprocessError, run_subprocess

DEFAULT_SEEK_SECONDS = 8.0


def get_duration_seconds(data: bytes, *, timeout_seconds: float = 10.0) -> float | None:
    """Liefert die Videodauer in Sekunden, oder None, wenn sie nicht ermittelbar ist."""
    with tempfile.NamedTemporaryFile(suffix=".mp4") as tmp_video:
        tmp_video.write(data)
        tmp_video.flush()

        result = run_subprocess(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                tmp_video.name,
            ],
            timeout_seconds=timeout_seconds,
        )
        if result.returncode != 0:
            return None
        try:
            parsed = json.loads(result.stdout)
            return float(parsed["format"]["duration"])
        except (KeyError, ValueError, json.JSONDecodeError):
            return None


def extract_frame(
    data: bytes,
    *,
    seek_seconds: float = DEFAULT_SEEK_SECONDS,
    timeout_seconds: float = 30.0,
) -> bytes:
    """Extrahiert einen Frame als PNG. `seek_seconds` wird auf die Videodauer geklemmt
    (Sicherheitsnetz gegen ein Seek hinter das Videoende, siehe ffprobe-Check)."""
    duration = get_duration_seconds(data, timeout_seconds=timeout_seconds)
    if duration is not None and duration > 0:
        seek_seconds = min(seek_seconds, max(0.0, duration - 0.1))

    with tempfile.TemporaryDirectory() as tmp_dir:
        video_path = Path(tmp_dir) / "input.mp4"
        frame_path = Path(tmp_dir) / "frame.png"
        video_path.write_bytes(data)

        result = run_subprocess(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                str(seek_seconds),
                "-i",
                str(video_path),
                "-frames:v",
                "1",
                "-f",
                "image2",
                str(frame_path),
            ],
            timeout_seconds=timeout_seconds,
        )
        if result.returncode != 0 or not frame_path.exists():
            raise SubprocessError(
                f"Frame-Extraktion fehlgeschlagen: {result.stderr.decode(errors='replace')}"
            )
        return frame_path.read_bytes()
