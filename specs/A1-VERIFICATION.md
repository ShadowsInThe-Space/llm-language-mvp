# A1-VERIFICATION — Checker, Evidenz und Referenzabnahme

**Status:** M2-Entwurf, normativer Vertrag für Issue #19 (2026-09-20).
Zusammen mit [A1-IR](A1-IR.md) definiert dieses Dokument die kleinste
implementierbare Verifikationsfläche. Es erweitert weder den P0-Checker
`cert-v0.1` noch behauptet es eine formale Verifikation der Python-TCB.

## 1. Aussagen und Statusachsen

Der Checker unterscheidet vier voneinander unabhängige Aussagen:

| Aussage | Erlaubte Werte | Bedeutung |
|---|---|---|
| Struktur | `invalid`, `checked` | IR ist nach den A1-Regeln wohlgeformt bzw. abgelehnt |
| Vertrag | `unverified`, `counterexample`, `proved` | gebundene `requires`/`ensures`- und Callpflichten |
| Lauf | `not_run`, `returned`, `input_rejected`, `resource_exhausted`, `precondition_failed`, `postcondition_failed`, `host_error` | ein konkreter Referenzlauf |
| Target | `not_checked`, `tested`, `validated` | gesonderte Zielausführung/Translation-Validation |

Nur die Kombination `structure=checked` und `contract=proved` darf im
Verifikationsbericht als `proved` zusammengefasst werden. `tested`, ein
Interpreter-Trace, ein Target-Typecheck, ein Solver-`unsat` oder ein vom
Kandidaten gesetztes `proved`-Feld darf diese Kombination niemals erzeugen.
Ein Ressourcenlimit, Timeout, unvollständige Evidenz oder unbekannte Theorie
ergibt `unverified`, nicht `proved`. Ein konkreter Fehlerlauf ergibt
`counterexample` nur, wenn die Eingangsvorbedingung erfüllt und der Lauf durch
den Referenzinterpreter reproduziert wurde.

Das Urteil bezieht sich ausschließlich auf den Hash des autorisierten A1-IR-
Dokuments und dessen Vertrag. Es beweist weder die fachliche Übersetzung der
Autorensprache in diese IR noch Codegenerator, Browser, Datenbank,
Authentifizierung, Betriebssystem oder Fremdverträge.

## 2. Checkergrenze und unveränderliche Eingabe

`check(document, evidence, limits)` liest einen unveränderlichen Snapshot:

1. strikter kanonischer JSON-Decoder (keine Duplicate Keys, keine Floats,
   keine unbekannten Pflichtobjektfelder);
2. Hash-/Versionsbindung nach `A1-IR.md`;
3. unabhängige Struktur-, Typ-, Effekt- und Bindungsprüfung;
4. deterministische Rekonstruktion aller Vertragsobligationen;
5. unabhängige Prüfung der angegebenen Evidenz gegen genau diese Obligationen;
6. abschließende kanonische Größen- und Vollständigkeitsprüfung.

Der Checker übernimmt keine Typen, Verträge, Pfadbedingungen, Zeilen oder
Obligations-IDs aus `evidence`. Er erzeugt sie selbst aus dem IR. Ein Solver
darf Kandidaten für Belege liefern, aber dessen Prämissen und Ergebnis werden
verworfen; nur die nachfolgend beschriebenen, vom Checker nachgerechneten
Regeln zählen.

## 3. Verifikationsformat

Ein akzeptiertes Dokument hat `schema="a1-evidence-v1"` und exakt folgende
semantische Felder:

```json
{
  "schema":"a1-evidence-v1",
  "ir_hash":"sha256-hex",
  "checker":"a1-check-v1",
  "rule_set":"a1-rules-v1",
  "limits": {"max_steps":1000000},
  "obligations": {"obligation-id": {
    "kind":"structural|linear_refutation|direct_value",
    "proof": {"...":"..."}
  }},
  "summaries": {"function-id": {
    "function_hash":"sha256-hex", "status":"proved",
    "summary_hash":"sha256-hex"
  }},
  "counterexamples": []
}
```

