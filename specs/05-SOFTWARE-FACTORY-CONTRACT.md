# 05 — Vertrag der autonomen Software-Fabrik

## 1. Rollen

| Rolle | Verantwortung | Vertrauensstatus |
| --- | --- | --- |
| Menschlicher Auftraggeber | Ziele, Prioritäten, reale Einschränkungen, Abnahme der Fachspezifikation | Quelle fachlicher Autorität |
| Chef-Orchestrator/Architekt | sokratische Spezifikation, Zerlegung, Risiko- und Beweisplanung | nicht für Soundness vertraut |
| Syntheseagenten | Code-, Vertrags- und Beweiskandidaten | nicht vertraut |
| Review-Agenten | Gegenbeispiele, Spezifikationslücken, alternative Beweise | nicht vertraut |
| Proof-Kernel | formale Akzeptanz von Typen und Beweisen | TCB |
| Build-Sealer | bindet geprüfte Artefakte und Annahmen | minimale TCB |

## 2. Spezifikation vor Synthese

Kein Feature darf direkt aus einer informellen Anweisung in Release-Code übergehen. Der Orchestrator erstellt zuerst:

1. fachliche Ziele und Nicht-Ziele;
2. beobachtbare Invarianten;
3. Eingabe-, Ausgabe- und Fehlerdomänen;
4. Sicherheits- und Autoritätsgrenzen;
5. Ressourcen- und Performancebudgets;
6. Beweisverpflichtungen;
7. explizite Annahmen und FFI-Grenzen;
8. Abnahmekriterien.

Der Mensch muss nicht zwischen technischen Mechanismen wählen, die er nicht beurteilen kann. Der Architekt setzt sichere Defaults, erklärt nur Entscheidungen mit relevanten Produktfolgen und eskaliert echte Zielkonflikte.

## 3. Sokratisches Gate

Der Orchestrator fragt nur dann nach, wenn mindestens eines gilt:

- zwei plausible Semantiken erzeugen sichtbar unterschiedliches Produktverhalten;
- eine Entscheidung verändert Kosten, Datenschutz, Sicherheit oder Rechtsfolgen wesentlich;
- die Fachdomäne enthält eine nicht ableitbare Priorität;
- eine Annahme kann nicht sicher gesetzt werden.

Reine Compiler-, Arithmetik-, Typ- oder Beweisdetails setzt der Architekt anhand der Projektprinzipien selbst.

## 4. Syntheseprotokoll

Jeder Arbeitsauftrag wird als versioniertes Paket verarbeitet:

```text
Intent
-> Formal Contract
-> Threat/Failure Model
-> Proof Obligations
-> Candidate Synthesis
-> Independent Counterexample Search
-> Kernel Check
-> Compile/Translation Validation
-> Artifact Seal
-> Human-visible Assurance Report
```

Agentenkonsens ist keine Akzeptanzbedingung. Ein einzelner korrekter Beweis genügt; hundert zustimmende Agenten ohne Beweis genügen nicht.

## 5. Beweisverpflichtungen pro Funktion

Standardmäßig werden mindestens geprüft:

- Typ- und Speichersicherheit;
- Erfüllung der Nachbedingung unter der Vorbedingung;
- vollständige Fehlerbehandlung;
- Ressourcen- und Capability-Nutzung;
- Terminierung für totale Funktionen;
- Abwesenheit nicht deklarierter Effekte;
- Erhaltung von Modul- und Dateninvarianten.

Zusätzliche Domänenbeweise können Vertraulichkeit, Integrität, Protokolltreue, Kostenobergrenzen oder Echtzeiteigenschaften umfassen.

## 6. Tests und Beweise

Für den Aufbau der Fabrik gilt TDD. Tests treiben Parser, Diagnostik, Integrationen, UX und den noch nicht formalisierten Bootstrap-Code.

Für erzeugte Programme gilt:

- Ein bewiesener Vertrag ersetzt klassische Unit-Tests für genau die bewiesene Eigenschaft.
- Tests sind kein Ersatz für einen fehlenden Beweis.
- System-, Hardware-, FFI-, Performance- und Spezifikationsvalidierung können weiterhin Tests oder Messungen benötigen.
- Ein A4-Release zeigt transparent, welche Teile bewiesen, getestet, angenommen oder ungeprüft sind.

## 7. Abbruch- und Reparaturregeln

Die Fabrik MUSS stoppen, wenn:

- der Kernel einen Beweis ablehnt;
- Spezifikation und Implementierung nicht dieselben Hashes referenzieren;
- eine Annahme unversioniert ist;
- ein Solver nur ein nicht prüfbares Ergebnis liefert;
- zwei Target-Validatoren widersprechen;
- ein Ressourcenbudget überschritten wird;
- ein Agent eine Capability außerhalb seines Auftrags anfordert.

Reparatur bedeutet neue Kandidatensynthese oder eine bewusst versionierte Spezifikationsänderung. Die Fabrik darf Anforderungen niemals stillschweigend abschwächen, um einen Beweis zu erhalten.

## 8. Audit-Trail

Jede Entscheidung erhält:

- stabile ID;
- Autor und Rolle;
- Zeitstempel;
- Eingabe- und Ausgabehashes;
- Begründung;
- verworfene Alternativen;
- betroffene Beweisverpflichtungen;
- Freigabestatus.

Dieser Trail ist Bestandteil des Projekts, aber nicht automatisch Bestandteil des ausführbaren Programms.
