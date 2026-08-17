# KI-Provider

`us_mediakit` selbst hat keinen voreingestellten KI-Anbieter — jede Instanz konfiguriert
ihre eigenen Provider. Zwei Kategorien, zwei Schnittstellen:

- **Bildbeschreibung** (`caption`): ein generischer OpenAI-kompatibler Chat-Provider
  (`us_mediakit.providers.base.VisionChatProvider`). Funktioniert identisch für ein
  selbst gehostetes Vision-Modell oder einen BYOK-Endpunkt.
- **Bild-Upscaling/-Verbesserung** (`ai_upscale`): eine projekteigene
  Bild-rein/Bild-raus-Schnittstelle über HTTP (`ImageEnhanceProvider`) — dafür gibt es
  keinen etablierten Branchenstandard.

## Eingebaute Provider

| Name | Schnittstelle | Läuft wo | Einsatzempfehlung |
|---|---|---|---|
| `real-esrgan` | `ImageEnhanceProvider` | eigener Provider-Prozess (Modellgewichte separat, siehe unten) | Standard-Upscaling, auch ohne GPU (CPU-Fallback langsamer) |
| `codeformer` | `ImageEnhanceProvider` | eigener Provider-Prozess | Gesichtsrestauration, primär als `restore_faces`-Zusatzschritt, nicht als alleinstehendes Upscaling — siehe Hinweis unten |
| `seedvr2-3b`/`seedvr2-7b` | `ImageEnhanceProvider` | eigener Provider-Prozess, braucht dedizierte GPU | Stark degradiertes Ausgangsmaterial, nicht der Standardfall |
| `claid-ai` | `ImageEnhanceProvider` | echter externer Dienst (claid.ai) | Übergangslösung/Vergleichs-Baseline — laut Projektzielen langfristig durch selbst gehostete Modelle zu ersetzen |
| generischer OpenAI-kompatibler Provider | `VisionChatProvider` | selbst gehostetes Vision-Modell oder BYOK-Endpunkt | `caption` — jedes OpenAI-Chat-API-kompatible Modell mit Bildeingabe |

**`codeformer` ohne Credits-Gewicht als primärer `ai_upscale`-Provider:** `costweights.json`
enthält nur `face_restore.codeformer` (den Zusatzschritt-Preis), keinen
`ai_upscale.codeformer`-Eintrag — ein Versuch, CodeFormer direkt als `provider` in
`POST /v1/ai_upscale` zu wählen, liefert deshalb `422`, keinen Serverfehler.

## Konfiguration

Über eine YAML-Datei (`USMEDIAKIT_PROVIDERS_CONFIG`, Beispiel in
[`config/providers.example.yaml`](../src/us_mediakit/config/providers.example.yaml)) —
**vorläufige Entscheidung**, kein endgültig festgelegtes Format (siehe Programmierplan
Abschnitt 9: "Provider-Konfigurationsformat final festlegen" ist ein offener Punkt).

```yaml
providers:
  caption:
    default: null # Instanz-Default; leer = kein Default, nur BYOK möglich
    base_url: "http://localhost:8803/v1"
    model: "gemma-vision"
    api_key_env: null # Name einer Umgebungsvariable, falls der Endpunkt Auth braucht
  ai_upscale:
    default: null
    registered:
      real-esrgan: {endpoint: "http://localhost:8801"}
      codeformer:  {endpoint: "http://localhost:8802"}
      seedvr2-3b:  {endpoint: "http://localhost:8804"}
      claid-ai:    {api_key_env: "CLAID_API_KEY"}
```

## Auflösungsreihenfolge

Request-Angabe > Account-Default > Instanz-Default > keiner konfiguriert → Fehler
(`us_mediakit.providers.resolution.resolve_provider`). **Account-Default kommt vom
Kundenbereich**, nicht aus einer eigenen us-mediakit-Datenbanktabelle — wer diese
Funktion aufruft, muss den Account-Default selbst nachschlagen und nur das Ergebnis
übergeben.

Für `caption` gibt es keine "registrierte" Liste mehrerer benannter Provider wie bei
`ai_upscale` — pro Instanz genau ein konfigurierter Endpunkt, per-Request per BYOK
(`provider_url`/`provider_key`/`provider_model`) überschreibbar.

## Fallback-Verhalten

`ai_upscale`: schlägt der Provider mit einem Netzwerk-/Erreichbarkeitsfehler fehl (z. B.
claid.ai-Ausfall), fällt der Endpunkt auf ein einfaches, nicht-KI-gestütztes Resize
zurück (`ai_upscale_fallback: true` in der Antwort), statt zu scheitern. Abgerechnet
wird trotzdem der angefragte Umfang — der Fallback ist ein Qualitäts-, kein
Preis-Nachlass.

`restore_faces`: schlägt der CodeFormer-Zusatzschritt fehl, bleibt das bereits
erfolgreiche Upscaling-Ergebnis bestehen, statt die ganze Operation scheitern zu lassen
— ebenfalls ohne Preisnachlass, siehe Kommentar in `api/v1/ai_upscale.py`.

`caption`: ein Provider-Fehler (4xx/5xx bzw. Nichterreichbarkeit) liefert `502`, kein
Fallback — anders als bei `ai_upscale` gibt es keinen sinnvollen "einfachen" Ersatz für
eine KI-generierte Bildbeschreibung.

## Eigenen Provider anbinden

**`ImageEnhanceProvider`:** von `us_mediakit.providers.image_enhance.HttpImageEnhanceProvider`
erben (bedient den projekteigenen HTTP-Vertrag, siehe Docstring dort) oder
`us_mediakit.providers.base.ImageEnhanceProvider` direkt implementieren, wenn der
tatsächliche Dienst einen eigenen Vertrag hat (wie `claid_ai.py`). In
`providers/registry.py`s `build_ai_upscale_provider` einen Fall für den neuen Namen
ergänzen.

**`VisionChatProvider`:** in aller Regel reicht `OpenAICompatibleVisionProvider` mit
passender `base_url`/`model` — eine eigene Implementierung ist nur nötig, wenn der
Dienst nicht OpenAI-chat-API-kompatibel ist.

## Ressourcenbedarf (Serverplanung)

Siehe Phase 5 im Programmierplan für die Festplatten-/VRAM-Tabelle der
Real-ESRGAN/CodeFormer/SeedVR2-Varianten — hier nicht dupliziert, da modellspezifisch
und vor Rollout gegen die Ziel-Hardware zu verifizieren.
