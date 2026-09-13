# Herkunft der Beispielquellen

`hello.llapp` und `notes.llapp` wurden vom unabhängigen Syntheseagenten
`web_app_author` anhand von `docs/W1-SPEC.md` verfasst. Der Agent hat ausschließlich
diese beiden Sprachquellen und diese Herkunftsnotiz erstellt; Compiler und
Spezifikation wurden nicht verändert.

`hello.llapp` beschreibt die vorgegebene Hello-Anwendung. `notes.llapp` deklariert
eine andere App-ID, zwei unabhängige Textspeicher mit 1024 beziehungsweise 2048
UTF-8-Bytes Kapazität, vier Aktionen und zwei vollständige Eingabe-/Ausgabegruppen.

Deklarationsfolge, Widgetsyntax, Referenzen und Textgrenzen wurden anhand der
Spezifikation geprüft. Bei Erstellung war `src/llmlang/web/parser.py` noch nicht
vorhanden; eine Prüfung mit `parse_app` wurde daher nicht ausgeführt. Diese Notiz
behauptet keine Kompilation und keine Prüfung von Browser, API oder Persistenz.
