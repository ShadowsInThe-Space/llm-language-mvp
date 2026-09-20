# A1 — Begrenzte Listen und deterministischer Text (normativ)

Dieses Dokument definiert den reinen A1-Wertumfang von Issue #20 auf der
M2-Basis. **MUSS**, **DARF NICHT**, **SOLL** und **DARF** sind normativ. Die
Signaturen und Repräsentationen in diesem Dokument beschreiben die Semantik,
nicht zusätzliche Parser-Syntax. Ein Frontend darf eine andere Quellsyntax
anbieten, muss aber auf genau diese Werte und Operationen kanonisieren.

## 1. Geltung und Vorrang

`List<T,N>` ist die normative Bezeichnung. Die frühere Planungsbezeichnung
`Seq<T,N>` ist kein zweiter Typ und darf weder eine abweichende Kapazitäts- noch
eine abweichende Reihenfolgensemantik einführen. M2-Implementierungen müssen
historische P0-, w1-, w2- und pkg1-Quellen unverändert akzeptieren; dieses
Profil wird nur durch eine explizite A1-Deklaration aktiviert.

Für A1-`Text<N>` gilt die bereits eingefrorene M0-Regel „keine Normalisierung,
kein implizites trim, UTF-8-Bytegrenze“. Die allgemeinere frühe
Syntax-Skizze in `specs/01-CANONICAL-SYNTAX.md`, die NFC für Stringliterale
nennt, wird für A1-Text ausdrücklich überschrieben. Ein Textwert darf durch
Kanonisierung nicht in einen semantisch anderen Unicode-Wert geändert werden.

`Option<T>` und `Result<T,E>` sind die allgemeinen algebraischen Typen aus
Issue #17. A1 fügt dafür keine Compiler-Sonderfälle hinzu:

```text
Option<T> = None(Unit) | Some(T)
Result<T,E> = Ok(T) | Err(E)
CapacityError = CapacityExceeded
```

Die Konstruktoren sind disjunkt, Matches sind vollständig, und `CapacityError`
ist ein normaler, explizit behandelbarer Fehlerwert.

## 2. `List<T,N>`

### 2.1 Typ und Werte

`N` ist ein nichtnegativer, zur Spezialisierungszeit bekannter `Nat`-Wert. Ein
negativer, dynamischer, nicht ganzzahliger oder nicht auswertbarer
Kapazitätsparameter ist ein Typ-/Refinement-Fehler. `N = 0` ist gültig.

Ein Wert `xs : List<T,N>` ist eine geordnete endliche Folge
`[v_0, ..., v_(l-1)]` mit:

```text
0 <= l <= N
v_i : T                  für jedes 0 <= i < l
```

Die Reihenfolge ist Teil des Wertes. Duplikate sind erlaubt. Es gibt weder
stille Abschneidung noch einen impliziten Defaultwert. Eine Datenbanktabelle,
ein Iterator oder eine paginierte Antwort ist nicht automatisch eine
`List<T,N>`; die Begrenzung muss am jeweiligen Wert explizit modelliert werden.

### 2.2 Operationen

Die folgenden totalen Operationen sind semantisch festgelegt. `length` ist nur
für Listen erlaubt; bei Text muss `codepoint_count` oder `utf8_bytes` benutzt
werden.

| Operation | Signatur | Ergebnis und Fehlerverhalten |
| --- | --- | --- |
| leere Liste | `empty<T,N>() : List<T,N>` | `[]`; auch bei `N = 0` gültig |
| Länge | `list_length : List<T,N> -> Nat` | `l`; immer `0 <= l <= N` |
| Index | `index : List<T,N> × Nat -> Option<T>` | `Some(v_i)` genau für `i < l`, sonst `None`; kein Trap und kein Lesen bis `N` |
| Anhängen | `append : List<T,N> × T -> Result<List<T,N>,CapacityError>` | bei `l < N`: `Ok([v_0,...,v_(l-1),v])`; bei `l = N`: `Err(CapacityExceeded)` und unveränderte Eingabe |
| Abbildung | `map<T,U,N> : List<T,N> × (T -> U) -> List<U,N>` | gleiche Länge und Reihenfolge; Callback genau einmal je Element |
| Faltung | `fold<T,A,N> : List<T,N> × A × (A × T -> A) -> A` | Links-Faltung in Indexreihenfolge `0,1,...,l-1`; bei leerer Liste exakt `init` |

