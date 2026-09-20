# A1-IR — kanonische typisierte Ausführungs-IR

**Status:** M2-Entwurf, normativer Vertrag für Issue #19 (2026-09-20). Die
Implementierung darf nur die hier freigegebene Teilmenge als `a1-ir-v1`
bezeichnen. P0, w1, w2 und pkg1 werden durch dieses Dokument nicht geändert.

Die IR ist ein kleiner, unabhängiger Zwischenvertrag zwischen Elaboration,
Verifikation, Referenzinterpreter und späterem Target-Lowering. Sie ist kein
untypisiertes JSON-AST und kein Beweis, dass eine Autorensyntax korrekt in die
IR übersetzt wurde. Eine solche Source-to-IR-Brücke wird separat gebunden.

## 1. Profile, Artefakte und Vertrauensgrenze

Ein A1-Artefakt besitzt die festen Kennungen:

```text
format  = "a1-ir-v1"
profile = "a1"
checker = "a1-check-v1"       (im Verifikationsdokument verwendet)
```

Die Versionen von Sprachprofil, IR, Checker, Zertifikatsformat und Target-ABI
sind unabhängige Achsen. Ein Artefakt darf keine fehlende Version durch einen
Default ergänzen. Solver, Elaborador, Optimierer und Agenten liefern Daten oder
Vorschläge; sie gehören nicht zur Vertrauensgrenze des strukturellen Checkers.

Ein IR-Dokument enthält mindestens `format`, `profile`, `types`, `functions`,
`specializations`, `entrypoints` und `limits`. Unbekannte Top-Level-Schlüssel,
doppelte Schlüssel, fehlende Pflichtfelder, JSON-Fließkommazahlen und
unbegrenzte Integer werden abgelehnt. Metadaten-Indizes sind kleine explizite
JSON-Integer; Sprachwerte sind typisierte Objekte, niemals JSON-Zahlen.

## 2. Kanonische JSON- und Hashregeln

Die semantische Bindung erfolgt über genau die kanonischen UTF-8-Bytes des
Dokuments ohne ein eigenes Hashfeld:

```text
hash = SHA-256(
  frame("llmlang:a1-ir", format, profile, checker, canonical_json(document))
)
frame(s1,...,sn) = für jedes s: u64-be(length(UTF-8(s))) || UTF-8(s)
```

`canonical_json` verwendet keine Leerzeichen, sortiert Objekt-Schlüssel nach
ihrem UTF-8-Bytewert und erhält Array-Reihenfolgen. Strings verwenden gültiges
UTF-8 und die eindeutige JSON-Escapeform; Sprachtexte werden dabei **nicht**
normalisiert. Schlüssel und qualifizierte IDs sind ASCII. `true`, `false` und
`null` sind die einzigen JSON-Literale außer begrenzten, nichtnegativen
Metadaten-Integer. Ein Integer-Typwert steht als
`{"type":"Int","value":"-7"}`. Werte sind rekursiv kanonisch und haben
keine unbenannten Hostobjekte.

Der Hash umfasst Typdeklarationen, Signaturen, Verträge, Körper, Effekte,
Orte, Spezialisierungen und Budgets. Debugnamen, Spans und freie Beschreibungen
sind außerhalb des Hashes in einem separaten Provenienzobjekt zulässig. Eine
geänderte Reihenfolge von Feldern oder Blöcken ist nur dann semantisch gleich,
wenn sie dieselben kanonischen Arrays erzeugt; Hashmaps dürfen nie die Ordnung
bestimmen.

## 3. Typen und Werte

### 3.1 Grundform

Jeder Typ ist ein geschlossenes Objekt mit genau dem Schlüssel `kind` plus den
für diese Variante festgelegten Feldern. A1 unterstützt:

```text
{"kind":"unit"}
{"kind":"bool"}
{"kind":"int"}                         mathematische exakte Ganzzahl
{"kind":"nat"}                         Int mit Invariante x >= 0
{"kind":"text","max_bytes":N}        gültige Unicode-Skalare ohne U+0000
{"kind":"list","elem":T,"capacity":N}
{"kind":"option","elem":T}
{"kind":"result","ok":T,"error":E}
{"kind":"record","id":ID,"args":[T,...]}
{"kind":"variant","id":ID,"args":[T,...]}
{"kind":"type_var","index":I}
{"kind":"capacity_var","index":I}
```

