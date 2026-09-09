# 06 — P0-Präzisierungen nach Architekturreview

**Stand:** 2026-09-08 · `p0-review-draft-1` · Entwurfsregeln, nicht implementiert.

Dieses Dokument präzisiert den [MVP-Vorschlag](https://app.notion.com/p/3d52a8c323a2819687a1c1e385f9e6f8) und D-011 bis D-016. Bei Widersprüchen gelten für P0 diese Regeln vor dem älteren MVP-Vorschlag und vor v0.1. Die vollständige Zielsprache bleibt Forschungsentwurf; P0 implementiert weder deren abhängige Typentheorie noch A3/A4. Der [Reviewbericht](../REVIEW-2026-09-08.md) erklärt Befunde und Diskussion.

## 1. Umfang und verbindliche Aussage

P0 bleibt ein CLI mit `Bool`, mathematischem `Int`, reinen Ausdrücken, `let`, `if`, nichtrekursiven Funktionen und quantorenfreien linearen Verträgen. Addition, Subtraktion und Multiplikation mit einer syntaktischen Integerkonstante sind erlaubt. Keine Division, variablen Produkte, Imports, Effekte, Ressourcenwerte, Rekursion, Corekursion oder benutzerdefinierten Axiome.

Der Nachweis bezieht sich auf den autorisierten Contract-AST und exakt den geprüften Core:

```text
für jede öffentliche Funktion f und jeden typkorrekten Input x:
  requires_f(x) => ensures_f(x, eval_P0(core, f, x))
zusätzlich unter derselben Einstiegsvorbedingung:
  alle tatsächlich erreichten Aufrufe erfüllen ihre Vorbedingungen.
```

Abstrakte Terminierung folgt aus endlichen Termen und streng absteigenden Deklarationsindizes bei Aufrufen. Damit ist weder die Implementierung des Checkers bewiesen noch eine erfolgreiche Ausführung mit endlichem physischem Speicher garantiert.

## 2. Spezifikationsbindung und TCB

Ein Auftrag friert vor Synthese Profilversion, geordnete Signaturen, Parameterreihenfolge, Ergebnistypen und alle Verträge als kanonische Bytes ein. Der kleine vertrauenswürdige Parser und Typprüfer rekonstruiert diese Daten selbst. Der Kandidat DARF nur erlaubte Funktionskörper und Zertifikate liefern. Doppelte, unbekannte oder überschreibende Vertragsfelder werden abgewiesen.

Eine gültige Herleitung für einen vom Kandidaten ersetzten Vertrag zählt niemals. Der Checker erzeugt seine Verpflichtungen selbst aus der eingefrorenen Baseline und dem geprüften Core. Ein Solver darf keine zusätzliche Prämisse, Vertragsannahme oder Verpflichtung einschleusen. Die Auswahl des freigegebenen Baseline-Hashes stammt aus dem Auftraggeberprozess, niemals aus der Kandidatenantwort.

Der Formalisierungsschritt von menschlicher Absicht zum autorisierten Contract-AST bleibt eine sichtbare Spezifikationsgrenze. Eine generative Übersetzung von Autorentext in andere Verträge ist kein durch bloße Kernelprüfung abgesicherter Schritt. Bis zu einer separat geprüften Source→Core-Brücke gilt die Garantie ausdrücklich für den autorisierten Core-Vertrag.

Zur P0-TCB gehören Parser/Decoder, Typ- und Bindungsprüfung, Verpflichtungsrekonstruktion inklusive Substitution und Zweigabdeckung, Zertifikatsprüfung, Baseline-/Artefaktbindung sowie deren verwendete exakte Arithmetik. Für die tatsächliche Ausführung kommen Interpreter, Eingabeadapter und Host-Runtime hinzu; Betriebssystem und Hardware sind Umgebungsannahmen. Python-Tests oder zwei zustimmende Agenten reduzieren diese Liste nicht automatisch.

## 3. Kanonisierung, Binder und Transport

- P0 erhält die autorisierte Deklarationsreihenfolge. Eine Funktion mit Index `j` darf nur Funktionen mit Index kleiner `j` aufrufen. Die allgemeine Sortierregel aus `01-CANONICAL-SYNTAX.md`, Abschnitt 5, gilt in P0 nicht. Kanonisch bedeutet eindeutig für einen geordneten AST, nicht identisch bei beliebiger Deklarationspermutation.
- Parameter stehen links nach rechts; `(var 0)` bezeichnet den letzten Parameter. `let` wertet den gebundenen Ausdruck im bisherigen Kontext aus und erweitert nur für seinen Körper den Kontext um Index 0. Bestehende Variablen verschieben sich dort um eins. Substitution ist capture-vermeidend.
- `result` ist nur in Nachbedingungen erlaubt und liegt in einem getrennten Ergebnisplatz. Es verschiebt keine Parameterindizes. In Vorbedingungen und Funktionskörpern ist es ungültig.
- `if` wertet erst die Bedingung und dann ausschließlich den ausgewählten Zweig aus. Boolesche `and`/`or` sind strikt binär und werten beide Operanden links nach rechts aus. Daher gelten Aufrufvorbedingungen auch für einen logisch entbehrlichen zweiten Operanden. Verträge dürfen in P0 keine Funktionsaufrufe enthalten.
- Namen sind diagnostische Metadaten. Semantische Referenzen verwenden ausschließlich geprüfte Indizes. Inhaltshashes schließen ihr eigenes Feld aus; Domäne, Profilversion und Inhalt werden eindeutig gerahmt. Hashes ersetzen weder Autorisierung noch Semantikerhaltung.
- Integerliterale sind kanonische Dezimalzahlen: `0` oder optionales Minus vor einer von null verschiedenen ersten Ziffer; kein `+`, `-0`, Exponent, Dezimalpunkt oder führende Null. P0 besitzt keine Stringwerte in der Programmiersprache.
- JSON transportiert Sprachwerte typisiert: `{"type":"Int","value":"9007199254740993"}` und `{"type":"Bool","value":true}`. Mathematische Integer werden niemals über Gleitkommazahlen dekodiert. Auch Gegenbeispiele, Literalwerte und Zertifikatszahlen bleiben exakt. Metadatenindizes und Budgets dürfen nur explizit begrenzte JSON-Zahlen sein.
- Rationale Zertifikatskoeffizienten werden als gekürzte Paare kanonischer Integerstrings dargestellt; Nenner strikt positiv, null als `0/1`. Negative Koeffizienten sind unzulässig. Duplicate JSON keys, nicht endliche Zahlen und unbekannte Tags werden abgewiesen.

Die Transportentscheidung folgt aus der begrenzten interoperablen Integerpräzision üblicher JSON-Empfänger; JSON selbst erzwingt keine beliebig genaue Zahlenimplementierung. Siehe [RFC 8259, Abschnitt 6](https://www.rfc-editor.org/rfc/rfc8259#section-6).

## 4. Zertifikatsumfang `cert-v0`

Die Zertifikatssprache prüft eine beschränkte Klasse linearer Widersprüche. Sie behauptet keine Vollständigkeit für quantorenfreie Integerarithmetik.

Der Checker rekonstruiert für jede Nachbedingung und jede Aufrufvorbedingung die Formel einer Verletzung. Er wertet den Core symbolisch aus und erzeugt alle relevanten booleschen Zweige selbst. Vollständige Expansion darf an einem expliziten Größenbudget scheitern; dann bleibt der Status `unverified`. Pfade werden nur durch einen geprüften Widerspruch oder eine vollständig ausgewertete boolesche Falschheit verworfen.

Erlaubte arithmetische Normalisierung:

```text
Ganzzahlige lineare Terme werden exakt zu a·x <= b gesammelt.
u < v     wird zu u - v <= -1, sofern u und v ganzzahlig sind.
u = v     wird zu u - v <= 0 UND v - u <= 0.
u != v    wird zu u < v ODER v < u.
```

Negationen und boolesche Verknüpfungen werden mit expliziten wahrheitserhaltenden Regeln verarbeitet. Alle Koeffizienten und Schranken der Zeilen bleiben ganzzahlig. Es gibt keine impliziten GCD-, floor- oder Integralschnitte und keine Rundung rationaler Zwischenausdrücke.

Für ein Blatt mit ausschließlich vom Checker erzeugten Zeilen `a_i·x <= b_i` enthält ein arithmetischer Beleg nichtnegative rationale Gewichte `lambda_i`. Der Checker prüft exakt:

```text
alle lambda_i >= 0
Summe_i lambda_i * a_i = Nullvektor
Summe_i lambda_i * b_i < 0
```

Aus den Prämissen würde dann `0 <= eine negative Zahl` folgen. Da nichtnegative Linearkombinationen die Ungleichungsrichtung erhalten, ist dieses Blatt unerfüllbar. Gleitkommatoleranzen sind verboten.

Ein Zertifikat liefert lediglich Bindungsdaten und Koeffizienten für die vom Checker identifizierten Blätter. Es darf keine eigenen Prämissen, neuen Split-Atome oder ausgelassenen Zweige definieren. Zweig-IDs binden Verpflichtung und deterministische Verzweigungsposition; jede erforderliche Blatt-ID muss genau einmal nachgewiesen sein. Rein boolesch widersprüchliche Blätter schließt der Checker selbst.

Beispiel eines linearen Schlusses, keine ausgeführte Implementierung:

```text
requested - available <= 0       (aus dem Minimum-Zweig)
available - requested <= -1      (aus dessen behaupteter Verletzung)
Gewichte 1, 1 ergeben 0 <= -1.
```

Bekannte Grenze: `2*x = 1` besitzt keine ganzzahlige Lösung, aber eine reelle Lösung. In `cert-v0` ohne zusätzliche Integer-Cuts und ohne neue Split-Atome kann die reelle Relaxation dieses positiven Gleichheitszweigs nicht geschlossen werden. Erwartet wird hier `domain_unknown`, nicht `contract_empty`. Freies Splitten bei `x <= 0` würde die Situation ändern und ist deshalb ausdrücklich außerhalb dieser Zertifikatsversion. Der Solver darf leistungsfähiger sein als der Checker; ein nicht rekonstruierbares `UNSAT` bleibt unzureichend.

## 5. Drei getrennte Statusachsen

| Achse | Zustände | Bedeutung |
| --- | --- | --- |
| Verifikation | `invalid`, `unverified`, `counterexample`, `proved` | Vertragserfüllung des gebundenen Core |
| Vertragsdomäne | `domain_nonempty`, `contract_empty`, `domain_unknown` | Existenz erlaubter Eingaben; je öffentlichem Einstieg |
| Ausführung | `not_run`, `returned`, `input_rejected`, `resource_exhausted`, `host_error` | Ergebnis eines konkreten Host-Laufs |

`domain_nonempty` verlangt einen typgeprüften, konkret gegen die Vorbedingung nachgerechneten Zeugen. `contract_empty` verlangt einen unabhängig geprüften Unerfüllbarkeitsbeleg für die Vorbedingung. Kein Zeuge, Timeout oder Solver-`unknown` ergibt nur `domain_unknown`.

`counterexample` verlangt einen typkorrekten, im Interpreter nachvollzogenen ganzzahligen bzw. booleschen Fall, der die Vorbedingung des öffentlichen Einstiegs erfüllt und anschließend entweder dessen Nachbedingung oder eine erreichte Aufrufvorbedingung verletzt. Beispielsweise ist `x=-1` bei `requires x>=0; body x; ensures result>=0` kein Gegenbeispiel, sondern eine unzulässige Eingabe. `proved` verlangt vollständig akzeptierte Verpflichtungen. Defekte Zertifikate, fehlende Blätter oder ausgeschöpfte Prüfbudgets liefern kein `proved`.

Ein Vertrag mit leerer Domäne kann logisch vakuos bewiesen sein; er zählt trotzdem nicht als erfolgreiche MVP-Demo. Dafür sind `proved`, `domain_nonempty`, ein substantiver Golden-Vertrag und die tatsächlich erfolgreiche Demonstrationsausführung nötig. Das Ausbleiben eines Laufes ändert einen bestehenden Core-Beweis nicht.

## 6. Unveränderliche Artefakte und Ressourcen

Prüfung und Ausführung verwenden dieselben unveränderlichen Core-Bytes bzw. denselben daraus geprüften AST. Ein Dateipfad oder ein vom Modell geliefertes `proved` reicht nicht. Änderungen an Profil, Signaturen, Vertrag, Körper oder Zertifikat invalidieren die zugehörige Akzeptanzbindung. Beim erneuten Laden wird erneut geprüft; ein persistenter Proof-Cache gehört nicht zu P0.

Modell- und Solverantworten sind Daten. Sie erhalten keinen ausführbaren Zugriff auf den Host, die Baseline oder den Prüfer. Der erste Modelladapter ist ein begrenzter Kandidatenlieferant. Eine Vertragsänderung ist ein gesonderter Spezifikationsvorgang außerhalb der Reparaturschleife, gemäß den vorhandenen Zuständigkeiten des Projekts.

Limits gelten vor bzw. während Dekodierung für Eingabebytes, Ziffernzahl, AST-Tiefe, expandierte Aufrufe, Zweigzahl, Zertifikatsgröße und Koeffizientenbitlänge. Deterministische Arbeitsbudgets gehören zur Prüfkonfiguration. Ein zusätzlicher Wallclock-Abbruch darf `unverified` bewirken und ist kein semantisches Urteil über den Kandidaten.

## 7. Abnahmefolge und verbleibende Spezifikationsarbeit

1. **Parser-Gate:** vollständige P0-Operator-/Stelligkeitstabelle, typisierte Grammatik, Container- und Hash-Byteformat fixieren; Binderregeln mit gültigen und ungültigen Beispielen abnehmen.
2. **Semantik-Gate:** Referenzinterpreter, Typregeln und symbolische Regeln pro Operator sowie Aufrufverpflichtungen spezifizieren. TDD, Property-Tests und unabhängige konkrete Gegenbeispielauswertung aufbauen.
3. **Beweis-Gate:** endliche Rewrite-Tabelle und `cert-v0`-Schema vollständig festhalten, Soundness der Regeln herleiten; manipulierte Gewichte, fremde Zeilen, fehlende Zweige, Contract-Austausch, falsche Binder und veraltete Bindungen als ablehnende Regressionen prüfen.
4. **Fabrik-Gate:** die zehn Golden-Verträge aus D-015 zu konkreten Fixtures mit Randfällen ausarbeiten; alle Referenzbelege prüfen. Erst danach einen Modelladapter und die budgetierte Reparatur anschließen.

Die Architekturentscheidungen sind damit präzisiert; die genannten Tabellen, Implementierungen und Tests sind noch zu erstellen. P0 ist bereit für diesen schrittweisen TDD-Bootstrap, nicht für eine Behauptung bereits bewiesener Sprach-Soundness oder Release-Assurance.
