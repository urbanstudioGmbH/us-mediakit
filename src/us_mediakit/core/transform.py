"""Zuschnitt/Skalierung — Portierung der Fit-Modi aus SimpleImageLibrary3 (PHP).

Referenz ist der **Imagick-Pfad** von SimpleImageLibrary3 (`thumbnailFromStringImagick`),
nicht der GD-Fallback-Pfad: Die PHP-Klasse nutzt Imagick, wenn die Extension geladen ist
(`if(extension_loaded('imagick')) return thumbnailFromStringImagick(...)`), und das ist auf
dem Produktivserver der Fall. GD-spezifische Eigenheiten (z. B. eine EXIF-Rotationskorrektur
nur im Imagick-Pfad, ein anderes Schärfen-Verhalten im GD-Pfad) werden hier bewusst nicht
repliziert, weil sie im tatsächlich aktiven Pfad nicht auftreten.

Bekannte, absichtlich übernommene Eigenheiten aus dem Original (nicht "Bugs", die hier zu
fixen wären — Ziel ist Bildparität mit dem heutigen Ausgabeverhalten):

- `greedycrop` skaliert Breite/Höhe mit vertauschten Faktoren (siehe `_greedycrop`,
  identisch zur PHP-Formel) — das verzerrt das Seitenverhältnis beim Zwischenschritt
  absichtlich, um in jedem Fall beide Zielmaße zu erreichen, bevor zugeschnitten wird.
- Bei `greedyscalecrop`/`full` wird **nicht** vergrößert, wenn kein `ai`-Provider gesetzt
  ist und die Zielbreite größer als die Zwischenbreite ist (`scale > 1`) — das Bild bleibt
  dann kleiner als die Zielgröße. Das ist bestehendes Verhalten, keine neue Einschränkung.

Eine Abweichung ist bewusst **nicht** übernommen: Die Imagick-Fassung parst einen
übergebenen `aspect_ratio`-String ohne Bindestrich nicht robust (Division durch einen
undefinierten Index). Hier wird stattdessen die robustere Fallback-Logik aus dem
GD-Pfad verwendet (einzelner numerischer Wert erlaubt) — ein Crash bei einer
Formatabweichung wäre kein sinnvoller Paritätsanspruch.

PHPs `round()` rundet Halbwerte von Null weg (0.5 → 1, -0.5 → -1), Pythons `round()`
rundet kaufmännisch zum geraden Wert — deshalb `php_round()` als eigene Funktion, damit
Rundungsergebnisse an Preset-Grenzen exakt übereinstimmen.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from PIL import Image, ImageFilter, ImageOps

FitMode = dict[str, Any]

_VALID_CROP_OVERRIDES = ("crop", "greedycrop", "greedyscalecrop")


def php_round(value: float) -> float:
    """PHP-kompatibles Runden: Halbwerte werden von Null weg gerundet."""
    if value >= 0:
        return math.floor(value + 0.5)
    return math.ceil(value - 0.5)


def _is_numeric(value: Any) -> bool:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return True
    if isinstance(value, str):
        try:
            float(value)
            return True
        except ValueError:
            return False
    return False


def parse_zoom(zoom: str | float | None, mode_zoom_default: str | float | None) -> float:
    """Portierung der Zoom-Parsing-Logik: Faktor (<10) oder Prozent (>=10), geklemmt auf [1.0, 5.0]."""
    if not zoom:
        zoom = mode_zoom_default
    try:
        zoom_float = float(zoom) if zoom else 0.0
    except (TypeError, ValueError):
        zoom_float = 0.0
    if 0 < zoom_float < 10:
        zoom_float *= 100
    return max(100, min(500, int(zoom_float))) / 100


def parse_aspect_ratio(aspect_ratio: str | None) -> float | None:
    """"W-H" (Bruch) oder einzelner numerischer Wert. None, wenn nicht parsbar."""
    if aspect_ratio is None:
        return None
    parts = aspect_ratio.split("-")
    if len(parts) == 2:
        try:
            divisor = int(parts[1])
            if divisor == 0:
                return None
            return int(parts[0]) / divisor
        except ValueError:
            return None
    if _is_numeric(aspect_ratio):
        return float(aspect_ratio)
    return None


def get_fractional_shift(shift: Any, max_val: float, target: float) -> float:
    """Position eines Ausschnitts im verfügbaren Raum, 0–100 % oder left/right/top/bottom."""
    if shift == "left" or shift == "top":
        numeric_shift = 0.0
    elif shift == "right" or shift == "bottom":
        numeric_shift = 100.0
    elif _is_numeric(shift):
        numeric_shift = float(shift)
    else:
        numeric_shift = 50.0
    numeric_shift = max(0.0, min(100.0, numeric_shift))
    return (max_val - target) * (numeric_shift / 100.0)


def get_xy_alignment(mode: FitMode, w: float, h: float) -> tuple[int, int]:
    """Position für den einfachen "crop"-Modus. Default: zentriert."""
    mode_w = mode.get("w") or 0
    mode_h = mode.get("h") or 0
    x = php_round((w / 2) - (mode_w / 2))
    y = php_round((h / 2) - (mode_h / 2))

    xalign = mode.get("xalign")
    if _is_numeric(xalign):
        x = get_fractional_shift(xalign, w, mode_w)
    elif xalign == "left":
        x = 0
    elif xalign == "right":
        x = w - mode_w

    yalign = mode.get("yalign")
    if _is_numeric(yalign):
        y = get_fractional_shift(yalign, h, mode_h)
    elif yalign == "top":
        y = 0
    elif yalign == "bottom":
        y = h - mode_h

    return int(x), int(y)


def _get_subpicture_for_aspect_and_zoom(
    image: Image.Image, mode: FitMode, ratio: float | None, zoom: float
) -> Image.Image:
    """Cover-Rechteck (Seitenverhältnis) + Zoom + Ausrichtung, als ein Zuschnitt."""
    w, h = image.size
    zoom = zoom if (isinstance(zoom, (int, float)) and zoom > 0) else 1.0
    xalign = mode.get("xalign", 50)
    yalign = mode.get("yalign", 50)

    if not ratio or ratio <= 0:
        crop_w, crop_h = float(w), float(h)
    else:
        src_ar = w / max(h, 1e-9)
        if src_ar >= ratio:
            crop_h = float(h)
            crop_w = php_round(crop_h * ratio)
        else:
            crop_w = float(w)
            crop_h = php_round(crop_w / ratio)

    eff_w = max(1.0, crop_w / zoom)
    eff_h = max(1.0, crop_h / zoom)

    start_x = get_fractional_shift(xalign, w, eff_w)
    start_y = get_fractional_shift(yalign, h, eff_h)

    start_x = max(0.0, min(w - eff_w, start_x))
    start_y = max(0.0, min(h - eff_h, start_y))
    eff_w = int(php_round(eff_w))
    eff_h = int(php_round(eff_h))
    start_x = int(php_round(start_x))
    start_y = int(php_round(start_y))

    box = (start_x, start_y, start_x + eff_w, start_y + eff_h)
    return image.crop(box)


def _ensure_rgba(image: Image.Image) -> Image.Image:
    if image.mode != "RGBA":
        return image.convert("RGBA")
    return image


@dataclass
class FitResult:
    image: Image.Image
    target_width: int
    target_height: int
    scale: float
    ai_pending: bool


def apply_fit(
    image: Image.Image,
    mode: FitMode,
    *,
    crop: str | None = None,
    aspect_ratio: str | None = None,
    alignx: str | float | None = None,
    aligny: str | float | None = None,
    zoom: str | float | None = None,
    ai: str | None = None,
    max_upscale_factor: float | None = None,
) -> FitResult:
    """Wendet einen Fit-Modus an. `mode` ist ein Preset aus imageformats.json.

    EXIF-Ausrichtung wird vor jeder Berechnung korrigiert (Gegenstück zu
    Imagick::autoOrient() im Original).

    `max_upscale_factor`: explizites Opt-in für einfache (bikubische/Lanczos)
    Vergrößerung ohne KI-Provider, standardmäßig weiterhin `None` (= keine
    Vergrößerung, bisheriges Verhalten unverändert). Gesetzt auf z. B. `2.0` wird bis
    zum Faktor 2 einfach hochskaliert; reicht das nicht für die volle Zielgröße, bleibt
    das Ergebnis an der Obergrenze stehen (immer noch kleiner als angefragt, aber näher
    dran als ganz ohne Vergrößerung) — `target_width`/`target_height` melden weiterhin
    die tatsächlich angefragte Zielgröße, nicht die gedeckelte, damit der bestehende
    "kleiner als angefragt"-Hinweis (CLI/API) unverändert greift.
    """
    mode = dict(mode)  # Preset nicht mutieren, Request-Overrides gelten nur lokal
    image = ImageOps.exif_transpose(image) or image
    image = _ensure_rgba(image)
    w, h = image.size

    aspect_ratio_fractional = parse_aspect_ratio(aspect_ratio)

    resolved_zoom = parse_zoom(zoom, mode.get("zoom"))

    if crop and crop in _VALID_CROP_OVERRIDES:
        mode["fit"] = crop
    if aspect_ratio is not None and not crop:
        mode["fit"] = "greedyscalecrop"
    if resolved_zoom != 1.0:
        mode["fit"] = "greedyscalecrop"
    if alignx is not None:
        mode["xalign"] = alignx
    if aligny is not None:
        mode["yalign"] = aligny

    fit = mode.get("fit")
    target_width = mode.get("w") or w
    target_height = mode.get("h") or h
    scale = 1.0
    ai_pending = False

    if fit == "crop":
        x, y = get_xy_alignment(mode, w, h)
        box = (x, y, x + mode["w"], y + mode["h"])
        result_image = image.crop(box)
        target_width, target_height = mode["w"], mode["h"]

    elif fit == "greedycrop":
        sw = mode["w"] / w
        sh = mode["h"] / h
        s = min(sw, sh)
        s2 = (1 / s) if s < 1 else 1
        sw *= s2
        sh *= s2
        new_width = math.ceil(w * sh)
        new_height = math.ceil(h * sw)
        scaled = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        x, y = get_xy_alignment(mode, new_width, new_height)
        box = (x, y, x + mode["w"], y + mode["h"])
        result_image = scaled.crop(box)
        target_width, target_height = mode["w"], mode["h"]

    elif fit in ("greedyscalecrop", "full"):
        if aspect_ratio_fractional:
            ratio = aspect_ratio_fractional
        elif mode.get("w") and mode.get("h"):
            ratio = mode["w"] / mode["h"]
        else:
            ratio = w / h

        cropped = _get_subpicture_for_aspect_and_zoom(image, mode, ratio, resolved_zoom)
        cropped_width, cropped_height = cropped.size

        scale = (mode["w"] / cropped_width) if mode.get("w") else 1.0
        target_width = cropped_width * scale
        target_height = cropped_height * scale
        ai_pending = bool(ai) and scale > 1

        if scale <= 1:
            effective_scale: float | None = scale
        elif not ai and max_upscale_factor is not None:
            effective_scale = min(scale, max_upscale_factor)
        else:
            effective_scale = None  # weder AI noch Opt-in -- Ergebnis bleibt ungeskaliert klein

        if not ai and (mode.get("w") or mode.get("h")) and effective_scale is not None:
            eff_width = cropped_width * effective_scale
            eff_height = cropped_height * effective_scale
            new_size = (int(php_round(eff_width)), int(php_round(eff_height)))
            result_image = cropped.resize(new_size, Image.Resampling.LANCZOS)
            if effective_scale < 1:
                # Näherung an ImageMagicks unsharpMaskImage(0, 0.5, 1, 0) — keine
                # bitgenaue Übereinstimmung möglich (andere Algorithmus-Parametrisierung),
                # daher im Golden-Image-Test mit Toleranzband bewerten, nicht 1:1-Diff.
                result_image = result_image.filter(
                    ImageFilter.UnsharpMask(radius=2, percent=50, threshold=0)
                )
        else:
            result_image = cropped

        target_width = int(php_round(target_width))
        target_height = int(php_round(target_height))

    else:
        raise ValueError(f"Unbekannter Fit-Modus: {fit!r}")

    return FitResult(
        image=result_image,
        target_width=target_width,
        target_height=target_height,
        scale=scale,
        ai_pending=ai_pending,
    )
