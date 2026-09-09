# 02 — Typ- und Beweissystem

## 1. Fundament

Der Proof Core basiert auf intensionaler abhängiger Typentheorie mit Curry-Howard-Korrespondenz. Propositionen sind Typen; ein Beweis ist ein Term dieses Typs.

Der Kern umfasst zunächst:

- kumulative Universen `Type 0`, `Type 1`, …;
- abhängige Funktionen `Pi`;
- abhängige Paare `Sigma`;
- induktive Datentypen und eliminierende Rekursion;
- propositionale Gleichheit `Eq`;
- leeren Typ `Never` und Einheitstyp `Unit`;
- Summentypen, Produkttypen und `Result`;
- Refinement-Typen als elaborierte Sigma-Typen;
- Multiplizitäten für erased, linear, affin und unrestricted.

Universumsprüfung MUSS Girard-artige Inkonsistenzen verhindern. Allgemeine Rekursion ist kein Bestandteil des totalen Proof Core.

## 2. Entscheidbare Prüfung

Der Kernel prüft Beweisterme, er sucht sie nicht. Definitorische Gleichheit wird durch eine deterministische, terminierende Normalisierungsstrategie entschieden.

Automatisierung DARF:

- Beweisterme konstruieren;
- SMT-, SAT- oder algebraische Solver verwenden;
- Lemmas auswählen;
- Programme und Verträge synthetisieren.

Das Ergebnis MUSS jedoch ein Kernel-prüfbarer Beweisterm oder ein auf einen kleinen zertifizierten Checker reduzierbares Zertifikat sein.

## 3. Totale Funktionen

Funktionen sind standardmäßig total. Rekursion wird nur akzeptiert, wenn mindestens eine der folgenden Formen vorliegt:

- strukturelle Rekursion auf einem induktiven Argument;
- wohlbegründete Rekursion mit explizitem Abnahmemaß;
- Co-Rekursion mit nachgewiesener Produktivität;
- explizite `Partial`-Berechnung außerhalb von A2.

`Partial`-Programme können typisiert werden, dürfen aber ohne zusätzliche liveness-spezifische Beweise nicht als total oder A2 markiert werden.

## 4. Verträge

Jede öffentliche Funktion MUSS einen Vertrag besitzen. `requires true` und `ensures true` sind zulässig, aber explizit.

Eine Funktion

```text
f : (x : A) ->{E} B
requires P(x)
ensures  Q(x, result)
```

wird im Proof Core sinngemäß zu:

```text
f : (x : A) -> (pre : P x) -> Effect E (Sigma B (Q x))
```

Vorbedingungen sind daher keine Kommentare. Der Aufrufer muss sie beweisen. Nachbedingungen werden vom Funktionskörper geliefert.

## 5. Refinements

`Refine A P` enthält einen Wert `a : A` und einen gelöschten Beweis `P(a)`. Beispiele:

```text
NonZero I64  := Refine I64 (lambda x. x != 0)
Index n      := Refine Nat (lambda i. i < n)
NonEmpty xs  := Refine (List A) (lambda xs. length xs > 0)
```

Beweise werden nach erfolgreicher Typprüfung gelöscht, sofern sie keine Laufzeitdaten beeinflussen.

## 6. Ressourcen und Ownership

Werte sind standardmäßig unveränderlich und `*`-nutzbar. Externe Ressourcen, Speicherregionen, Locks, Dateien, Sockets und Capabilities sind affin oder linear.

Invarianten:

- ein linearer Wert MUSS exakt einmal verbraucht werden;
- ein affiner Wert DARF höchstens einmal verbraucht werden;
- Alias und Mutation dürfen nicht gleichzeitig auf denselben Speicher zugreifen;
- Destruktoren für Ressourcen sind explizite, typisierte Operationen;
- ein Resource Leak ist bei linearen Ressourcen ein Typfehler.

Borrowing wird im Core nicht als Sonderregel behandelt, sondern über zeitlich indizierte Capabilities und Regionen elaboriert.

## 7. Effekte und Capabilities

Jeder Effekt erscheint in der Funktionssignatur. Eine leere Effektmenge bedeutet referenzielle Transparenz.

Vorgesehene Basiseffekte:

```text
IO, State region, Alloc region, Time, Random, Net endpoint,
Spawn scope, Nondet, Partial, Foreign contract-id
```

Effektberechtigung allein reicht nicht: privilegierte Operationen verlangen zusätzlich einen nicht fälschbaren Capability-Wert. Dadurch ist Autorität ein expliziter Datenfluss und global ambient authority ausgeschlossen.

## 8. Datenabstraktion

Module exportieren ausschließlich ein gehashtes Interface aus Typen, Signaturen, Verträgen und freigegebenen Theoremen. Implementierungsdetails sind nicht durch Namenskonventionen, sondern durch fehlende Konstruktor- oder Eliminatorrechte verborgen.

Ein Interface-Hash ändert sich bei jeder semantisch relevanten Vertragsänderung.

## 9. Proof Erasure

Terme mit Multiplizität `0` dürfen die Laufzeit nicht beeinflussen. Der Erasure-Checker MUSS beweisen, dass gelöschte Terme weder kontrollflussrelevante Informationen noch Ressourcen oder Effekte enthalten.

Nach Erasure bleibt ein typisiertes EIR-Programm. Die Erasure-Korrektheit ist ein eigener Satz:

```text
observable(PC-program) = observable(erase(PC-program))
```