`limits` darf nur die tatsächlich verwendete, vom Auftrag autorisierte
Konfiguration binden; ein Kandidat darf ein strengeres Budget wählen, aber
keines erhöhen. Die Menge der `obligations` muss exakt der vom Checker
rekonstruierten Menge entsprechen: keine fehlende, zusätzliche oder doppelte
Pflicht. `summaries` werden nur für erfolgreich geprüfte Callees erzeugt und
enthalten kein frei erfundenes Prädikat. `counterexamples` sind Berichtsdaten,
keine alternative Beweisquelle; für ein positives Urteil ist die Liste leer.

## 4. Explizite Regelversion und Reihenfolge

`rule_set="a1-rules-v1"` bezeichnet die geschlossene Tabelle dieser Regeln.
Der Checker prüft in dieser stabilen Reihenfolge und meldet den ersten Fehler
nach `(Dokumentposition, Regelnummer, Pfad)`:

| Regel | Verpflichtung |
|---|---|
| `A1-S001` | Dokument, Version, IDs, Hash, Pflichtfelder und Limits |
| `A1-S002` | Typdeklarationen nominal, geschlossen und vollständig |
| `A1-S003` | Parameter-, Blockparameter-, Value- und Terminator-Bindungen |
| `A1-S004` | A-Normalnummern: jede Definition einmal, kein illegaler Vorwärtsverweis |
| `A1-S005` | Instruktionssignatur, exakte Operandentypen, Resultattyp |
| `A1-S006` | Records: Konstruktorfelder, Nominalität und Projektion |
| `A1-S007` | Varianten, `Option`/`Result`, disjunkte Konstruktoren |
| `A1-S008` | `match`/`switch_variant` vollständig und ohne Duplikat |
| `A1-S009` | Funktionssignatur, Callgraph, Ort und Effektteilmenge |
| `A1-S010` | Spezialisierung von Typ-/Kapazitätsparametern |
| `A1-S011` | Nat-Einführung und externe Refinementvalidierung |
| `A1-S012` | bounded map/fold, Callback, Reihenfolge und Kapazität |
| `A1-S013` | Vertragssyntax und reine Formelgrenze |
| `A1-C001` | strukturelle Vertragsidentität/Normalisierung |
| `A1-C002` | Pfadbedingung und callee-Precondition |
| `A1-C003` | callee-Postcondition und Summary-Bindung |
| `A1-C004` | generische Callback-/Spezialisierungszusammenfassung |
| `A1-C005` | Refinement- und Bounded-Iteration-Pflichten |
| `A1-C006` | exakt geprüfte lineare Widerlegung |

Es gibt keinen versteckten Fallback, der eine unbekannte Operation, ein
unbekanntes Prädikat oder eine unbekannte Evidenz als `proved` behandelt.

## 5. Strukturregeln (ohne Solver)

### 5.1 Bindung und A-Normalform — S001–S005

Der Checker zählt zuerst alle Kosten und prüft dann jede Definition in
Dokumentreihenfolge. IDs müssen in ihrer Funktion lückenlos `0..V-1` sein.
Parameter sind die ersten Definitionen. Ein Wert darf nur einen vorher
definierten Wert oder eine statische ID referenzieren. Ein Blockparameter darf
nur im eigenen Block und seinen Nachfolgern über die entsprechende Kante
verwendet werden. Ein Rückgabewert muss im dominierenden Block definiert sein;
uninitialisierte oder mutierte Werte existieren nicht.

Jede Instruktion wird anhand einer geschlossenen Signaturtabelle geprüft. Die
deklarierte `type`-, `effects`- und `location`-Angabe wird nicht inferiert und
darf der rekonstruierten Bedeutung nicht widersprechen. `shared` plus nicht
leere Effekte wird abgelehnt; Effektlisten müssen eine deklarierte Caller-
Obermenge besitzen. Ein nicht unterstütztes, aber syntaktisch beschriebenes
Hosteffektfeld kann strukturell `checked` sein, verhindert aber ein
vertragliches `proved`.