`append` darf am Kapazitätsrand keinen Wert verwerfen, überschreiben oder in
eine größere Kapazität implizit umwandeln. Wer bei voller Liste Erfolg
benötigt, muss den `Err`-Fall durch ein vollständiges `match` behandeln oder
eine ausdrücklich anders typisierte Operation aufrufen.

Für `map` gilt elementweise:

```text
map([], f)       = []
map([x] ++ xs,f) = [f(x)] ++ map(xs,f)
```

Für `fold` gilt:

```text
fold([], z, f)       = z
fold([x] ++ xs,z, f) = fold(xs, f(z,x), f)
```

Der Callback ist eine statisch auflösbare, nichtrekursive Funktionsreferenz
gemäß Issue #18. Dynamische Closures, implizite globale Funktionen und
iterationabhängige Callback-Auswahl sind ausgeschlossen. Seine Eingabe- und
Ausgabetypen, Vorbedingung, Nachbedingung und Effekte werden als Teil der
Spezialisierung gebunden. Ist die Vorbedingung für einen erreichbaren Wert
nicht beweisbar, wird das Programm abgelehnt; ein `map`/`fold` darf diesen
Fehler nicht zur Laufzeit überspringen.

### 2.3 Bounds, Spezialisierung und Budgets

Der Verifier prüft die tatsächliche Länge `l` und expandiert für einen
allgemeinen Vertrag höchstens die Indizes `0 .. N-1`. Für jeden expandierten
Index gilt `i < l`; Schritte ab `l` sind No-op und dürfen weder den
Akkumulator noch ein Ergebnis verändern. Der Zielcode darf eine Schleife
verwenden, muss aber dieselbe Reihenfolge, dieselbe Anzahl Callback-Aufrufe
und dieselben Fehlerwerte erzeugen.

Eine A1-Prüfung erhält ein unveränderliches Ressourcenbudget. Mindestens diese
Obergrenzen sind vor der Expansion zu prüfen:

```text
max_list_capacity      >= jede verwendete N
max_collection_steps   >= Summe der vorgesehenen map-/fold-Schritte
max_generic_instances  >= Anzahl verschiedener (Funktions-ID, Typen, N)-Tupel
max_canonical_bytes     >= Eingabe- und Ergebnisdarstellung
```

Die effektiven Laufzeitschritte sind `length(xs)` je `map` bzw. `fold`; die
konservative Beweisobergrenze ist `N`. Ein überschrittenes Budget ist weder
ein Beweis für ein falsches Programm noch ein Kapazitätsfehler. Es muss mit
Lauf-/Verifikationsstatus `resource_exhausted` bzw. `unverified` fail-closed
enden. Budgets dürfen nicht durch Chunking, ungeprüftes Inlining oder
targetabhängige Zähler umgangen werden.

Für `a1-ir-v1` gelten mindestens die dort eingefrorenen Obergrenzen
`max_collection_capacity = 256`, `max_text_bytes = 1_024` und
`max_bounded_steps = 100_000`. Ein Auftrag darf restriktivere Werte setzen;
eine Erhöhung braucht eine neue Profil-/IR-Version und ist nicht durch eine
Quelloption erlaubt.

Verwendete generische Instanzen werden dedupliziert und nach der kanonischen
Funktionsreferenz, den kanonischen Typ-IDs und `N` sortiert. Diese Reihenfolge
bestimmt Expansion, Diagnosepfade und Hashing; Dateisystem-, Hashmap- oder
Threadreihenfolge ist nicht semantisch.

