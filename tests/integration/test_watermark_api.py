"""`/v1/watermark` und `/v1/watermark/detect` End-to-End."""

from __future__ import annotations

import base64
import importlib.util
import io
from pathlib import Path

import pytest
from PIL import Image

from tests.integration._helpers import auth

requires_invisible_watermark = pytest.mark.skipif(
    importlib.util.find_spec("imwatermark") is None,
    reason="invisible-watermark nicht installiert ([watermark]-Extra)",
)

_REAL_PHOTO = Path(__file__).parent.parent.parent / "docs" / "images" / "source.png"


def _real_photo_b64() -> str:
    with Image.open(_REAL_PHOTO) as img:
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("ascii")


def _logo_b64() -> str:
    buf = io.BytesIO()
    Image.new("RGBA", (60, 30), (255, 0, 0, 200)).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


# --- sichtbar ---


def test_watermark_visible_with_logo(client, raw_api_key):
    response = client.post(
        "/v1/watermark",
        json={
            "request_id": "wm-1",
            "source": _real_photo_b64(),
            "mode": "visible",
            "logo": _logo_b64(),
        },
        headers=auth(raw_api_key),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["credits_charged"] == 2  # watermark_visible laut costweights.json
    with Image.open(io.BytesIO(base64.b64decode(body["data"]))):
        pass


def test_watermark_visible_with_text(client, raw_api_key):
    response = client.post(
        "/v1/watermark",
        json={"request_id": "wm-2", "source": _real_photo_b64(), "mode": "visible", "text": "© test"},
        headers=auth(raw_api_key),
    )
    assert response.status_code == 200


def test_watermark_visible_without_logo_or_text_returns_422(client, raw_api_key):
    response = client.post(
        "/v1/watermark",
        json={"request_id": "wm-3", "source": _real_photo_b64(), "mode": "visible"},
        headers=auth(raw_api_key),
    )
    assert response.status_code == 422


def test_watermark_invalid_mode_returns_422(client, raw_api_key):
    response = client.post(
        "/v1/watermark",
        json={"request_id": "wm-4", "source": _real_photo_b64(), "mode": "sideways"},
        headers=auth(raw_api_key),
    )
    assert response.status_code == 422


# --- unsichtbar ---


@requires_invisible_watermark
def test_watermark_invisible_generates_reference_id_when_omitted(client, raw_api_key):
    response = client.post(
        "/v1/watermark",
        json={"request_id": "wm-5", "source": _real_photo_b64(), "mode": "invisible"},
        headers=auth(raw_api_key),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["credits_charged"] == 4  # watermark_invisible laut costweights.json
    assert len(bytes.fromhex(body["reference_id"])) == 4


@requires_invisible_watermark
def test_watermark_invisible_uses_caller_supplied_reference_id(client, raw_api_key):
    response = client.post(
        "/v1/watermark",
        json={
            "request_id": "wm-6",
            "source": _real_photo_b64(),
            "mode": "invisible",
            "reference_id": "01020304",
        },
        headers=auth(raw_api_key),
    )
    assert response.status_code == 200
    assert response.json()["reference_id"] == "01020304"


@requires_invisible_watermark
def test_watermark_invisible_rejects_wrong_length_reference_id(client, raw_api_key):
    response = client.post(
        "/v1/watermark",
        json={
            "request_id": "wm-7",
            "source": _real_photo_b64(),
            "mode": "invisible",
            "reference_id": "0102",
        },
        headers=auth(raw_api_key),
    )
    assert response.status_code == 422


@requires_invisible_watermark
def test_watermark_invisible_too_small_image_returns_422(client, raw_api_key):
    buf = io.BytesIO()
    Image.new("RGB", (100, 100), (10, 10, 10)).save(buf, format="PNG")
    small_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    response = client.post(
        "/v1/watermark",
        json={"request_id": "wm-8", "source": small_b64, "mode": "invisible"},
        headers=auth(raw_api_key),
    )
    assert response.status_code == 422


# --- Erkennung ---


@requires_invisible_watermark
def test_watermark_detect_roundtrip_via_api(client, raw_api_key):
    embed_response = client.post(
        "/v1/watermark",
        json={
            "request_id": "wm-9",
            "source": _real_photo_b64(),
            "mode": "invisible",
            "reference_id": "deadbeef",
        },
        headers=auth(raw_api_key),
    )
    watermarked_b64 = embed_response.json()["data"]

    detect_response = client.post(
        "/v1/watermark/detect",
        json={"request_id": "wm-10", "source": watermarked_b64},
        headers=auth(raw_api_key),
    )
    assert detect_response.status_code == 200
    body = detect_response.json()
    assert body["detected"] is True
    assert body["reference_id"] == "deadbeef"
    assert body["credits_charged"] == 1  # watermark_detect laut costweights.json


@requires_invisible_watermark
def test_watermark_detect_on_plain_image_reports_not_detected(client, raw_api_key):
    response = client.post(
        "/v1/watermark/detect",
        json={"request_id": "wm-11", "source": _real_photo_b64()},
        headers=auth(raw_api_key),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["detected"] is False
    assert body["reference_id"] is None
