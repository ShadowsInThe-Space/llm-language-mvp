# A1 — Nominale Datentypen und Fallunterscheidung (Entwurf für M2)

**Status:** normative Draft-Spezifikation für Issue #17, Profil `a1`, M2/v0.6.0.
P0, w1, w2 und `pkg1` bleiben unverändert. Diese Datei beschreibt noch keine
Implementierung und erweitert keinen Beweisstatus des P0-Kernels.

Die Schlüsselwörter **MUSS**, **DARF NICHT**, **SOLL**, **SOLL NICHT** und
**DARF** sind normativ. Fehlermeldungen sind nicht stabil; Diagnosecodes,
Pfadform und Kanonisierung sind stabil.

## 1. Ziel und Grenze

Der A1-Typkern stellt unveränderliche nominale Records, geschlossene Varianten,
`Option`, `Result`, vollständiges `match` und die Verfeinerung `Nat` über dem
exakten `Int` bereit. Fachbegriffe wie `Customer`, `Booking` oder
`BookingError` werden als normale Deklarationen geschrieben; es gibt keine
domänenspezifischen Opcodes.

Im ersten A1-Schnitt sind nicht enthalten: Null, Mutation, Vererbung, offene
Row-Typen, implizite Überladung, dynamische Reflexion, rekursive Datentypen,
beliebige abhängige Typen, beliebige User-Refinements, Exceptions und
unbegrenzte Collections. Bounded Collections werden in #19 definiert; diese
Spezifikation liefert lediglich die Typanwendungs- und Nominalitätsregeln, die
eine solche Bibliothek braucht.

`Int` bleibt mathematisch exakt. Es gibt keine implizite Umwandlung in
JavaScript-`number`, Maschineninteger oder `Float`. `Nat` ist dieselbe
Laufzeitrepräsentation mit dem statischen Prädikat `0 <= n`, kein zweiter
Rechenkern.

## 2. Kanonische Quelle

### 2.1 Ein Modul, eine S-Expression

Die autoritative A1-Quelle ist eine UTF-8-S-Expression. Sie wird als genau eine
Form `(module a1 ...)` eingelesen. Der Parser MUSS Eingabebytes, AST-Knoten,
Tiefe und Integerbits vor und während des Aufbaus begrenzen; die P0-Defaults
bleiben die Untergrenze. Kommentare, Stringliterale, Makros und Präprozessoren
gehören nicht zur A1-Quelle.

Ein Identifier ist ein ASCII-Atom der Form
`[a-z][a-z0-9_.-]{0,63}`. Profil- und Grundtypen bleiben die festgelegten
Atome `a1`, `Unit`, `Bool`, `Int` und `Nat`. Integerliterale sind kanonische
Dezimalatome `0` oder `[1-9][0-9]*`, mit optionalem `-` nur für `Int`; `+1`,
`-0`, führende Nullen und Exponenten sind ungültig. Ein A1-Programm DARF keine
JSON-Zahl als Sprachwert verwenden.

Die deklarative Form ist:

```text
(module a1
  (name booking)
  (types
    (type booking-state
      (record
        (field total Nat)
        (field used Nat)))
    (type booking-error
      (variant
        (ctor sold-out Unit)
        (ctor invalid-quantity Unit))))
  (functions ...))
```

`name` ist der lokale Modulname. Paket- und Importauflösung bleiben `pkg1`-
Verantwortung; der vollständig qualifizierte Typname ist
`package.module.type`. Ein Modul MUSS genau einen Typnamen und jede Feld-/
Konstruktorbezeichnung höchstens einmal deklarieren. Private Namen werden wie
in `pkg1` nicht exportiert, sind aber innerhalb des Moduls typgleich.

### 2.2 Type-Expressions

```text
type ::= Unit | Bool | Int | Nat | QualifiedType
       | (QualifiedType type-arg ...)
```

Typanwendungen sind nur für eine deklarierte generische Record-/Variant- oder
Bibliotheksdefinition gültig. Die Parameterzahl und Parameterkind müssen exakt
passen. `Option<T>` und `Result<T,E>` sind keine versteckten Sonderfälle:

