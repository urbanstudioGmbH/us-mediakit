import base64
import io
from pathlib import Path

from PIL import Image

from tests.integration._helpers import auth as _auth
from tests.integration._helpers import jpeg_b64 as _jpeg_b64
from us_mediakit.db.models import ApiKey

_FIXTURES = Path(__file__).parent.parent / "fixtures" / "c2pa"


# --- health ---


def test_health_needs_no_auth(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# --- Auth-Fälle ---


def test_thumbnail_without_auth_header_rejected(client):
    response = client.post("/v1/thumbnail", json={"request_id": "r1", "source": "", "mode": "x"})
    assert response.status_code == 401


def test_thumbnail_with_unknown_key_rejected(client):
    response = client.post(
        "/v1/thumbnail",
        json={"request_id": "r1", "source": "", "mode": "x"},
        headers=_auth("usmk_doesnotexist"),
    )
    assert response.status_code == 401


def test_thumbnail_with_suspended_key_rejected(client, raw_api_key, session_factory):
    with session_factory() as session:
        key = session.query(ApiKey).filter_by(account_ref="acct-1").one()
        key.status = "suspended"
        session.commit()

    response = client.post(
        "/v1/thumbnail",
        json={"request_id": "r1", "source": _jpeg_b64(), "mode": "showcase_medium"},
        headers=_auth(raw_api_key),
    )
    assert response.status_code == 403


# --- thumbnail ---


def test_thumbnail_happy_path(client, raw_api_key):
    response = client.post(
        "/v1/thumbnail",
        json={"request_id": "r-thumb-1", "source": _jpeg_b64(400, 300), "mode": "showcase_medium"},
        headers=_auth(raw_api_key),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["credits_charged"] == 3
    assert body["dry_run"] is False
    decoded = base64.b64decode(body["data"])
    with Image.open(io.BytesIO(decoded)) as img:
        assert img.format == "JPEG"


def test_thumbnail_unknown_mode_returns_422(client, raw_api_key):
    response = client.post(
        "/v1/thumbnail",
        json={"request_id": "r-thumb-2", "source": _jpeg_b64(), "mode": "does_not_exist"},
        headers=_auth(raw_api_key),
    )
    assert response.status_code == 422


def test_thumbnail_dry_run_costs_nothing_and_does_not_process(client, raw_api_key):
    response = client.post(
        "/v1/thumbnail",
        json={
            "request_id": "r-dry-1",
            "source": _jpeg_b64(400, 300),
            "mode": "showcase_medium",
            "dry_run": True,
        },
        headers=_auth(raw_api_key),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["dry_run"] is True
    assert body["estimated_credits"] == 3
    assert body["confidence"] == "exact"
    assert body["data"] is None


# --- Idempotenz ---


def test_repeated_request_id_returns_cached_response_without_double_billing(
    client, raw_api_key, session_factory
):
    payload = {
        "request_id": "r-idem-1",
        "source": _jpeg_b64(400, 300),
        "mode": "showcase_medium",
    }
    first = client.post("/v1/thumbnail", json=payload, headers=_auth(raw_api_key))
    second = client.post("/v1/thumbnail", json=payload, headers=_auth(raw_api_key))

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["data"] == second.json()["data"]

    from us_mediakit.db.models import UsageEvent

    with session_factory() as session:
        count = session.query(UsageEvent).filter_by(request_id="r-idem-1").count()
    assert count == 1


# --- Admin ---


def test_admin_endpoint_without_token_rejected(client):
    response = client.post("/admin/api-keys", json={"account_ref": "a", "label": "l"})
    assert response.status_code == 401


def test_admin_create_and_use_api_key(client):
    create_response = client.post(
        "/admin/api-keys",
        json={"account_ref": "acct-new", "label": "Neuer Key"},
        headers=_auth("test-admin-token"),
    )
    assert create_response.status_code == 200
    new_key = create_response.json()["api_key"]

    thumb_response = client.post(
        "/v1/thumbnail",
        json={"request_id": "r-admin-1", "source": _jpeg_b64(), "mode": "showcase_medium"},
        headers=_auth(new_key),
    )
    assert thumb_response.status_code == 200


def test_admin_suspend_then_reactivate(client, raw_api_key, session_factory):
    with session_factory() as session:
        key_id = session.query(ApiKey).filter_by(account_ref="acct-1").one().id

    suspend = client.post(f"/admin/api-keys/{key_id}/suspend", headers=_auth("test-admin-token"))
    assert suspend.status_code == 200
    assert suspend.json()["status"] == "suspended"

    blocked = client.post(
        "/v1/thumbnail",
        json={"request_id": "r-susp-1", "source": _jpeg_b64(), "mode": "showcase_medium"},
        headers=_auth(raw_api_key),
    )
    assert blocked.status_code == 403

    reactivate = client.post(
        f"/admin/api-keys/{key_id}/reactivate", headers=_auth("test-admin-token")
    )
    assert reactivate.status_code == 200

    allowed = client.post(
        "/v1/thumbnail",
        json={"request_id": "r-susp-2", "source": _jpeg_b64(), "mode": "showcase_medium"},
        headers=_auth(raw_api_key),
    )
    assert allowed.status_code == 200


def test_admin_usage_export_has_no_gaps_or_duplicates_on_repeated_poll(client, raw_api_key):
    for i in range(5):
        client.post(
            "/v1/thumbnail",
            json={"request_id": f"r-export-{i}", "source": _jpeg_b64(), "mode": "showcase_medium"},
            headers=_auth(raw_api_key),
        )

    all_ids: list[int] = []
    since_id = 0
    while True:
        response = client.get(
            "/admin/usage/export",
            params={"since_id": since_id, "limit": 2},
            headers=_auth("test-admin-token"),
        )
        assert response.status_code == 200
        body = response.json()
        all_ids.extend(event["id"] for event in body["events"])
        if body["next_since_id"] is None:
            break
        since_id = body["next_since_id"]

    assert len(all_ids) == 5
    assert len(set(all_ids)) == 5  # keine Duplikate
    assert all_ids == sorted(all_ids)  # keine Lücken/Unordnung


def test_admin_account_usage_aggregation(client, raw_api_key):
    client.post(
        "/v1/thumbnail",
        json={"request_id": "r-agg-1", "source": _jpeg_b64(), "mode": "showcase_medium"},
        headers=_auth(raw_api_key),
    )

    response = client.get(
        "/admin/accounts/acct-1/usage",
        headers=_auth("test-admin-token"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["by_operation"]["thumbnail"]["count"] == 1
    assert body["total_credits"] == 3


# --- Meta / C2PA über HTTP ---


def test_meta_read_endpoint(client, raw_api_key):
    response = client.post(
        "/v1/meta/read",
        json={"request_id": "r-meta-1", "source": _jpeg_b64()},
        headers=_auth(raw_api_key),
    )
    assert response.status_code == 200
    assert response.json()["tags"]["File:MIMEType"] == "image/jpeg"


def test_c2pa_verify_without_manifest(client, raw_api_key):
    response = client.post(
        "/v1/c2pa/verify",
        json={"request_id": "r-c2pa-1", "source": _jpeg_b64()},
        headers=_auth(raw_api_key),
    )
    assert response.status_code == 200
    assert response.json()["has_manifest"] is False


def test_c2pa_sign_without_configured_signer_returns_503(client, raw_api_key, monkeypatch):
    monkeypatch.delenv("USMEDIAKIT_C2PA_CERT_FILE", raising=False)
    monkeypatch.delenv("USMEDIAKIT_C2PA_KEY_FILE", raising=False)

    response = client.post(
        "/v1/c2pa/sign",
        json={
            "request_id": "r-c2pa-sign-1",
            "source": _jpeg_b64(),
            "digital_source_type": "digitalCapture",
        },
        headers=_auth(raw_api_key),
    )
    assert response.status_code == 503


def test_c2pa_sign_with_configured_signer(client, raw_api_key, monkeypatch):
    monkeypatch.setenv("USMEDIAKIT_C2PA_CERT_FILE", str(_FIXTURES / "es256_certs.pem"))
    monkeypatch.setenv("USMEDIAKIT_C2PA_KEY_FILE", str(_FIXTURES / "es256_private.key"))

    response = client.post(
        "/v1/c2pa/sign",
        json={
            "request_id": "r-c2pa-sign-2",
            "source": _jpeg_b64(),
            "digital_source_type": "digitalCapture",
        },
        headers=_auth(raw_api_key),
    )
    assert response.status_code == 200
    signed = base64.b64decode(response.json()["data"])

    from us_mediakit.c2pa.read import has_manifest

    assert has_manifest(signed, "image/jpeg") is True


# Alle Endpunkte sind seit Phase 6 echt implementiert — siehe test_caption.py,
# test_ai_upscale.py, test_watermark_api.py für die jeweiligen Phase-5/6-Endpunkttests.