### 5.2 Records und Projektionen — S006

Für `record_make(T, f_0,...,f_n)` prüft der Checker nominale Record-ID,
Spezialisierung, Feldanzahl, feste Deklarationsreihenfolge und jeden Feldtyp.
Für `project(x, field)` muss der Typ von `x` genau der nominalen Record-ID
entsprechen und `field` genau einmal erklärt sein. Die strukturellen Regeln
erzeugen die überprüfbare Identität:

```text
project(record_make(T, f_0,...,f_n), field_i) = f_i
```

Nur diese Identität wird ohne weiteren Vertragsschritt angenommen. Eine
gleichnamige oder gleich geformte Fremdstruktur ist kein Beweis. Falscher
Feldtyp, fremde ID und veränderter Projektionstext sind `invalid` bzw. brechen
die Hashbindung.

### 5.3 Varianten und exhaustive match — S007–S008

`variant_make(V,C,payload)` benötigt eine deklarierte Konstruktor-ID `C` der
geschlossenen Variante `V`; Payload-Abwesenheit bzw. Payload-Typ muss exakt
passen. Konstruktoren derselben `V` sind disjunkt. `Option` und `Result` folgen
denselben Regeln wie jede andere Variante.

Eine `switch_variant` muss die vollständige deklarierte Konstruktorliste genau
einmal enthalten. Jeder Arm besitzt den passenden Payloadbinder und ein
wohlgetyptes Ziel. Ein Defaultarm, ein unbekannter Tag, ein fehlender Arm,
Duplikate oder ein unpassender Payload sind nie „unreachable“, sondern stabile
Fehler. Der Checker prüft alle Arme, auch wenn der Interpreter für eine
konkrete Eingabe nur einen Arm ausführt.

### 5.4 Calls und Callee-Summaries — S009/C002–C003

Der Callgraph wird aus statischen Funktions-IDs gebaut, topologisch sortiert und
auf Zyklen geprüft. Ein Call ist nur gültig, wenn Argumente und konkrete
Spezialisierung zur Signatur passen, der Caller die transitiven Effekte/Orte
zulässt und die `requires`-Pflicht des Callees unter der aktuellen
Pfadbedingung erfüllt ist.

Nach vollständiger Prüfung des Callees erzeugt der Checker:

```json
{
  "function_hash":"...", "specialization_hash":"...",
  "requires_hash":"...", "ensures_hash":"...",
  "effects":[], "location":"shared", "checker":"a1-check-v1",
  "status":"proved"
}
```

`summary_hash` ist der Hash dieser kanonischen Zusammenfassung. Ein Call darf
nur auf diese exakte Summary verweisen. Der Kandidat kann weder Summarystatus
noch Vertrag austauschen. Ein Summary-Cache ist ungültig, wenn irgendein
Körper-, Vertrags-, Typ-, Effekt-, Ort-, Spezial- oder Checkerfeld abweicht.

### 5.5 Generics und Nat — S010–S011/C004

Spezialisierungen werden vor der Vertragsprüfung erzeugt. Der Checker ersetzt
Typ- und Kapazitätsvariablen positionsgenau, prüft geschlossene Typen und
`0 <= capacity <= max_collection_capacity`, berechnet die kanonische
Spezialisierungs-ID und prüft die materialisierte Funktion erneut. Eine
unbenutzte Instanz wird nicht expandiert; eine benötigte Instanz darf nicht
fehlen. Die sortierte Instanzmenge und jedes `body_hash` sind Teil der
Evidenzbindung.

Für `refine_nat(x)` rekonstruiert der Checker die Pflicht `x >= 0`. Er akzeptiert
nur eine direkte strukturelle Folgerung (z. B. `const 0`, bereits geprüfter Nat-
Wert oder eine zugelassene Projektion) oder einen `A1-C006`-Beleg. `Int` wird
nicht implizit als `Nat` behandelt; Subtraktion zweier Nat-Werte gibt zunächst
Int. Decoder validieren dieselbe Bedingung zur Laufzeit.