`record` und `variant` verweisen nominal auf einen Eintrag in `types`; gleiche
Felder oder gleiche Payloads erzeugen keine strukturelle Gleichheit. IDs sind
qualifizierte, kanonische ASCII-Referenzen (bei pkg1 normalerweise
`package/module/decl`). `Option<T>` und `Result<T,E>` sind normale geschlossene
Varianten mit den Konstruktoren `none|some` bzw. `ok|err`, keine impliziten
Nullwerte oder Checker-Sonderfälle.

Ein Recordtyp wird in `types` einmalig erklärt:

```json
{"kind":"record_def","id":"booking/Booking","fields":[
  {"id":"total","type":{"kind":"nat"}},
  {"id":"used","type":{"kind":"nat"}}
]}
```

Eine Variantendeklaration enthält eine geordnete, endliche Konstruktorliste;
jeder Konstruktor hat eine eindeutige ASCII-ID und höchstens eine Payload. Die
Liste ist die vollständige geschlossene Welt. Rekursive Deklarationen, offene
Rows, Vererbung und dynamische Reflection sind in `a1-ir-v1` verboten.

`capacity` und `max_bytes` sind nichtnegative kanonische Metadaten-Integer.
Typparameter und Kapazitätsparameter werden nur über eine explizite, geordnete
Spezialisierung ersetzt. Unaufgelöste Variablen sind nur im generischen
Original erlaubt, nicht in einer ausführbaren Spezialisierung.

### 3.2 Laufzeitwerte

Der Interpreter verwendet immutable Werte:

```text
Unit
Bool
Int (exakt, dezimal gebunden)
Text (Unicode-Skalarfolge, unverändert)
Record(type_id, ordered fields)
Variant(type_id, constructor_id, optional payload)
List(capacity, ordered values)
```

Ein Laufzeitwert trägt immer seinen nominalen Typ. Eine Eingabe-/Hostgrenze
validiert Typ, Integerbits, Text-UTF-8/Nullbyte und Listen-Kapazität erneut.
`Nat` wird an jeder externen Grenze und bei jeder Einführung geprüft; ein
früheres Typurteil ist kein Ersatz für diese Validierung.

## 4. Funktionen, Werte und Blöcke

### 4.1 A-Normalform

Eine Funktion ist eine unveränderliche Folge von CFG-Blöcken. Jeder Block hat
eine eindeutige lokale ID. Innerhalb einer Funktion sind alle Blockparameter
und instruktionserzeugten Werte eine lückenlose Folge `0..V-1`; jede Definition
kommt genau einmal vor. Ein Operandenverweis ist stets eine bereits definierte
Wertnummer oder ein expliziter Funktions-/Typverweis. Es gibt keine verschachtelte
Ausdruckssyntax, implizite temporäre Werte oder mutable Zellen.

Eine minimal gültige Form ist:

```json
{
  "id":"booking/reserve",
  "type_params":[], "capacity_params":[],
  "params":[{"value":0,"type":{"kind":"record","id":"booking/Booking","args":[]}}],
  "result":{"kind":"result","ok":{"kind":"nat"},"error":{"kind":"unit"}},
  "effects":[], "location":"shared",
  "requires":{"op":"true"},
  "ensures":{"op":"true"},
  "blocks":[{"id":0,"params":[],"values":[
    {"id":1,"op":"project","type":{"kind":"nat"},"record":0,"field":"used",
     "effects":[],"location":"shared"}
  ],"terminator":{"op":"return","value":1}}]
}
```

Parameterwerte werden vor dem ersten Block in derselben Nummerierungsdomäne
reserviert. Ein Blockparameter ist eine neue Definition; seine eingehenden
Argumente stehen im `branch`/`cond_branch`-Terminator des Vorgängerblocks.
Blockparameter sind die einzige Phi-Form. Es gibt keine implizite SSA-Reparatur.
Die Norm erlaubt Rückkanten nur innerhalb der unten definierten
`bounded_map`-/`bounded_fold`-Semantik; ein allgemeiner CFG-Zyklus und
allgemeine Rekursion sind verboten.

### 4.2 Pflichtfelder jeder Instruktion

Jede wertproduzierende Instruktion enthält `id`, `op`, `type`, `effects` und
`location`. `effects` ist eine geordnete, duplicate-freie Liste expliziter
Effekt-IDs; reine Instruktionen haben `[]`. `location` ist exakt einer von
`shared`, `client`, `server`. `shared` darf nur typ- und wertdeterministische
Instruktionen ohne Effekte enthalten. Die Felder sind auch bei reinem A1-Code
Pflicht, damit spätere Target-/Capability-Regeln nicht aus fehlenden Angaben
schließen müssen.

