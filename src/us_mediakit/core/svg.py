"""SVG-Sanitizing vor Passthrough.

SVG wird nie neu gerastert, sondern (wie im PHP-Original) unverändert an den Client
durchgereicht — das eigentliche Sicherheitsrisiko ist daher nicht die Bildverarbeitung,
sondern eingebettetes JavaScript/externe Referenzen im SVG selbst (XSS/SSRF).

Bewusst ohne zusätzliche Abhängigkeit (kein `defusedxml`): Ein `<!DOCTYPE`-Präfix wird
grundsätzlich entfernt, bevor mit der Standardbibliothek geparst wird — legitimes SVG
braucht keine interne DTD/Entity-Definition, und das eliminiert sowohl externe
Entity-Auflösung als auch "Billion Laughs"-Angriffe über interne Entities, ohne den
XML-Parser selbst ersetzen zu müssen.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

_DOCTYPE_RE = re.compile(r"<!DOCTYPE[^>\[]*(\[[^\]]*\])?\s*>", re.IGNORECASE | re.DOTALL)
_DANGEROUS_TAG_LOCALNAMES = {"script", "foreignObject"}
_HREF_ATTR_LOCALNAMES = {"href"}


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


class SvgSanitizeError(ValueError):
    pass


def sanitize_svg(data: bytes) -> bytes:
    """Entfernt Skripte, Event-Handler und gefährliche Referenzen aus SVG-Daten."""
    text = data.decode("utf-8", errors="replace")
    text = _DOCTYPE_RE.sub("", text)

    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise SvgSanitizeError(f"SVG konnte nicht geparst werden: {exc}") from exc

    for parent in list(root.iter()):
        for child in list(parent):
            if _local_name(child.tag) in _DANGEROUS_TAG_LOCALNAMES:
                parent.remove(child)

    for element in root.iter():
        for attr_name in list(element.attrib):
            local = _local_name(attr_name)
            value = element.attrib[attr_name]

            if local.lower().startswith("on"):
                del element.attrib[attr_name]
                continue

            if local in _HREF_ATTR_LOCALNAMES:
                stripped = value.strip().lower()
                if stripped.startswith(("javascript:", "data:text/html")):
                    del element.attrib[attr_name]

    return ET.tostring(root, encoding="utf-8")
