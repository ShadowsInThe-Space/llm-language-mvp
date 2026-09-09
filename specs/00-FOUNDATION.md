# 00 — Fundament und Geltungsbereich

## 1. Status und normative Sprache

Dieses Dokument ist ein Entwurf. Die Schlüsselwörter **MUSS**, **DARF NICHT**, **SOLLTE**, **SOLLTE NICHT** und **DARF** sind normativ.

Ein Compiler darf ein Programm nur als `verified` kennzeichnen, wenn alle MUSS-Regeln der deklarierten Sprach- und Target-Version erfüllt sowie alle erforderlichen Beweise durch den Referenzkernel akzeptiert wurden.

## 2. Primäres Entwurfsziel

Die primäre Schnittstelle richtet sich an LLMs, Syntheseagenten und automatische Transformationssysteme. Menschliche Lesbarkeit ist nützlich, aber kein Optimierungsziel des kanonischen Formats.

Die Optimierungsreihenfolge lautet:

1. semantische Eindeutigkeit;
2. lokale maschinelle Prüfbarkeit;
3. geringe strukturelle Entropie und stabile Tokenmuster;
4. formale Korrektheit;
5. vorhersehbare Kosten;
6. Laufzeit- und Speicherleistung;
7. menschliche Bequemlichkeit.

Tokenkürze darf niemals Eindeutigkeit oder Beweisbarkeit verschlechtern.

## 3. Nicht-Ziele von v0.x

- eine ergonomische Allzwecksprache für manuelles Programmieren;
- vollständige Verifikation beliebiger Betriebssysteme, Hardware oder Fremdbibliotheken;
- automatische Erkennung einer fachlich falschen Spezifikation;
- unbeschränkte Metaprogrammierung oder textuelle Makros;
- unkontrolliertes `unsafe`;
- Quellkompatibilität mit bestehenden Sprachen.

## 4. Bedeutung von Korrektheit

Für ein Programm `p`, eine Spezifikation `S`, eine Semantik `⟦·⟧` und explizite Umgebungsannahmen `A` bedeutet `verified`:

```text
Kernel ⊢ proof : ∀ input. A(input) → S(input, ⟦p⟧(input))
```

Die Garantie ist konditional. Sie hängt von folgenden Elementen ab:

- Richtigkeit der formalen Spezifikation;
- Soundness des kleinen Proof-Kernels;
- Übereinstimmung von formaler und tatsächlicher Target-Semantik;
- Gültigkeit expliziter Hardware-, Runtime- und FFI-Annahmen.

Nicht formalisierte Erwartungen sind keine bewiesenen Eigenschaften.

## 5. Assurance-Stufen

| Stufe | Bezeichnung | Bedeutung |
| --- | --- | --- |
| A0 | `parsed` | Syntax und Struktur sind gültig. |
| A1 | `typed` | Typen, Ressourcen und Effekte sind gültig; kein vollständiger Funktionsbeweis. |
| A2 | `proved` | Verträge und Terminierung des Core-Programms sind bewiesen. |
| A3 | `validated` | Zusätzlich ist die konkrete Übersetzung zum Target validiert. |
| A4 | `sealed` | Artefakt, Spezifikation, Beweise, Toolchain und Annahmen sind content-addressed und reproduzierbar gebunden. |

Nur A2 oder höher DARF als formal verifiziert bezeichnet werden. A4 ist das Ziel für Software-Fabrik-Releases.

## 6. Sprachschichten

Die Architektur trennt genau drei Schichten:

1. **Canonical Source (CS):** einziges austauschbares, diffbares Autorenformat.
2. **Proof Core (PC):** minimaler dependently typed Calculus, den der Kernel prüft.
3. **Execution IR (EIR):** typisierte, explizit speicher- und maschinennahe Repräsentation.

Jede Übersetzung CS → PC MUSS deterministisch sein. PC → EIR MUSS entweder durch einen verifizierten Compiler erfolgen oder pro Build ein vom Kernel prüfbares Übersetzungszertifikat erzeugen.

## 7. Globale Invarianten

Ein akzeptiertes Core-Programm MUSS folgende Eigenschaften besitzen:

- keine ungebundenen Namen;
- keine impliziten Typkonvertierungen;
- keine implizite Operatorüberladung;
- keine versteckten Effekte;
- keine unbehandelten partiellen Operationen;
- keine Nutzung einer affinen Ressource nach Verbrauch;
- keine nicht nachgewiesene Rekursion in A2+;
- keine Abhängigkeit von nicht versionierten Modulen;
- deterministische Kanonisierung.

## 8. Vertrauensprinzip

Agenten, LLMs, Optimierer, SMT-Solver und externe Compiler gelten grundsätzlich als nicht vertrauenswürdig. Sie dürfen Kandidaten und Zertifikate erzeugen. Akzeptanzentscheidungen trifft ausschließlich ein kleiner deterministischer Checker.
