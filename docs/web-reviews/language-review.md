# Expertenvorschlag: Webprofil w1

Status: Entwurf, mit Compiler- und Securityexperten abgestimmt; noch keine Implementierung.

## Empfehlung

P0 bleibt als bestehender reiner, beweisbarer Rechenkern unverändert. Ein getrenntes
Webprofil `w1` beschreibt eine kleine vollständige Anwendung deklarativ: persistente
Textspeicher, explizite Serveraktionen und eine typisierte UI. Ein Compiler erzeugt
aus genau einer `.llapp`-Datei Datenbankschema, Serverregistrierung/API und Browsercode.
Es gibt keine eingebetteten JavaScript-, Python-, HTML- oder SQL-Fragmente.

Die erste Version ist eine Sprache für einfache persistente Formulare. Sie ist noch
keine allgemeine Websprache: keine beliebigen Queries, Listen, Beziehungen, Schleifen,
Nutzerkonten, P0-Aufrufe, Effekte in freien Ausdrücken oder frei programmierbare CSS-Regeln.
Diese Einschränkung ist eine klare Sprachgrenze und kein Beweis ihrer Erweiterbarkeit.

## Vollständiges Beispiel

```text
(app w1 hello_demo
  (store greeting (Text 4096))
  (action save_greeting (write greeting))
  (action load_greeting (read greeting))
  (page "/"
    (title "Unsere erste AI-Webanwendung")
    (input message "Neuer Text" (for greeting)
      (initial "Hello new AI World"))
    (button save "Speichern"
      (invoke save_greeting (input message))
      (into result))
    (button show "Anzeigen"
      (invoke load_greeting)
      (into result))
    (output result "Gespeicherter Text")))
```

`store` definiert einen dauerhaften optional vorhandenen skalaren Wert. Es gibt
keine DB-Defaults und keine Seeds. Vor dem ersten erfolgreichen Speichern liefert
Lesen `found:false`. Ein App-Neustart oder Browser-Reload verändert Werte niemals.

`read` und `write` sind explizite Datenbankeffekte, keine P0-Ausdrücke. Jede Aktion
besitzt genau einen Effekt auf genau einen deklarierten Speicher. Die öffentliche
API darf nur diese registrierten Aktionen adressieren; der Client wählt keine
Tabellennamen, SQL-Ausdrücke, Dateipfade oder sonstigen Serverfähigkeiten.

`input ... (for store)` übernimmt den Texttyp aus der Speicherdeklaration. Das
Inputwidget wird als Textarea erzeugt und durch sein eigenes `(initial "...")`
vorbelegt. Das ist reine UI-Initialisierung; weder DB-Write noch impliziter DB-Read.
Der Button `show` liest den tatsächlich gespeicherten Wert vom Server. Der Button
`save` schreibt den aktuellen Eingabewert und zeigt erst nach erfolgreichem Commit
die bestätigte Serverantwort an. Ein Fehler lässt die letzte bestätigte Ausgabe
unverändert und wird separat angezeigt. Erfolgreiches Speichern des Leerstrings ist
zulässig; der Client darf leere Werte nicht durch die Vorbelegung ersetzen. Ein
Read mit `found:false` löscht die bisherige Ausgabe für dieses Ziel und zeigt eine
separate Meldung über den fehlenden Wert. Kein UI-Fallback erfindet einen DB-Inhalt.

## Grammatik und Normalform

```ebnf
app        = "(" "app" "w1" identifier store+ action+ page ")" ;
store      = "(" "store" identifier text_type ")" ;
text_type  = "(" "Text" positive_integer ")" ;
action     = "(" "action" identifier "(" effect identifier ")" ")" ;
effect     = "read" | "write" ;
page       = "(" "page" "\"/\"" "(" "title" string ")" widget+ ")" ;
widget     = input | button | output ;
input      = "(" "input" identifier string "(" "for" identifier ")"
             "(" "initial" string ")" ")" ;
output     = "(" "output" identifier string ")" ;
button     = "(" "button" identifier string invoke "(" "into" identifier ")" ")" ;
invoke     = "(" "invoke" identifier [ "(" "input" identifier ")" ] ")" ;
identifier = lower_letter { lower_letter | digit | "_" } ;
```

