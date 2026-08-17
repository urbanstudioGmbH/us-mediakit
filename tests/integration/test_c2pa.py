import io
import shutil
from pathlib import Path

import pytest
from PIL import Image

from us_mediakit.c2pa.propagate import propagate
from us_mediakit.c2pa.read import has_manifest, read_manifest
from us_mediakit.c2pa.sign import IngredientRef, SignerConfig, SignRequest, sign
from us_mediakit.c2pa.verify import verify
from us_mediakit.c2pa.vocabulary import resolve_digital_source_type
from us_mediakit.core.pipeline import ThumbnailRequest, generate_thumbnail
from us_mediakit.metadata.write import write_tags

requires_exiftool = pytest.mark.skipif(
    shutil.which("exiftool") is None, reason="exiftool nicht installiert"
)

_FIXTURES = Path(__file__).parent.parent / "fixtures" / "c2pa"


@pytest.fixture
def signer_config() -> SignerConfig:
    return SignerConfig(
        sign_cert=(_FIXTURES / "es256_certs.pem").read_bytes(),
        private_key=(_FIXTURES / "es256_private.key").read_bytes(),
        alg="es256",
    )


def _jpeg_bytes(w: int = 200, h: int = 100) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (30, 90, 160)).save(buf, format="JPEG")
    return buf.getvalue()


# --- Vokabular ---


def test_resolve_digital_source_type_short_name():
    url = resolve_digital_source_type("algorithmicallyEnhanced")
    assert url == "http://cv.iptc.org/newscodes/digitalsourcetype/algorithmicallyEnhanced"


def test_resolve_digital_source_type_passthrough_url():
    url = "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"
    assert resolve_digital_source_type(url) == url


def test_resolve_digital_source_type_unknown_raises():
    with pytest.raises(ValueError):
        resolve_digital_source_type("totallyMadeUp")


# --- read/sign/verify Grundfunktionen ---


def test_read_manifest_returns_none_without_manifest():
    assert read_manifest(_jpeg_bytes(), "image/jpeg") is None
    assert has_manifest(_jpeg_bytes(), "image/jpeg") is False


def test_sign_produces_readable_manifest(signer_config):
    signed = sign(
        SignRequest(
            data=_jpeg_bytes(),
            mime_type="image/jpeg",
            signer_config=signer_config,
            digital_source_type="digitalCapture",
        )
    )
    manifest = read_manifest(signed, "image/jpeg")
    assert manifest is not None
    actions = manifest["assertions"][0]["data"]["actions"]
    assert actions[0]["digitalSourceType"].endswith("digitalCapture")


def test_verify_signed_manifest_is_cryptographically_valid(signer_config):
    """`validation_state` bewertet nur die kryptografische Gültigkeit (Signatur/Hash-Bindung),
    nicht die Vertrauenswürdigkeit der Zertifikatskette — die beiden sind getrennte
    Achsen. Ein "untrusted"-Eintrag in `failure` kann daher neben `validation_state ==
    "Valid"` stehen: die Signatur selbst stimmt, dem Aussteller wird trotzdem nicht
    vertraut. Für Produktivbetrieb braucht es in jedem Fall ein über das
    C2PA-Conformance-Programm ausgestelltes Zertifikat (siehe docs/c2pa-conformance.md)
    — "Valid" allein ist kein Vertrauensbeweis."""
    signed = sign(
        SignRequest(
            data=_jpeg_bytes(),
            mime_type="image/jpeg",
            signer_config=signer_config,
            digital_source_type="digitalCapture",
        )
    )
    result = verify(signed, "image/jpeg")

    assert result.has_manifest is True
    assert result.validation_state == "Valid"
    failures = result.validation_results["activeManifest"].get("failure", [])
    codes = {f["code"] for f in failures}
    assert codes <= {"signingCredential.untrusted"}


def test_verify_without_manifest_reports_has_manifest_false():
    result = verify(_jpeg_bytes(), "image/jpeg")
    assert result.has_manifest is False
    assert result.validation_state is None


def test_sign_never_mutates_an_existing_manifest_new_derivative_gets_own_manifest(signer_config):
    """Zentrales Prinzip: eine Ableitung bekommt ein NEUES Manifest mit
    Ingredient-Verweis, statt ein bestehendes zu verändern."""
    original_signed = sign(
        SignRequest(
            data=_jpeg_bytes(400, 300),
            mime_type="image/jpeg",
            signer_config=signer_config,
            digital_source_type="digitalCapture",
        )
    )
    derivative_source = _jpeg_bytes(100, 100)  # simuliert eine bereits verkleinerte Variante
    derivative_signed = sign(
        SignRequest(
            data=derivative_source,
            mime_type="image/jpeg",
            signer_config=signer_config,
            digital_source_type="digitalCapture",
            action="c2pa.resized",
            ingredient=IngredientRef(data=original_signed, mime_type="image/jpeg"),
        )
    )

    original_manifest = read_manifest(original_signed, "image/jpeg")
    derivative_manifest = read_manifest(derivative_signed, "image/jpeg")

    assert original_manifest["assertions"][0]["data"]["actions"][0]["action"] == "c2pa.created"
    assert derivative_manifest["ingredients"][0]["relationship"] == "parentOf"
    assert derivative_manifest["assertions"][0]["data"]["actions"][0]["action"] == "c2pa.resized"
    # Das Original-Manifest ist unverändert erhalten (eigenes Label, eigene Signatur).
    assert original_manifest["label"] != derivative_manifest["label"]


