# Expertenreview: Fullstack-Compiler für LLM-Language

Status: Abgestimmte Planung vor Implementierung, 2026-09-08.

## Entscheidung

P0 bleibt unverändert. Das separate Profil `w1` beschreibt persistente Textslots,
explizite Read-/Write-Aktionen und eine deklarative Browseroberfläche. Der vorhandene
Pythoncompiler erhält eine additive Source-to-Source-Compilerstufe. Sie erzeugt
Vinext/React-Module, API-Handler und ein Drizzle-Datenbankschema aus einer `.llapp`.
Vinext/Vite erzeugen anschließend Browserassets/Worker; `drizzle-kit generate`
erzeugt SQL-Migrationen mit unveränderlichem Journal/Snapshot. Das ist eine echte
mehrstufige Compilerpipeline, ohne einen Maschinencode-Compiler zu behaupten.

Der Lead hat Sites/Vinext mit D1-Binding `DB` festgelegt. Compileragenten bearbeiten
ausschließlich das separate Pythonprojekt. Nur der Lead integriert Compileroutput
im Site-Checkout, erzeugt Migrationen und führt Browser-QA/Hosting aus.

Der Anwendungscode wird vollständig in `.llapp` beschrieben: Slotnamen, Textgrenzen,
Aktionen, Inputvorbelegung, Labels, Widgetreihenfolge und Antwortbindungen. Gemeinsame
HTTP-/DB-/UI-Hilfsfunktionen dürfen Compilerbibliothek sein. Eine manuell geschriebene
Hallo-Demo mit angehängtem Quellhash würde diese Anforderung nicht erfüllen.