Stringlexik folgt JSON-Strings: doppelte Anführungszeichen, definierte JSON-Escapes,
keine rohen Steuerzeichen. UTF-8 ist strikt, keine ungepaarten UTF-16-Surrogate,
kein U+0000. Ein gültiges escaped Surrogatpaar wird zu einem Unicode-Skalar dekodiert.
Insbesondere sind `<`, `>`, Anführungszeichen und nichtlateinische Zeichen normale
Textdaten. Sie werden nicht als HTML/Code interpretiert. Kommentare fehlen in w1.

Ein Textwert wird unverändert erhalten: kein trim, Unicode-Normalisieren oder
Zeilenumbruch-Ersetzen. `Text N` bedeutet höchstens N UTF-8-Bytes. Dieses Maß ist auf
Server und Browser identisch zu implementieren; JavaScript `.length` genügt nicht. Der Client verwendet
`new TextEncoder().encode(value).length`, SQL begrenzt
`length(CAST(value AS BLOB))` und Python `len(value.encode("utf-8"))`.
Die Browservalidierung verbessert die UX, die Servervalidierung entscheidet.
Native Textarea-Bedienung normalisiert CR/CRLF durch den Browser zu LF. Dieser
UI-Eingabevorgang wird nicht als byteerhaltender Transport vorhandener Daten
behauptet. API, Persistenz und Ausgabebindung ändern empfangene Textwerte nicht;
die direkte API-Abnahme prüft daher CR, LF und CRLF getrennt.

Kanonische Repräsentation: eine vollständig geklammerte Zeile ohne abschließenden
Newline, genau ein Leerzeichen zwischen Elementen. IDs und Ganzzahlen sind bereits
kanonisch; Strings werden mit JSON-Kodierung, `ensure_ascii=false` und minimalen
definierten Escapes serialisiert. Whitespace oder äquivalente String-Escapes ändern
den kanonischen Inhalt nicht. Deklarations- und Widgetreihenfolge bleibt erhalten;
keine Sortierung, da Widgetreihenfolge sichtbar ist. Der Compiler bietet `format`
oder ein kanonisches Feld seines Check-Ergebnisses; Roundtrip ist ein Prüfziel.

`source_hash` bindet mit SHA-256 die UTF-8-Bytes von `llapp-w1\0` plus kanonischem
Quelltext. Der Hash identifiziert den Build, nicht den dauerhaften Datenbanknamen.
Compiler-/Runtimeversionen und Zielprofile stehen zusätzlich im Buildmanifest.
Die Hashbindung allein ist weder Codebeweis noch Signatur.

## Bindungs- und Typregeln

1. App-ID und alle Namen sind 1–64 ASCII-Zeichen lang; erstes Zeichen a–z.
   Schlüsselwörter dürfen nicht als deklarierte IDs verwendet werden.
2. Speicher-IDs und Aktions-IDs sind jeweils eindeutig. Widget-IDs sind gemeinsam
   über input/button/output eindeutig. Separate Namensräume machen eine Speicher-ID
   `message` und eine Input-ID `message` ohne Schattenbindung möglich.
3. Deklarationen werden vor Bindungsprüfung gesammelt. Vorwärtsreferenzen sind
   erlaubt, unbekannte Namen und doppelte Deklarationen sind Fehler.
4. `read s` besitzt Signatur `() -> Option(Text(N_s))`. `write s` besitzt Signatur
   `(Text(N_s)) -> Text(N_s)` und liefert erst nach Commit den gespeicherten Wert.
5. Inputtyp ist `Text(N_s)` des in `for` genannten Speichers. Sein `initial` muss
   diesen Typ erfüllen. UI-Outputs sind reine Textziele ohne Eingabesemantik; ein
   optionales Leseergebnis wird als vorhanden/fehlend unterschieden.
