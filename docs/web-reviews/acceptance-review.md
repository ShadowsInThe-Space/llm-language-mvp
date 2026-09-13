# Unabhängiger Abnahme- und TDD-Review für den Webcompiler

Status: Expertenreview vor Implementierungsfreeze, 2026-09-08.

## Gemeinsame Abnahmebasis

Geprüft wurden `language-review.md`, `compiler-review.md` und
`security-review.md`. Maßgeblicher gemeinsamer Entwurf ist `w1`: begrenzte
persistente Textslots, benannte `read`-/`write`-Aktionen, deklarative UI,
Python-Compiler mit generierten Vinext-TSX-/API-/SQL-Artefakten, D1/SQLite.
Die alten Vorschläge `web0`, append-only/latest und Zeichenanzahl aus dem ersten
Compilerreview müssen vor Freeze als überholt gekennzeichnet oder ersetzt werden.

Der Mindestnachweis besteht aus einer agentengeschriebenen `.llapp`, ihrer
Kompilation ohne Handkorrekturen an erzeugten Dateien, einem tatsächlichen
Browserlauf und einer echten Datenbank. Ein Screenshot einer statischen Seite
oder ein erfolgreicher POST mit Antwort-Echo genügt nicht.

Das Webprofil liefert `compiled` und Testergebnisse. Es übernimmt nicht den
P0-Status `proved`. P0 bleibt unverändert und wird als Regression mitgeprüft.

## Technische Entscheidungen vor Freeze

1. Exakte Import- und Rückgabetypen der Parser-/Check-/Compile-API festlegen,
   damit unabhängige Tests denselben öffentlichen Vertrag verwenden.
2. Compilerpfade und Besitzgrenzen festlegen: welche Dateien generiert werden,
   welche Hostdateien außerhalb des Compilers liegen und wie `verify-build`
   beziehungsweise erneute Bytekompilation Veränderungen erkennt.
3. Exakte HTTP-Routen, Methoden, Erfolgs-/Fehlerschemas und Statuscodes festlegen.
   Unbekannte Aktionsnamen dürfen keinen dynamischen SQL-/Dateizugriff erzeugen.
4. Text bleibt eine Folge von Unicode-Skalarwerten ohne NUL, begrenzt in
   UTF-8-Bytes. Leerstring ist gültig. Keine Normalisierung oder Trimmung.
   HTML `input type=text` erhält Zeilenumbrüche nicht; ein `textarea` ist der
   passende erste Generator für ein allgemeines w1-Textinput. Direkter API-Roundtrip
   muss auch CR, LF und CRLF bytegetreu erhalten; die UI darf keine umfassendere
   Eingabefähigkeit behaupten, als ihre Browserkontrolle bietet.
5. Migration/Initialisierung muss bei erneutem Start vorhandene Werte erhalten.
   Geänderter Default darf kein vorhandenes Slot überschreiben. Inkompatible
   Typänderung muss den dokumentierten Migrationsfehler liefern.
6. Die Hostingplattform muss HTML und API gemeinsam schützen. Der Lead prüft
   den tatsächlichen Hostzugang und mögliche direkte Worker-Origins. Für lokale
   Tests ist die fehlende Hostingauthentisierung eine benannte Testgrenze.

## Definition of Done als beobachtbares Verhalten

| ID | Handlung | Erforderlicher Nachweis |
| --- | --- | --- |
| D01 | Agent schreibt Hello-App nur in `.llapp` | Quellartefakt, Agentenauftrag, Quellhash |
| D02 | Compiler erzeugt Zielmodule | Manifest plus ausführbare TSX-, API-, SQL-Artefakte |
| D03 | Browser öffnet erzeugte Seite | Tatsächliche URL, Browserengine/-version, Screenshot |
| D04 | Anzeigen-Button liest den initialen Wert | `Hello new AI World` aus dem DB-Lesepfad |
| D05 | Nutzer speichert eigenen eindeutigen Wert | Erst erfolgreicher Commit führt zur Erfolgsanzeige |
| D06 | Seite wird neu geladen, Input wird absichtlich verändert, dann Anzeigen gedrückt | Ausgabe ist der gespeicherte Wert, weder Input noch Default |
| D07 | Neue Browsersitzung lädt denselben Wert | Persistenz liegt nicht in localStorage oder DOM |
| D08 | Runtime wird neugestartet oder gleiche App mit gleicher DB neu veröffentlicht | Danach liest neuer Prozess denselben eigenen Wert |
| D09 | Unicode und gespeicherter XSS-Text werden angezeigt | Exakter Text, kein erzeugtes HTML/Script und keine Ausführung |
| D10 | Zweite unterschiedlich strukturierte App wird kompiliert | Zwei unabhängige Slots funktionieren ohne Compileränderung |
| D11 | Fehler- und Grenzfälle werden ausgeführt | Ablehnung verändert gespeicherten Zustand nicht |
| D12 | Alle verwendeten Qualitätstore laufen | P0-/Compiler-/Runtime-Tests, Ruff, mypy, Target-Typecheck und Build |

