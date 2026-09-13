# Web-Compiler MVP: Security- und Datenbankreview

Stand: 2026-09-08. Phase 1 abgeschlossen: mit Lead und Sprachexperten abgestimmte Regeln vor Implementierung.

## Festgelegtes Ziel

Ein vollständig aus unserer Sprache erzeugtes Webprogramm speichert einen Text in
einer echten Datenbank und liest ihn auf ausdrücklichen Button-Klick wieder aus.
Der Text bleibt nach Browser-Reload und neuer Browsersitzung erhalten. Das Profil `w1` erlaubt maximal acht deklarierte Textslots mit festem
serverseitigem Namensmapping; die Demo nutzt einen Slot. Speichern ersetzt dessen aktuellen Wert; mehrere gleichzeitige Schreibzugriffe gelten
in Datenbank-Reihenfolge, der zuletzt erfolgreich geschriebene Wert bleibt erhalten.
Eine Historie, Kontenverwaltung und frei wählbare Datensatz-IDs gehören nicht zum MVP.

Vom Lead festgelegte Plattform: privates Sites-Hosting, erzeugte Vinext-React-Seite
mit TypeScript-API-Route in einem Cloudflare Worker und D1/SQLite. Compiler in Python.
Die reine Datenbanksemantik gilt ebenso im lokalen SQLite-Testadapter.
Hostingkonfiguration ist vertrauenswürdige Deployment-Eingabe,
der Anwendungstext darf keine eigenen Server- oder Datenbankziele festlegen.

## Assurance-Grenze

Die vorhandenen P0-Beweise betreffen reine Bool-/Integerfunktionen im P0-Modell.
Strings, DOM, HTTP, Datenbank und Codegenerierung sind neue Komponenten. Erfolgreiche
P0-Prüfung beweist weder dieses Backend noch browserübergreifende Darstellung.
Das Webprofil braucht statische Prüfungen, Generator- und Laufzeittests sowie
End-to-End-Abnahme. Es darf kein A3/A4- oder vollständiges Sicherheitsbeweissiegel
ausgeben. Ein Quell-/Artefakthash belegt Zuordnung, keine semantische Korrektheit.

## Textvertrag

Mit dem Sprachexperten abgestimmte Definition für `Text(N)` in `w1`, `1 <= N <= 4096`:

- Folge von Unicode-Skalarwerten ohne U+0000; leere Zeichenfolge ist zulässig.
- Keine stillschweigende Normalisierung, Trimmung, HTML-Bereinigung oder Ersetzung.
  Kombinierende Zeichen, Emoji, Anführungszeichen, Backslashes und RTL-Text bleiben
  exakt erhalten. Nicht gepaarte UTF-16-Surrogate werden zurückgewiesen.
- Höchstens N UTF-8-Bytes nach JSON-Dekodierung, absolut maximal 4096. Das ist keine Anzahl von
  UTF-16-Codeeinheiten, sichtbaren Zeichen oder Graphemen.
- HTTP-Requestbody maximal 32768 Bytes; diese Grenze umfasst auch JSON-Escapes.
  Limit beim Lesen des Streams erzwingen, nicht nur `Content-Length` vertrauen.
- Browser und Server validieren identisch. Servervalidierung entscheidet; ein
  Browserattribut wie `maxlength` ersetzt die UTF-8-Prüfung nicht.
- API erwartet genau `{ "value": <Text> }`; Arrays, `null`, Zahlen, weitere Felder
  und mehrfach angegebene Schlüssel werden zurückgewiesen. Keine Typumwandlung.
- Eine erfolgreiche Speicherung darf erst nach erfolgreicher DB-Operation angezeigt
  werden. Gespeicherter Wert wird beim Laden aus der DB gelesen, nicht aus DOM,
  localStorage, einem Antwort-Echo oder dem voreingestellten Begrüßungstext.

Für das DB-Schema spiegeln `NOT NULL`, festgelegter Typ und ein Byte-Limit die
wesentlichen invarianten Grenzen. `length(CAST(value AS BLOB)) <= N` prüft die
Byte-Länge; serverseitige Scalar-/NUL-Prüfung bleibt zusätzlich erforderlich.

## Compilergrenzen: Text bleibt Daten