6. Ein read-Aufruf hat kein Argument. Ein write-Aufruf hat genau eine Inputreferenz.
   Für `Text(N_input) -> Text(N_action)` muss `N_input <= N_action` gelten.
   Keine impliziten Konvertierungen oder freien Ausdrucksknoten sind erlaubt.
7. `into` referenziert ein deklariertes output-Widget. Ein Output darf Ergebnisse
   mehrerer Aktionen anzeigen. Textdarstellung geschieht über Textknoten/textContent.
8. Genau eine Seite mit Pfad `/` ist vorhanden. Titel und Labels sind Textliterale.
   Mindestens ein Input, ein read-Button und ein write-Button sind DoD-Anforderungen
   an die Beispiel-App, keine künstlichen universellen Sprachrestriktionen.
9. Statisch gültig bedeutet AST/Binder/Typen/Effektumfang gültig. Es ist kein P0-
   `proved`-Status. Webruntime, DB, Authentizität und Zielcode sind eigene Vertrauens-
   bzw. Prüfgrenzen. Erfolg heißt hier `compiled`, nicht `proved` oder `sealed`.

## Konkreter AST-Vertrag

Neue Typen gehören in eigene `web_*`-Module, nicht in `model.Expr` von P0. Alle
semantischen Datenklassen sind frozen; Listen werden als Tupel modelliert. Der
Parser erzeugt zunächst Formknoten mit Spans. Nach Bindungs-/Typprüfung entsteht:

```python
@dataclass(frozen=True)
class TextStore:
    name: str
    max_bytes: int

@dataclass(frozen=True)
class WebAction:
    name: str
    effect: Literal["read", "write"]
    store: str

@dataclass(frozen=True)
class TextInput:
    name: str
    label: str
    store: str
    initial: str

@dataclass(frozen=True)
class ActionButton:
    name: str
    label: str
    action: str
    input: str | None
    output: str

@dataclass(frozen=True)
class TextOutput:
    name: str
    label: str

type Widget = TextInput | ActionButton | TextOutput

@dataclass(frozen=True)
class WebPage:
    path: str  # always "/" in w1
    title: str
    widgets: tuple[Widget, ...]

@dataclass(frozen=True)
class WebApp:
    profile: Literal["w1"]
    name: str
    stores: tuple[TextStore, ...]
    actions: tuple[WebAction, ...]
    page: WebPage
```

Die Implementierung darf Referenzen intern zu Indizes auflösen. Semantik und
Canonicalisierung beruhen auf den deklarierten Namen und ihrer Reihenfolge.
Source-Spans sind diagnostische Metadaten und werden nicht in den semantischen
Hash aufgenommen. Ein öffentlich konstruierbares AST muss beim Compilerentrypoint
erneut validiert werden oder über einen klar internen typgeprüften Weg eintreten;
`frozen=True` allein ist keine Validitätsgarantie.

## Persistenz und Zielcodevertrag

Zielplattform nach Architekturabstimmung: Vinext, generierte React-TSX-Seite,
TypeScript-API-Routen im Cloudflare Worker, D1/SQLite und generiertes CSS. Vinext/Vite
übersetzen die Zielmodule anschließend in Browser-JavaScript/HTML bzw. Worker-Code.
Der Python-Compiler erzeugt diese Artefakte; die Demo-App wird nicht separat per Hand
in React implementiert. D1 speichert dauerhaft, nicht localStorage oder Workerspeicher.

Die DB-Implementierung verwendet eine interne
Wertetabelle mit zusammengesetztem Schlüssel `(app_id, store_id)`. Der SQL-Teil
der Kompilation sind benötigte Tabellen und Constraints, keine Initialdaten.
Der Compiler erzeugt `db/schema.ts` für Drizzle. `drizzle-kit generate` erzeugt
nachgelagert SQL-Migrationen mit Journal/Snapshot. Requests führen kein DDL aus. Der Compiler darf die tatsächliche DB-Arbeit einer geprüften gemeinsamen
Runtime übertragen; er muss nicht dieselbe CRUD-Logik für jeden Button neu erfinden.