### 5.6 Bounded map/fold — S012/C004–C005

Der Checker liest die statische Kapazität `N`, die Callback-Signatur und den
geprüften Callback-Summary-Hash. Für jeden potentiell ausgeführten Index
`i=0..N-1` erzeugt er eine Pflicht mit Pfadbedingung `i < length`. Für `map`
werden Resultattyp, Länge und Kapazität geprüft; für `fold` wird der Initwert
als Akkumulator verwendet. Die Regel ist leerlistenstabil und erhält die
Reihenfolge. Callback-Vor-/Nachbedingungen und `Nat`-Einführungen werden unter
jeder expandierten Bedingung erneut geprüft. Eine Schleife über einen
veränderlichen Hostcontainer, ein dynamischer Callback oder stille Kürzung ist
außerhalb A1.

## 6. Vertragsprüfung und Belegsprache

### 6.1 Strukturelle Vertragsregeln — C001

Verträge sind reine geschlossene Formeln mit `true`, `false`, `not`, `and`,
`or`, `eq`, `lt`, `le`, Konstruktor-/Projektionsidentitäten und exakten
linearen Ganzzahltermen. Freie Variablen, Effekte, Calls, Textnormalisierung,
beliebige Stringtheorie und nicht deklarierte Operatoren werden abgelehnt.

Der Checker normalisiert nur mit expliziten, wert-/wahrheitserhaltenden Regeln:

```text
project(record_make(...), field_i)  ->  field_i
eq(x,x)                             ->  true
and(true,p), or(false,p)            ->  p
not(not(p))                         ->  p
u < v                               ->  u - v <= -1   (Int/Nat)
u = v                               ->  (u-v<=0) and (v-u<=0)
```

Ein strukturell nach `false` reduzierter Pfad gilt als geschlossen. Jede andere
Pflicht bleibt offen und braucht einen überprüften Beleg oder liefert
`unverified`.

### 6.2 Lineare Widerlegung — C006

Ein `linear_refutation-v1`-Beleg enthält nur eine Liste kanonischer, gekürzter,
nichtnegativer rationaler Gewichte. Die Zeilen selbst rekonstruiert der
Checker aus genau einer Pflicht; Kandidaten dürfen keine Prämissen, Koeffizien-
tenzeilen, Splitpunkte oder Variablen hinzufügen:

```text
rows:  a_i · x <= b_i
weights: lambda_i >= 0
accept iff  Sum(lambda_i*a_i) = 0  and  Sum(lambda_i*b_i) < 0
```

Zähler/Nenner sind Dezimalstrings, Nenner positiv, Brüche gekürzt, alle
Zwischenergebnisse exakt. Eine fehlende Zeile, falsche Reihenfolge, negative
Gewichte, Rundung, fremde Obligation-ID oder ein nichtlinearer Term wird
abgelehnt. Das ist bewusst derselbe konservative Vertrauensstil wie
`cert-v0.1`; dieses Format ist kein vollständiger Entscheider für Integerlogik.

`int_mul` mit zwei variablen Faktoren, unbekannte Text-/Unicode-Theorien,
allgemeine Quantoren und Solver-Modelle haben in A1 keinen automatischen
Beweisweg. Ein Solver darf einen Belegvorschlag oder ein Gegenbeispiel liefern;
ohne die obige unabhängige Nachrechnung bleibt der Status `unverified`.

### 6.3 Preconditions, Ensures und Summaries

Für jede öffentliche Funktion rekonstruiert der Checker mindestens:

```text
O-pre  = requires(inputs) -> execution can call body
O-post = requires(inputs) -> ensures(inputs, returned_value)
```

Für jeden erreichbaren Call gibt es zusätzlich `O-call-<id>` mit der konkreten
Callee-Precondition. Bei jedem `bounded_map`/`fold` entstehen Callback-
Obligationen je expandiertem Schritt. Die vollständige Menge wird vor dem
Lesen der Evidenz erzeugt und lexikografisch nach Funktion, Block, Value und
Expansion geordnet. Eine Summary ist nur dann `proved`, wenn ihre eigenen
Pflichten sowie alle transitiven Summaries bewiesen sind.

