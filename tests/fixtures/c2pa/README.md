# C2PA-Testzertifikat

`es256_certs.pem` und `es256_private.key` sind Test-Fixtures aus dem offiziellen
[`c2pa-python`](https://github.com/contentauth/c2pa-python)-Projekt (Adobe, dual
MIT/Apache-2.0-lizenziert, wie `us-mediakit` selbst), übernommen aus
`tests/fixtures/` bei Commit `1a7c5948a33c8ca21cff3af85a1908b135ca563b`. Das
Zertifikat ist explizit als `FOR TESTING_ONLY` gekennzeichnet und dient
ausschließlich dazu, den Signier-/Lese-/Verifizieren-Roundtrip in dieser Testsuite
gegen die reale `c2pa-python`-Bibliothek zu prüfen.

**Nicht für den Produktivbetrieb verwenden.** Ein selbst signiertes bzw. nicht
trust-anchored Testzertifikat signiert zwar technisch korrekt, wird aber von jedem
C2PA-Prüfer als `signingCredential.untrusted` markiert — erwartetes, korrektes
Verhalten (siehe `test_c2pa.py`). Für produktiv vertrauenswürdige Signaturen braucht
es ein über das C2PA-Conformance-Programm ausgestelltes Zertifikat, siehe
[`docs/c2pa-conformance.md`](../../../docs/c2pa-conformance.md).
