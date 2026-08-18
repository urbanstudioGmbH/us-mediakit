import shutil

import pytest

from tests.integration._helpers import auth as _auth
from tests.integration._helpers import video_b64 as _video_b64

requires_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg nicht installiert")


@requires_ffmpeg
def test_thumbnail_video_seek_seconds_is_honored_via_api(client, raw_api_key):
    video_b64 = _video_b64(4)

    response_early = client.post(
        "/v1/thumbnail",
        json={
            "request_id": "seek-early",
            "source": video_b64,
            "mode": "showcase_medium",
            "is_video": True,
            "video_seek_seconds": 0.2,
            "output_format": "png",
        },
        headers=_auth(raw_api_key),
    )
    response_late = client.post(
        "/v1/thumbnail",
        json={
            "request_id": "seek-late",
            "source": video_b64,
            "mode": "showcase_medium",
            "is_video": True,
            "video_seek_seconds": 3.8,
            "output_format": "png",
        },
        headers=_auth(raw_api_key),
    )

    assert response_early.status_code == 200
    assert response_late.status_code == 200
    assert response_early.json()["data"] != response_late.json()["data"]


@requires_ffmpeg
def test_thumbnail_video_seek_seconds_omitted_uses_library_default(client, raw_api_key):
    """Regressionsschutz: ohne video_seek_seconds im Request muss weiterhin das
    bisherige Default-Verhalten (DEFAULT_SEEK_SECONDS, auf die Videodauer geklemmt)
    greifen, nicht z. B. 0 oder ein Validierungsfehler."""
    response = client.post(
        "/v1/thumbnail",
        json={
            "request_id": "seek-default",
            "source": _video_b64(4),
            "mode": "showcase_medium",
            "is_video": True,
            "output_format": "png",
        },
        headers=_auth(raw_api_key),
    )
    assert response.status_code == 200