## 3. `Text<N>`

### 3.1 Werte und Validierung

`Text<N>` ist eine unveränderliche Folge von Unicode-Skalarwerten
`[u_0, ..., u_(k-1)]`, gespeichert und gemessen als deren Standard-UTF-8.
Zulässige Skalarwerte sind `U+0000 .. U+D7FF` und `U+E000 .. U+10FFFF`;
Surrogates `U+D800 .. U+DFFF` sind keine Skalarwerte.

Ein Wert erfüllt:

```text
utf8_bytes(t) = byte length of UTF-8(t)
0 <= utf8_bytes(t) <= N
U+0000 ist in t nicht enthalten
```

`N` ist ein nichtnegativer, statisch gebundener `Nat`-Wert in Bytes. Ein
mehrbyteiger Skalar verbraucht genau seine tatsächliche UTF-8-Länge (zum
Beispiel `é` zwei und `😀` vier Bytes). Ein Text darf leer sein, wenn `N >= 0`.

Ein Konstruktor/Decoder muss UTF-8 strikt validieren: Überlängen, verkürzte
Sequenzen, ungültige Fortsetzungsbytes, Surrogates und nichtkanonische
Mehrbyteformen werden abgelehnt. Er muss außerdem U+0000 und eine
Überschreitung von `N` ablehnen. Keiner dieser Fälle darf durch Ersetzung,
Ignorieren, Lossy-Decoding, NFC/NFD-Normalisierung oder trim „repariert“
werden. Rohtext ist weder HTML, URL noch SQL.

Die Hostgrenze verwendet dafür semantisch
`from_utf8<N> : ByteSeq -> Result<Text<N>,TextError>`. `TextError` unterscheidet
mindestens `InvalidUtf8`, `Surrogate`, `Nul` und `CapacityExceeded`; eine
ungültige externe Eingabe ist ein `Err`/`input_rejected`, kein teilweise
erzeugter Text. Ein statisches Literal mit derselben Verletzung wird vor der
Ausführung mit `A1_TEXT_*` abgelehnt.

### 3.2 Operationen

| Operation | Signatur | Exakte Semantik |
| --- | --- | --- |
| Bytezahl | `utf8_bytes : Text<N> -> Nat` | Anzahl der UTF-8-Bytes der unveränderten Skalarfolge |
| Codepointzahl | `codepoint_count : Text<N> -> Nat` | Anzahl der Unicode-Skalarwerte, nicht Bytes und nicht Grapheme |
| Präfix | `prefix_codepoints : Text<N> × Nat -> Text<N>` | erste `min(q,k)` Skalarwerte; bei `q >= k` der unveränderte Text, bei `q = 0` leer |
| Konkatenation | `concat : Text<N> × Text<M> -> Text<N+M>` | Skalarfolge links gefolgt von rechts; keine Normalisierung oder trim |

`prefix_codepoints` darf nur an Skalargrenzen schneiden. Es darf niemals ein
UTF-8-Präfix erzeugen, das der Decoder nicht akzeptieren würde. Das Präfix
erbt die deklarierte Kapazität `N`; die tatsächliche Bytezahl kann kleiner
sein. Ein gewünschtes kleineres Zielbudget ist eine separate, explizite
Operation mit `Result<...,CapacityError>`, niemals stilles Abschneiden.

`concat` ist nur dann erfolgreich, wenn seine statisch deklarierte Zielgrenze
die Summe der Eingangsgrenzen abbilden kann. Eine Implementierung mit kleinerer
Zielkapazität muss einen expliziten `Result`-Fehler liefern. Die einfache
`concat`-Signatur erzeugt daher keinen Laufzeitfehler und keine unbemerkte
Kapazitätsänderung.