D1 unterstützt vorbereitete Statements mit `.bind(...)`, passend zur kleinen
emittierten Runtime. SQL-Fähigkeiten stammen aus dem Serverbinding, nicht aus dem
Browser. [D1 Prepared Statements](https://developers.cloudflare.com/d1/worker-api/prepared-statements/),
[D1 Database Binding](https://developers.cloudflare.com/d1/worker-api/d1-database/)

## Verbindliche Semantik

Die genaue Grammatik wird mit `language-review.md` zusammengeführt. Gemeinsamer
Kern: maximal acht benannte Textslots, pro Slot höchstens 4096 UTF-8-Bytes; leere
Strings erlaubt; NUL und ungepaarte Surrogate verboten; kein trim oder Normalisieren.
`Text N` zählt Bytes, nicht UTF-16-Codeunits. Requestbody maximal 32768 Bytes.

Der Startwert `Hello new AI World` gehört als `(initial ...)` zum Inputwidget.
Stores besitzen keinen Default. Ein unbeschriebener Slot antwortet auf GET mit
`found:false`. Es gibt weder Seeds noch Rückfall auf einen Quellwert beim DB-Lesen.
Die Oberfläche zeigt den Zustand „Noch nichts gespeichert“ getrennt vom Leerstring.

„Speichern“ sendet den aktuellen Input an den Server. Ein atomarer UPSERT persistiert
ihn; erst die erfolgreiche Serverantwort bestätigt das Speichern. „Anzeigen“ führt
einen echten Lesezugriff aus und zeigt den DB-Wert. Eine fehlgeschlagene Aktion erhält
den letzten bestätigten Output und zeigt separat einen Fehler. Kein localStorage als
Datenbankersatz. Gleichzeitige Writes haben Last-write-wins-Semantik; eine Antwort
bestätigt den eigenen Commit, nicht die Abwesenheit späterer Writes.

Die private Site besitzt gemeinsam genutzte Slots für ihre berechtigten Besucher.
Es gibt keine Konten oder Nutzerrecordisolation im Sprachprofil. Plattformzugang ist
eine getrennte Hostinggrenze. Lokale QA besitzt keine erfundenen SIWC-/Authheader.

## Parser und Datenmodell

P0-Reader, -Hashdomänen und -Typregeln nicht verändern. Ein neuer begrenzter Reader
verarbeitet S-Expressions mit JSON-kompatibel escaped Strings. Symbol und Textliteral
sind unterschiedliche Knoten. Stringescapes, Byte-/Knoten-/Tiefengrenzen und gültige
Unicodewerte werden beim Lesen geprüft. Diagnosen besitzen stabile Codes und Spans.

Kleine frozen Dataclasses genügen:

- `TextType(max_bytes)`
- `Store(name, text_type)`
- `Action(name, effect, store)` mit geschlossenem Effekt `read` oder `write`
- `Input(id, label, store, initial)`
- `Output(id, label)`
- `Button(id, label, action, input_id_or_none, output_id)`
- `Page(title, widgets)`
- `WebApp(profile, app_id, stores, actions, page)`

Bindungsprüfung: eindeutige Slot-/Aktionsnamen und Widget-IDs; nur bekannte Formen;
gültige Referenzen; passende Input-/Aktionskapazitäten; read ohne Argument, write mit
genau einem Input; jede Ausgabe zeigt auf ein Outputwidget. Namen sind begrenzte
ASCII-Identifier. Keine frei eingebetteten SQL-, HTML-, JS-, Pfad- oder URL-Fragmente.

Eine validierte IR enthält aufgelöste Bindungen, Routen und Storekonfiguration.
Falls sie keine neue Information ergänzt, ist ein erfolgreich validiertes `WebApp`
einfacher als dieselben Felder in zwei parallelen Klassenhierarchien. Emitters dürfen
nur erfolgreich geprüfte Daten bekommen. Eine unvalidierte JSON-Abkürzung ist verboten.

## Deterministische Compilerartefakte

Gleiche kanonische Quelle, Compilerversion und Ziel ergeben bytegleiche direkte
Compilerartefakte. Keine Uhrzeit, Zufalls-ID, absolute Checkoutpfade oder Hosting-IDs
einbetten. Quell-/Widgetreihenfolge bleibt erhalten. SQL-Journalmetadaten nachgelagerter
Werkzeuge werden separat erfasst; Determinismus dieser Compilerstufe ist nicht ohne
Prüfung eine Zusage für jeden Deploymentbyte.

| Artefakt | Herkunft |
| --- | --- |
| `app/page.tsx` | Python: echter React-Baum, Widget-IDs, Eventbindings und Texte |
| `app/...css` | Python: zugängliche gemeinsame Designbasis und erlaubte Quellwerte |
| `app/api/store/[slot]/route.ts` | Python: zugelassene Slots/Aktionen, Validatoren, DB-Aufrufe |
| `db/schema.ts` | Python: Drizzle-Schema mit aus Slots abgeleiteten Constraints |
| `manifest.json` | Python: Profil, Ziel, Quelle, Version und Artefakthashes |
| SQL/Journal/Snapshot | Drizzle aus dem emittierten Schema |
| Browserassets/Worker | Vinext/Vite aus emittierter Seite und API |

Keine Seeddatei. Keine CREATE-TABLE- oder Initialisierung im Requesthandler.
Der Compiler ist allgemeiner als eine einzelne Demoseite: Eine zweite gültige Quelle
mit zwei Slots muss neue DOM-Struktur, unabhängige API-Bindungen und passende
DB-Konfiguration erzeugen, ohne Compiler-/Runtimeänderungen.

React-Textknoten behandeln Quell- und DB-Strings als Daten; kein
`dangerouslySetInnerHTML`. TypeScript-Literale mit geeignetem JSON-Encoding erzeugen,
nicht durch rohe Interpolation. CSP muss mit Vinext-Hydration und Hosting abgestimmt
sein; keine naive `script-src 'self'`-Richtlinie als ungeprüfte Sicherheitsbehauptung.

## API und Datenbankschema

Gemeinsame Route `/api/store/[slot]`: GET liest, PUT akzeptiert exakt
`{ "value": "..." }`. Unbekannte Slots antworten 404. Fremdfelder, falsche Typen,
zu große Bodies oder ungültige Texte werden abgelehnt. Der emittierte Katalog bestimmt
serverseitig, welche Quelle read/write für welchen Slot erlaubt. Die Clientauswahl
einer Route darf keine zusätzliche nichtdeklarierte Fähigkeit freischalten.

Eine Tabelle mit stabilem App-/Slotschlüssel genügt. `app_id` ist Datenidentität;
niemals den Quellhash als DB-Namespace verwenden, da UI-Änderungen sonst scheinbar
Daten verlieren. Textconstraints stammen aus dem kompilierten Slotkatalog. Serverseitig
UTF-8-Bytezahl prüfen; SQL beispielsweise über `length(CAST(value AS BLOB))` absichern.
NUL bleibt ausdrücklich ausgeschlossen.

Ein SQL-Statement pro prepare-Aufruf. Werte werden mit `.bind(...)` gebunden;
Identifikatoren stammen nur aus geprüfter Generatorstruktur. Speichern ist ein
einzelner atomarer UPSERT, kein Read-modify-write-Ablauf. API-Antworten sollen den
eigenen bestätigten Wert enthalten; ein getrennt nachgeschobener Read könnte bereits
einen konkurrierenden Write sehen. GET muss vorhandenen Leerstring von absent trennen.

Drizzle erzeugt Migrationen aus `db/schema.ts`; SQL/Journal/Snapshot werden gemeinsam
archiviert und nicht nachträglich editiert oder durch alternative DDL ersetzt.
Inkompatible Text-/Schemaschrumpfung muss mit Migrationsdiagnose abbrechen statt Daten
zu löschen. Allgemeine automatische Schemaevolution gehört nicht zu w1.

## Manifest und Assurance

Manifest mindestens: Profil, Compilerversion, Ziel, kanonischer Quellhash und sortierte
Dateiliste mit relativem Pfad, Bytezahl und SHA-256. Der kanonische Quelltext ist ein
Artefakt. Optionaler Raw-Source-Hash dokumentiert Herkunft zusätzlich. Kein rekursiver
Eigenhash des Manifests. Keine Geheimnisse oder Deployment-IDs als Sprachbestandteil.

Dateibindung dokumentiert einen Buildstand. Sie beweist weder Quellabsicht noch
Semantikübersetzung oder Urheberschaft. Neu kompilieren und Dateien vergleichen ist
ein nützliches Factory-Gate, aber kein A3-Beweis.

Erfolg heißt `compiled`, nicht P0-`proved` oder A4-`sealed`. Bestehende P0-Zertifikate
gelten nicht für Text, React, HTTP, SQL, Worker, Drizzle oder Vinext. Der Webcompiler
wird zunächst durch statische Prüfung, TDD, Integration und Browserabnahme abgesichert.

## TDD-Gates und Definition of Done

1. Parser/Checker RED → GREEN: Minimalquelle sowie falsche Referenzen, Typen, Arity,
   Strings und Limits. Propertytests für kanonisches Roundtrip und Textgrenzen.
2. Emitters RED → GREEN: zwei unabhängige Quellen, darunter zwei Slots, ändern
   nachweislich Widgetstruktur, Aktionen und Schema. Äquivalenter Whitespace und
   äquivalente Stringescapes ändern direkte Compilerartefakte nicht.
3. Targetgate: emittiertes TSX/TS tatsächlich bauen; Textsnapshots genügen nicht.
   Emittiertes Drizzle-Schema migrieren und ausschließlich den erzeugten Handler
   ausführen. Ein SQLite-Testadapter ergänzt echte D1-QA, ersetzt sie nicht heimlich.
4. HTTP-/DB-Gates: absent, Leerstring, Emoji/UTF-8-Grenze, Quotes, SQL-artiger Text,
   Scriptpayload. Falsches JSON, Fremdfelder, unbekannter Slot, Origin- und Bodyfehler
   verändern nichts. Keine SQL-/Secretdetails in Runtimefehlern.
5. Persistenzgate: Save, frischer Read, Reload und möglichst Runtime-Neustart erhalten
   den Wert. Titeländerung bei gleicher App-ID darf vorhandene Daten nicht verlieren.
6. Browsergate: generierter Input zeigt `Hello new AI World`; speichern und separat
   aus DB laden; anderen Text speichern, reloaden und wieder laden. Scriptpayload
   erscheint nur als Text. Screenshot, URL und echte HTTP-/DB-Belege archivieren.
   Nur tatsächlich getestete Browserengines nennen.
7. Gesamtgate: vorhandene P0-Suite, neue Python-Tests, Ruff, mypy, Targetbuild und
   Browserabnahme erfolgreich. Generierte Dateien nie manuell reparieren: Compiler
   oder Sprachquelle ändern, neu erzeugen und relevante Gates wiederholen.

Abnahme liefert agentengeschriebene `.llapp`, eingefrorene Quelle und Manifest,
emittierten Zielcode, Migrationen, echte Persistenzbelege und private Browser-URL.
Jedes Ergebnis wird an den konkret ausgeführten Quell-/Artefaktstand gebunden.

## Module und Arbeitsaufteilung

Additive Module im bestehenden Pythonpackage:

- `web_model.py`: immutable Daten, Limits, Diagnostics.
- `web_parser.py`: begrenzter Reader, Decode, kanonische Darstellung.
- `web_check.py`: Referenz-/Typ-/Effektprüfung, optionales Lowering.
- `web_emit.py`: getrennte React-, CSS-, API- und Drizzleemitter.
- `web_build.py`: Prüfung, feste Outputpfade, Hashmanifest, deterministische Ausgabe.

CLI: `llmlang compile-web app.llapp --target vinext-d1 --out build/web`.
Genaue Flagform/Modulaufteilung darf der Lead vereinfachen. Erst alle Ausgaben
validieren, dann feste compilerbesessene relative Pfade schreiben; keine Pfade aus
Nutzertext. Zielprofil und Version bleiben im Manifest explizit.

Nach eingefrorener Spec können Parser/Checker, Emitters und unabhängige
Sicherheits-/Integrationschecks parallel im Compilerprojekt entstehen. Nur der Lead
integriert Site-Output, Drizzle/Vinext, Browser-QA und Hosting. Noch technisch zu
fixieren sind die konkrete Python-Modul-API, Importpfade der Site-Primitives und
exakte Antwort-/Fehlerobjekte; dafür ist keine Produktentscheidung des Nutzers nötig.