```text
(type Option
  (type-params T)
  (variant
    (ctor none Unit)
    (ctor some T)))

(type Result
  (type-params T E)
  (variant
    (ctor ok T)
    (ctor err E)))
```

Die beiden Definitionen sind Teil des A1-Preludes und werden durch denselben
Variant-/Match-Checker geprüft wie eine Nutzerdefinition. Implementierungen
dürfen sie vorladen, müssen aber dieselben Deklarations- und Bindungsregeln
anwenden. Ein anderer `Option`- oder `Result`-Typ ist nominal verschieden.

### 2.3 Records

Ein Record ist geschlossen, unveränderlich und nominal. Seine Form lautet:

```text
(type customer
  (record
    (field id customer-id)
    (field display-name Text)))
```

Für die M2-Typbasis ist `Text` eine bereits zugelassene Target-/Bibliotheks-
Erweiterung oder ein späteres #19-Attribut; das Recordmodell selbst behandelt
jeden bereits aufgelösten Typ nominal. `Text` ist hier kein Anlass für einen
neuen Domain-Opcode.

Felder werden in der Kanonisierung lexikografisch nach ihrer eindeutigen
Bezeichnung sortiert. Eine Quelle, die dieselbe Feldbezeichnung doppelt angibt,
ist ungültig. Bei `record.make` MUSS die Menge der Felder exakt der
Deklaration entsprechen: kein ausgelassenes, zusätzliches oder doppelt
angegebenes Feld. Die Reihenfolge im Quelltext von `record.make` ist daher
nicht semantisch.

```text
(record.make customer
  (field display-name (var 1))
  (field id (var 0)))
(record.get customer id (var 0))
```

`record.get` akzeptiert nur den nominal identischen Recordtyp und ein in diesem
Record deklariertes Feld. Strukturähnliche Records, Aliasnamen oder gleiche
Laufzeitrepräsentationen ersetzen keine Nominalität. `customer-id` und
`booking-id` sind deshalb auch bei beiden zugrundeliegendem `Int` nicht
austauschbar.

### 2.4 Geschlossene Varianten

Eine Variante ist eine endliche, geschlossene Summe. Ein Konstruktor besitzt im
M2-Kern entweder keine Nutzlast oder genau eine Nutzlast; mehrere fachliche
Felder werden als eigener Recordtyp gebündelt.

```text
(type booking-error
  (variant
    (ctor sold-out Unit)
    (ctor invalid-quantity Unit)
    (ctor retryable retry-reason)))

(variant.make booking-error sold-out)
(variant.make booking-error retryable (var 0))
```

Konstruktoren einer Variante sind eindeutig und werden in der kanonischen
Darstellung nach ihrem Namen sortiert. Ein Konstruktor einer anderen Variante
ist auch bei gleicher Nutzlast nicht zulässig. Es gibt keinen offenen
`other`-/`default`-Konstruktor, der unbekannte Fälle verschluckt.

### 2.5 Ausdrucksformen

Der A1-Ausdruckskern ist absichtlich klein und mit dem bestehenden de-Bruijn-
Transport kompatibel:

```text
expr ::= (var nonnegative-index)
       | exact-int-literal | true | false | unit
       | (let expr expr)
       | (if expr expr expr)
       | (record.make QualifiedType (field name expr) ...)
       | (record.get QualifiedType field expr)
       | (variant.make QualifiedType ctor [expr])
       | (match expr (case ctor [bind] expr) ...)
       | (call QualifiedFunction ...)
       | (int.add expr expr) | (int.sub expr expr)
       | (int.mul expr expr) | (int.le expr expr)
       | (int.lt expr expr) | (int.eq expr expr)
```

`var 0` ist die zuletzt gebundene Variable. `let` wertet zuerst den gebundenen
Ausdruck aus und erweitert nur den Körperkontext. Ein `case` mit Nutzlast muss
genau einen Binder besitzen; bei `Unit` gibt es keinen Binder. Fallzweige
werden in der kanonischen Form nach dem qualifizierten Konstruktor sortiert,
ohne die Auswertungsreihenfolge eines Zweigs zu verändern. Wildcards und
mehrfach passende Muster sind verboten.

