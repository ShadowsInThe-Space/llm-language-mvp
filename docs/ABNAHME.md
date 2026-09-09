# MVP P0 v0.2.0 — Abnahme vom 2026-09-08

Die Definition of Done ist erfüllt: Ein realer Session-Agent hat das erste
Hello-World-Programm in der neuen Sprache geschrieben. Der unabhängige Checker
hat den festen Vertrag akzeptiert; der Referenzinterpreter hat das Programm ausgeführt.

```text
Hello World
```

## Tatsächlich ausgeführte Gates

| Gate | Ergebnis |
| --- | --- |
| Gesamte Testsuite | 178 Tests bestanden, 8,65 Sekunden |
| Ruff für Source, Tests und Demo | Alle Prüfungen bestanden |
| Strenge mypy-Typprüfung | Keine Befunde in 12 Quelldateien |
| Golden Programs | 10 von 10 mit akzeptiertem Beleg; 58 konkrete Auswertungen korrekt |
| Hello World | Agentenquelle akzeptiert, Ausgabe exakt `Hello World\n` |
| Agentenreparatur | Erst Gegenbeispiel, dann akzeptierter Kandidat; zwei Versuche |
| Paket | Installierbares Python-Wheel und vollständiger Quellstand |

Die Tests prüfen unter anderem Binder, Ganzzahlarithmetik, Bool/Int-Trennung,
Aufrufvorbedingungen, ungültige Quellen, gefälschte Zertifikate, ausgelassene Pflichten,
veraltete Hashbindungen, Ressourcenbudgets sowie echte lokale HTTP-Adapteraufrufe.
Die Abnahmeprüfung bleibt auch mit `python -O` aktiv.

## Herkunft der Agentenprogramme

Sechs Subagents arbeiteten an Sprachkern, Beweisweg, Fabrik, Beispielen, unabhängiger
Sicherheitsprüfung und der konkreten Programmsynthese. Der Lead integrierte die Teile
und führte die übergreifenden Prüfungen aus.

`hello_synthesis` erhielt den eingefrorenen Vertrag und die Sprachregeln und schrieb
`examples/hello/hello.ll` direkt. Der erste Prüfversuch erreichte die Zweiggrenze.
Daraufhin wurde eine exakte, unabhängig geprüfte Widerspruchsregel im Checker ergänzt.
Vertrag und Agentenprogramm blieben unverändert; die positive Regression ging danach durch.

Für die Reparatur wurde zunächst ein absichtlich falsches Kontingentprogramm geprüft.
Der Solver lieferte den konkreten Fall `requested=1`, `available=0`, `result=1`;
der Interpreter bestätigte die Vertragsverletzung. Der Agent erhielt dieses tatsächliche
Feedback und schrieb `examples/agent-repair/repaired.ll` mit einem Rückwärtsaufruf
des Minimum-Helfers. Die erneute Prüfung akzeptierte alle Verpflichtungen. Die Ausführung
mit `requested=7`, `available=3` lieferte `3`.

Die Dateien in `evidence/` halten Auftrag, Feedback, Quellhashes und Ergebnisse fest.
Diese Herkunftsnotizen dokumentieren die beobachtete Sitzung; sie sind keine
kryptografische Identitätsbestätigung eines Modells. Die mitgelieferte Demo spielt die
echten Agentenantworten erneut durch den Checker. Neue Modellanfragen sind über den
HTTP-Adapter möglich; ein kostenpflichtiger externer Modellaufruf gehörte nicht zur Abnahme.
Modelltoken und Sitzungskosten wurden nicht vom Host bereitgestellt und werden nicht geschätzt.

## Abnahme wiederholen

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python scripts/demo.py
python -m pytest -q
```

Der Demolauf speichert frische Belege unter `build/demo/`. Die während der Umsetzung
erzeugten Nachweise stehen in `evidence/acceptance/`, die Tool-Gates in
`evidence/validation.json`. Abhängigkeiten sind in `requirements.lock` festgehalten.

## Geltungsbereich

Implementiert ist der gemeinsam festgelegte P0 mit `Bool`, mathematischem `Int`,
linearen Verträgen, reinem Core, Referenzinterpreter, Zertifikatschecker, CLI und begrenzter
Generate–Verify–Repair-Schleife. Der Host schreibt die berechneten Zeichencodes auf stdout;
die Sprache selbst enthält noch keine Strings oder I/O-Effekte.

`proved` gilt relativ zur dokumentierten TCB. Parser, symbolische Auswertung, Checker,
Interpreter und Python-Laufzeit sind getestet, aber ihre Implementierung ist nicht formal
bewiesen. Nativer Compiler, A3/A4, abhängige Typen und affine Ressourcen gehören zu späteren
Profilen. Die vollständigen Grenzen stehen in [ASSURANCE.md](ASSURANCE.md).

Der nächste fachliche Ausbau ist P1 mit `Nat`, `I64`, `Result` und expliziter Division-
und Overflow-Semantik. P0 ist als ausführbarer Meilenstein abgeschlossen.
