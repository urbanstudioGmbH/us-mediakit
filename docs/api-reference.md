# API-Referenz

Diese Datei wächst mit jeder Phase (siehe Programmierplan Abschnitt 10). Aktuell
dokumentiert: Zuschnitt (Phase 1) und Metadaten (Phase 2). C2PA, der Netzwerk-Dienst,
KI-Provider und Wasserzeichen folgen in den jeweiligen Phasen.

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
