"""Provider-Auflösungsreihenfolge: Request-Angabe > Account-Default > Instanz-Default
> keiner konfiguriert.

Bewusst eine reine Funktion ohne eigenen Datenzugriff: "Account-Default" ist eine vom
Kundenbereich verwaltete Einstellung (kein Feld im `ApiKey`-Datenmodell, siehe Abschnitt
4) — wer diese Funktion aufruft, muss den Account-Default selbst nachschlagen (Kundenbereich-
Abfrage, eigene Konfiguration) und hier nur das *Ergebnis* übergeben.
"""

from __future__ import annotations


class NoProviderConfiguredError(RuntimeError):
    pass


def resolve_provider(
    *,
    request_provider: str | None,
    account_default_provider: str | None,
    instance_default_provider: str | None,
) -> str:
    """Liefert den zu verwendenden Provider-Namen, oder wirft, wenn keine Ebene etwas festlegt."""
    for candidate in (request_provider, account_default_provider, instance_default_provider):
        if candidate:
            return candidate
    raise NoProviderConfiguredError(
        "Kein Provider konfiguriert: weder im Request, noch als Account- oder Instanz-Default."
    )