## 3. Statische Semantik

Die Kernurteile lauten `Σ ⊢ τ type` und `Σ; Γ ⊢ e : τ`. `Σ` ist die geprüfte
Symboltabelle; `Γ` ist ein Tupel von de-Bruijn-Typen, dessen Ende Index `0`
bezeichnet. Ein öffentliches `fn` muss zusätzlich eine explizite Parameter- und
Ergebnistypisierung besitzen; lokale Inferenz darf diese Deklaration nicht
ersetzen.

### 3.1 Grundregeln

```text
-------------------  (T-Var)
Σ; Γ, τ ⊢ var 0 : τ

Σ; Γ ⊢ e1 : τ1     Σ; Γ, τ1 ⊢ e2 : τ2
-----------------------------------------  (T-Let)
Σ; Γ ⊢ (let e1 e2) : τ2

Σ; Γ ⊢ c : Bool   Σ; Γ ⊢ e1 : τ   Σ; Γ ⊢ e2 : τ
------------------------------------------------  (T-If)
Σ; Γ ⊢ (if c e1 e2) : τ
```

Für Literale gilt `Int`, `Bool` beziehungsweise `Unit`. `Nat` wird nicht aus
einem beliebigen `Int`-Literal erraten; ein Nat-Literal wird explizit als
`(nat-literal digits)` geschrieben. Implementierungen dürfen dafür die
kanonische Kurzform `(nat digits)` akzeptieren, müssen sie aber in dieselbe
interne Form überführen. Ein negatives Nat-Literal ist ein `E_A1_NAT`-Fehler.

### 3.2 Nominale Records

Sei `fields(R) = {f_i : τ_i}`. Dann gilt:

```text
∀i. Σ; Γ ⊢ e_i : τ_i     fields(make) = fields(R)
-------------------------------------------------  (T-Record-Make)
Σ; Γ ⊢ record.make R {f_i=e_i} : R

Σ; Γ ⊢ e : R     field(R, f) = τ
--------------------------------  (T-Record-Get)
Σ; Γ ⊢ record.get R f e : τ
```

Die Gleichheitszeichen in den Regeln sind exakte, nominale Typidentität; es
gibt keine strukturelle Subtypisierung von Records. Ein `Nat` darf an einer
Stelle erwartet werden, an der `Int` erwartet wird (Refinement-Elimination),
aber ein `Int` darf nie implizit als `Nat` verwendet werden.

### 3.3 Varianten und vollständiges `match`

Sei `ctors(V) = {c_i : payload_i}`. Für einen Konstruktor ohne Payload gilt
`variant.make V c : V`; mit Payload `e` gilt zusätzlich
`Σ; Γ ⊢ e : payload_c`.

```text
Σ; Γ ⊢ s : V
∀c ∈ ctors(V). Σ; Γ, payload(c) ⊢ branch(c) : τ
branches = ctors(V), jeweils genau einmal
----------------------------------------------------  (T-Match)
Σ; Γ ⊢ match s {c => branch(c)} : τ
```

Bei einer Unit-Nutzlast wird `Γ` nicht erweitert. Ein fehlender Konstruktor,
ein unbekannter Konstruktor, ein Duplikat oder ein Branch mit abweichendem
Ergebnistyp wird abgelehnt. Diese Regel gilt transitiv für `Option` und
`Result`; sie haben keine impliziten `null`-, Ausnahme- oder Defaultpfade.

### 3.4 `Option` und `Result` als gewöhnliche Varianten

Unter den Prelude-Definitionen folgen unmittelbar:

```text
Option<T> = none(Unit) | some(T)
Result<T,E> = ok(T) | err(E)
```

Somit sind etwa `(variant.make (Option customer) none)` und
`(variant.make (Result booking-state booking-error) err e)` gewöhnliche
Konstruktionen. Der Checker darf für Diagnosekomfort Kürzel wie `none`, `some`,
`ok` und `err` ausgeben, darf aber keine Sondersemantik einführen.

### 3.5 `Nat`-Refinement

Die semantische Definition lautet:

```text
Nat = { n : Int | 0 <= n }
```

