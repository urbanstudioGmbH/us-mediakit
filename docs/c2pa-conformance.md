# Ein vertrauenswürdiges C2PA-Zertifikat bekommen

`us_mediakit.c2pa.sign` signiert technisch korrekt mit jedem X.509-Zertifikat, das man
ihm gibt — auch mit einem selbst signierten Testzertifikat (siehe
`tests/fixtures/c2pa/`). Das Ergebnis ist dann aber für jeden Prüfer
`signingCredential.untrusted`: die Signatur stimmt, aber niemand hat einen Grund, dem
Aussteller zu vertrauen. Damit Content Credentials draußen tatsächlich als
vertrauenswürdig angezeigt werden (z. B. im Content-Credentials-Verify-Tool oder in
Plattformen, die die C2PA-Trust-Liste prüfen), muss das Zertifikat von einer Stelle
stammen, die auf dieser Trust-Liste steht.

## Der Ablauf in Kürze

C2PA selbst stellt keine Zertifikate aus. C2PA pflegt eine **Trust-Liste** (welche
Root-/Intermediate-CAs als vertrauenswürdig gelten) und ein **Conformance-Programm**
(welche Produkte/Implementierungen als konform gelten). Ein Zertifikat bekommt man erst
von einer auf der Trust-Liste gelisteten Zertifizierungsstelle (CA) — und die stellt
eines typischerweise erst aus, wenn die eigene Implementierung das Conformance-Programm
durchlaufen hat.

1. **Expression of Interest** einreichen über [c2pa.org/conformance](https://c2pa.org/conformance/).
2. **Rechtsvereinbarung** mit C2PA unterschreiben.
3. **Technische und Sicherheitsprüfung**: Architekturunterlagen einreichen (wie wird
   signiert, wo liegt der private Schlüssel, welche Assertions werden erzeugt). Details
   und Anforderungen (u. a. eine Security-Requirements-Appendix) stehen im
   [`conformance-public`-Repository](https://github.com/c2pa-org/conformance-public).
4. Bei Freigabe: Aufnahme in die öffentliche **Conforming Products List**, einsehbar
   über den [Conformance Explorer](https://c2pa-org.github.io/conformance-explorer/).
5. **Erst jetzt** stellt eine teilnehmende CA das eigentliche Signier-Zertifikat aus.

Rückfragen zum Prozess: conformance@c2pa.org. Eine konkrete Bearbeitungsdauer ist auf
keiner offiziellen Seite genannt — im Zweifel direkt nachfragen.

## Zertifizierungsstellen

Aktuell auf der C2PA-Trust-Liste:

- **SSL.com** — hat einen produktiv nutzbaren Weg: nach Conformance-Freigabe reicht man
  Certificate Signing Request, Organization-Validation-Unterlagen und eine
  Produktvalidierung ein. Ein **kostenloser Tarif** ist verfügbar: ein
  Level-1-Claim-Signing-Zertifikat (1 Jahr gültig) plus 10.000 kostenlose
  Trust-Timestamps pro Jahr, sobald eine gültige Conformance-Freigabe vorliegt.
  Kostenpflichtige/Enterprise-Tarife existieren darüber hinaus, ohne veröffentlichte
  Preise. ([SSL.com — Einreichungsleitfaden](https://www.ssl.com/article/how-to-submit-to-the-c2pa-conformance-program/))
- **DigiCert** — "C2PA Media Trust" (Document/Device Trust Manager) befindet sich
  Stand jetzt in einer kostenlosen Beta mit Registrierungsformular, noch ohne
  veröffentlichten Produktivpfad oder Preise. ([DigiCert C2PA Media Trust](https://www.digicert.com/solutions/c2pa-media-trust))

**Wichtiger Stichtag:** Die frühere "Interim Trust List" (ITL) wurde zum 1. Januar 2026
eingefroren — keine neuen Einträge mehr. Der Weg über das Conformance-Programm plus
eine der oben genannten CAs ist seither der einzige Weg zu einem neuen, vertrauten
Zertifikat.

## Technische Anforderungen ans Zertifikat

- X.509, EC (ES256/ES384/ES512) oder RSA (PS256) oder Ed25519 als Signaturalgorithmus.
- Extended Key Usage: die Spezifikation definiert eine eigene
  `c2pa-kp-claimSigning`-OID; alternativ die allgemeine Document-Signing-EKU
  (RFC 9336). Das in dieser Testsuite verwendete Testzertifikat nutzt stattdessen
  `emailProtection` — für Testzertifikate verbreitet, für ein produktives,
  trust-gelistetes Zertifikat aber nicht der vorgesehene Weg.
- Zwei Assurance-Level (1 und 2) sind über eine X.509-v3-Extension kodiert. Level 2
  verlangt hardware-gestützte Schlüsselablage (z. B. HSM).
- Subject/Authority-Key-Identifier müssen korrekt gesetzt sein, sonst scheitert der
  Kettenaufbau bereits beim Signieren mit einer wenig aussagekräftigen Fehlermeldung
  (`the certificate is invalid`) — siehe `tests/fixtures/c2pa/` für ein Zertifikat, das
  es richtig macht.

## Für die Entwicklung: selbst signiertes Zertifikat

Für lokale Entwicklung und Tests reicht ein selbst signiertes Zertifikat mit korrektem
Subject/Authority-Key-Identifier-Paar — `openssl` kann das erzeugen. Ergebnis ist immer
`signingCredential.untrusted`, aber Signieren/Lesen/Verifizieren funktionieren
identisch zum produktiven Fall. `tests/fixtures/c2pa/` enthält ein passendes,
öffentlich verfügbares Beispiel (aus dem `c2pa-python`-Projekt, ausdrücklich nur für
Tests bestimmt).

`USMEDIAKIT_C2PA_CERT_FILE`/`USMEDIAKIT_C2PA_KEY_FILE` (Netzwerk-Dienst) bzw.
`--c2pa-cert`/`--c2pa-key` (CLI) nehmen jedes X.509-Zertifikat/Schlüssel-Paar entgegen,
unabhängig davon, ob es trust-gelistet ist oder nicht — siehe
[`operations.md`](operations.md) und [`api-reference.md`](api-reference.md).