- Die Sprache enthält keine Hostcode-Einschübe, `eval`, freien SQL-Text oder HTML.
- Compiler erzeugt nur bekannte Formen aus vollständig validiertem AST. Unbekannte
  Formen, doppelte Definitionen und falsche Referenzen führen zu Fehlern, nicht zu
  kommentarloser Auslassung oder Best-Effort-Ausgabe.
- Namen sind auf eine dokumentierte ASCII-Identifiergrammatik mit Längenlimit
  begrenzt. Maximal 64 ASCII-Zeichen pro Namen. SQL-/JS-Namen entstehen durch eindeutiges, reserviertes Namensmapping;
  aus dem Browser kommende Feld-/Tabellennamen werden nie als SQL-Identifier genutzt.
- Quelltextliterale werden mit dem Serializer des jeweiligen Zielkontexts erzeugt.
  Insbesondere niemals Texte in JavaScript-Template-Literale, HTML-Attribute oder
  SQL-Literale einkleben. Browserkonfiguration steht in externem JSON oder wird mit
  einem explizit script-sicheren JSON-Verfahren übertragen.
- Generierte Ausgabe hat eine feste Dateiliste unter dem Outputverzeichnis.
  Quelltextnamen sind keine Dateipfade. `../`, absolute Pfade und Symlinkausbrüche
  dürfen keine Dateien außerhalb dieses Verzeichnisses erzeugen oder ersetzen.
- Quelltext maximal 128 KiB, 4096 AST-Knoten, Tiefe 32, acht Slots,
  16 Aktionen und 64 Widgets; keine unbeschränkte Vorverarbeitung oder vom Quelltext ausgehenden Netzwerkzugriffe.

## DOM und XSS

