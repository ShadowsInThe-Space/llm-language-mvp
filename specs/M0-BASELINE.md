# M0 — Verbindliche Kompatibilitätsbasis (m0-v1)

Issue #12. Historischer Ausgangspunkt: Git-Commit `149553a`, Paket 0.4.0,
P0-Checker `cert-v0.1`, Webcompiler `web.0.4.0`, Ziel `vinext-d1`.
MUSS und DARF NICHT bezeichnen verpflichtende Regeln.

## Geltung und Vorrang

Für die implementierte Sprache gelten dieses Dokument und die eingefrorenen
Dokumente `docs/P0.md`, `docs/ASSURANCE.md`, `docs/W1-SPEC.md` und `docs/W2-SPEC.md`.
W2 ergänzt W1 ausschließlich für explizit mit `w2` deklarierte Anwendungen.
Die frühen Dokumente `specs/00` bis `specs/06` beschreiben auch Zukunftsziele;
sie aktivieren keine heute nicht implementierten Sprachmerkmale. Insbesondere
sind abhängige Typen, Module, NFC-Normalisierung und ein A4-Siegel keine
Eigenschaften dieser Baseline. Bei Konflikten hat dieser M0-Vertrag Vorrang.

## Profile und Verhalten

| Profil | Syntax und Verhalten | Akzeptanz |
| --- | --- | --- |
| p0 | Getrennte `spec`/`candidate`, Int/Bool, De-Bruijn-Binder, endliche rückwärts gerichtete Aufrufe; strikte Bool-Operatoren, selektives if | Nur unabhängig rekonstruierte und geprüfte cert-v0.1-Belege führen zu proved |
| w1 | `app w1`, Textspeicher mit Ersetzen, read/write, gebundene Widgets | Statisch geprüft, kompiliert und durch Integrationstests geprüft |
| w2 | `app w2`, append-only Historie, Idempotenz, Auswahl/Pagination, lokales clear | Wie w1, keine formale Web-End-to-End-Garantie |

Unbekannte Profile MÜSSEN abgelehnt werden. W1 DARF `clear` nicht übernehmen.
Das Quellenformat ist UTF-8. P0 unterstützt weder Strings noch Kommentare.
Webtext wird nicht normalisiert oder implizit getrimmt; Textgrenzen zählen
UTF-8-Bytes, Historienpräfixe Unicode-Codepoints. Die vollständigen Grammatiken,
Limits und HTTP-/Speicherregeln stehen in den oben genannten Profilverträgen.

## Kanonische Bytes und Hashes

P0 serialisiert den geordneten Baum mit genau einem Leerzeichen zwischen
Elementen, kanonischen Dezimalzahlen, ohne Schluss-Newline. Es gibt keine
Umordnung, Umbenennung oder semantische Vereinfachung beim Hashen.

Für P0 gilt SHA-256 über die Konkatenation von vier gerahmten UTF-8-Feldern:
Domäne (`llmlang:baseline` oder `llmlang:candidate`), `p0`, `cert-v0.1`,
kanonischer Quelltext. Jedes Feld wird mit seiner Bytezahl als vorzeichenlosem
64-bit Big-Endian-Wert eingeleitet. Arbeitsverzeichnis und Dateipfad fehlen.

Für Webquellen gilt SHA-256 über `UTF8("llapp-" + profile + "\0")` gefolgt
von den kanonischen UTF-8-Quellbytes ohne Schluss-Newline. Die erzeugte
`llmlang/source.llapp` enthält zusätzlich ein Newline. Artefakthashes sind
SHA-256 über die exakten UTF-8-Dateibytes. Die Manifest-Datei hasht sich nicht
selbst; `files` enthält die anderen Dateien inklusive IR und kanonischer Quelle.
Manifest/IR-JSON: ensure_ascii, sortierte Schlüssel, Einrückung 2, Schluss-Newline.
Ein Zielverzeichnis ist kein semantischer Input.

`tests/fixtures/m0-v1.json` enthält fest eingecheckte Referenzwerte für sämtliche
historischen Beispiele, Spezifikationen und Abnahmezertifikate sowie kanonische
P0-Quellen/-Hashes und vollständige Webmanifeste. Tests dürfen ihre erwarteten
Werte nicht automatisch aus dem jeweils aktuellen Compiler aktualisieren.

## Beweis- und Laufgrenze

Verifikation bleibt `invalid | unverified | counterexample | proved`.
Domänenstatus bleibt `domain_nonempty | contract_empty | domain_unknown`.
Laufstatus bleibt separat `returned | input_rejected | resource_exhausted | host_error`.
Timeout oder fehlende Belege beweisen weder Korrektheit noch Fehlerhaftigkeit.
Ein geänderter Vertrag, Kandidat, Checker oder Hash verwirft ein altes Zertifikat.
Historische gültige Zertifikate MÜSSEN ohne Solver erneut prüfbar bleiben.
Rationale Farkas-Belege bleiben unvollständig für Integerarithmetik.
Die Python-Implementierung des Checkers gehört weiterhin zur TCB.

