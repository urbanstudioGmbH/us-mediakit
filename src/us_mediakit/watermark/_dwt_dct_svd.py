"""DWT-DCT-SVD-Wasserzeichenalgorithmus.

Aus [`invisible-watermark`](https://github.com/ShieldMnt/invisible-watermark)
(MIT-Lizenz, © Qingquan Wang) übernommen, statt die Bibliothek als Abhängigkeit
einzubinden: `invisible-watermark` bietet zusätzlich eine GAN-basierte Methode
(`rivaGan`), die beim bloßen *Import* des Pakets unbedingt PyTorch lädt (mehrere
hundert MB) — auch wenn wie hier ausschließlich `dwtDctSvd` genutzt wird, ein reiner
DWT/DCT/SVD-Algorithmus ganz ohne ML-Modell. Diese Datei enthält nur den tatsächlich
genutzten Teil, unverändert im Verhalten (identischer Algorithmus, identische
Default-Parameter `scales`/`block` — alle bisher gemessenen Robustheitswerte in
`invisible.py` gelten deshalb unverändert weiter), nur als eigenständige Funktionen
statt als Klassenmethoden.
"""

from __future__ import annotations

import cv2
import numpy as np
import pywt

_DEFAULT_SCALES = (0.0, 36.0, 0.0)
_DEFAULT_BLOCK = 4


def _diffuse_dct_svd(block: np.ndarray, bit: int, scale: float) -> np.ndarray:
    u, s, v = np.linalg.svd(cv2.dct(block))
    s[0] = (s[0] // scale + 0.25 + 0.5 * bit) * scale
    return cv2.idct(np.dot(u, np.dot(np.diag(s), v)))


def _infer_dct_svd(block: np.ndarray, scale: float) -> int:
    _, s, _ = np.linalg.svd(cv2.dct(block))
    return int((s[0] % scale) > scale * 0.5)


def _encode_frame(frame: np.ndarray, bits: list[int], scale: float, block_size: int) -> None:
    row, col = frame.shape
    num = 0
    for i in range(row // block_size):
        for j in range(col // block_size):
            r0, c0 = i * block_size, j * block_size
            block = frame[r0 : r0 + block_size, c0 : c0 + block_size]
            bit = bits[num % len(bits)]
            frame[r0 : r0 + block_size, c0 : c0 + block_size] = _diffuse_dct_svd(block, bit, scale)
            num += 1


def _decode_frame(frame: np.ndarray, num_bits: int, scale: float, block_size: int, scores: list[list[int]]) -> None:
    row, col = frame.shape
    num = 0
    for i in range(row // block_size):
        for j in range(col // block_size):
            r0, c0 = i * block_size, j * block_size
            block = frame[r0 : r0 + block_size, c0 : c0 + block_size]
            scores[num % num_bits].append(_infer_dct_svd(block, scale))
            num += 1


def embed_bits(
    bgr: np.ndarray,
    bits: list[int],
    *,
    scales: tuple[float, float, float] = _DEFAULT_SCALES,
    block: int = _DEFAULT_BLOCK,
) -> np.ndarray:
    """Bettet `bits` (Liste von 0/1) per DWT-DCT-SVD ein und gibt das codierte BGR-Bild zurück."""
    row, col, _ = bgr.shape
    yuv = cv2.cvtColor(bgr, cv2.COLOR_BGR2YUV)

    for channel in range(2):
        if scales[channel] <= 0:
            continue
        ca1, (h1, v1, d1) = pywt.dwt2(yuv[: row // 4 * 4, : col // 4 * 4, channel], "haar")
        _encode_frame(ca1, bits, scales[channel], block)
        yuv[: row // 4 * 4, : col // 4 * 4, channel] = pywt.idwt2((ca1, (v1, h1, d1)), "haar")

    return cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR)


def extract_bits(
    bgr: np.ndarray,
    num_bits: int,
    *,
    scales: tuple[float, float, float] = _DEFAULT_SCALES,
    block: int = _DEFAULT_BLOCK,
) -> np.ndarray:
    """Liest `num_bits` Bits zurück (Mehrheitsentscheid je Bit über alle Blöcke)."""
    row, col, _ = bgr.shape
    yuv = cv2.cvtColor(bgr, cv2.COLOR_BGR2YUV)

    scores: list[list[int]] = [[] for _ in range(num_bits)]
    for channel in range(2):
        if scales[channel] <= 0:
            continue
        ca1, _ = pywt.dwt2(yuv[: row // 4 * 4, : col // 4 * 4, channel], "haar")
        _decode_frame(ca1, num_bits, scales[channel], block, scores)

    avg_scores = np.array([float(np.mean(s)) for s in scores])
    return avg_scores * 255 > 127