## 7. Counterexample-v1

Ein Gegenbeispiel bleibt maschinenlesbar und bindet den reproduzierten Lauf:

```json
{
  "schema":"a1-counterexample-v1",
  "ir_hash":"...", "checker":"a1-check-v1",
  "entry":"booking/reserve", "obligation_id":"O-post-...",
  "kind":"precondition|postcondition|call_precondition|runtime",
  "inputs":[{"type":"Int","value":"7"}],
  "path":[{"block":0},{"value":4},{"call":"rules/check"}],
  "observed":{"type":"Int","value":"-1"},
  "expected":{"op":"ge","left":{"result":true},"right":{"int":"0"}},
  "diagnostic":{"code":"A1_E_CONTRACT","path":["functions",0]}
}
```

Der Checker akzeptiert es nur, wenn `inputs` typkorrekt sind, `requires` wahr
ist, die Referenzmaschine denselben Pfad deterministisch ausführt und
`observed`/`expected` die benannte Pflicht tatsächlich verletzen. Ein
unzulässiger Input, ein erfundener Trace, ein Ergebnis aus einem anderen
`ir_hash` oder ein Solver-only-Gegenbeispiel ist kein A1-Gegenbeispiel.

## 8. Stable Diagnostics

Jede Ablehnung verwendet das bestehende additive Envelope `diagnostic-v1` und
einen der folgenden stabilen Codes. `phase` wird wie in
`src/llmlang/diagnostics.py` aus dem Code abgeleitet; freie Fehlermeldungen
ändern nicht Code oder Pfad:

| Code | Bedeutung |
|---|---|
| `A1_E_VERSION` | unbekannte/fehlende Format-, Profil-, Checker- oder Regelversion |
| `A1_E_JSON` | nichtkanonisches JSON, Duplicate Key, Float oder unbekannter Schlüssel |
| `A1_E_HASH` | IR-, Summary- oder Evidence-Hash stimmt nicht |
| `A1_E_TYPE` | falscher Typ, Konstruktor, Feld, Operand oder Resultat |
| `A1_E_BINDING` | Value-/Block-/Function-Referenz, Vorwärtsverweis oder Spezialisierung falsch |
| `A1_E_CONTROL` | ungültiger Terminator, CFG-Kante, Zyklus oder fehlender Matcharm |
| `A1_E_EFFECT` | Ort-/Effekt-/Capability-Vertrag verletzt |
| `A1_E_CONTRACT` | offene, verletzte oder unzulässige Vertragsformel |
| `A1_E_EVIDENCE` | fehlende, zusätzliche, manipulierte oder falsch gewichtete Evidenz |
| `A1_E_COUNTEREXAMPLE` | Gegenbeispiel nicht durch den Interpreter reproduzierbar |
| `A1_E_LIMIT` | deterministisches strukturelles Budget überschritten |
| `A1_E_RESOURCE` | Laufzeit-/Beweis-/Evidenzbudget erschöpft |
| `A1_E_HOST` | explizite Capability oder Hostimplementierung fehlt |

`path` ist eine kanonische Liste aus Strings und begrenzten Integersegmenten,
beispielsweise `['functions','booking/reserve','blocks',0,'values',4]`.
Keine absolute Datei, Speicheradresse, Zeit oder zufällige ID darf den Pfad
beeinflussen. Diagnosen werden in der oben genannten Regelreihenfolge erzeugt;
bei gleichrangigen Fehlern entscheidet die kanonische Arrayposition.

## 9. Referenzinterpreter ist keine Beweisinstanz

Der Interpreter aus `A1-IR.md` darf für drei Zwecke verwendet werden:

1. konkrete Ausführung und Inputvalidierung;
2. reproduzierbare Counterexamples;
3. Differentialtests gegen ein Target.