Es gibt absichtlich keine allgemeine Operation `length(Text)`. Byte- und
Codepointmaß sind getrennt benannt; ein späteres Graphemmaß wäre eine neue,
explizit versionierte Operation.

### 3.3 Kanonische Darstellung

Die semantische Kanonisierung eines Textwerts ist im `a1-ir-v1`-Artefakt ein
kanonisches JSON-Wertobjekt mit Kapazität und unveränderten UTF-8-Bytes. Die
Bytekomponente wird als lowercase-Hexfeld dargestellt, damit JSON-Escapeformen
nicht mit dem Sprachwert verwechselt werden:

```text
canonical_text(N,t) = {
  "kind":"text", "max_bytes":N,
  "utf8_hex":lowercase_hex(raw_utf8(t))
}
```

Die umgebende `canonical_json`-Regel, Feldsortierung und Hashbindung sind die
von `a1-ir-v1` festgelegten Regeln. `raw_utf8(t)` enthält genau die strikt
validierten Bytes; weder Unicode-Normalisierung noch Whitespace-/Escape-
Vereinheitlichung darf diese Bytes ändern. Die kanonische Quelltextform muss
diese Bytefolge verlustfrei ausdrücken.

Die semantische Kanonisierung einer Liste ist ein geordnetes Wertobjekt:

```text
canonical_list(T,N,[v0,...,v(l-1)]) = {
  "kind":"list", "capacity":N, "values":[canonical_value(v0),...]
}
```

Der Elementtyp steht verbindlich in der kanonischen Typbeschreibung des
umgebenden IR-Werts; `canonical_value` ist rekursiv und eindeutig. Dadurch
bleiben `[]`, leere Texte, verschachtelte Listen und Werte mit variabler
Bytegröße eindeutig. Die Reihenfolge der Elemente bleibt erhalten. Kapazität,
tatsächliche Länge und Elementtyp werden nie aus einer Zielrepräsentation
erraten oder weggelassen.

## 4. Target-unabhängiges Differentialmodell

Jede A1-Implementierung muss gegen ein unabhängiges Referenzmodell `R`
verglichen werden. `R` benutzt keine Targetbibliothek, keine Zielcode-
Auswertung und keine vom Compiler erzeugte Collection-Hilfsfunktion. Für einen
kanonischen Testfall `c` werden mindestens aufgezeichnet:

```text
c = (program_bytes, type_environment, initial_values, operation_trace, budgets)
R(c) = (status, canonical_values, canonical_errors, observations, diagnostics)
G(c) = (status, canonical_values, canonical_errors, observations, diagnostics)
```

`G` ist der tatsächlich erzeugte Zielcode unter der festgelegten Runtime. Die
Vergleichsrelation verlangt:

1. gleiche Terminierungs-/Fehlerklasse (`returned`, `input_rejected`,
   `resource_exhausted`, `host_error`);
2. bei Erfolg bytegleiche kanonische Werte und gleiche Reihenfolge;
3. bei `Option`/`Result` gleichen Konstruktor und rekursiv gleichen Payload;
4. bei Texten bytegleiche unveränderte UTF-8-Werte sowie gleiche
   `utf8_bytes`-/`codepoint_count`-Beobachtungen;
5. bei erwarteten Ablehnungen gleichen stabilen Diagnosecode und gleiche
   Phase, nicht zwingend dieselbe menschenlesbare Meldung;
6. gleiche Budgetgrenze: kein Target darf durch Überlauf, stilles Kürzen oder
   abweichende Integer-/Stringdarstellung einen Fall grün machen.

Testausführung, `proved`/`unverified`-Status und formale Beweisannahmen werden
getrennt aufgezeichnet. Ein erfolgreicher Differentialtest beweist nicht den
Vertrag; ein akzeptiertes Proof-Zertifikat ersetzt keinen ausgeführten
Differentialtest.

