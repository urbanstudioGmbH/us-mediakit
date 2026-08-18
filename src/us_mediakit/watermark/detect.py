"""Erkennung des unsichtbaren Wasserzeichens — das Gegenstück zu `invisible.py`.

Prüft ein beliebiges Bild (z. B. eines, das irgendwo im Netz gefunden wurde) darauf, ob
es ein von uns eingebettetes Signal trägt, und liefert die eingebettete Referenz-ID.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import numpy as np
from PIL import Image

from us_mediakit.watermark import _dwt_dct_svd
from us_mediakit.watermark.invisible import MAGIC, MIN_DIMENSION, PAYLOAD_LENGTH_BITS, _pil_to_cv2


@dataclass
class DetectionResult:
    detected: bool
    reference_id: bytes | None


def detect(data: bytes) -> DetectionResult:
    """Prüft `data` auf ein per `invisible.embed()` eingebettetes Signal.

    **Wichtige Einschränkung:** `detected=False` ist ein Hinweis, kein Beweis für aktive
    Entfernung — starke Nachbearbeitung (aggressive Kompression, Resize) kann das Signal
    unabhängig von Absicht abschwächen (siehe Robustheitsangaben in `invisible.py`). Ein
    belastbarer "wurde entfernt"-Nachweis braucht zusätzlich einen Abgleich mit einem
    `usage_events`-Datensatz, der belegt, dass genau dieses Bild ursprünglich markiert wurde.
    """
    with Image.open(io.BytesIO(data)) as img:
        img.load()
        if img.width <= MIN_DIMENSION or img.height <= MIN_DIMENSION:
            # Zu klein für ein plausibles Signal — kein Fehler, sondern "nicht erkannt".
            return DetectionResult(detected=False, reference_id=None)
        cv2_image = _pil_to_cv2(img)

    bits = _dwt_dct_svd.extract_bits(cv2_image, PAYLOAD_LENGTH_BITS)
    decoded = np.packbits(bits).tobytes()

    if decoded[: len(MAGIC)] != MAGIC:
        return DetectionResult(detected=False, reference_id=None)

    return DetectionResult(detected=True, reference_id=decoded[len(MAGIC) :])