Für D08 ist ein Reload kein Serverneustart. Bei Cloudflare ersetzt ein dokumentiertes
erneutes Deployment auf dieselbe D1-Bindung den kontrollierten Prozessneustart.
Falls dieser Schritt technisch nicht möglich ist, wird D08 ausdrücklich offen
ausgewiesen; ein lokaler SQLite-Neustart darf nicht als D1-Neustart bezeichnet werden.

## TDD-Reihenfolge und unabhängige Orakel

Jeder neue Teil beginnt mit einem fehlenden Verhalten als RED-Test. GREEN darf
zunächst die kleinste passende Implementierung sein; Refactoring erhält dieselben
Verhaltenstests. Nicht jeder Grenzfall benötigt einen separat protokollierten
RED-Zyklus, aber Compiler, Runtime und Browserpfad benötigen jeweils einen echten
anfänglichen Fehlschlag. Bugs beginnen mit dem reproduzierenden Negativfall.

1. Öffentliche `parse/check`-API: gültige Quelle, stabile Diagnose und Bindungsfehler.
2. Kanonische Normalform: parserunabhängig ausgewählte Äquivalenzpaare und geänderte
   sichtbare Texte; Propertytests für gültige Strings und Whitespacevarianten.
3. Codegenerierung: zwei unabhängige Programme, syntaktisch ausführbarer Zielcode,
   neu erzeugtes Schema und echte Zielruntime.
4. API-/Datenbankintegration: realer Dateispeicher oder D1, kein bloßes Mock für
   Persistenz; Mockfehler ausschließlich für gezielte DB-/Netzwerkausfälle.
5. Browser: Kompilation der echten Beispielquelle, Build/Start, bediente Buttons,
   DB-Wert nach Reload und neuer Instanz.
6. Bestehendes P0 und Gesamtqualitätstore als Abschlussregression.

Tests dürfen nicht nur erwarten, was dieselbe Generierungsfunktion ausgerechnet
hat. Textwerte, erwartete Routen/Bindings und semantische Varianten werden im Test
aus dem dokumentierten Sprachvertrag bestimmt. Zielcode darf weder auswendig als
ganzer Snapshot erwartet noch für Tests nachträglich gepatcht werden.

## Compiler- und Sprachtests

