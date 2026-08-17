"""Sichtbares Wasserzeichen — Logo/Schriftzug halbtransparent einblenden.

Reine Bildkomposition mit Pillow (bereits Kern-Abhängigkeit), keine zusätzliche
Bibliothek nötig — anders als das unsichtbare Wasserzeichen (siehe `invisible.py`).
"""

from __future__ import annotations

import io

from PIL import Image, ImageDraw, ImageFont

_POSITIONS = ("top-left", "top-right", "bottom-left", "bottom-right", "center")


class VisibleWatermarkError(ValueError):
    pass


def _anchor_xy(position: str, canvas_size: tuple[int, int], element_size: tuple[int, int], margin: int) -> tuple[int, int]:
    cw, ch = canvas_size
    ew, eh = element_size
    if position == "top-left":
        return margin, margin
    if position == "top-right":
        return cw - ew - margin, margin
    if position == "bottom-left":
        return margin, ch - eh - margin
    if position == "bottom-right":
        return cw - ew - margin, ch - eh - margin
    if position == "center":
        return (cw - ew) // 2, (ch - eh) // 2
    raise VisibleWatermarkError(f"Unbekannte Position {position!r}. Bekannt: {', '.join(_POSITIONS)}")


def _apply_opacity(overlay: Image.Image, opacity: float) -> Image.Image:
    if not 0.0 <= opacity <= 1.0:
        raise VisibleWatermarkError(f"opacity muss zwischen 0 und 1 liegen, war {opacity}.")
    overlay = overlay.convert("RGBA")
    alpha = overlay.getchannel("A").point(lambda a: int(a * opacity))
    overlay.putalpha(alpha)
    return overlay


def apply_logo(
    data: bytes,
    logo_data: bytes,
    *,
    position: str = "bottom-right",
    opacity: float = 0.6,
    margin: int = 20,
    scale: float = 0.15,
    output_format: str = "JPEG",
    quality: int = 90,
) -> bytes:
    """Blendet ein Logo (`logo_data`, beliebiges von Pillow lesbares Format, idealerweise
    mit Alphakanal) halbtransparent ein. `scale` ist die Logo-Breite relativ zur
    Bildbreite (0.15 = 15 %)."""
    if not 0.0 < scale <= 1.0:
        raise VisibleWatermarkError(f"scale muss zwischen 0 (exklusiv) und 1 liegen, war {scale}.")

    with Image.open(io.BytesIO(data)) as base_img, Image.open(io.BytesIO(logo_data)) as logo_img:
        base_img.load()
        logo_img.load()
        base = base_img.convert("RGBA")
        logo = logo_img.convert("RGBA")

        target_width = max(1, int(base.width * scale))
        target_height = max(1, int(logo.height * (target_width / logo.width)))
        logo = logo.resize((target_width, target_height), Image.Resampling.LANCZOS)
        logo = _apply_opacity(logo, opacity)

        xy = _anchor_xy(position, base.size, logo.size, margin)
        composited = base.copy()
        composited.alpha_composite(logo, dest=xy)

        return _encode(composited, output_format, quality)


def apply_text(
    data: bytes,
    text: str,
    *,
    position: str = "bottom-right",
    opacity: float = 0.6,
    margin: int = 20,
    font_size_ratio: float = 0.04,
    color: tuple[int, int, int] = (255, 255, 255),
    output_format: str = "JPEG",
    quality: int = 90,
) -> bytes:
    """Blendet einen Schriftzug halbtransparent ein. `font_size_ratio` ist die
    Schriftgröße relativ zur Bildhöhe (0.04 = 4 %)."""
    with Image.open(io.BytesIO(data)) as base_img:
        base_img.load()
        base = base_img.convert("RGBA")

        font_size = max(8, int(base.height * font_size_ratio))
        font = ImageFont.load_default(size=font_size)

        overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_size = (int(bbox[2] - bbox[0]), int(bbox[3] - bbox[1]))
        xy = _anchor_xy(position, base.size, text_size, margin)
        draw.text((xy[0] - bbox[0], xy[1] - bbox[1]), text, font=font, fill=(*color, 255))

        overlay = _apply_opacity(overlay, opacity)
        composited = Image.alpha_composite(base, overlay)

        return _encode(composited, output_format, quality)


def _encode(image: Image.Image, output_format: str, quality: int) -> bytes:
    fmt = output_format.upper()
    if fmt == "JPEG":
        image = image.convert("RGB")
    buffer = io.BytesIO()
    save_kwargs = {"quality": quality} if fmt in ("JPEG", "WEBP") else {}
    image.save(buffer, format=fmt, **save_kwargs)
    return buffer.getvalue()
