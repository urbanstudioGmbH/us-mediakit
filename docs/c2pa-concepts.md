# C2PA / Content Credentials — Grundlagen

Diese Seite erklärt C2PA so weit, wie man es braucht, um mit us-mediakit sinnvoll zu
arbeiten — keine vollständige Spezifikationslektüre.

## Was ist ein C2PA-Manifest?

Ein kryptographisch signierter Datensatz, der einer Bild-/Video-/Audiodatei beigelegt
wird (bei JPEG z. B. als eigenes Segment) und Aussagen über ihre Herkunft trifft: wer/was
hat sie erzeugt oder verändert, mit welchem Werkzeug, war KI beteiligt. "Content
Credentials" ist der Endnutzer-Name für dieselbe Sache.

Zwei Bausteine sind für uns-mediakit relevant:

- **Actions** — was wurde getan (`c2pa.created`, `c2pa.resized`, `c2pa.cropped`, ...),
  jeweils mit einem Pflichtfeld `digitalSourceType` aus der [IPTC-Vokabularliste](http://cv.iptc.org/newscodes/digitalsourcetype/)
  (z. B. `digitalCapture`, `trainedAlgorithmicMedia`, `algorithmicallyEnhanced`,
  `compositeSynthetic`). us_mediakit.c2pa.vocabulary löst Kurznamen automatisch auf die
  volle IPTC-URL auf.
- **Ingredients** — Verweise auf andere Assets, aus denen das aktuelle erzeugt wurde,
  mit einer `relationship` (bei uns ausschließlich `parentOf`: "dieses Ingredient ist der
  Vorgänger des aktuellen Assets").

## Warum ein bestehendes Manifest nie verändert wird

Eine Signatur bindet sich kryptographisch an genau die Pixel/Bytes, die zum
Signierzeitpunkt vorlagen. Jede Änderung — auch ein simples Verkleinern — macht eine
vorhandene Signatur ungültig. us-mediakit signiert deshalb nie nach: **jede erzeugte
Bildvariante bekommt ein eigenes, neues Manifest**, das per Ingredient-Assertion
(`relationship: "parentOf"`) auf das Original verweist. Über beliebig viele
Ableitungsstufen (Original → Thumbnail → nochmals verkleinertes Thumbnail → ...) bleibt
die Kette so lückenlos nachvollziehbar, ohne dass irgendwo ein bestehendes Manifest
angefasst wird.

```
Original (eigenes Manifest, signiert)
  ↑ Ingredient (parentOf)
Thumbnail 1280×375 (eigenes Manifest, signiert)
  ↑ Ingredient (parentOf)
Thumbnail 300×300 (eigenes Manifest, signiert)
```

## Die Propagations-Pflichtprüfung

Kein separat aufzurufendes Feature — us-mediakit prüft bei **jeder** derivat-erzeugenden
Operation automatisch, ob eines von drei Signalen vorliegt, und erzeugt nur dann ein
neues Manifest:

1. **Die Quelle hat bereits ein gültiges C2PA-Manifest.** → wird als Ingredient
   referenziert, `digitalSourceType` wird aus dessen Actions übernommen.
2. **Die Quelle hat kein Manifest, aber ein IPTC/XMP `DigitalSourceType`-Feld.** → neues
   Manifest ohne Ingredient (nichts zum Verketten vorhanden).
3. **Der Aufrufer liefert `digital_source_type`/`actions`/`assertions` explizit mit** —
   z. B. weil das aufrufende System weiß "das kam von Midjourney", die Datei selbst aber
   nur ein einfaches JPEG ohne jedes Signal ist.

Trifft **nichts** davon zu, bleibt das Ergebnis unverändert — us-mediakit erfindet nie
eine Provenienz für unbekannten Ursprung. Library-Ebene: `us_mediakit.c2pa.propagate.propagate`,
eingehängt in `core.pipeline.generate_thumbnail` als Standard-Hook. Ohne konfiguriertes
Zertifikat (`ThumbnailRequest.c2pa_signer_config`) verhält sich der Hook wie ein No-Op —
die Prüfung ist immer aktiv, das Signieren nur, wenn ein Zertifikat hinterlegt ist.

## Eigenes lokales Modell kennzeichnen

Ein selbst gehostetes Vision-/Upscaling-Modell hat selbst kein C2PA-Bewusstsein — es
liefert nur Pixel zurück. Damit die KI-Beteiligung trotzdem
dokumentiert wird, liefert der aufrufende Code den passenden `digital_source_type`
explizit mit (Fall 3 oben), z. B. `algorithmicallyEnhanced` für ein KI-Upscaling oder
`compositeSynthetic` für eine vollständig KI-generierte Bildbeschreibung, die als
Bildinhalt interpretiert werden könnte.

## Vertrauenswürdigkeit — "signiert" ist nicht "vertrauenswürdig"

`validation_state` bewertet ausschließlich, ob Signatur und Hash-Bindung kryptographisch
stimmen — unabhängig davon, ob dem Aussteller des Zertifikats vertraut wird. Ein
selbst signiertes Testzertifikat kann `validation_state: "Valid"` liefern und trotzdem
den Eintrag `signingCredential.untrusted` in den Validierungsergebnissen tragen: die
Signatur ist technisch korrekt, der Aussteller ist aber nicht in einer anerkannten
Trust-Liste. Für produktiv vertrauenswürdige Signaturen braucht es ein über das
[C2PA-Conformance-Programm](https://c2pa.org/conformance/) ausgestelltes Zertifikat —
siehe [`c2pa-conformance.md`](c2pa-conformance.md) für den Antragsweg.

`tests/fixtures/c2pa/` enthält ein offizielles Testzertifikat aus dem `c2pa-python`-Projekt
für die eigene Testsuite — ausdrücklich nur für Tests, nie für Produktivbetrieb.