Freigegebene reine Instruktionen sind:

| Operation | Operanden | Ergebnis / Regel |
|---|---|---|
| `const` | typisierter Wert | Typ ist exakt der Literaltyp |
| `move` | Wert | unveränderlicher Alias mit identischem Typ |
| `record_make` | Feldwerte in Deklarationsreihenfolge | nominaler Record |
| `project` | Recordwert, Feld-ID | exakt deklariertes Feld |
| `variant_make` | Konstruktor-ID, optionale Payload | nominale Variante |
| `option_none`, `option_some` | — / Wert | `Option<T>` |
| `result_ok`, `result_err` | Wert | `Result<T,E>` |
| `match_value` | scrutinee, geschlossene Arm-Tabelle | ein Ergebnisblock pro Konstruktor |
| `eq`, `int_add`, `int_sub`, `int_mul`, `int_le`, `int_lt` | typisierte Werte | exakte, deklarierte Typsemantik |
| `text_utf8_bytes`, `text_codepoint_count` | Text | exakte Maße; kein `length` |
| `text_prefix_codepoints`, `text_concat` | Text und Grenze bzw. zwei Texte | skalar-sicheres Praefix bzw. kapazitaetsgepruefte Konkatenation |
| `list_empty`, `list_cons`, `list_index` | typisierte Werte | Kapazität bzw. `Option<T>` |
| `list_append` | Liste und Element | `Result<List<T,N>, CapacityError>`; kein implizites Wachstum |
| `refine_nat` | `Int` | `Nat`, nur mit geprüfter Nichtnegativität |
| `call` | statischer Funktionsverweis, Werte | callee-Ergebnis; Vorbedingung/Effects geprüft |
| `bounded_map` | Liste, statischer Callback, Kapazität | Liste gleicher Kapazität, Reihenfolge erhalten |
| `bounded_fold` | Liste, Init, statischer Callback | Akkumulator, höchstens `N` Schritte |

Boolesche Operationen dürfen als eigene `not`, `and`, `or`-Instruktionen
vorkommen. `and` und `or` haben im A1-Interpreter die definierte
Links-nach-rechts-**strikte** Auswertung wie P0; ein Target darf daraus kein
kurzschließendes JavaScript machen. Arithmetik bleibt exakt; Maschineninteger,
Gleitkomma, implizite Casts, Overflow-Wrap und Division sind in dieser Version
nicht freigegeben. `int_mul` kann für die Vertragsprüfung außerhalb des linearen
Fragments liegen und erhält dann keinen solverischen Beweisstatus.

### 4.3 Terminatoren und expliziter Kontrollfluss

Jeder Block endet exakt mit einem Term:

```text
return value
branch target args
cond_branch condition then(args) else(args)
switch_variant scrutinee { constructor -> target(args), ... }
fail error_value
```

`return` passt exakt zum Funktionsresultat. `branch`-Argumente passen in Anzahl
und Typ zu den Zielblockparametern. `cond_branch` verlangt `Bool`. Eine
`switch_variant` enthält jeden Konstruktor genau einmal und keinen Defaultarm;
die Konstruktorliste kommt ausschließlich aus der nominalen Typdeklaration.
Nicht erreichte Blöcke sind trotzdem wohlgeformt und werden geprüft. Terminator-
und Armreihenfolge ist semantisch und kanonisch.

## 5. Verträge, Calls und proven Callee Summaries

`requires` und `ensures` sind gebundene, reine Prädikate über Parameter,
Spezialvariablen `result` sowie strukturelle Projektionen/Konstruktoren. Sie
dürfen keine Effekte, Hostwerte, freien Namen oder Calls enthalten. Der
Checker darf das Prädikat nicht durch das aus einer Kandidatenantwort gelieferte
Prädikat ersetzen.

Eine `call`-Instruktion enthält eine vollständig aufgelöste Funktion-ID und eine
konkrete Spezialisierungs-ID oder `null` für nichtgenerische Funktionen. Vor der
Verwendung prüft der Checker:

1. Argumenttypen und Spezialsubstitution passen exakt zur callee-Signatur;
2. der Aufrufgraph bleibt azyklisch und der Aufruf ist budgetiert;
3. der rekonstruierte Pfad erfüllt die callee-`requires`;
4. der callee-Summary-Hash bindet Funktion, Vertrag, Körper, Spezialisierung,
   Checkerversion und Effekt-/Ortdeklaration;
