"""Credits-Berechnung aus `costweights.json`.

Wichtig (Programmierplan Abschnitt 3): einmal berechnete `credits` in `usage_events`
dürfen sich rückwirkend nie ändern, auch wenn die Datei später angepasst wird. Deshalb
gibt `CostTable.load()` immer auch die `version` mit zurück, die zusammen mit `credits`
pro `UsageEvent` gespeichert wird (`credits_table_version`).

`us_mediakit` selbst kennt keine Währung — `external_cost_micros` (z. B. die reale
claid.ai-Rechnungsposition) wird unverändert für die Buchhaltung mitgeführt, während
`credits` über `external_cost_conversion` rein technisch draus abgeleitet wird
(Marge bereits eingerechnet). us-mediakit weiß dabei nie, was ein Credit in echtem Geld
wert ist — das entscheidet ausschließlich der Kundenbereich.
"""

from __future__ import annotations

from dataclasses import dataclass

from us_mediakit.config import load_costweights


@dataclass
class CostTable:
    version: int
    weights: dict[str, float]
    micros_per_credit: int | None
    margin_factor: float | None

    @classmethod
    def load(cls, path: str | None = None) -> CostTable:
        data = load_costweights(path)
        conversion = data.get("external_cost_conversion", {})
        return cls(
            version=data["version"],
            weights=data["weights"],
            micros_per_credit=conversion.get("micros_per_credit"),
            margin_factor=conversion.get("margin_factor"),
        )

    def weight_for(self, operation: str) -> float:
        try:
            return self.weights[operation]
        except KeyError:
            known = ", ".join(sorted(self.weights))
            raise ValueError(f"Keine Credits-Gewichtung für Operation {operation!r}. Bekannt: {known}") from None

    def credits_for_operation(self, operation: str) -> float:
        return self.weight_for(operation)

    def credits_for_external_cost(self, external_cost_micros: int) -> float:
        """Rechnet einen realen Fremdkosten-Betrag (z. B. claid.ai, in Millionstel
        Währungseinheiten) inkl. Marge in Credits um."""
        if self.micros_per_credit is None or self.margin_factor is None:
            raise ValueError(
                "external_cost_conversion ist in costweights.json nicht konfiguriert."
            )
        return (external_cost_micros * self.margin_factor) / self.micros_per_credit
