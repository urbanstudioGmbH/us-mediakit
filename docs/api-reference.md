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
