"""C2PA-Manifest erzeugen und signieren — erweiterbares Actions-/Assertions-Schema.

**Wichtiges Prinzip (siehe Programmierplan Phase 3):** Ein bestehendes, signiertes
Manifest wird nie nachträglich verändert/neu signiert — jede Pixel-Änderung würde eine
vorhandene Signatur ohnehin ungültig machen. Stattdessen bekommt jede Cache-Variante ein
eigenes, frisches Manifest, das per Ingredient-Assertion (`relationship: "parentOf"`) auf
das Original verweist. Dadurch bleibt die Provenienzkette über beliebig viele
Ableitungsstufen nachvollziehbar, ohne dass ein bestehendes Manifest angefasst wird.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Any

import c2pa

from us_mediakit.c2pa.vocabulary import resolve_digital_source_type

DEFAULT_CLAIM_GENERATOR = "us-mediakit"


@dataclass
class SignerConfig:
    """Zertifikat + privater Schlüssel, jeweils als PEM-Bytes.

    `sign_cert` ist die vollständige Zertifikatskette (Leaf-Zertifikat zuerst, danach
    ggf. Intermediate-CAs). Für Produktivbetrieb muss diese Kette auf ein über das
    C2PA-Conformance-Programm ausgestelltes, vertrauenswürdiges Zertifikat zurückgehen
    (siehe Programmierplan Abschnitt 9) — ein selbst signiertes Testzertifikat signiert
    zwar technisch korrekt, wird aber von jedem Prüfer als "untrusted" markiert.
    """

    sign_cert: bytes
    private_key: bytes
    alg: str = "es256"
    ta_url: str | None = None

    def build_signer(self) -> c2pa.Signer:
        info = c2pa.C2paSignerInfo(
            alg=self.alg, sign_cert=self.sign_cert, private_key=self.private_key, ta_url=self.ta_url
        )
        return c2pa.Signer.from_info(info)


@dataclass
class IngredientRef:
    """Verweis auf das Original, das als Ingredient in das neue Manifest aufgenommen wird."""

    data: bytes
    mime_type: str
    title: str = "source"
    relationship: str = "parentOf"


@dataclass
class SignRequest:
    data: bytes
    mime_type: str
    signer_config: SignerConfig
    digital_source_type: str
    action: str = "c2pa.created"
    extra_actions: list[dict[str, Any]] = field(default_factory=list)
    extra_assertions: list[dict[str, Any]] = field(default_factory=list)
    ingredient: IngredientRef | None = None
    claim_generator: str = DEFAULT_CLAIM_GENERATOR


def sign(request: SignRequest) -> bytes:
    """Signiert `request.data` mit einem frischen, eigenen Manifest und gibt die
    signierten Bytes zurück."""
    actions_data = [
        {
            "action": request.action,
            "digitalSourceType": resolve_digital_source_type(request.digital_source_type),
        },
        *request.extra_actions,
    ]

    manifest: dict[str, Any] = {
        "claim_generator": request.claim_generator,
        "assertions": [
            {"label": "c2pa.actions", "data": {"actions": actions_data}},
            *request.extra_assertions,
        ],
    }

    builder = c2pa.Builder(manifest)
    if request.ingredient is not None:
        ingredient_json = {
            "title": request.ingredient.title,
            "relationship": request.ingredient.relationship,
        }
        builder.add_ingredient_from_stream(
            ingredient_json, request.ingredient.mime_type, io.BytesIO(request.ingredient.data)
        )

    signer = request.signer_config.build_signer()
    dest_stream = io.BytesIO()
    builder.sign(signer, request.mime_type, io.BytesIO(request.data), dest_stream)
    return dest_stream.getvalue()
