"""`/v1/caption` End-to-End über den BYOK-Pfad gegen einen echten cuttlefish-Prozess."""

from __future__ import annotations

import base64
import shutil
import socket
import subprocess
import time

import pytest

from tests.integration._helpers import auth, jpeg_b64

pytestmark = pytest.mark.skipif(
    shutil.which("cuttlefish") is None,
    reason="cuttlefish nicht installiert (verlangt Python >= 3.12, siehe CONTRIBUTING.md)",
)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_until_up(port: int, timeout_seconds: float = 10.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("cuttlefish ist nicht rechtzeitig gestartet.")


@pytest.fixture(scope="module")
def cuttlefish_base_url():
    port = _free_port()
    proc = subprocess.Popen(
        ["cuttlefish", "serve", "--host", "127.0.0.1", "--port", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_until_up(port)
        yield f"http://127.0.0.1:{port}/v1"
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_caption_byok_writes_fixed_caption_into_metadata(client, raw_api_key, cuttlefish_base_url):
    response = client.post(
        "/v1/caption",
        json={
            "request_id": "cap-1",
            "source": jpeg_b64(200, 100),
            "provider_url": cuttlefish_base_url,
            "provider_model": "cuttlefish/fixed",
        },
        headers=auth(raw_api_key),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["caption"] == "This is a deterministic Cuttlefish response."
    assert body["skipped_existing"] is False
    assert body["credits_charged"] == 1  # caption.byok laut costweights.json

    from us_mediakit.metadata.read import read_metadata

    tags = read_metadata(base64.b64decode(body["data"]))
    assert tags["IPTC:ObjectName"] == "This is a deterministic Cuttlefish response."


def test_caption_only_if_empty_skips_when_already_present(client, raw_api_key, cuttlefish_base_url):
    from us_mediakit.metadata.write import write_tags

    pre_tagged = write_tags(base64.b64decode(jpeg_b64(200, 100)), {"IPTC:ObjectName": "Bereits da"})

    response = client.post(
        "/v1/caption",
        json={
            "request_id": "cap-2",
            "source": base64.b64encode(pre_tagged).decode("ascii"),
            "write_to": ["IPTC:ObjectName"],
            # absichtlich eine nicht erreichbare Adresse: skip muss greifen, BEVOR
            # irgendein Provider kontaktiert wird
            "provider_url": "http://127.0.0.1:1/v1",
            "provider_model": "cuttlefish/fixed",
        },
        headers=auth(raw_api_key),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["skipped_existing"] is True
    assert body["credits_charged"] == 0


def test_caption_dry_run_estimates_without_calling_provider(client, raw_api_key):
    response = client.post(
        "/v1/caption",
        json={
            "request_id": "cap-3",
            "source": jpeg_b64(),
            "dry_run": True,
            "provider_url": "http://127.0.0.1:1/v1",  # unerreichbar — dry_run darf nie dorthin
            "provider_model": "cuttlefish/fixed",
        },
        headers=auth(raw_api_key),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["dry_run"] is True
    assert body["estimated_credits"] == 1


def test_caption_provider_error_returns_502(client, raw_api_key, cuttlefish_base_url):
    response = client.post(
        "/v1/caption",
        json={
            "request_id": "cap-4",
            "source": jpeg_b64(),
            "provider_url": cuttlefish_base_url,
            "provider_model": "cuttlefish/error-503",
        },
        headers=auth(raw_api_key),
    )
    assert response.status_code == 502


def test_caption_mirror_exif_writes_both_fields(client, raw_api_key, cuttlefish_base_url):
    response = client.post(
        "/v1/caption",
        json={
            "request_id": "cap-5",
            "source": jpeg_b64(),
            "mirror_exif": True,
            "provider_url": cuttlefish_base_url,
            "provider_model": "cuttlefish/fixed",
        },
        headers=auth(raw_api_key),
    )
    assert response.status_code == 200

    from us_mediakit.metadata.read import read_metadata

    tags = read_metadata(base64.b64decode(response.json()["data"]))
    assert tags["EXIF:ImageDescription"] == "This is a deterministic Cuttlefish response."


def test_caption_without_any_provider_configured_returns_503(client, raw_api_key, monkeypatch):
    monkeypatch.delenv("USMEDIAKIT_PROVIDERS_CONFIG", raising=False)
    from us_mediakit.providers import registry

    registry.load_provider_config.cache_clear()

    response = client.post(
        "/v1/caption",
        json={"request_id": "cap-6", "source": jpeg_b64()},
        headers=auth(raw_api_key),
    )
    assert response.status_code == 503
