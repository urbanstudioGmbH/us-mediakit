"""Testet OpenAICompatibleVisionProvider gegen einen echten cuttlefish-Prozess
(OpenAI-kompatibler Mock-LLM-Dienst, https://github.com/urbanstudioGmbH/cuttlefish) —
keine Mocks auf HTTP-Ebene, sondern ein echter Server, echte Requests.
"""

from __future__ import annotations

import socket
import subprocess
import time

import pytest

from us_mediakit.providers.base import ProviderError, ProviderUnavailableError
from us_mediakit.providers.vision_chat import OpenAICompatibleVisionProvider


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


def _tiny_jpeg() -> bytes:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (10, 10), "red").save(buf, format="JPEG")
    return buf.getvalue()


def test_caption_fixed_response(cuttlefish_base_url):
    provider = OpenAICompatibleVisionProvider(base_url=cuttlefish_base_url, model="cuttlefish/fixed")
    result = provider.caption(_tiny_jpeg(), prompt="Beschreibe dieses Bild.")
    assert result == "This is a deterministic Cuttlefish response."


def test_caption_echo_roundtrips_prompt_text(cuttlefish_base_url):
    """Bestätigt, dass der Prompt-Text im multi-part content-Array (Text + image_url)
    tatsächlich als Text-Teil ankommt, statt in der Bild-Codierung verloren zu gehen."""
    provider = OpenAICompatibleVisionProvider(base_url=cuttlefish_base_url, model="cuttlefish/echo")
    result = provider.caption(_tiny_jpeg(), prompt="ECHO_MARKER_XYZ_123")
    assert result == "ECHO_MARKER_XYZ_123"


def test_caption_server_error_raises_unavailable(cuttlefish_base_url):
    provider = OpenAICompatibleVisionProvider(base_url=cuttlefish_base_url, model="cuttlefish/error-503")
    with pytest.raises(ProviderUnavailableError):
        provider.caption(_tiny_jpeg(), prompt="hi")


def test_caption_client_error_raises_provider_error(cuttlefish_base_url):
    provider = OpenAICompatibleVisionProvider(base_url=cuttlefish_base_url, model="cuttlefish/error-429")
    with pytest.raises(ProviderError):
        provider.caption(_tiny_jpeg(), prompt="hi")


def test_caption_unreachable_endpoint_raises_unavailable():
    provider = OpenAICompatibleVisionProvider(
        base_url="http://127.0.0.1:1", model="cuttlefish/fixed", timeout_seconds=2
    )
    with pytest.raises(ProviderUnavailableError):
        provider.caption(_tiny_jpeg(), prompt="hi")
