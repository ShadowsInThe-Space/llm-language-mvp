# Abnahme des Fullstack-Compilers w1

Stand: 2026-09-08. Compilerpaket 0.3.0, Webprofil w1.

Die vom Nutzer geforderte Strecke funktioniert: Ein Session-Agent schrieb das
Programm in unserer Sprache; der Compiler erzeugte UI, API und Schema; ein echter
Browser speicherte Texte in einer Datenbank und lud sie wieder. Die erzeugte Webseite
ist privat bereitgestellt: [Hello AI World](https://hello-ai-world.adaptiveaisolutions.chatgpt.site).

## Ergebnis nach Prüfbereich

| Kriterium | Tatsächlich ausgeführter Nachweis |
| --- | --- |
| Spezifikation vor Umsetzung | Commit `4e3bab7` enthält W1-SPEC und W1-PLAN; `8e17e94` ergänzt den abschließenden Expertenabgleich vor Implementierung |
| Expertenarbeit | Vier Experten für Sprache, Compilerarchitektur, Security/DB und unabhängige Abnahme; Lead integriert; eigener fünfter Agent schreibt die Programme |
| Agentenquelle | `hello.llapp` und `notes.llapp`, Herkunft und Rohdatei-Hashes in `evidence/web/` |
| Eigener Compiler | Lexer, Parser, unveränderlicher AST, Typ-/Referenz-/Limitprüfung, kanonische Quelle, Emitter, CLI, atomische Artefaktausgabe und Recompilationsvergleich |
| Generalität | Zweite Agentenquelle kompiliert ohne Compileränderung zu zwei Speichern, vier Aktionen und acht Widgets |
| Gesamttests | **297 bestanden in 14,09 Sekunden**, darunter alle bisherigen P0-Tests; JUnit-Protokoll `evidence/web/tests-final.xml` |
| Unabhängige Runtime-Abnahme | 44 Tests durch Compiler → generiertes TypeScript → Node 24 → reale SQLite-Datei; final mit tatsächlich erzeugtem Drizzle-SQL |
| Pythonqualität | Ruff ohne Befunde; strenges mypy ohne Befunde in 19 Quelldateien |
| Zielcode | Vinext/Vite-Produktionsbuild erfolgreich, `tsc --noEmit` und ESLint erfolgreich |
| Browser | Tatsächliche Chrome-Interaktion über Buttons und Texteingabe |
| Persistenz | Laden ohne Übernahme ungespeicherter Eingabe; Reload; Prozessneustart der Preview bei erhaltener D1-Datei; erneutes Laden desselben Wertes |
| Dateneigenschaften | Leerstring, Unicode, Emoji, Zeilenumbrüche, HTML-/SQL-artige Texte; Ausgabe bleibt Text; zu große Eingabe bewahrt bestätigten Wert |
| Distribution | Wheel 0.3.0 isoliert installiert, beide Programme daraus kompiliert und verifiziert; alle Hello-Zielquelldateien bytegleich mit der bereitgestellten Site |
| Bereitstellung | Private Veröffentlichung vom Hostingdienst erfolgreich bestätigt; Produktionsdatenbank wird durch die generierte Migration angelegt |

## Browserablauf

1. Vor dem ersten Speichern meldete Laden korrekt einen leeren Speicher.
2. **Speichern** schrieb `Hello new AI World`; die Oberfläche zeigte die bestätigte Antwort.
3. Eine andere, ungespeicherte Eingabe änderte das Resultat von **Aus Datenbank laden** nicht.
4. Unicode und Zeichenfolgen wie `<script>…</script>` wurden gespeichert und nach Reload
   exakt als Text angezeigt; im Ausgabeelement entstand kein Scriptknoten.
5. Ein leerer String wurde gespeichert und von einem fehlenden Eintrag unterschieden.
6. Eine Eingabe oberhalb der Bytegrenze wurde abgewiesen; die bestätigte Ausgabe blieb erhalten.
7. Nach Beenden und erneutem Starten des Preview-Serverprozesses konnte Chrome
   `Hello new AI World` erneut aus der D1-Datei laden.

Die Browserbelege stehen unter `evidence/web/browser.json` und `browser.jpg`.
Die unabhängigen Runtime-Tests prüfen zusätzlich malformed UTF-8, doppelte JSON-Schlüssel,
Origin-/Methoden-/Medientypfehler ohne Datenänderung, SQL-Constraints, App-/Slottrennung,
gleichzeitige vollständige Schreibvorgänge, Datenbankausfälle und neue Node-Prozesse.

## Gefundene und behobene Fehler

Eine Parsergrenzdiagnose lieferte zuerst W_PARSE statt W_LIMIT; Regression und Korrektur
sind protokolliert. Die Browserprüfung fand außerdem vor Hydration aktiv angezeigte
Buttons, deren sehr früher Klick verloren gehen konnte. Der Compiler erzeugt nun
gesperrte Eingaben und Buttons bis zur Clientbereitschaft. Ein sofortiger Reload/Klick
bestand danach im Browser. Die Anwendung wurde aus derselben Agentenquelle neu erzeugt.

Die Browserautomatisierung konnte ein Feld mit `fill("")` nicht leeren; die Abnahme
verwendete deshalb echte Tastaturaktionen zur Leerstringeingabe. Browser-Erweiterungslogs
und ein Hydrationhinweis zu deren `data-oai-...`-Attributen sind Umgebungsbefunde,
keine unterdrückten Anwendungsfehler.

## Präzise Reichweite

Die Browserabnahme läuft auf der internen Preview mit echter lokaler D1-Persistenz.
Die private Produktionsbereitstellung verwendet eine separate, dauerhaft gehostete
D1-Datenbank; Preview-Testwerte werden nicht als Seeds übertragen. Auf der veröffentlichten
Seite schreibt der erste Klick auf Speichern den Anfangstext. Die erfolgreiche
Bereitstellung wurde durch den Hostingdienst bestätigt; eine Browserprüfung der
Produktions-URL wird nicht behauptet. Safari und Firefox wurden nicht eigens ausgeführt.

w1 ist ein spezifiziertes, getestetes Formularprofil. Der Compiler selbst, die React-
und Worker-Laufzeit sowie die Datenbank sind nicht formal bewiesen. Es gibt keine
A3-/A4-Zertifizierung. Freie Datenmodelle, Listen, Beziehungen, Querysprache,
mehrseitige Anwendungen, Benutzerkonten und die Verbindung zu P0-Businesslogik sind
weiterer Ausbau. Keiner dieser Punkte verhindert die hier geforderte Hello-/DB-Strecke.

## Nachweise

`evidence/web/spec-freeze.json`, `*-source.json`, `tests-final.xml`, `wheel-smoke.json`,
`generated-migration.sql`, `browser.json`, `browser.jpg` sowie `validation.json`
und `deployment.json` dokumentieren die ausgeführten Schritte.
