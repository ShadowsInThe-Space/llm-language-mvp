# 03 — Operationelle Semantik und Laufzeit

## 1. Auswertungsmodell

Der reine Kern verwendet strikte Call-by-Value-Auswertung in definierter Links-nach-rechts-Reihenfolge. Compileroptimierungen dürfen die Reihenfolge nur verändern, wenn Beobachtungsäquivalenz bewiesen oder zertifiziert wird.

Nichtdeterminismus ist ausschließlich über den Effekt `Nondet` zulässig. Zeit, Zufall und I/O sind keine globalen Funktionen, sondern Operationen auf expliziten Capabilities.

## 2. Integerdomänen

Die Sprache trennt mathematische und maschinennahe Zahlen:

| Typ | Semantik |
| --- | --- |
| `Nat` | beliebig große natürliche Zahl |
| `Int` | beliebig große ganze Zahl |
| `U8…U128` | Maschineninteger mit festem Wertebereich |
| `I8…I128` | vorzeichenbehafteter Maschineninteger mit festem Wertebereich |

Operationen auf `Nat` und `Int` folgen mathematischer Arithmetik, begrenzt nur durch explizite Ressourcenbudgets. Maschineninteger dürfen niemals implizit überlaufen.

## 3. Arithmetikmodi

Für Maschineninteger existieren getrennte Operationen:

- `add.checked : I64 -> I64 -> Result I64 Overflow`
- `add.proved  : (a:I64) -> (b:I64) -> NoOverflowAdd a b -> I64`
- `add.wrap    : I64 -> I64 -> I64`
- `add.sat     : I64 -> I64 -> I64`

Dasselbe Muster gilt für Subtraktion und Multiplikation. Es gibt keinen kontextabhängigen globalen Arithmetikmodus. `wrap` und `sat` sind explizite, semantisch eigenständige Operationen.

Der Optimierer darf `checked` in eine ungeprüfte Maschinenoperation umwandeln, wenn er einen Kernel-prüfbaren `NoOverflow`-Beweis erzeugt.

## 4. Division und Rest

Division ist im Core nie implizit partiell.

```text
div.checked : I64 -> I64 -> Result I64 (DivZero | Overflow)
div.proved  : (a:I64) -> (b:I64) -> NonZero b
              -> Not(a = I64.MIN and b = -1) -> I64
```

Festlegungen:

- Division durch null liefert bei `div.checked` den Wert `Err DivZero`.
- `div.proved` kann nur kompiliert werden, wenn `b != 0` bewiesen ist.
- `I64.MIN / -1` liefert bei `div.checked` `Err Overflow`.
- Für `Int` ist `MIN / -1` irrelevant; nur der Nichtnull-Beweis ist nötig.
- Ein konstanter, falscher Beweisaufruf wird beim Kompilieren abgelehnt.
- Es gibt keinen versteckten Trap, Panic oder plattformabhängigen Quotienten.
- Die Rundungsrichtung der signierten Integerdivision ist `toward-zero`; `div-euclid` ist eine separate Operation.

## 5. Fehler

Erwartbare Fehler sind algebraische Daten (`Result`, Summentypen), keine Exceptions. Unmögliche Zustände werden über Typen ausgeschlossen.

Ein A2-Programm DARF nur dann terminieren, ohne seinen Rückgabetyp zu liefern, wenn dies durch einen deklarierten Effekt beschrieben ist, beispielsweise Prozessabbruch in einer Host-Shell. Der reine Core kennt keinen `panic`.

## 6. Speicher

Das abstrakte Modell besteht aus disjunkten Regionen und typisierten Speicherzellen. Jeder mutierende Zugriff benötigt eine einzigartige Capability für Zelle und Region.

Ziele:

- Use-after-free, Double-free und Data Races sind im typisierten Core nicht darstellbar;
- Bounds-Checks werden durch `Index n` bewiesen oder explizit als `Result` behandelt;
- Layout und Alignment werden im EIR explizit;
- Initialisierung ist ein typisierter Zustandsübergang;
- Pointerarithmetik existiert nur auf regionsgebundenen, bounds-bewiesenen Adressen.

Garbage Collection darf später als Target-Profil angeboten werden, ist aber kein semantisches Fundament.

## 7. Kostenmodell

Jede Target-Spezifikation MUSS ein versioniertes Kostenmodell für relevante Ressourcen definieren:

- Schritte oder Fuel;
- maximale Heap- und Stackbelegung;
- Allokationen;
- I/O-Mengen;
- optional Energie- oder Latenzbudgets.

Ein Budget ist ein linearer Capability-Wert. Eine Berechnung kann Ressourcen nicht verbrauchen, die ihr nicht übergeben wurden. Exakte Kostenbeweise sind optional; sichere obere Schranken sind ausreichend.

## 8. Nebenläufigkeit

Nebenläufigkeit ist strukturiert: Jeder Task gehört zu einem Scope, dessen Abschluss, Join oder Cancel typisiert wird. Verwaiste Tasks sind im Core nicht erlaubt.

Kommunikation erfolgt bevorzugt über lineare Channels mit Session-Typen. Ein Protokoll beschreibt erlaubte Sende-, Empfangs- und Abschlusszustände. Der Typzustand verhindert falsche Nachrichtenreihenfolgen und doppelte Channel-Nutzung.

Deterministische Parallelprogramme dürfen als rein gelten, wenn ihre Ergebnisrelation unabhängig vom Schedule bewiesen ist. Andernfalls ist `Nondet` sichtbar.

## 9. Fremdcode und Systemgrenzen

FFI-Aufrufe sind nur über `Foreign contract-id` zulässig. Ein FFI-Wrapper MUSS:

- ABI, Layout und Ownership beschreiben;
- Vor- und Nachbedingungen angeben;
- mögliche Fehler und Effekte deklarieren;
- die Vertrauensannahme in das Release-Manifest aufnehmen.

Ein Beweis über einen FFI-Aufruf beweist die Folgerung **unter Annahme des Foreign-Vertrags**, nicht die tatsächliche Implementierung des Fremdcodes. Diese Grenze muss im Assurance-Bericht sichtbar bleiben.
