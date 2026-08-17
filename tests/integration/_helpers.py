import base64
import io

from PIL import Image


def auth(key: str) -> dict:
    return {"Authorization": f"Bearer {key}"}


def jpeg_b64(w: int = 200, h: int = 100) -> str:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (30, 90, 160)).save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode("ascii")