Der sichtbare Compileroutput enthält mindestens: kanonischen Quelltext, typisierte
IR/Manifest, Drizzle-Schema, Serveraktionsregistrierung, UI-Modul und Hashes; die
nachgelagerte Drizzle-Migration gehört zum vollständigen Buildpaket.
Der Browser erhält weder DB-Schlüssel noch serverseitige Verbindungsdetails. Literale
werden ausschließlich sicher kodiert; Namen werden über validierte Generator-
Bindungen übertragen. Runtime-Textwerte werden nur als DB-Parameter gebunden.
Die Slot-API ist same-origin GET/PUT `/api/store/{slot}`. PUT akzeptiert exakt
`{"value":string}`, unbekannte Slots ergeben404. Read liefert eine diskriminierte
Antwort `{"found":false}` oder `{"found":true,"value":string}`. Der erzeugte Server
prüft, ob der Slot laut deklarierter Aktion überhaupt den HTTP-Effekt unterstützt.

Anwendungsidentität ist die explizite App-ID. Schema-/Typänderungen dürfen den alten
Bestand nicht stillschweigend löschen. Eine inkompatible Änderung gibt zunächst
einen klaren Migrationsfehler aus. Eine automatische allgemeine Migration ist nicht
Teil von w1. Schreibvorgänge sind atomar; für dieses skalare Beispiel gilt eine klar
dokumentierte Last-write-wins-Semantik bei gleichzeitigen Requests. Ein erfolgreicher
Write-Response bestätigt den eigenen Commit, nicht die Abwesenheit späterer Writes.

Keine Konten/Auth im Sprachprofil: Die Demo verwendet bewusst gemeinsame Slots für
alle autorisierten Besucher einer privat gehosteten Site. Es gibt keine behauptete
Nutzer- oder Mandantentrennung. Der Hostzugang und Same-Origin-Schutz begrenzen den
Zugang; sichere Cookies/Authentifizierung erfolgen durch die Hostingplattform.

## Grenzen und stabile Diagnosen

Quelltext max. 128 KiB, max. 4.096 AST-Knoten, Tiefe max. 32, max. 8 Speicher,
16 Aktionen, 64 Widgets. Textgrenze `N` liegt in 1..4.096. Literalgrenze max.
4.096 UTF-8-Bytes; Titel/Labels max. 256 Bytes. Ein Request darf höchstens 32 KiB
JSON enthalten (klarer tatsächlicher Wire-Limit, vor JSON-Parsing prüfen). Keine
Datei-/Netzwerkimports oder zyklischen Programmabhängigkeiten.

Diagnosen verwenden `{code, message, span:{start,end}, path?}` mit nullbasierten
Unicode-Skalaroffsets, halboffen `[start,end)`. Lexikfehler zeigen ihre Fundstelle;
semantische Fehler die zugehörige Referenz oder Deklaration. End-of-file ist ein
leerer Span. Fremde Toolausnahmen, SQL-Details und Secrets gehen nicht zum Client.

| Code | Bedeutung |
| --- | --- |
| W_LEX | UTF-8, Token oder String-Escape ungültig |
| W_PARSE | Knoten, Arity oder Deklarationsreihenfolge unzulässig |
| W_PROFILE | Unbekanntes Sprachprofil |
| W_NAME | Ungültiger/reservierter Bezeichner |
| W_DUPLICATE | Doppelte Deklaration im Namensraum |
| W_UNBOUND | Referenz existiert nicht |
| W_TYPE | Falsche Referenzart, Argumentzahl oder Textkapazität |
| W_LIMIT | Quellen-, AST-, Literal- oder Profilgrenze überschritten |
| W_INITIAL | UI-Vorbelegung passt nicht in deklarierten Texttyp |
| W_TARGET | Zielprofil unterstützt eine deklarierte Fähigkeit nicht |
| W_SCHEMA | Bestehendes DB-Schema ist inkompatibel; Migration erforderlich |