## Diagnosevertrag diagnostic-v1

Jede serialisierte Sprachdiagnose enthält `schema`, `phase`, `code`, `message`,
`span` und `symbol`. Bisherige `path`- und `span`-Felder bleiben erhalten.
Die Ergänzung ist additiv; Verbraucher müssen unbekannte Felder tolerieren.
Menschenlesbare Meldungen sind nicht als stabile Vergleichsschlüssel definiert.

`phase` ist eine stabile Fehlerkategorie, kein dynamischer Stack-/Pipeline-Trace:

| phase | Codes |
| --- | --- |
| parse | E_PARSE, W_PARSE, W_LEX, W_PROFILE |
| io | E_IO, W_IO |
| transport | E_JSON, E_ENCODING |
| verify | E_CERTIFICATE, E_SEARCH, E_UNPROVED, E_OPERATOR, E_RESULT |
| factory | E_PROVIDER*, E_FACTORY*, E_CONFIG |
| resource | E_LIMIT, E_RESOURCE, W_LIMIT |
| target | W_TARGET |
| execute | E_PRECONDITION, E_OUTPUT |
| validate | übrige Codes, etwa E_TYPE, E_BINDING, W_UNBOUND |

`span` ist entweder null (nicht verfügbar) oder `{start,end}` mit nullbasierten,
halb offenen Unicode-Zeichenpositionen. WebError-Objekte ohne bekannte
Position behalten das historische `{start:0,end:0}`. CLI-I/O-Fallbacks, die bisher
gar kein span-Feld hatten, erhalten null. P0 behält seinen historischen `path` und
setzt span auf null, da AST-Pfade keine Textkoordinaten sind. `symbol` ist null,
solange der Erzeuger keinen zuverlässigen Symbolbezug liefert; Namen werden
nicht aus Fehlermeldungen geraten. In M0 liefern alle Erzeuger null.
CLI-Argumentfehler von argparse bleiben Host-Usage-Fehler auf stderr außerhalb
dieses Sprachdiagnosevertrags. HTTP-Antworten des generierten Webservers bleiben
dem jeweiligen Webprofil unterstellt.

## Toolchain und Umgebungsannahmen

Python >=3.12, Paketabhängigkeiten gemäß pyproject.toml; requirements.lock
zeichnet die frühere Abnahmeumgebung auf. Lokale Integrationstests benötigen
Node.js 24 mit TypeScript-Stripping und node:sqlite. CI verwendet Python 3.12
und 3.13 sowie Node 24 und installiert die aufgezeichneten Lock-Versionen.
Z3 schlägt Belege vor; sein Versionswechsel darf den Checker nicht umgehen.
Solverlaufzeit, Zeugenwahl und Zertifikatskoeffizienten sind keine eingefrorenen
Bytegarantien. Kanonische Inputs, Checker-Akzeptanz und beobachtbare Ergebnisse sind es.

Das Webziel setzt Vinext/React, Drizzle-Schema und eine D1-kompatible
DB-Bindung voraus. Die SQLite-Tests prüfen generierte Serveroperationen mit
unabhängigem Referenzschema. Sie beweisen weder Cloudflare-Betrieb noch eine
neue Browser-/Produktionsabnahme. Externe Laufzeit und Authentifizierung bleiben
Hostannahmen gemäß W1/W2 und docs/W1-GUIDE.md.

## Abnahme und M1-Sperre

Vor M1 müssen die vollständige Testsuite, Ruff und Mypy grün sein. Die
Kompatibilitätstests vergleichen festgeschriebene Bytes und alte Zertifikate;
die Golden-Tests prüfen zehn historische Rechenaufgaben, Hello und Repair;
Webtests prüfen generierte w1/w2-Operationen gegen echte SQLite-Persistenz.
Negative Fälle müssen Quellen-/Hashdrift, veraltete Zertifikate, manipulierte
Ausgabedateien und fremde Profile erkennen.

Die CI führt diese Prüfungen für jeden Pull Request und main-Push aus.
M1 darf erst auf der gemergten grünen M0-Basis beginnen. Spätere Erweiterungen
müssen diesen Gate weiter bestehen. Inkompatible Änderungen brauchen eine
explizite neue Profil-/Checker-/Baseline-Version mit Migrationsbegründung;
das Überschreiben alter Erwartungswerte zur Beseitigung eines Fehlers ist verboten.