Textausgabe erfolgt ausschließlich als React-Textkind (entspricht DOM-Textknoten).
Eingabewerte werden als React-Stringwerte an Formelemente gebunden.
`dangerouslySetInnerHTML` ist ebenfalls ausgeschlossen. Kein `innerHTML`, `outerHTML`,
`insertAdjacentHTML` oder dynamischer Eventhandlertext. So werden auch gespeicherte
Angriffsstrings als Text dargestellt. MDN dokumentiert HTML-Injektionssinks als
XSS-Risiko: [innerHTML](https://developer.mozilla.org/en-US/docs/Web/API/Element/innerHTML).

Statische HTML-Struktur entsteht aus festen Tags und Attributen des Compilers.
CSP muss nach Inspektion des Vinext-Produktionsbundles definiert werden, insbesondere
für Framework-Hydration/Inline-Skripte. Wenn nötig Nonces/Hashes verwenden. Die
Abnahme darf keine wirksame CSP behaupten, bevor die produktive Seite samt Hydration
unter der tatsächlichen Richtlinie funktioniert. Mindestens keine selbst erzeugten
Inline-Handler oder `eval`, außerdem `object-src 'none'`, `base-uri 'none'` und
`form-action 'self'`, soweit kompatibel mit bestätigtem Hosting. Framing-Regeln
müssen zur privaten Hosting-/Preview-Einbettung passen; keine ungeprüfte Annahme
über benötigte Host-Domains. API und Dokumente liefern
korrekte Content-Types plus `X-Content-Type-Options: nosniff`.

## API, Origin und private Hosting-Grenze

- API und Frontend laufen unter derselben Origin. Generierter Browsercode verwendet
  feste relative API-Pfade; keine URL aus Textfeld oder Datenbank.
- Lesen ist nebenwirkungsfrei. Schreiben ist ausschließlich PUT mit
  `Content-Type: application/json` (optional gültiger UTF-8-Charset-Angabe).
- Schreibzugriffe erfordern `Origin == request URL origin` beziehungsweise die
  explizit konfigurierte externe Origin bei einem bestätigten Proxy. Fehlende,
  `null` oder fremde Origin wird mit 403 zurückgewiesen; kein Suffix-/Substringtest.
- Keine CORS-Freigabe für fremde Origins, kein `Access-Control-Allow-Origin: *`.
  Unerwartete Methoden erhalten 405. GET-Requests dürfen nie speichern.
- Origin ist CSRF-Schutz für Browserzugriffe, keine Nutzeridentität und kein Ersatz
  für Zugriffsschutz. Browser schicken Origin üblicherweise bei gleichursprünglichen
  PUT-Requests: [MDN Origin](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Origin).
- Die App hat im MVP keine Mandantentrennung. Alle berechtigten Besucher dieser
  privaten Site teilen denselben Bestand deklarierter Textslots; dies muss in der Dokumentation stehen.
- Der Lead hat owner-only private Sites als Plattform-Zugangsgrenze festgelegt.
  Kein eigenes Login, keine UserRecords, kein vom Client gelieferter Auth-Header,
  kein selbst gebauter Preview-Bypass. Lokale Vorschau hat keine SIWC-Anmeldung und
  wird nicht als veröffentlichte Zugriffskontrolle ausgegeben.
- Private Veröffentlichung muss HTML und API gleichermaßen schützen. Eine aus
  ausgeloggtem Kontext direkt erreichbare API wäre ein Abnahmefehler. Geschützte
  Vorschau und etwaiger öffentlicher Workerursprung dürfen keinen Bypass bilden.
- D1-Bindings und Secrets existieren nur im Serverprozess. Kein Secret erscheint in
  Browserbundle, Manifest, Fehlermeldung, Screenshot oder erzeugtem Quelltext.

## Datenbank und Persistenz

Ein einzelner atomischer `INSERT ... ON CONFLICT ... DO UPDATE` pro Speicherung,
mit dem statisch zugeordneten Slotschlüssel und gebundenem Textparameter, genügt.
Ein vom Browser übermittelter Actionname wird ausschließlich in einer statischen
Allowlist nachgeschlagen; er bestimmt nie selbst SQL-Identifier oder freie SQL-Texte. Keine vorherige
Leseentscheidung, keine mehrteilige Read-Modify-Write-Transaktion. UI deaktiviert
den Save-Button während einer laufenden Speicherung; der Server bleibt auch bei
direkt gesendeten parallelen Requests korrekt. Es wird keine Änderungshistorie
versprochen. Erneutes Speichern desselben Textes hat denselben Endzustand.

SQL wird aus compilerkontrollierten Templates erstellt. Werte werden ausschließlich
gebunden. Cloudflare empfiehlt vorbereitete Statements mit `bind()` zur Trennung
von Daten und SQL: [D1 prepared statements](https://developers.cloudflare.com/d1/worker-api/prepared-statements/).

Der deklarierte Default `Hello new AI World` belegt ausschließlich das Eingabefeld
vor. Es gibt keinen DB-Seed. GET vor dem ersten Speichern liefert `found: false`;
die Oberfläche muss den leeren DB-Zustand anzeigen. Erst Save persistiert den Text.
Unbekannte Slots liefern 404. Es gibt keinen Begrüßungsfallback bei DB-Fehlern.
Laden nach bestätigtem Speichern liest den geschriebenen Wert, sofern seitdem kein
anderer Zugriff geschrieben hat. Für D1 ohne Sessions gehen Abfragen laut offizieller
Dokumentation an die Primärdatenbank. Im MVP keine Read-Replica-Konfiguration oder
ungebundene Sessions hinzufügen: [D1 read replication](https://developers.cloudflare.com/d1/best-practices/read-replication/).

API-Antworten erhalten `Cache-Control: no-store`; Browser lädt ebenfalls ohne Cache.
Eine lokale DB-Datei gehört in ein persistentes Runtime-Datenverzeichnis, niemals
in einen bei Kompilierung ausgetauschten Buildordner. Cloudflare-D1-Bindung bleibt
bei neuer Veröffentlichung dieselbe, solange keine explizite neue Umgebung erzeugt
wird. Lokale und veröffentlichte Datenbanken werden klar unterschieden.

## Schema und Fehler

- Compiler erzeugt Drizzle-Schema in `db/schema.ts`; Deployment erzeugt/wendet die
  geprüfte Migration an. Keine CREATE-/ALTER-/Seed-Operation im Requestpfad.
- Erste Migration besitzt festen Namen, Version und Hash. Das Deploymentmanifest
  bindet Quellhash, Compilerversion, Schemafassung und generierte Artefakte.
- Angewandte Migrationen sind unveränderlich; keine automatischen DROP-/RESET-Befehle.
  Versionswechsel erzeugen eine neue explizite Migration. Für den MVP genügt v1;
  ein inkompatibles vorhandenes Schema wird erkannt und als Fehler gemeldet.
- Migrationsausführung vor Annahme von API-Schreibzugriffen. Wiederanwendung
  überschreibt keinen bereits gespeicherten Text.
- DB-Ausfall oder fehlende Bindung liefert 503 mit stabilem maschinenlesbarem Code,
  kein 200 mit erfundenem Begrüßungstext. SQL, Stacktrace und Bindingnamen bleiben
  interne Diagnosen ohne vom Nutzer eingegebenen Text.
- Validierungsfehler 400/422, zu großer Request 413, falscher Medientyp 415,
  verbotene Origin 403 und unbekannte Route 404. Der gemeinsame API-Vertrag legt
  die genaue Zuordnung endgültig fest.
- UI zeigt Fehler, bewahrt die Eingabe und zeigt keinen falschen Speichernachweis.
  Bei Netzwerkabbruch nach möglichem Commit darf sie nur „Ergebnis unklar; erneut
  laden“ beziehungsweise eine entsprechende neutrale Fehlermeldung anzeigen.

## Verbindliche Tests für die Freigabe

| Bereich | Positiver oder negativer Test | Erwartung |
|---|---|---|
| Persistenz | Erstes GET bei leerer DB | `found: false`, kein Default-Fallback |
| Persistenz | Vorbelegtes `Hello new AI World` speichern, danach laden | Wert stammt aus DB |
| Persistenz | Eigenen eindeutigen Text speichern, Seite neu laden, Load drücken | Exakter gespeicherter Text |
| Persistenz | Server/Worker neu starten bzw. neu veröffentlichen ohne DB-Neuanlage | Wert bleibt erhalten |
| Unicode | Emoji, kombinierende Zeichen, RTL, Quotes, Backslashes, leere Zeichenfolge | Exakter Roundtrip |
| Grenzen | 4096 und 4097 UTF-8-Bytes, mehrbyteige Grenzfälle | Grenze akzeptiert, Überschreitung abgewiesen |
| Decoder | Ungepaarte Surrogate, NUL, kaputtes JSON, falscher Typ, Zusatz-/Doppelfeld | Keine DB-Änderung, stabile Diagnose |
| Bodygröße | Gestreamter Body über 32768 ohne Content-Length | 413, begrenzte Verarbeitung |
| Stored XSS | `<img src=x onerror=...>`, `</script><script>...</script>` | Exakter Text, keine Elementerzeugung oder Ausführung |
| SQL | `'); DROP TABLE ...; --` speichern und laden | Text erhalten, Schema und Folgeschreiben intakt |
| CSRF | Fremde, fehlende und `null` Origin; falscher Medientyp; GET speichern | Abgewiesen, alter Wert unverändert |
| Fehler | DB-Bindung fehlt, SQL-Operation wirft Fehler, Netzwerkausfall | Kein Erfolgsfeedback, keine internen Informationen |
| Parallelität | Zwei gleichzeitige gültige Saves | Ganzer Wert A oder B, keine Mischdaten, DB konsistent |
| Zugriff | Privaten HTML- und API-Endpunkt ohne berechtigte Sitzung abrufen | Kein Appinhalt oder gespeicherter Text zugänglich |
| Compiler | Unbekannte AST-Form, Referenzfehler, bösartige Literale und Pfadnamen | Fehler oder sichere datengetreue Ausgabe |
| Migration | Schema-/Deployvorgang erneut ausführen nach eigener Speicherung | Eigener Wert bleibt bestehen |
| Browser | Chromium/Chrome sowie verfügbare Firefox/WebKit-Engines | Gleicher Save-Reload-Load-Roundtrip; Engines genau benennen |

Die Abnahme protokolliert Kommandos, tatsächliche Ergebnisse und Browsernamen,
Quell-/Artefakthashes, DB-Umgebung und Screenshot des nach Reload aus der DB geladenen
eigenen Wertes. Nicht verfügbare Browser werden nicht als getestet bezeichnet.
Der Experte verlangt keinen zusätzlichen Loginbau, keine Historie und kein ORM für
diesen MVP; die bestätigte private Hosting-Grenze ist die vorgesehene Zugangskontrolle.
