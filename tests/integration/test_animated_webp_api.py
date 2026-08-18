import base64
import io
import shutil

import pytest
from PIL import Image

from tests.integration._helpers import auth as _auth
from tests.integration._helpers import video_b64 as _video_b64

requires_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg nicht installiert")


@requires_ffmpeg
def test_animated_webp_happy_path(client, raw_api_key):
    response = client.post(
        "/v1/animated_webp",
        json={
            "request_id": "r-webp-1",
            "source": _video_b64(2),
            "start_seconds": 0.0,
            "duration_seconds": 1.0,
            "fps": 8,
        },
        headers=_auth(raw_api_key),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["credits_charged"] == 10
    assert body["frame_count"] > 1
    with Image.open(io.BytesIO(base64.b64decode(body["data"]))) as img:
        assert img.format == "WEBP"


def test_animated_webp_duration_over_limit_returns_422(client, raw_api_key):
    response = client.post(
        "/v1/animated_webp",
        json={
            "request_id": "r-webp-2",
            "source": base64.b64encode(b"not-a-real-video").decode("ascii"),
            "duration_seconds": 999,
        },
        headers=_auth(raw_api_key),
    )
    assert response.status_code == 422


def test_animated_webp_dry_run_costs_nothing(client, raw_api_key):
    response = client.post(
        "/v1/animated_webp",
        json={
            "request_id": "r-webp-3",
            "source": base64.b64encode(b"not-a-real-video").decode("ascii"),
            "dry_run": True,
        },
        headers=_auth(raw_api_key),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["dry_run"] is True
    assert body["estimated_credits"] == 10
