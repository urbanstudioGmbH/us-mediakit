import json

import httpx
import pytest

from us_mediakit.providers.base import ProviderError, ProviderUnavailableError
from us_mediakit.providers.claid_ai import CLAID_ENDPOINT, ClaidAiProvider


def _client_with_handler(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_enhance_happy_path_downloads_result_from_tmp_url():
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == CLAID_ENDPOINT:
            body = json.loads(request.content)
            assert body["input"].startswith("data:image/jpeg;base64,")
            assert body["operations"]["restorations"]["upscale"] == "smart_enhance"
            assert body["operations"]["resizing"] == {"width": 300, "height": 200, "fit": "cover"}
            assert body["output"]["format"] == {"type": "jpeg", "quality": 90}
            return httpx.Response(
                200, json={"data": {"output": {"tmp_url": "https://claid.example/tmp/result.jpg"}}}
            )
        if str(request.url) == "https://claid.example/tmp/result.jpg":
            return httpx.Response(200, content=b"upscaled-bytes")
        raise AssertionError(f"unerwartete URL: {request.url}")

    provider = ClaidAiProvider(api_key="fake-key", client=_client_with_handler(handler))
    result = provider.enhance(_jpeg_bytes(), target_width=300, target_height=200)

    assert result.data == b"upscaled-bytes"
    assert result.provider == "claid-ai"
    assert result.external_cost_micros is None


def test_enhance_without_target_size_omits_resizing():
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == CLAID_ENDPOINT:
            body = json.loads(request.content)
            assert "resizing" not in body["operations"]
            return httpx.Response(
                200, json={"data": {"output": {"tmp_url": "https://claid.example/tmp/x.jpg"}}}
            )
        return httpx.Response(200, content=b"bytes")

    provider = ClaidAiProvider(api_key="fake-key", client=_client_with_handler(handler))
    provider.enhance(_jpeg_bytes())


def test_enhance_png_uses_optimal_compression_not_quality():
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == CLAID_ENDPOINT:
            body = json.loads(request.content)
            assert body["output"]["format"] == {"type": "png", "compression": "optimal"}
            return httpx.Response(
                200, json={"data": {"output": {"tmp_url": "https://claid.example/tmp/x.png"}}}
            )
        return httpx.Response(200, content=b"bytes")

    provider = ClaidAiProvider(api_key="fake-key", client=_client_with_handler(handler))
    provider.enhance(_png_bytes())


def test_enhance_server_error_raises_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="down")

    provider = ClaidAiProvider(api_key="fake-key", client=_client_with_handler(handler))
    with pytest.raises(ProviderUnavailableError):
        provider.enhance(_jpeg_bytes())


def test_enhance_client_error_raises_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="unauthorized")

    provider = ClaidAiProvider(api_key="wrong-key", client=_client_with_handler(handler))
    with pytest.raises(ProviderError):
        provider.enhance(_jpeg_bytes())


def test_enhance_download_failure_raises_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == CLAID_ENDPOINT:
            return httpx.Response(
                200, json={"data": {"output": {"tmp_url": "https://claid.example/tmp/gone.jpg"}}}
            )
        return httpx.Response(404, text="not found")

    provider = ClaidAiProvider(api_key="fake-key", client=_client_with_handler(handler))
    with pytest.raises(ProviderUnavailableError):
        provider.enhance(_jpeg_bytes())


def _jpeg_bytes() -> bytes:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (10, 10), "red").save(buf, format="JPEG")
    return buf.getvalue()


def _png_bytes() -> bytes:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (10, 10), "red").save(buf, format="PNG")
    return buf.getvalue()