# --- Propagations-Entscheidung ---


def _dummy_request(**overrides) -> ThumbnailRequest:
    defaults = {"source": b"", "mode": {"w": 10, "h": 10, "fit": "full"}}
    defaults.update(overrides)
    return ThumbnailRequest(**defaults)


def test_propagate_chains_ingredient_when_source_has_manifest(signer_config):
    source_signed = sign(
        SignRequest(
            data=_jpeg_bytes(400, 300),
            mime_type="image/jpeg",
            signer_config=signer_config,
            digital_source_type="digitalCapture",
        )
    )
    result_bytes = _jpeg_bytes(100, 100)
    request = _dummy_request(c2pa_signer_config=signer_config, c2pa_action="c2pa.resized")

    propagated = propagate(source=source_signed, result=result_bytes, request=request)

    manifest = read_manifest(propagated, "image/jpeg")
    assert manifest is not None
    assert manifest["ingredients"][0]["relationship"] == "parentOf"
    # digital_source_type wurde aus dem Quell-Manifest übernommen, nicht neu erfunden.
    assert manifest["assertions"][0]["data"]["actions"][0]["digitalSourceType"].endswith(
        "digitalCapture"
    )


@requires_exiftool
def test_propagate_uses_iptc_tag_without_full_manifest(signer_config):
    source_with_iptc_tag = write_tags(
        _jpeg_bytes(400, 300),
        {"XMP-iptcExt:DigitalSourceType": "http://cv.iptc.org/newscodes/digitalsourcetype/algorithmicallyEnhanced"},
    )
    result_bytes = _jpeg_bytes(100, 100)
    request = _dummy_request(c2pa_signer_config=signer_config, c2pa_action="c2pa.resized")

    propagated = propagate(source=source_with_iptc_tag, result=result_bytes, request=request)

    manifest = read_manifest(propagated, "image/jpeg")
    assert manifest is not None
    assert manifest.get("ingredients", []) == []  # keine Ingredient-Kette, Quelle hatte kein Manifest
    assert manifest["assertions"][0]["data"]["actions"][0]["digitalSourceType"].endswith(
        "algorithmicallyEnhanced"
    )


def test_propagate_uses_caller_supplied_digital_source_type(signer_config):
    result_bytes = _jpeg_bytes(100, 100)
    request = _dummy_request(
        c2pa_signer_config=signer_config,
        c2pa_action="c2pa.resized",
        c2pa_digital_source_type="compositeSynthetic",
    )

    propagated = propagate(source=_jpeg_bytes(), result=result_bytes, request=request)

    manifest = read_manifest(propagated, "image/jpeg")
    assert manifest["assertions"][0]["data"]["actions"][0]["digitalSourceType"].endswith(
        "compositeSynthetic"
    )


def test_propagate_does_not_invent_provenance_without_any_signal(signer_config):
    result_bytes = _jpeg_bytes(100, 100)
    request = _dummy_request(c2pa_signer_config=signer_config)

    propagated = propagate(source=_jpeg_bytes(), result=result_bytes, request=request)

    assert propagated == result_bytes
    assert read_manifest(propagated, "image/jpeg") is None


def test_propagate_noop_without_signer_config():
    request = _dummy_request(c2pa_signer_config=None)
    result_bytes = _jpeg_bytes(100, 100)

    propagated = propagate(source=_jpeg_bytes(), result=result_bytes, request=request)

    assert propagated == result_bytes


def test_propagate_noop_when_carry_c2pa_disabled(signer_config):
    request = _dummy_request(c2pa_signer_config=signer_config, carry_c2pa=False)
    result_bytes = _jpeg_bytes(100, 100)

    source_signed = sign(
        SignRequest(
            data=_jpeg_bytes(400, 300),
            mime_type="image/jpeg",
            signer_config=signer_config,
            digital_source_type="digitalCapture",
        )
    )

    propagated = propagate(source=source_signed, result=result_bytes, request=request)

    assert propagated == result_bytes


# --- Integration mit der Pipeline ---


def test_pipeline_propagates_manifest_end_to_end(signer_config):
    source_signed = sign(
        SignRequest(
            data=_jpeg_bytes(400, 300),
            mime_type="image/jpeg",
            signer_config=signer_config,
            digital_source_type="trainedAlgorithmicMedia",
        )
    )
    request = ThumbnailRequest(
        source=source_signed,
        mode={"w": 100, "h": 100, "fit": "full"},
        c2pa_signer_config=signer_config,
        carry_metadata=False,  # exiftool nicht Teil dieses Tests
    )

    result = generate_thumbnail(request)

    manifest = read_manifest(result.data, "image/jpeg")
    assert manifest is not None
    assert manifest["ingredients"][0]["relationship"] == "parentOf"
    assert manifest["assertions"][0]["data"]["actions"][0]["action"] == "c2pa.resized"
    assert manifest["assertions"][0]["data"]["actions"][0]["digitalSourceType"].endswith(
        "trainedAlgorithmicMedia"
    )


def test_pipeline_without_signer_config_behaves_like_before(signer_config=None):
    request = ThumbnailRequest(
        source=_jpeg_bytes(400, 300),
        mode={"w": 100, "h": 100, "fit": "full"},
        carry_metadata=False,
    )

    result = generate_thumbnail(request)

    assert read_manifest(result.data, "image/jpeg") is None