Er darf keine fehlende strukturelle Regel ersetzen. Ein erfolgreicher Lauf
beweist keine Universalquantifizierung über andere Inputs; ein fehlgeschlagener
Lauf beweist keine falsche Vertragssemantik ohne gültige Eingabebindung. Der
Checker und der Interpreter müssen dieselbe kanonische IR lesen, bleiben aber
getrennte Implementierungsrollen. Tests erhöhen die Evidenz, nicht die
Vertrauensklasse.

## 10. RED/GREEN-Abnahme für #17–#20/#31

### RED zuerst

Vor der Implementierung müssen fokussierte Tests die folgenden Fälle ablehnen:

- Record-Projektion über fremde nominale ID oder falschen Feldtyp;
- unbekannter/duplizierter Variantentag und nicht-exhaustives `match`;
- Call mit falschem Callback, falscher Summary oder verletzter Precondition;
- generische Instanz mit freiem Typparameter, negativer Kapazität, Duplikat
  oder nichtdeterministischer Reihenfolge;
- `Int` ohne geprüfte `x >= 0`-Einführung als `Nat`;
- `bounded_map`/`fold` mit dynamischem Callback, falscher Kapazität,
  übersprungener Länge oder erschöpftem Expansionsbudget;
- fehlende/zusätzliche Obligation, fremde Prämisse, manipuliertes Gewicht,
  veralteter Hash oder Solver-only-`unsat`;
- falscher Counterexample-Input, Trace oder `observed`-Wert.

Jeder RED-Fall muss seinen stabilen Code und den stabilen Pfad prüfen, nicht nur
eine Exception oder einen Textvergleich.

### GREEN danach

Die integrierte Abnahme verlangt mindestens:

1. zwei verschiedene Consumer (z. B. Booking und CRM) verwenden dieselbe
   generische `map`-/`fold`-Bibliothek mit mindestens zwei Recordtypen und zwei
   Kapazitäten;
2. ein vollständiger Lauf kombiniert Records, Varianten, Option/Result, Nat,
   leere/volle Listen und mehrbyteigen Unicode-Text;
3. der Checker erzeugt für jeden Call, jeden Matcharm, jede Refinement- und
   jede Bounded-Iteration-Pflicht eine vollständige Evidenzmenge;
4. der Referenzinterpreter liefert deterministische Resultate und reproduziert
   mindestens ein gültiges maschinenlesbares Gegenbeispiel;
5. Hashes ändern sich bei Feld-, Tag-, Vertrag-, Körper-, Effekt-, Ort- oder
   Spezialisierungsänderung; Whitespace/Provenienz außerhalb des Hashes ändert
   die Semantik nicht;
6. P0/w1/w2/pkg1-Regressions-, Installations- und Releaseprüfungen bleiben
   grün. Ihre bisherigen Belege werden nicht in A1-Belege umetikettiert.

Property-Tests sollen zusätzlich capture-vermeidende Spezialisierung,
Projection/Constructor-Identitäten, Matchabdeckung, deterministische
Kanonisierung, Listen-/Textgrenzen und mutierte Evidenz abdecken. Das sind
entscheidende RED/GREEN-Sicherungen, aber weder ein Beweis des Checkers noch
eine Ersetzung der unabhängigen Regelprüfung.

## 11. Assurance- und Targetgrenze

Die A1-Abnahme darf drei Artefakte separat ausweisen:

```text
structural_checked   = IR-Regeln bestanden
contract_proved      = A1-Evidenz vollständig und unabhängig geprüft
reference_tested     = konkrete Interpreterfälle bestanden
target_differential  = konkrete Ziel-/Referenzfälle gleich
```

`contract_proved` setzt `structural_checked` voraus, aber weder
`reference_tested` noch `target_differential`. Umgekehrt macht ein bestandenes
Target-Differential keinen Vertrag `proved`. Eine spätere Translation
Validation muss Quell-IR, tatsächlich gelesene Ziel-IR/Bytes und ihre eigene
Regelversion binden; ein Hashvergleich zweier vom selben Emitter behaupteter
IRs genügt nicht.