Der erste Kern erlaubt genau diese eingebaute Refinement-Definition. Beliebige
Prädikate, Refinement-Abstraktionen, abhängige Rückgabetypen und von Werten
abhängige Feldtypen sind nicht Teil von A1. `nat.from-int : Int -> Result Nat NatError`
ist eine Prelude-Funktion mit einem geprüften Decoder; ein Cast ersetzt die
Prüfung nicht.

Für die struktur-erhaltenden arithmetischen Regeln gilt:

```text
Γ ⊢ a : Nat   Γ ⊢ b : Nat
-------------------------  (T-Nat-Add)
Γ ⊢ int.add a b : Nat

Γ ⊢ a : Nat   Γ ⊢ b : Nat
-------------------------  (T-Nat-Mul)
Γ ⊢ int.mul a b : Nat

Γ ⊢ a : Int   Γ ⊢ b : Int
-------------------------  (T-Int-Sub)
Γ ⊢ int.sub a b : Int
```

`int.sub Nat Nat` liefert also **nicht** automatisch `Nat`. Eine Nat-Resultat-
Anforderung muss über `nat.from-int`/eine explizite geprüfte Bibliotheksfunktion
oder einen vom Checker akzeptierten, benannten Beweisweg erfüllt werden. Ein
externer Decoder darf bei einer negativen Eingabe nur einen `Result`-Fehler
liefern und keine ungültige Nat-Instanz erzeugen.

## 4. Auswertung und Laufzeitvertrag

Records sind Werte; ihre Felder werden in kanonischer Feldreihenfolge erzeugt
und gelesen. `if` wertet nur den gewählten Zweig aus. `let` ist strikt. Die
Argumente eines Aufrufs werden links nach rechts ausgewertet. Die alten P0-
Regeln für eager `and`/`or` gelten unverändert, falls diese Operatoren in einem
A1-Unterprofil angeboten werden.

Der Referenzinterpreter und der IR-Lowerer müssen dieselbe nominale Tag-
Repräsentation, dieselbe Konstruktor-Disjunktheit und denselben Fehlerweg
verwenden. Die Zielrepräsentation ist ein Implementierungsdetail, solange sie
vor dem Hostausgang validiert wird. Große `Int`-Werte bleiben als exakte
Dezimalstrings im Wirecodec; sie dürfen nicht über JSON- oder JS-Floats laufen.

## 5. Kanonisierung und stabile Diagnosen

Die semantische Kanonisierung entfernt Whitespace, sortiert Typdeklarationen
nach voll qualifiziertem Namen, Felder/Konstruktoren nach Namen und Matchfälle
nach Konstruktor. Parameter- und Branchkörperreihenfolgen bleiben erhalten.
Integer werden ohne `+`, führende Nullen oder `-0` serialisiert. Die
Kanonisierung MUSS idempotent sein. Hashbytes sind UTF-8 von
`a1:source\0` gefolgt von der kanonischen Form; Rohquell-Whitespace und
Dateipfade sind nicht Bestandteil.

Die Diagnose bleibt `diagnostic-v1` mit `schema`, `phase`, `code`, `message`,
`path`, `span` und `symbol`. Für A1 sind mindestens diese Codes stabil:

| Code | Bedeutung |
| --- | --- |
| `E_A1_PARSE` | Form, Token oder Profil ungültig |
| `E_A1_NAME` | unbekannter oder doppelt deklarierter Name |
| `E_A1_TYPE` | unbekannter, falsch angewendeter oder inkompatibler Typ |
| `E_A1_FIELD` | Recordfeld fehlt, extra, doppelt oder falsch typisiert |
| `E_A1_VARIANT` | unbekannter/falsch angewendeter Konstruktor |
| `E_A1_MATCH` | Match nicht vollständig, doppelt oder mit falschem Binder |
| `E_A1_BINDING` | Variable außerhalb ihres de-Bruijn-Kontexts |
| `E_A1_NAT` | nicht nachgewiesene oder negative Nat-Verfeinerung |
| `E_A1_CALL` | Aufruf-/Signaturfehler; Details in A1-GENERICS |
| `E_LIMIT` | parser-/checker-/Ausgabebudget erschöpft |