Runtime/API-Fehler getrennt: `INPUT_INVALID`, `SLOT_UNKNOWN`, `REQUEST_TOO_LARGE`,
`ORIGIN_REJECTED`, `STORAGE_UNAVAILABLE`. Compilerdiagnosen sind keine HTTP-Protokolle.

## Generalitätstest: zweite unabhängig deklarierte App

```text
(app w1 studio_notes
  (store announcement (Text 800))
  (store rehearsal_note (Text 1600))
  (action publish (write announcement))
  (action read_announcement (read announcement))
  (action save_note (write rehearsal_note))
  (action read_note (read rehearsal_note))
  (page "/"
    (title "Studio-Notizen")
    (input announcement_text "Ankündigung" (for announcement)
      (initial "Willkommen im Studio"))
    (button publish_button "Veröffentlichen"
      (invoke publish (input announcement_text)) (into announcement_view))
    (button announcement_button "Ankündigung laden"
      (invoke read_announcement) (into announcement_view))
    (output announcement_view "Aktuelle Ankündigung")
    (input note_text "Probennotiz" (for rehearsal_note)
      (initial "Nächste Probe: Freitag"))
    (button note_save "Notiz speichern"
      (invoke save_note (input note_text)) (into note_view))
    (button note_load "Notiz laden"
      (invoke read_note) (into note_view))
    (output note_view "Gespeicherte Notiz")))
```

Dieser Test darf keine Compiler- oder Runtimeänderung benötigen. Die zwei Speicher
müssen unabhängig funktionieren; die andere App-ID muss einen getrennten Bestand
erhalten. Eine andere Vorbelegung und andere IDs allein wären ein zu schwacher Nachweis
für einen allgemeinen Compiler. Zusätzliche Sicherheitsfälle: leere Strings, Emoji,
Zeilenumbrüche, Quotes, `</script><img src=x onerror=alert(1)>`, SQL-ähnliche Inhalte,
exaktes UTF-8-Limit und ein Byte darüber.

## Konkrete Risiken und Entscheidung

- Zu breites Zielprofil: beliebiges UI, relationale Queries und freie Effekte würden
  die erste Lieferung stark ausweiten. Empfehlung: w1 auf persistente Textformulare
  begrenzen und diese Grenze ausdrücklich dokumentieren.
- Nur ein JSON-Interpreter als Compiler verkauft: Empfehlung: echte Artefakte und
  Codegen-Schritte liefern, aber kleine gemeinsame Runtime für HTTP/DB/DOM behalten.
- Beweise überdehnen: P0-Zertifikate beweisen weder SQL-Transaktionen noch DOM-Verhalten.
  Empfehlung: getrennte Status/Assurance und beobachtbare Browser-/DB-Abnahme.
- Schemaänderungen überschreiben Daten: Empfehlung: keinerlei automatische Seeds
  und inkompatible Typänderungen blockieren, nicht automatisch Daten neu initialisieren.
- Clientzustand täuscht Persistenz vor: Abnahme muss einen neuen Browserkontext oder
  Reload plus echten Server-Read, idealerweise auch Serverneustart, umfassen. Der
  Client darf localStorage nicht als autoritative Datenbank verwenden.
- UI-Codeinjection durch Compilerliterale: AST-Literale nur sicher kodieren und an
  Textknoten binden. Keine dynamische HTML-Ausführung und keine HTML-Strings in DSL.

Empfohlene gemeinsame Entscheidung: w1 wie oben als kleinstes kohärentes Webprofil,
das heutige P0 unverändert und offen ausgewiesene Webruntime-Assurance durch TDD,
Typprüfung, Sicherheits-/Integrationstests und echte Browser-Abnahme.
