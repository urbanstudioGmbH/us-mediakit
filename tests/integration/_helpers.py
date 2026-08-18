import base64
import io
import subprocess
import tempfile
from pathlib import Path

from PIL import Image


def auth(key: str) -> dict:
    return {"Authorization": f"Bearer {key}"}


def jpeg_b64(w: int = 200, h: int = 100) -> str:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (30, 90, 160)).save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def video_b64(duration_seconds: int = 2) -> str:
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_path = Path(tmp_dir) / "test.mp4"
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"testsrc=duration={duration_seconds}:size=64x64:rate=10",
                str(out_path),
            ],
            check=True,
            timeout=30,
        )
        return base64.b64encode(out_path.read_bytes()).decode("ascii")
