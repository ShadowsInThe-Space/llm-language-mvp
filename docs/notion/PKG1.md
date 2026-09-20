# M1: Pakete, Linker und Quellbindung

Stand 2026-09-20. Importierbare Notion-Dokumentation zu Issues #13–#15.

## Architektur

Ein Paket enthält ein JSON-Manifest sowie separate P0-Vertrags- und Körperdateien.
Ein expliziter Lock bindet exakte Versionen und kanonische Inhalte der gesamten
transitiven Abhängigkeitskette. Der Resolver erzeugt einen unveränderlichen
Snapshot. Der Linker ordnet Module topologisch, nummeriert Aufrufe um und erzeugt
ein gebundenes P0-Gesamtprogramm. Der unabhängige Linkcheck rekonstruiert Herkunft,
Verträge, Exports und Binder aus dem autorisierten Snapshot. Erst danach darf der
P0-Zertifikatschecker einen Paketbeleg akzeptieren.

## Verantwortlichkeiten

- Parser: striktes pkg1-Format und unveränderte P0-Grammatik.
- Resolver: exakte Auflösung, Sichtbarkeit, sichere Dateilesung und Budgets.
- Linker: deterministischer Übersetzungsvorschlag ohne Proof-Autorität.
- Bindungschecker: unabhängige Herkunfts- und Strukturprüfung.
- P0-Checker: mathematische Vertragsprüfung im bekannten TCB-Modell.

## Sprach- und Typgrenze

Int/Bool, P0-Verträge und nichtrekursive Funktionen bleiben erhalten. Namen und
Aliase leben in der Modulhülle; innerhalb der Funktionen bleibt die numerische
P0-Syntax. Importplätze stehen vor lokalen Funktionsplätzen. Parameter-/let-Binder
werden nicht verändert. Neue Datentypen und Webkomposition folgen erst später.

## Abnahme

413 lokale Tests, Ruff und striktes Mypy bestanden. Die dokumentierte CLI-Kette
lief tatsächlich bis zur zertifizierten Ausführung: Minimum von 7 und 3 ergibt 3.
Historische M0-Werte unverändert. Manipulierte Verträge/Körper/Binder/Exports und
alte Belege bei transitiven Änderungen werden abgelehnt. Pfad-/Symlink-/FIFO-
sowie kumulative Budgetfälle sind geprüft. Die Implementierung des Linkchecks
selbst ist nicht formal bewiesen.

## Verbindliche Quellen im Repository

- specs/PKG1-SPEC.md
- specs/PKG1-LINKING.md
- specs/PKG1-ACCEPTANCE.md
- docs/PKG1-GUIDE.md
- Log.md

Dies ist die lokale Importvorlage; ein Upload in Notion wird nicht behauptet.
