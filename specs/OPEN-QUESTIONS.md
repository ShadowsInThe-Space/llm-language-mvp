# Offene Entscheidungen nach v0.1

Diese Punkte sind bewusst noch nicht normativ festgelegt. Sie werden erst nach Prototypen, Benchmarks oder formaler Modellierung entschieden.

## Priorität P0 — für den Minimalkern nötig

1. **Core Calculus:** Calculus of Inductive Constructions, Quantitative Type Theory oder kleinerer abhängiger Lambda-Kalkül.
2. **Universen:** kumulativ oder explizit polymorph; konkrete Level-Syntax.
3. **Definitorische Gleichheit:** Normalization-by-Evaluation versus abstrakte Maschine.
4. **Induktive Typen:** Positivitäts-, Größen- und Terminierungsregeln.
5. **Effektrepräsentation:** algebraische Effekte, indexierte Monaden oder direktes Capability-Passing im Core.
6. **Kanonische Operatorliste:** Mnemonics, feste Stelligkeiten und Binary Encoding.
7. **Erstes Target:** formale VM als Referenz; zusätzlich Wasm oder RV64 als erster praktischer Backendpfad.

## Priorität P1 — für realistische Programme

1. Region- und Borrow-Modell inklusive asynchroner Lifetimes.
2. Session-Typen und strukturiertes Cancel-Verhalten.
3. Float-Semantik: IEEE-754 exakt, Intervalle, Rundungsmodi und NaN-Policy.
4. String-/Unicode-Semantik und normalisierte Textoperationen.
5. Separate Kompilierung bei abhängigen Typen.
6. Proof-Caching und inkrementelle Revalidierung.
7. Zertifikatformate für SMT, Bit-Vektoren und Optimierungen.
8. Sichere Package- und Interface-Evolution.

## Priorität P2 — Software-Fabrik und Optimierung

1. Agentenprotokoll für Spezifikation, Gegenbeispielsuche und Beweisreparatur.
2. Benchmark zur tatsächlichen LLM-Token- und Fehlereffizienz verschiedener Syntaxen.
3. Proof-Carrying Build Cache über mehrere Agenten und Maschinen.
4. Informationsfluss-Typen und Security Labels.
5. Probabilistische Programme und statistische Verträge.
6. Zertifizierte Foreign-Contract-Generatoren.

## Festlegungsregel

Eine offene Entscheidung wird nur geschlossen, wenn mindestens vorliegt:

- präzise Problemdefinition;
- zwei ernsthafte Alternativen;
- Auswirkungen auf Soundness, TCB, Tokenkosten und Laufzeit;
- kleines ausführbares Beispiel;
- Test- oder Beweisstrategie;
- dokumentierte Entscheidung in `Log.md`.