`path` ist eine stabile AST-Pfadfolge nach dem P0-Prinzip; `span` ist null,
wenn kein zuverlässiger Unicode-Quellspan vorhanden ist. Verbraucher dürfen
Meldungstexte und unbekannte additive Felder nicht als Schlüssel verwenden.

## 6. RED/GREEN-Abnahmematrix für #17

| Fall | Erwartung | Beleg/Gate |
| --- | --- | --- |
| Feld mit falschem Typ | RED `E_A1_FIELD` | Typprüfung vor Auswertung |
| `customer-id` an `booking-id`-Parameter | RED `E_A1_TYPE` | nominale Signaturprüfung |
| Record mit fehlendem/extra Feld | RED `E_A1_FIELD` | exakte Feldmengenprüfung |
| Konstruktor aus anderer Variante | RED `E_A1_VARIANT` | nominale Tagprüfung |
| doppelte Konstruktoren/Felder | RED `E_A1_NAME` | Symboltabellenprüfung |
| fehlender `match`-Fall | RED `E_A1_MATCH` | vollständige Konstruktorabdeckung |
| doppelter/default/wildcard-Fall | RED `E_A1_MATCH` | genau-einmal-Abdeckung |
| `Option`/`Result`-Kürzel mit eigener Sonderlogik | RED `E_A1_TYPE` | Prelude muss allgemeine Regeln nutzen |
| negatives `Nat`-Literal oder ungeprüfter Int→Nat-Cast | RED `E_A1_NAT` | Refinement-Decoder |
| zwei nominal gleiche Records in anderer Modulauflösung | RED `E_A1_TYPE` | qname-/Packagebindung |
| korrekt typisierter Record | GREEN | Konstruktion, Projektion, Roundtrip |
| jeder Variantkonstruktor mit passender Payload | GREEN | Konstruktion und Match |
| vollständiger Match über eigene Variante | GREEN | alle Zweige, gleicher Ergebnistyp |
| `Option<T>` als `none|some(T)` | GREEN | allgemeine Variantregeln |
| `Result<T,E>` als `ok|err(E)` | GREEN | allgemeine Variantregeln |
| `Nat`-Add zweier nichtnegativer Werte | GREEN | exakte Ausführung/Refinement |
| Mutation von Feldtyp, Tag oder Branch | RED | Source-/IR-Hashbindung und Negativtest |

Ein GREEN-Ergebnis beweist zunächst Parsing, statische Struktur und
Referenzausführung. Es ist kein automatischer Vertrags- oder Target-
Übersetzungsbeweis.

## 7. Vertrag mit dem IR-Worker (offen zu integrieren)

Der IR-Worker muss vor seiner Implementierung schriftlich bestätigen:

1. Jede IR-Value trägt eine aufgelöste nominale `type_id`; Recordfeldnamen und
   Varianttags sind keine frei interpretierbaren Strings.
2. `record.make`, `record.get`, `variant.make` und `match` werden als eigene,
   typisierte IR-Knoten mit expliziter Feld-/Konstruktorliste ausgegeben.
3. Die Matchliste enthält jeden Konstruktor genau einmal; der Worker darf keinen
   impliziten Defaultzweig ergänzen.
4. `Nat` trägt entweder den Refinementstatus aus dem geprüften Decoder oder
   einen expliziten `Result`-Fehlerweg. Der Worker darf eine Int→Nat-Prüfung
   nicht entfernen.
5. Auswertungsreihenfolge, exakte Integerwerte und Fehlerbehandlung werden bei
   Lowering und Zielausführung erhalten.
6. Der IR-Hash bindet kanonische A1-Quelle, Prelude-/Checker-Version,
   nominale Symboltabelle und Target-ABI. Ein generischer ungetypter JSON-AST
   ist kein dauerhafter Vertrag.

Offen sind die konkrete EIR-Tagcodierung und das Targetcodec-Format. Sie dürfen
die oben genannten Invarianten nicht abschwächen und werden als separater
`a1-ir-v1`-Vertrag mit eigenem Hash festgelegt.