5. der Summary-Status ist `proved`, nicht bloß `tested`, `suggested` oder von
   einem Solver gemeldet.

Eine Summary ist ein vom Checker erzeugtes Ergebnis, kein vom Kandidaten
behauptetes Freiticket. Beim vollständigen Prüfen wird zuerst der callee in
topologischer Reihenfolge geprüft. Ein alter oder nur neu gehashter Summary-
Eintrag wird bei jeder abweichenden Eingabe abgelehnt. M1 bleibt damit korrekt:
vollständige Programme werden erneut gebunden und geprüft; modulare Summary-
Caches sind nur eine spätere Optimierung für exakt identische Hashes.

## 6. Generics und deterministische Spezialisierung

Generische Funktionen deklarieren `type_params` und `capacity_params` in fester
Reihenfolge. Jede Nutzung enthält eine explizite Substitution:

```json
{"id":"std/map/BookingToNat#Booking#8",
 "generic":"std/map/BookingToNat",
 "types":[{"kind":"record","id":"booking/Booking","args":[]}],
 "capacities":[8], "body_hash":"..."}
```

Eine Spezialisierung ist gültig, wenn alle Typen geschlossen, alle Kapazitäten
`0 <= N <= max_collection_capacity` und alle Bindungen positionsgenau sind.
Instanz-IDs werden aus generic-ID und kanonischer Substitution gebildet; die
Liste wird nach diesen IDs sortiert und darf keine Duplikate enthalten. Nur
tatsächlich referenzierte Instanzen werden materialisiert. Implizite
Überladung, Typeclasses, Runtime-Reflection und dynamische Closures sind
verboten. Callback-Referenzen für `bounded_map`/`bounded_fold` sind statische
Funktions-/Spezialisierungs-IDs.

## 7. Nat und Refinements

`Nat` ist in A1 eine Refinement-Sicht auf exaktes `Int`, kein separater
Arithmetikkern. `refine_nat(x)` ist nur erlaubt, wenn der Checker die Pflicht
`x >= 0` strukturell oder mit einem akzeptierten, checkerprüfbaren Beleg
schließt. Ein Solver-`unsat` ohne Beleg, ein früher Cast oder ein behauptetes
`proved`-Feld genügt nicht. An Eingabe-, Text-, Listen- und Hostgrenzen wird die
Bedingung zusätzlich ausgeführt; bei Verletzung entsteht `input_rejected`.

`Nat - Nat` liefert in A1 ein `Int`, sofern kein separater Vertrag einen
geprüften Refinement-Schritt liefert. Eine implizite Nat-Annahme durch
Untertypung ist verboten.

## 8. Bounded map/fold

Für `bounded_map` und `bounded_fold` gelten dieselben Regeln im Interpreter,
Checker und späteren Target:

- Die Eingabeliste trägt `capacity=N` und ihre tatsächliche Länge `0..N`.
- Der Callback ist statisch referenziert, rein, spezialisiert und hat einen
  geprüften Summary-Hash.
- Verarbeitung erfolgt in Indexreihenfolge `0,1,...,length-1`; leere Listen
  führen keinen Callback aus.
- `map` erhält dieselbe Länge/Kapazität; `fold` gibt den Initwert bei leerer
  Liste zurück. Es gibt keine stille Kürzung, Mutation oder Iteration außerhalb
  der Länge.
- Der Checker expandiert höchstens `N` Schritte und fügt für jeden Schritt die
  Pfadbedingung `i < length` hinzu. Alle `N`-Schritte, Callbackverträge und
  Kapazitätsgrenzen werden budgetiert. Budgetüberschreitung ist `unverified`,
  nicht `proved`.

Eine Datenbankseite ist kein globales `List<T,N>`-Versprechen. Cursor-,
Authentifizierungs- und Transaktionsverträge bleiben Adaptergrenzen.

## 9. Effekte und Orts-Platzhalter

`effects` und `location` sind in A1 bereits Teil des semantischen Hashes, auch
wenn der erste reine Kern nur `effects=[]` verifiziert. Ein Call darf höchstens
die deklarierten Caller-Effekte verwenden. `client` darf keine server-only-
Fähigkeit besitzen; `shared` darf nur pure Operationen verwenden. Nichtleere
Effektmengen müssen eine explizite Capability-/Hostbeschreibung tragen und
können in A1 interpretiert bzw. strukturell typgeprüft werden, erhalten aber
ohne eine freigegebene A1-Hostregel höchstens `tested`/`unverified`, nie
`proved`. Diese Platzhalter verhindern, dass M3-Effekte später stillschweigend
die Bedeutung eines alten Hashes ändern.

