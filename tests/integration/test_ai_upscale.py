"""`/v1/ai_upscale` End-to-End gegen einen echten lokalen Test-Doppelgänger-Server, der
den projekteigenen Bild-rein/Bild-raus-HTTP-Vertrag aus `providers/image_enhance.py`
bedient — kein Mock auf Python-Objektebene, sondern ein echter HTTP-Request-Roundtrip.
"""

from __future__ import annotations

import base64
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from tests.integration._helpers import auth, jpeg_b64


class _EnhanceServerState:
    def __init__(self) -> None:
        self.mode = "success"  # "success" | "error-503" | "error-422"
        self.received_payloads: list[dict] = []


def _make_handler(state: _EnhanceServerState) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            state.received_payloads.append(body)

            if state.mode == "error-503":
                self.send_response(503)
                self.end_headers()
                self.wfile.write(b"overloaded")
                return
            if state.mode == "error-422":
                self.send_response(422)
                self.end_headers()
                self.wfile.write(b"bad request")
                return

            enhanced = base64.b64encode(b"enhanced-image-bytes").decode("ascii")
            response = json.dumps({"image": enhanced, "external_cost_micros": None}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        def log_message(self, format: str, *args: object) -> None:  # Testausgabe stumm halten
            pass

    return Handler


@pytest.fixture
def enhance_server():
    state = _EnhanceServerState()
    server = HTTPServer(("127.0.0.1", 0), _make_handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield state, f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)


@pytest.fixture
def providers_config_file(tmp_path, enhance_server):
    _state, base_url = enhance_server
    path = tmp_path / "providers.yaml"
    path.write_text(
        f"""
providers:
  ai_upscale:
    default: "real-esrgan"
    registered:
      real-esrgan:
        endpoint: "{base_url}"
      codeformer:
        endpoint: "{base_url}"
      seedvr2-3b:
        endpoint: "{base_url}"
""",
        encoding="utf-8",
    )
    return path


@pytest.fixture(autouse=True)
def _clear_registry_cache():
    from us_mediakit.providers import registry

    registry.load_provider_config.cache_clear()
    yield
    registry.load_provider_config.cache_clear()


def test_ai_upscale_happy_path_uses_instance_default(
    client, raw_api_key, providers_config_file, monkeypatch, enhance_server
):
    monkeypatch.setenv("USMEDIAKIT_PROVIDERS_CONFIG", str(providers_config_file))
    state, _ = enhance_server

    response = client.post(
        "/v1/ai_upscale",
        json={"request_id": "up-1", "source": jpeg_b64(100, 100), "target_width": 400, "target_height": 300},
        headers=auth(raw_api_key),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "real-esrgan"
    assert body["ai_upscale_fallback"] is False
    assert base64.b64decode(body["data"]) == b"enhanced-image-bytes"
    assert body["credits_charged"] == 5  # ai_upscale.real-esrgan laut costweights.json

    assert state.received_payloads[0]["target_width"] == 400
    assert state.received_payloads[0]["target_height"] == 300


def test_ai_upscale_explicit_provider_overrides_instance_default(
    client, raw_api_key, providers_config_file, monkeypatch
):
    monkeypatch.setenv("USMEDIAKIT_PROVIDERS_CONFIG", str(providers_config_file))
    response = client.post(
        "/v1/ai_upscale",
        json={"request_id": "up-2", "source": jpeg_b64(), "provider": "seedvr2-3b"},
        headers=auth(raw_api_key),
    )
    assert response.status_code == 200
    assert response.json()["provider"] == "seedvr2-3b"


def test_ai_upscale_provider_without_cost_weight_returns_422(
    client, raw_api_key, providers_config_file, monkeypatch
):
    """codeformer ist registriert (für restore_faces), aber nicht als primärer
    ai_upscale-Provider bepreist — das muss eine klare 422 sein, kein 500er."""
    monkeypatch.setenv("USMEDIAKIT_PROVIDERS_CONFIG", str(providers_config_file))
    response = client.post(
        "/v1/ai_upscale",
        json={"request_id": "up-2b", "source": jpeg_b64(), "provider": "codeformer"},
        headers=auth(raw_api_key),
    )
    assert response.status_code == 422


def test_ai_upscale_no_provider_configured_returns_422(client, raw_api_key, monkeypatch):
    monkeypatch.delenv("USMEDIAKIT_PROVIDERS_CONFIG", raising=False)
    response = client.post(
        "/v1/ai_upscale",
        json={"request_id": "up-3", "source": jpeg_b64()},
        headers=auth(raw_api_key),
    )
    assert response.status_code == 422


def test_ai_upscale_provider_unavailable_falls_back_to_plain_resize(
    client, raw_api_key, providers_config_file, monkeypatch, enhance_server
):
    monkeypatch.setenv("USMEDIAKIT_PROVIDERS_CONFIG", str(providers_config_file))
    state, _ = enhance_server
    state.mode = "error-503"

    response = client.post(
        "/v1/ai_upscale",
        json={
            "request_id": "up-4",
            "source": jpeg_b64(100, 100),
            "target_width": 50,
            "target_height": 50,
        },
        headers=auth(raw_api_key),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ai_upscale_fallback"] is True
    # Trotz Fallback wird der angefragte Umfang abgerechnet (siehe ai_upscale.py-Kommentar).
    assert body["credits_charged"] == 5

    import io

    from PIL import Image

    with Image.open(io.BytesIO(base64.b64decode(body["data"]))) as img:
        assert img.size == (50, 50)


def test_ai_upscale_provider_client_error_returns_502(
    client, raw_api_key, providers_config_file, monkeypatch, enhance_server
):
    monkeypatch.setenv("USMEDIAKIT_PROVIDERS_CONFIG", str(providers_config_file))
    state, _ = enhance_server
    state.mode = "error-422"

    response = client.post(
        "/v1/ai_upscale",
        json={"request_id": "up-5", "source": jpeg_b64()},
        headers=auth(raw_api_key),
    )
    assert response.status_code == 502


def test_ai_upscale_restore_faces_charges_extra_credits(
    client, raw_api_key, providers_config_file, monkeypatch
):
    monkeypatch.setenv("USMEDIAKIT_PROVIDERS_CONFIG", str(providers_config_file))
    response = client.post(
        "/v1/ai_upscale",
        json={"request_id": "up-6", "source": jpeg_b64(), "restore_faces": True},
        headers=auth(raw_api_key),
    )
    assert response.status_code == 200
    body = response.json()
    # ai_upscale.real-esrgan (5) + face_restore.codeformer (3) laut costweights.json
    assert body["credits_charged"] == 8
    assert body["provider"] == "real-esrgan+codeformer"


def test_ai_upscale_dry_run_with_restore_faces_includes_extra_credits(
    client, raw_api_key, providers_config_file, monkeypatch
):
    monkeypatch.setenv("USMEDIAKIT_PROVIDERS_CONFIG", str(providers_config_file))
    response = client.post(
        "/v1/ai_upscale",
        json={
            "request_id": "up-7",
            "source": jpeg_b64(),
            "restore_faces": True,
            "dry_run": True,
        },
        headers=auth(raw_api_key),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["dry_run"] is True
    assert body["estimated_credits"] == 8
