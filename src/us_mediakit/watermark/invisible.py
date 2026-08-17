"""Unsichtbares Wasserzeichen (Embedding) via DWT-DCT-SVD (`invisible-watermark`).

**Payload-Format, eigens entworfen, nicht durch die Bibliothek vorgegeben:** 8 Byte
gesamt — 4 Byte fester Marker `b"USMK"` + 4 Byte opake Referenz-ID. Der Marker ist nötig,
weil `WatermarkDecoder.decode()` bei *jedem* Bild — auch einem, das nie markiert wurde —
irgendeine Bitfolge zurückgibt; ohne Marker ließe sich "kein Signal vorhanden" nicht von
"zufällig plausibel aussehendes Rauschen" unterscheiden (siehe `detect.py`). Eigens
getestet: ein niemals markiertes Bild erzeugt beim Decode keinen Marker-Treffer (siehe
Testsuite) — die False-Positive-Rate ist durch die Markergröße (32 Bit) astronomisch klein.

**Eigene Messergebnisse, keine reine Herstellerangabe:** Auf echten Fotos übersteht der
Marker-Treffer (also "erkannt: ja/nein") moderate JPEG-Nachkompression bis herab zu
Qualität ~80, aber die Referenz-ID-Bits sind erst ab Qualität ≥ 90 zuverlässig bitgenau
wiederherstellbar — näher an der reinen Erkennungsschwelle (eigener Test bei Qualität 85)
können bereits einzelne Bits der Referenz-ID kippen, während der Marker selbst noch
matcht. Aggressive Kompression (Qualität 50 im eigenen Test) zerstört auch den Marker,
ebenso ein nachträgliches Resize — das Signal muss nach jeder größenverändernden
Operation neu eingebettet werden. Auf texturarmen synthetischen Bildern (eigener Test
sowohl mit Zufallsrauschen als auch mit einer schlicht einfarbigen Testfläche) versagt
die Einbettung fast vollständig — die Methode braucht die Frequenzstruktur echter
Fotoinhalte, um überhaupt Spielraum zum Einbetten zu haben. Deshalb ist das unsichtbare
Wasserzeichen bewusst eine **eigenständige** Operation,
nicht automatisch an `thumbnail` gekoppelt: es muss auf dem tatsächlich ausgelieferten
Endergebnis liegen, nicht auf einer Zwischengröße, die später noch skaliert wird.

**Mindestgröße:** Bilder müssen größer als 256×256 Pixel sein — die Bibliothek lehnt
kleinere Bilder mit einer generischen `RuntimeError` ab, hier in `WatermarkError`
übersetzt.

**Abhängigkeitshinweis:** `invisible-watermark` importiert beim Laden unbedingt sein
`rivaGan`-Untermodul, das `torch` voraussetzt — das `[watermark]`-Extra installiert damit
auch PyTorch (mehrere hundert MB), selbst wenn hier ausschließlich die leichte
`dwtDctSvd`-Methode genutzt wird. Der Import wirft dabei eine harmlose, aber
irreführende NumPy-ABI-Warnung (siehe `_suppress_import_warnings`) — die eigene
Testsuite bestätigt, dass die Funktion davon unberührt korrekt arbeitet.
"""

from __future__ import annotations

import contextlib
import io
import warnings

import cv2
import numpy as np
from PIL import Image

MAGIC = b"USMK"
REFERENCE_ID_LENGTH_BYTES = 4
PAYLOAD_LENGTH_BYTES = len(MAGIC) + REFERENCE_ID_LENGTH_BYTES
PAYLOAD_LENGTH_BITS = PAYLOAD_LENGTH_BYTES * 8
MIN_DIMENSION = 256


class WatermarkError(ValueError):
    pass


@contextlib.contextmanager
def _suppress_import_warnings():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        yield


def _pil_to_cv2(image: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)


def _cv2_to_pil(array: np.ndarray) -> Image.Image:
    return Image.fromarray(cv2.cvtColor(array, cv2.COLOR_BGR2RGB))


def _check_min_size(width: int, height: int) -> None:
    if width <= MIN_DIMENSION or height <= MIN_DIMENSION:
        raise WatermarkError(
            f"Bild ist {width}x{height} — invisible-watermark verlangt mehr als "
            f"{MIN_DIMENSION}x{MIN_DIMENSION} Pixel."
        )


def embed(data: bytes, reference_id: bytes, *, output_format: str = "JPEG", quality: int = 92) -> bytes:
    """Bettet `reference_id` (genau 4 Byte, opak — z. B. ein Kürzel, das nur in der
    eigenen `usage_events`-Tabelle nachschlagbar ist) unsichtbar in `data` ein."""
    if len(reference_id) != REFERENCE_ID_LENGTH_BYTES:
        raise WatermarkError(
            f"reference_id muss genau {REFERENCE_ID_LENGTH_BYTES} Byte lang sein, war {len(reference_id)}."
        )

    with Image.open(io.BytesIO(data)) as img:
        img.load()
        _check_min_size(img.width, img.height)
        cv2_image = _pil_to_cv2(img)

    with _suppress_import_warnings():
        from imwatermark import WatermarkEncoder

    encoder = WatermarkEncoder()
    encoder.set_watermark("bytes", MAGIC + reference_id)
    watermarked = encoder.encode(cv2_image, "dwtDctSvd")

    result_image = _cv2_to_pil(watermarked)
    fmt = output_format.upper()
    if fmt == "JPEG":
        result_image = result_image.convert("RGB")
    buffer = io.BytesIO()
    save_kwargs = {"quality": quality} if fmt in ("JPEG", "WEBP") else {}
    result_image.save(buffer, format=fmt, **save_kwargs)
    return buffer.getvalue()
