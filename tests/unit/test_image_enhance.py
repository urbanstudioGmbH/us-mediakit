import base64
import json

import httpx
import pytest

from us_mediakit.providers.base import ProviderError, ProviderUnavailableError
from us_mediakit.providers.real_esrgan import RealEsrganProvider


def _client_with_handler(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_enhance_sends_expected_payload_and_parses_response():
    captured_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        body = json.loads(request.content)
        assert body == {
            "image": base64.b64encode(b"fake-image-bytes").decode("ascii"),
            "target_width": 100,
            "target_height": 200,
            "restore_faces": True,
        }
        return httpx.Response(
            200,
            json={
                "image": base64.b64encode(b"enhanced-bytes").decode("ascii"),
                "external_cost_micros": None,
            },
        )

    provider = RealEsrganProvider(endpoint="http://fake-provider", client=_client_with_handler(handler))
    result = provider.enhance(b"fake-image-bytes", target_width=100, target_height=200, restore_faces=True)

    assert result.data == b"enhanced-bytes"
    assert result.provider == "real-esrgan"
    assert len(captured_requests) == 1
    assert captured_requests[0].url == "http://fake-provider/enhance"


def test_enhance_server_error_raises_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="overloaded")

    provider = RealEsrganProvider(endpoint="http://fake-provider", client=_client_with_handler(handler))
    with pytest.raises(ProviderUnavailableError):
        provider.enhance(b"data")


def test_enhance_client_error_raises_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, text="bad request")

    provider = RealEsrganProvider(endpoint="http://fake-provider", client=_client_with_handler(handler))
    with pytest.raises(ProviderError):
        provider.enhance(b"data")


def test_enhance_malformed_response_raises_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    provider = RealEsrganProvider(endpoint="http://fake-provider", client=_client_with_handler(handler))
    with pytest.raises(ProviderError):
        provider.enhance(b"data")


def test_enhance_transport_error_raises_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    provider = RealEsrganProvider(endpoint="http://fake-provider", client=_client_with_handler(handler))
    with pytest.raises(ProviderUnavailableError):
        provider.enhance(b"data")
