import io

import pytest
from PIL import Image

from us_mediakit.core.pipeline import (
    ThumbnailRequest,
    UnsupportedOutputFormatError,
    generate_thumbnail,
)


def _jpeg_bytes(w: int, h: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (10, 120, 200)).save(buf, format="JPEG")
    return buf.getvalue()


def test_generate_thumbnail_jpeg_roundtrip():
    request = ThumbnailRequest(
        source=_jpeg_bytes(400, 300),
        mode={"w": 100, "h": 100, "fit": "full", "xalign": "center", "yalign": "center"},
        output_format="jpg",
    )
    result = generate_thumbnail(request)

    assert result.content_type == "image/jpeg"
    assert (result.target_width, result.target_height) == (100, 100)
    with Image.open(io.BytesIO(result.data)) as decoded:
        assert decoded.size == (100, 100)


def test_generate_thumbnail_png_output_keeps_alpha():
    buf = io.BytesIO()
    Image.new("RGBA", (200, 200), (0, 0, 0, 0)).save(buf, format="PNG")

    request = ThumbnailRequest(
        source=buf.getvalue(),
        mode={"w": 50, "h": 50, "fit": "crop"},
        output_format="png",
    )
    result = generate_thumbnail(request)

    with Image.open(io.BytesIO(result.data)) as decoded:
        assert decoded.mode == "RGBA"
        assert decoded.size == (50, 50)


def test_generate_thumbnail_svg_passthrough_sanitized():
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    request = ThumbnailRequest(source=svg, mode={"w": 50, "h": 50, "fit": "full"})
    result = generate_thumbnail(request)

    assert result.content_type == "image/svg+xml"
    assert b"script" not in result.data


def test_generate_thumbnail_avif_output_roundtrips():
    request = ThumbnailRequest(
        source=_jpeg_bytes(200, 200),
        mode={"w": 50, "h": 50, "fit": "full"},
        output_format="avif",
        carry_metadata=False,
    )
    result = generate_thumbnail(request)

    assert result.content_type == "image/avif"
    with Image.open(io.BytesIO(result.data)) as decoded:
        assert decoded.format == "AVIF"
        assert decoded.size == (50, 50)


def test_generate_thumbnail_heic_output_roundtrips():
    request = ThumbnailRequest(
        source=_jpeg_bytes(200, 200),
        mode={"w": 50, "h": 50, "fit": "full"},
        output_format="heic",
        carry_metadata=False,
    )
    result = generate_thumbnail(request)

    assert result.content_type == "image/heic"
    with Image.open(io.BytesIO(result.data)) as decoded:
        assert decoded.size == (50, 50)


def test_generate_thumbnail_unknown_output_format_raises_clear_error():
    request = ThumbnailRequest(
        source=_jpeg_bytes(100, 100),
        mode={"w": 20, "h": 20, "fit": "full"},
        output_format="bogus",
    )
    with pytest.raises(UnsupportedOutputFormatError, match="bogus"):
        generate_thumbnail(request)


def test_provenance_hook_is_invoked():
    calls = []

    def hook(*, source, result, request):
        calls.append((len(source), len(result), request.mode))
        return result

    request = ThumbnailRequest(
        source=_jpeg_bytes(100, 100),
        mode={"w": 20, "h": 20, "fit": "full"},
    )
    generate_thumbnail(request, provenance_hook=hook)

    assert len(calls) == 1
