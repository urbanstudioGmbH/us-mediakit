# API-Referenz

Diese Datei wächst mit jeder Phase (siehe Programmierplan Abschnitt 10). Aktuell
dokumentiert: Zuschnitt (Phase 1), Metadaten (Phase 2), C2PA (Phase 3), Netzwerk-Dienst/
Konten/Metering (Phase 4). KI-Provider und Wasserzeichen folgen in Phase 5/6 — die
Routen `/v1/caption`, `/v1/ai_upscale`, `/v1/watermark`, `/v1/watermark/detect` existieren
bereits (Auth/Routing stehen), liefern aber bis dahin `501 Not Implemented`.

Alle `/v1/*`- und `/admin/*`-Endpunkte sind über den Netzwerk-Dienst erreichbar
(`us-mediakit serve`, siehe [`operations.md`](operations.md)). Die darunterliegenden
Library-Funktionen (siehe jeweilige Abschnitte unten) sind unabhängig davon auch ohne
Server nutzbar (Library/CLI).

## Zuschnitt (`thumbnail`)

Siehe [`fit-modes.md`](fit-modes.md) für die vier Fit-Modi mit Beispielbildern.

```bash
us-mediakit thumbnail photo.jpg --mode showcase_medium -o thumb.jpg
```

Library-Ebene: `us_mediakit.core.pipeline.generate_thumbnail(ThumbnailRequest(...))`.

## Metadaten

### Lesen

Liest alle von `exiftool` erkannten Gruppen (EXIF, IPTC, XMP, File, Composite, ...) als
ein flaches JSON-Objekt mit `Gruppe:Tag`-Schlüsseln (`-G`-Modus von exiftool).

```bash
us-mediakit meta read photo.jpg
```

```json
{
  "File:MIMEType": "image/jpeg",
  "EXIF:Orientation": 1,
  "IPTC:ObjectName": "Beispielbild",
  "XMP-dc:Description": "..."
}
```

Library-Ebene: `us_mediakit.metadata.read.read_metadata(data: bytes) -> dict`.

### Schreiben

Setzt einzelne Tags über `Gruppe:Tag=Wert` bzw. `Tag=Wert` (wenn die Gruppe eindeutig ist).

```bash
us-mediakit meta write photo.jpg --set "IPTC:ObjectName=Neuer Titel" --set "EXIF:ImageDescription=..."
```

Library-Ebene: `us_mediakit.metadata.write.write_tags(data: bytes, tags: dict[str, str]) -> bytes`.

### Standort entfernen (`strip_gps`)

Entfernt gezielt die EXIF-GPS-IFD sowie die gängigen XMP-Standort-Spiegelfelder, lässt alle
anderen Metadaten unverändert. Deckt keine proprietären, nicht standardisierten
Standort-Ablagen einzelner Programme ab (dokumentierte Scope-Grenze).

```bash
us-mediakit meta write photo.jpg --strip-gps
us-mediakit thumbnail photo.jpg --mode showcase_medium --strip-gps -o thumb.jpg
```

Library-Ebene: `us_mediakit.metadata.gps.strip_gps(data: bytes) -> bytes`.

### Automatische Übernahme bei jeder erzeugten Bildvariante

**Kein separat aufzurufendes Feature.** Jede über `thumbnail`/`generate_thumbnail` erzeugte
Bildvariante bekommt die Metadaten des Originals automatisch zurückgeschrieben — Standard ist
an (`carry_metadata: true`), analog zur C2PA-Propagationsregel aus Abschnitt 5a des
Programmierplans. Abschalten mit `--no-carry-metadata` bzw. `carry_metadata=False`.

**Bekannte Scope-Grenze in Phase 2:** Bei Video-Frame- oder PDF-Seiten-Extraktion
(`--video`/`--pdf`) wird die Metadaten-Übernahme ausgelassen — das extrahierte Rasterbild hat
keine sinnvoll übertragbaren Bild-Metadaten, und ein Mapping von Video-/PDF-Container-Metadaten
auf Bild-Metadaten ist hier nicht spezifiziert.

### exiftool-Prozessmodell

`us_mediakit.metadata.exiftool_client.ExifToolClient` hält einen einzigen `exiftool`-Prozess im
`-stay_open`-Modus am Leben (kein Perl-Neustart pro Aufruf). Ein Client-Objekt ist für **einen**
Worker/Thread gedacht — parallele Aufrufe über denselben Client werden serialisiert
(`threading.Lock`), nicht parallel im selben Prozess verarbeitet. Im Netzwerk-Dienst (Phase 4)
bekommt jeder Worker-Prozess seinen eigenen `ExifToolClient`.

## C2PA / Content Credentials

Grundlagen und die Propagations-Pflichtprüfung (Abschnitt 5a) sind in
[`c2pa-concepts.md`](c2pa-concepts.md) erklärt. Hier nur die Aufrufe.

### Prüfen

```bash
us-mediakit c2pa verify photo.jpg
```

Liefert `validation_state` (`"Valid"`/`"Invalid"`) plus die vollständigen
Validierungsergebnisse als JSON. Exit-Code 0 nur bei `"Valid"`.

Library-Ebene: `us_mediakit.c2pa.verify.verify(data: bytes, mime_type: str) -> VerificationResult`.

### Signieren

```bash
us-mediakit c2pa sign photo.jpg --cert cert-chain.pem --key private-key.pem --source-type digitalCapture
```

