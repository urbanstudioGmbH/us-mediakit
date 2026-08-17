"""IPTC Digital Source Type — Kurzname ↔ volle Vokabular-URL.

Die Kurznamen werden aus `c2pa.C2paDigitalSourceType` abgeleitet (SCREAMING_SNAKE_CASE →
camelCase), damit die Liste automatisch mit dem tatsächlich von `c2pa-python` unterstützten
Vokabular übereinstimmt, statt eine eigene, potenziell abweichende Liste zu pflegen.
"""

from __future__ import annotations

import c2pa

_BASE_URL = "http://cv.iptc.org/newscodes/digitalsourcetype/"


def _screaming_snake_to_camel(name: str) -> str:
    parts = name.lower().split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


DIGITAL_SOURCE_TYPES: dict[str, str] = {
    _screaming_snake_to_camel(member.name): _BASE_URL + _screaming_snake_to_camel(member.name)
    for member in c2pa.C2paDigitalSourceType
    if member.name != "EMPTY"
}


def resolve_digital_source_type(value: str) -> str:
    """Nimmt einen Kurznamen (z. B. "algorithmicallyEnhanced") oder bereits eine volle
    URL entgegen und liefert immer die volle IPTC-Vokabular-URL zurück."""
    if value.startswith(("http://", "https://")):
        return value
    try:
        return DIGITAL_SOURCE_TYPES[value]
    except KeyError:
        known = ", ".join(sorted(DIGITAL_SOURCE_TYPES))
        raise ValueError(f"Unbekannter digital_source_type {value!r}. Bekannt: {known}") from None