## 10. Referenzinterpreter und Laufstatus

Der Referenzinterpreter nimmt ausschließlich den geprüften, unveränderlichen
IR-Snapshot und explizite Eingaben/Capabilities an. Er läuft deterministisch
call-by-value, links nach rechts. Records, Varianten und Listen werden kopiert
oder strukturell geteilt, aber nie mutiert. Er prüft vor jedem Call die
Vorbedingung und vor dem Rücklauf die Nachbedingung, sofern der Lauf als
vertraglich instrumentiert angefordert ist.

Das Ergebnis ist maschinenlesbar:

```json
{"schema":"a1-execution-v1","status":"returned",
 "ir_hash":"...","entry":"...","result":{"type":"Int","value":"3"},
 "steps":17,"iterations":0,"trace":["b0","b1"]}
```

Erlaubte Statuswerte sind `not_run`, `returned`, `input_rejected`,
`resource_exhausted`, `precondition_failed`, `postcondition_failed`,
`host_error` und `invalid_program`. Tracewerte sind Block-/Call-IDs aus der
geprüften IR; ein Trace ist Laufzeitbeleg, kein mathematischer Beweis.

## 11. Ressourcenbudgets

Die folgenden konservativen Defaults sind Bestandteil von `a1-ir-v1`; ein
Auftrag darf sie nur explizit kleiner setzen oder in einer neuen Profilversion
ändern:

| Ressource | Default |
|---|---:|
| kanonische IR-Bytes | 2,000,000 |
| Typdeklarationen / Funktionen / Blöcke | 8,192 / 2,048 / 16,384 |
| Werte je Funktion / Gesamtwerte | 65,536 / 500,000 |
| AST-/Vertragsknoten | 100,000 |
| maximale Call-/CFG-Tiefe | 256 / 1,024 |
| Match-Konstruktoren je Tabelle | 256 |
| generische Spezialisierungen | 512 |
| Listen-/Textkapazität | 256 / 1,024 Bytes |
| Interpreter-Schritte / Bounded-Schritte | 1,000,000 / 100,000 |
| Beweisobligationen / Evidenzbytes | 100,000 / 4,000,000 |

Alle Zähler werden vor Expansion und während der Verarbeitung erhöht. Eine
Überschreitung liefert eine stabile Ressourcen-Diagnose und niemals ein
positives Verifikationsurteil. Wallclock-Abbruch ist ebenfalls `unverified`.

## 12. Kompatibilitäts- und Abnahmegrenze

P0 bleibt beim vorhandenen `cert-v0.1`-Checker und seinen Hash-/Binderregeln.
Eine A1-IR darf P0 nur über eine separat geprüfte, strukturerhaltende Brücke
verwenden; eine A1-Summary ersetzt keinen P0-Beleg. A1-`proved` bedeutet daher
höchstens: der gebundene `a1-ir-v1`-Vertrag wurde durch `a1-check-v1` akzeptiert.
Es behauptet keine formale Korrektheit des Python-Checkers, des Elaborador,
des Targets, von D1, Browser, Authprovider oder Fremdcode.

Für RED/GREEN-Abnahme müssen mindestens vorliegen:

1. RED: falscher Recordtyp/-feld, falscher Variantentag, fehlender Matcharm,
   falscher Callback, Zyklus, ungültige Nat-Annahme, Kapazitäts-/Beweisbudget-
   überschreitung und veralteter Hash werden deterministisch abgelehnt.
2. GREEN: zwei fachlich verschiedene Consumer verwenden unveränderte generische
   `map`-/`fold`-Logik mit mindestens zwei Recordtypen und zwei Kapazitäten;
   Records, Varianten, Option/Result, Nat, Unicode-Text und leere/volle Listen
   laufen im Referenzinterpreter zusammen.
3. Property-Tests erzeugen zulässige nummerierte IRs und mutationstesten
   Projection, Substitution, Match-Abdeckung, Callback und Hashbindung.
4. Referenz-/Target-Differentialtests sind Ausführungsevidenz. Sie dürfen den
   Checkerstatus nicht auf `proved` anheben; die Source-to-IR- und IR-to-Target-
   Übersetzungsbehauptungen bleiben separat.
