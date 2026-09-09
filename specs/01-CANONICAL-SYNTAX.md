# 01 — Kanonische Syntax

## 1. Design

Das kanonische Format ist eine getypte Präfixsprache mit genau einer Baumsyntax. Es gibt keine Operatorpräzedenz, optionale Semikolons, signifikante Einrückung oder syntaktischen Zucker.

Die erste Version verwendet bewusst lesbare Mnemonics. Eine spätere Opcode-Kodierung darf nur als Transportformat eingeführt werden und MUSS verlustfrei zur kanonischen Textform zurückführen.

## 2. Lexikalische Regeln

- Der normative Zeichensatz ist ASCII/UTF-8; Schlüsselwörter und kanonische Bezeichner sind ASCII.
- Whitespace trennt Tokens, besitzt aber keine Semantik.
- Kommentare sind in Autorenquellen erlaubt, aber nicht Bestandteil der kanonischen Form.
- Lokale Binder werden bei der Kanonisierung in De-Bruijn-Indizes umgeschrieben.
- Globale Referenzen werden durch `(ref <module-hash> <decl-index>)` identifiziert. Namen sind nicht semantisch.
- Zahlen besitzen eine eindeutige Darstellung: Dezimal, kein führendes `+`, keine führenden Nullen außer `0`.
- Strings verwenden UTF-8 und eine einzige Escape-Tabelle. Unicode MUSS in NFC normalisiert werden.

## 3. Minimale Grammatik

```ebnf
file       = "(" "unit" version module-hash imports decls ")" ;
version    = atom ;
module-hash= atom ;
imports    = "(" "imports" { import } ")" ;
import     = "(" "import" module-hash interface-hash ")" ;
decls      = "(" "decls" { decl } ")" ;

decl       = data-decl | fn-decl | theorem-decl | effect-decl | foreign-decl ;
fn-decl    = "(" "fn" symbol params result effects contract term ")" ;
theorem-decl = "(" "theorem" symbol proposition proof ")" ;

params     = "(" "params" { "(" type multiplicity ")" } ")" ;
result     = "(" "result" type ")" ;
effects    = "(" "effects" { effect-ref } ")" ;
contract   = "(" "contract" requires ensures ")" ;
requires   = "(" "requires" proposition ")" ;
ensures    = "(" "ensures" proposition ")" ;

term       = atom | "(" operator { term } ")" ;
type       = term ;
proposition= term ;
proof      = term ;

atom       = identifier | integer | string | hash ;
multiplicity = "0" | "1" | "?" | "*" ;
```

`0` bedeutet erased, `1` linear, `?` affin und `*` uneingeschränkt. Die endgültige Grammatik MUSS jedem Operator eine feste Stelligkeit oder eine eindeutig terminierte Operandenliste zuordnen.

## 4. Kanonische Funktionsform

Beispiel einer bewiesenen Division von Maschinenintegers:

```lisp
(fn div-safe
  (params (I64 *) ((refine I64 (ne (var 0) 0)) *))
  (result I64)
  (effects)
  (contract
    (requires (not (and (eq (var 1) I64.MIN) (eq (var 0) -1))))
    (ensures (eq result (math.div (to-int (var 1)) (to-int (var 0))))))
  (i64.div.proved (var 1) (var 0) (proof 0) (proof 1)))
```

Namen wie `div-safe` bleiben im Autorenformat erhalten. Die kanonische Form ersetzt den lokalen Zugriff ausschließlich durch Indizes und globale Symbole durch gehashte Referenzen.

## 5. Normalform

Ein gültiges Dokument besitzt exakt eine kanonische Bytefolge. Der Normalisierer MUSS:

1. Kommentare und nicht-semantische Metadaten entfernen;
2. Whitespace normalisieren;
3. Binder in De-Bruijn-Indizes überführen;
4. Deklarationen in Abhängigkeitsreihenfolge sortieren;
5. numerische und String-Literale normalisieren;
6. vollständig qualifizierte Operatoren einsetzen;
7. eine Versions- und Interface-Hashbindung erzeugen.

Zwei Programme sind syntaktisch identisch, wenn ihre kanonischen Bytefolgen identisch sind. Semantische Äquivalenz ist eine separate, beweispflichtige Relation.

## 6. Verbotene Mehrdeutigkeit

Die Sprache DARF im Core nicht besitzen:

- Überladung anhand erwarteter Typen;
- kontextabhängige Schlüsselwörter;
- implizite Dereferenzierung;
- implizite Integerbreiten;
- implizite Imports oder Prelude-Namen;
- benutzergesteuerte Parser-Makros;
- editionsabhängige Semantik ohne Versionsheader.

## 7. Token- und Strukturkosten

Der Compiler SOLL für jede Deklaration folgende Metriken ausgeben:

- Anzahl lexikalischer Tokens;
- AST-Knoten;
- maximale Baumtiefe;
- Anzahl implizit elaborierter Beweisterme;
- Größe der kanonischen und binären Form.

Diese Metriken sind Optimierungsdaten, keine semantischen Eigenschaften. Änderungen an Mnemonics oder Encoding werden erst akzeptiert, wenn sie auf repräsentativen Agentenaufgaben weniger Gesamtfehler oder geringere End-to-End-Kosten zeigen.