| ID | Testfall | Erwartung |
| --- | --- | --- |
| C01 | Gültige Ein-Slot-App; andere Namen und Labels | Geprüfte Bindungen stimmen mit Quelle überein |
| C02 | Forwardreferenzen auf deklarierte Aktionen/Outputs | Wie eingefrorene Grammatik erlaubt akzeptiert |
| C03 | Gleichnamige Store- und Input-ID in getrennten Namensräumen | Keine versehentliche Schattenbindung |
| C04 | Doppelte Store-/Action-ID oder gemeinsame Widget-ID | `W_DUPLICATE`, brauchbarer Span |
| C05 | Unbekannter Store/Input/Output/Action | `W_UNBOUND`, Referenzspan |
| C06 | `into` zeigt auf Input oder Button | `W_TYPE` |
| C07 | Read mit Argument; Write ohne/zwei Argumenten | Festgelegter Parse-/Typfehler |
| C08 | Input Text(9) an Write Text(8), auch wenn Default kurz | `W_TYPE`, kein wertabhängiges Durchwinken |
| C09 | Input Text(8) an Write Text(9) | Akzeptiert |
| C10 | Default exakt auf UTF-8-Limit; ein Byte darüber | Akzeptiert beziehungsweise `W_DEFAULT` |
| C11 | Profil, freie Form, Hostcode-, Query- oder HTML-Einschub unbekannt | Ablehnung, keine Ausführung/Best-Effort-Ausgabe |
| C12 | Schlechte Escapes, rohe Controls, Surrogatrest, NUL, kaputtes UTF-8 | Lexik-/Textfehler ohne Pythontraceback |
| C13 | Gültiges Surrogatpaar versus direkter Emoji | Gleiche kanonische Quelle und Hash |
| C14 | Whitespace und äquivalente JSON-Escapes | Bytegleicher Build bei gleichem Ziel/Version |
| C15 | Widgetreihenfolge oder sichtbarer Text geändert | Andere semantische Ausgabe und Quellhash |
| C16 | Titel/Label mit Quotes, Backticks, Dollarzeichen, `</script>` | Gültiger Zielcode; nur sichtbare Textdaten |
| C17 | Reservierte/zu lange Namen, `../`, Slash, Bindestrich, Unicode-ID | Dokumentierte Namensfehler |
| C18 | Größenlimits jeweils exakt/knapp überschritten | Begrenzte Verarbeitung, stabile Limitdiagnose |
| C19 | Klammernfehler am EOF hinter Emoji | Span zählt Unicode-Skalare, EOF leerer Span |
| C20 | Ungültige Quelle bei bestehendem Buildverzeichnis | Kein gemischter oder teilweise überschriebener Build |
| C21 | Ausgabeziel mit Symlink in besessenem Pfad | Kein Schreiben außerhalb des vorgesehenen Ziels |
| C22 | Ein generiertes Artefakt fehlt/ist geändert | Buildprüfung meldet Abweichung |

Grenzen werden gezielt geprüft: Quelle 128 KiB, Tiefe 32, 4096 AST-Knoten,
acht Stores, 16 Aktionen, 64 Widgets, Textkapazität 1..4096, IDs 1..64 Zeichen,
Titel/Labels 256 UTF-8-Bytes. Tests sollen die relevanten Grenzen isolieren statt
versehentlich vorher an einer anderen Grenze zu scheitern.

## Generalität als Schutz vor einer fest eingebauten Demo

Die unabhängige zweite Quelle heißt beispielsweise `studio_notes`, hat zwei
unterschiedlich große Stores, vier Aktionen, zwei Inputs und zwei Outputs. Die
Widgetreihenfolge unterscheidet sich sichtbar von Hello. Beide Slots werden mit
unterschiedlichen Texten beschrieben; Laden eines Slots darf den anderen nicht
ändern. Es gibt kein Literal `Hello new AI World` in dieser Quelle.

Zusätzlich werden zwei App-IDs mit gleichem Store-Namen in derselben Testdatenbank
verwendet. Speicherung in A darf B nicht ändern. Derselbe Appname mit neuem Label
und Default behält hingegen den bestehenden Wert. Diese Tests prüfen die
festgelegte Identität `(app_id, store_id)` und verhindern Hash-bedingten Datenverlust.

Alle Schritte verwenden denselben Compilerbinary-/Quellstand und dieselbe Runtime.
Ein Generator mit `if app_name == hello_demo` wäre ein Abnahmefehler. Der zweite
Build muss nicht parallel öffentlich gehostet werden; seine erzeugte Runtime muss
jedoch gegen echte SQLite-/D1-Semantik ausgeführt werden.

## Runtime-, DB- und Securitytests

