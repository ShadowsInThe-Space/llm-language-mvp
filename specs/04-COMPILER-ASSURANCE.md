# 04 — Compiler, Kernel und Assurance

## 1. Pipeline

```text
Canonical Source
  -> parse
  -> elaborate
  -> Proof Core
  -> kernel check
  -> erase proofs
  -> Execution IR
  -> optimize + certificates
  -> target lowering + validation
  -> sealed artifact
```

Jede Stufe produziert ein content-addressed Artefakt. Ein späterer Schritt darf niemals stillschweigend eine frühere Spezifikation, Annahme oder Toolchain-Version ersetzen.

## 2. Trusted Computing Base

Die angestrebte TCB umfasst nur:

- Proof-Kernel;
- Parser der kanonischen Kernelrepräsentation;
- Hash- und Signaturprimitiven;
- formale Target-Semantik beziehungsweise deren validierte Verbindung zur Hardware;
- minimale Artefaktprüfung und Loader-Komponenten.

LLMs, Orchestrator, SMT-Solver, Optimierer, Package-Resolver und Build-UI gehören nicht zur TCB.

## 3. Kernel

Der Referenzkernel SOLL klein genug sein, um unabhängig mehrfach implementiert und auditiert zu werden. Er MUSS:

- vollständig deterministisch sein;
- keine Netzwerk- oder Umgebungsabhängigkeit besitzen;
- Ressourcenlimits akzeptieren;
- jeden Fehler mit stabilem Code und Proof-Pfad melden;
- dieselbe Eingabe versionsgebunden identisch entscheiden.

Für A4 SOLLEN mindestens zwei diversitär implementierte Checker übereinstimmen.

## 4. Elaborator und Solver

Der Elaborator darf Komfortformen, Refinements und Taktiken in explizite Core-Terme übersetzen. Seine Korrektheit muss nicht vertraut werden, weil der resultierende Term erneut geprüft wird.

Solverausgaben ohne prüfbares Zertifikat gelten nur als Vorschläge. Timeouts, Solver-Crashes oder unterschiedliche Ergebnisse dürfen die Soundness nicht beeinflussen; sie führen höchstens zu `proof unavailable`.

## 5. Optimierungen

Eine Optimierung wird auf eine von zwei Arten zugelassen:

1. als bewiesene allgemeine Transformation; oder
2. durch Translation Validation für das konkrete Vorher/Nachher-Paar.

Zu validieren sind mindestens:

- Beobachtungsäquivalenz;
- Erhalt von Typ-, Effekt- und Ressourceninvarianten;
- Gültigkeit des Kostenvertrags, falls einer veröffentlicht wird;
- keine neu eingeführten Traps.

## 6. Bootstrap-Strategie

### Phase 0 — Spezifikation

Papiersemantik, Executable Model und Property-Tests werden gegeneinander geprüft.

### Phase 1 — Referenzimplementierung

Kernel, Parser und Compiler werden zunächst in einer speichersicheren etablierten Sprache implementiert. Diese Software-Fabrik-Komponenten werden strikt mit TDD, Fuzzing, Differential- und Property-Tests entwickelt.

### Phase 2 — Selbsthosting

Der Compiler wird in der neuen Sprache neu implementiert. Äquivalenztests und Bootstrapping-Reproduzierbarkeit vergleichen beide Implementierungen.

### Phase 3 — formaler Bootstrap

Kernel und kritische Compilerpässe erhalten maschinengeprüfte Korrektheitsbeweise. Tests bleiben als Defense-in-Depth und für nicht vollständig modellierte Systemgrenzen bestehen.

## 7. Release-Manifest

Jedes A4-Artefakt MUSS binden:

```text
source_hash
spec_hash
proof_hash
core_ir_hash
execution_ir_hash
binary_hash
compiler_hash
kernel_version
target_semantics_version
dependency_interface_hashes
assumptions
assurance_level
reproducibility_recipe
```

## 8. Reproduzierbarkeit

Builds sind hermetisch. Netzwerk, Uhrzeit, Zufall und lokale Dateisystemreihenfolge sind ohne explizite Inputs verboten. Ein A4-Build MUSS aus denselben Inputs dieselben kanonischen Zwischenartefakte und denselben Binärhash erzeugen oder eine explizit dokumentierte, semantisch validierte Nondeterminismusklasse besitzen.