`--source-type` akzeptiert Kurznamen aus der IPTC-Vokabularliste (z. B. `digitalCapture`,
`algorithmicallyEnhanced`, `trainedAlgorithmicMedia`, `compositeSynthetic`) oder eine volle
IPTC-URL. `--actions-json` erlaubt zusätzliche Actions/Assertions als JSON-Datei
(`{"actions": [...], "assertions": [...]}`).

Library-Ebene: `us_mediakit.c2pa.sign.sign(SignRequest(...)) -> bytes`.

**Zertifikat für Produktivbetrieb:** Muss über das C2PA-Conformance-Programm ausgestellt
sein, sonst wird die Signatur zwar kryptographisch korrekt, aber als `signingCredential.untrusted`
markiert (siehe `c2pa-concepts.md`).

### Automatische Propagation bei jeder erzeugten Bildvariante

Wie die Metadaten-Übernahme: kein separat aufzurufendes Feature, Standard ist an
(`carry_c2pa: true`). Erzeugt nur dann ein neues Manifest, wenn die Quelle ein Signal trägt
oder der Aufrufer eines mitliefert (siehe `c2pa-concepts.md`) — nie eine erfundene Provenienz.

```bash
us-mediakit thumbnail photo.jpg --mode showcase_medium \
  --c2pa-cert cert-chain.pem --c2pa-key private-key.pem \
  --c2pa-json overrides.json \
  -o thumb.jpg
```

`overrides.json`: `{"digital_source_type": "algorithmicallyEnhanced"}` — nur nötig, wenn die
Quelle selbst kein C2PA-Manifest und kein IPTC-`DigitalSourceType`-Feld trägt (Fall 3 aus
Abschnitt 5a). Abschalten mit `--no-carry-c2pa`.

Library-Ebene: `ThumbnailRequest.c2pa_signer_config`/`c2pa_digital_source_type`/`c2pa_actions`/
`c2pa_assertions`/`carry_c2pa`, ausgewertet von `us_mediakit.c2pa.propagate.propagate`, das
standardmäßig als Provenienz-Hook in `generate_thumbnail` eingehängt ist.

## Netzwerk-Dienst

### Auth

Zwei getrennte Schemata, `Authorization: Bearer <token>` in beiden Fällen:

- **API-Key** (`/v1/*`) — erzeugt über `POST /admin/api-keys`. Ungültig/unbekannt → 401,
  gesperrt → 403.
- **Admin-Token** (`/admin/*`) — ein Token pro Instanz, siehe `USMEDIAKIT_ADMIN_TOKEN_FILE`
  in [`operations.md`](operations.md). Nicht konfiguriert → 503, falsch → 403.

### `dry_run` und `request_id`

Auf jedem `/v1/*`-Endpunkt verfügbar:

- **`dry_run: true`** — liefert `estimated_credits`/`confidence: "exact"`, führt die
  Operation nicht aus, kein `usage_events`-Eintrag, 0 Credits.
- **`request_id`** — Idempotenz-Key. Eine Wiederholung mit derselben `request_id`
  liefert dieselbe bereits berechnete Antwort zurück, ohne die Operation erneut
  auszuführen oder erneut abzurechnen — solange die Antwort noch im Kurzzeit-Cache liegt
  (Standard 5 Minuten, pro Worker-Prozess, siehe `operations.md`). Danach liefert eine
  Wiederholung `409 Conflict`, statt eine möglicherweise andere Antwort vorzutäuschen.

### Admin — API-Keys

| Methode & Pfad | Zweck |
|---|---|
| `POST /admin/api-keys` | Erzeugt einen Key (`account_ref`, `label`). Der Klartext-Key ist nur in dieser Antwort sichtbar. |
| `POST /admin/api-keys/{id}/suspend` | Sperrt einen Key (z. B. Guthaben-Enforcement durch den Kundenbereich). |
| `POST /admin/api-keys/{id}/reactivate` | Entsperrt einen Key. |
| `DELETE /admin/api-keys/{id}` | Endgültiger Widerruf — löscht den Key-Datensatz. `usage_events` bleiben unabhängig davon erhalten (`account_ref` ist denormalisiert). |

### Admin — Nutzung

| Methode & Pfad | Zweck |
|---|---|
| `GET /admin/accounts/{account_ref}/usage` | Aggregierte Nutzung nach Operation (`count`, `credits`, `bytes_in`, `bytes_out`), optional `?from=`/`?to=` (ISO-8601). Für die Anzeige im Kundenbereich. |
| `GET /admin/usage/export` | Cursor-basiert (`since_id`, `limit`, Default 500, Max 5000): liefert `UsageEvent`-Zeilen mit `id > since_id`, aufsteigend, plus `next_since_id` für den nächsten Poll. Für den Guthaben-Abzug im Kundenbereich — siehe Abschnitt 9 des Programmierplans zur Abstimmung des Poll-Intervalls. |

### `GET /health`

Kein Auth. `{"status": "ok"}`, sobald die Anwendung läuft. Prüft keine Abhängigkeiten
(DB, `exiftool`, `ffmpeg`, `pdftoppm`).

### Rate-Limiting

Drei unabhängige Ebenen (nginx, Credits/Minute pro Plan-Tier, Video/PDF-Concurrency) —
siehe [`operations.md`](operations.md#rate-limiting--drei-unabhängige-ebenen).

### Noch nicht implementiert

`POST /v1/caption` und `POST /v1/ai_upscale` (Phase 5), `POST /v1/watermark` und
`POST /v1/watermark/detect` (Phase 6) sind bereits geroutet und erfordern einen gültigen
API-Key, liefern aber `501 Not Implemented`.