Die Fallgeneratoren müssen mindestens `N = 0`, leere und volle Listen,
Duplikate, Index `0`, Index `length-1`, Index `length` und größer,
mehrbyteige UTF-8-Skalare, kombinierte (nicht normalisierte) Sequenzen,
U+0000, Surrogates, ungültige UTF-8-Bytes, Bytegrenzen und Budgetgrenzen
erzeugen. Zufällige Reihenfolge ist dabei kein gültiger Orakelersatz: Die
Kanonisierung und der Generatorseed werden mit dem Fall gebunden.

## 5. Diagnosen und Fail-Closed-Regel

Alle neuen Meldungen verwenden das additive `diagnostic-v1`-Envelope aus
`specs/M0-BASELINE.md`: `schema`, `phase`, `code`, `message`, `span` und
`symbol`. `message` ist für Menschen und kein Vergleichsschlüssel. `span` ist
null oder ein Unicode-Zeichenbereich; `symbol` wird nicht geraten.

Die folgenden A1-Codes sind stabil und müssen dieselbe Ursache bezeichnen:

| Code | Phase | Bedeutung |
| --- | --- | --- |
| `A1_TYPE_CAPACITY` | `validate` | `N`/`M` ist kein zulässiger nichtnegativer statischer `Nat` |
| `A1_LIST_BOUNDS` | `validate` | Konstruktion oder statischer Zugriff verletzt die Listeninvariante |
| `A1_CALLBACK` | `validate` | Callbacktyp, Effekt, Referenz oder Vorbedingung passt nicht |
| `A1_TEXT_ENCODING` | `validate` | UTF-8 ist ungültig oder enthält einen Surrogatewert |
| `A1_TEXT_NUL` | `validate` | U+0000 ist enthalten |
| `A1_TEXT_CAPACITY` | `validate` | UTF-8-Bytegrenze ist überschritten |
| `A1_TEXT_OPERATION` | `validate` | unzulässige/mehrdeutige Textoperation, etwa `length(Text)` |
| `A1_BUDGET` | `resource` | ein explizites A1-Prüf- oder Ausführungsbudget ist erschöpft |
| `A1_CANONICAL` | `validate` | kanonische Darstellung ist mehrdeutig oder nicht bytegleich |

Ein Index außerhalb der aktuellen Länge ist bei `index` **kein** Diagnosefall,
sondern exakt `None`. Ein volles `append` ist exakt `Err(CapacityExceeded)`.
Nur wenn ein Kontext diesen Result-/Option-Wert entgegen seinem Typ als Erfolg
verwendet, entsteht eine passende Typ-/Match-Diagnose.

Unbekannte oder defekte Belege, Targetabweichungen, Callbackauslassungen,
Budgetüberläufe und nicht dekodierbare Werte dürfen nie zu `proved` oder einer
erfolgreichen Ausführung herabgestuft werden. Sie führen zu einer stabilen
Diagnose und dem getrennten Status `unverified`, `input_rejected` oder
`resource_exhausted`.

## 6. Abgrenzungen zu M2-Schnittstellen

- #17 liefert Records, Varianten, `Option` und `Result`; A1 verwendet deren
  allgemeinen Konstruktor-/Match-Regeln und erfindet keine Collectionspezial-
  konstruktoren.
- #18 liefert `Nat`, statische Funktionsreferenzen und deterministische,
  budgetierte Monomorphisierung; `map`/`fold` sind der erste verbindliche
  Verbraucher dieser Schnittstelle.
- #19 bindet die A-normal-formige IR, den Referenzinterpreter und explizite
  Checkerregeln. Jede Listeniteration und jeder Textoperator braucht dort eine
  benannte Regel; ein bloßes Target-`map` oder eine Host-Stringfunktion reicht
  nicht.
- Bestehende M0-Webprofile dürfen ihre eingefrorene Textsemantik behalten.
  A1-`Text<N>` ist ein reiner Sprachwert und macht aus HTML, URL, SQL oder
  Datenbankseiten keine `Text`-/`List`-Werte.