| ID | Testfall | Erwartung |
| --- | --- | --- |
| R01 | Save A, Save B, Load | B; kein append-only/Default-Fallback |
| R02 | Save Leerstring, Load, Neustart, Load | Stets vorhandener Leerstring |
| R03 | ` ä é 😀 العربية \" ' \\ ` mit führenden/folgenden Leerzeichen | Exakte Unicodefolge und UTF-8-Bytes |
| R04 | CR, LF und CRLF per API | Keine stillschweigende Normalisierung |
| R05 | 4096 ASCII-Bytes und 1024 vierbyteige Emoji | Akzeptiert; jeweilige Überschreitung abgelehnt |
| R06 | NUL/unpaariger Surrogat; falscher Werttyp; unbekanntes Feld | Ablehnung ohne Mutation |
| R07 | Duplicate JSON-Key, auch escaped äquivalent `text`/`te\\u0078t` | Ablehnung, nicht last-key-wins |
| R08 | Body >32768 Bytes ohne oder mit falschem Content-Length | 413 vor unbeschränktem Parsing |
| R09 | Kleine dekodierte Nutzlast, aber zu großer escaped Wirebody | Wirelimit entscheidet separat |
| R10 | Fremde/fehlende/`null` Origin, Subdomain-/Suffixtrick | 403 ohne Mutation |
| R11 | Falscher Medientyp, Methode oder unbekannte Aktion | Richtiger Fehler, kein CORS-/SQL-Fallback |
| R12 | SQL-Payload als Text und anschließend normales Schreiben | Exakter Roundtrip; Schema bleibt intakt |
| R13 | Fehlende DB/DB-Ausnahme | 503; kein erfolgreicher erfundener Default |
| R14 | Wiederholte Migration/Initialisierung nach eigenem Write | Eigener Wert erhalten |
| R15 | Änderung der Textkapazität bei vorhandenem Schema | Migrationsfehler, kein stiller Reset |
| R16 | Zwei gleichzeitige vollständige Writes | Einer der ganzen Werte bleibt, kein Mischzustand |
| R17 | Load nach abgeschlossenem Write ohne weiteren Writer | Geschriebener Wert, kein Cache |
| R18 | Browser-URL/API ohne Hostautorisierung | Keine privaten Texte über alternative Route zugänglich |

Nach jeder negativen schreibenden Anfrage liest ein gesonderter gültiger Request
den zuvor gespeicherten Kontrollwert. Ein HTTP-Fehlerstatus allein belegt keine
unterbliebene Datenbankänderung. Datenbanktests prüfen nach Möglichkeit zusätzlich
die Constraints mit direktem SQL, ohne den API-Validator zu verwenden.

## Browserablauf und Evidenz

1. Die Agentenquelle wird eingefroren, kompiliert und nur ihr Zieloutput gebaut.
2. Browser auf tatsächliche App-URL öffnen; Konsolen-/Netzwerkfehler beobachten.
3. Default laden und separat speichern. Danach einen einzigartigen eigenen Text
   mit Emoji und kombinierendem Zeichen speichern.
4. Reload, Input auf einen anderen ungespeicherten Text setzen, Laden drücken.
   Die Ausgabe muss exakt dem vorher gespeicherten Text entsprechen.
5. Neue Browsersitzung und erneutes Runtime-Deployment/Neustart auf derselben DB;
   erneut laden. DB-Umgebung und Reihenfolge im Protokoll vermerken.
6. XSS-String speichern und nach Reload laden. `textContent` muss exakt stimmen;
   es dürfen keine entsprechenden `img`-/`script`-Knoten oder Dialoge entstehen.
7. DB-/Netzwerkfehler kontrolliert auslösen: letzte bestätigte Ausgabe und Eingabe
   bleiben erhalten, kein falscher Erfolgsstatus. Die Anwendung behauptet bei
   einem nach möglichem Commit abgebrochenen Request keinen sicheren Nicht-Commit.
8. Am Ende sicheren sichtbaren Text setzen, erneut aus DB laden, Screenshot
   aufnehmen. XSS-Testpayload nicht als verwirrenden finalen Demostand belassen.

Primäre DoD ist tatsächlich verfügbares Chrome/Chromium. Firefox/WebKit werden
nur genannt, wenn sie wirklich gelaufen sind. Ein erfolgreicher Chromiumtest ist
kein Nachweis für alle jemals veröffentlichten Browser.

Der Abnahmebericht enthält Zeit, geprüften Quell-/Compilerstand, Manifesthash,
tatsächliche Kommandos/Exitcodes, Testzahlen, Browserengine/-version, App-URL,
DB-Umgebung, Persistenzschritte und echte Screenshots. API-Schlüssel, Cookies und
Hostingtokens werden nicht erfasst. Agentenprovenienz ist ein Arbeitsprotokoll,
keine kryptographische Urheberschaftsattestation.

## Freigabeempfehlung

Nach Fixierung der oben genannten öffentlichen Schnittstellen ist der Plan
implementierbar. Besonderes Augenmerk gilt dem UTF-8-Textvertrag, echter Persistenz
über einen neuen Runtimezustand, der zweistrukturierten Generalitätsprobe und der
Trennung von P0-Beweisen und Webtest-Assurance. Zusätzliche Sprachfeatures sind für
die aktuelle DoD nicht erforderlich.
