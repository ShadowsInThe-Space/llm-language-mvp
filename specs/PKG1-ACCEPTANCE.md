# pkg1 — Abnahme #13–#15

Vor Code gilt dieser Vertrag. M0-Fixtures und vorhandene Profile bleiben unverändert.

RED zuerst: unbekanntes/privates Exportziel, Namensduplikate, Paket-/Modulzyklen,
falsche exakte Versionen, unzulässige transitive Imports, Pfadtraversal/Symlinks,
Gesamtbudget, geänderte transitive Quelle bei altem Lock. Dann schmal implementieren.

Positiv: unabhängige Pakete mit transitiver Dependency, gleiches Paket über
Diamond-DAG nur einmal, mehrere Module und Exports, vollständige P0-Prüfung und
Referenzausführung. Identische kanonische Ausgabe in zwei Workspaceverzeichnissen.
Ein gemischter Parameter-/let-Fall prüft capture-freie Umnummerierung.

Bindung: vertauschte Körper; abgeschwächter Vertrag; vertauschte Parameter und
var-Indizes; falsch zugeordneter Export; semantisch anderer, für sich korrekt
bewiesener Core; veraltete Belege bei geänderter transitiver Bibliothek.
Jeder Fall muss am Bindungs-/Beleggate scheitern. Checker-Prüfung bleibt möglich,
wenn Linker und Solver deaktiviert sind. Malformed evidence führt zu false,
nicht zur Freigabe oder unkontrollierter Exception.

CLI: explizites Lock-Erzeugen, deterministisches Linken, Prüfen und Ausführen
mit gebundenem Beleg. Neue Dateien ohne implizites Überschreiben. Kein Netzwerk.
Beispiele und Anleitung müssen die tatsächlich ausführbaren Kommandos zeigen.

Abschluss: gesamte Pytest-Suite, Ruff, Mypy, unabhängiger Review, GitHub-CI;
danach Merge nach main. Issue #16 (formale Wiederverwendungsabnahme) bleibt ein
eigener Tracker; benötigte Integrationsfixtures dürfen dessen Szenario vorbereiten.
