# Lokale P0-Bibliotheken: pkg1

Umgesetzt für Issues #13–#16. Es gelten
[Paketformat](../specs/PKG1-SPEC.md), [Linking](../specs/PKG1-LINKING.md) und
[Abnahme](../specs/PKG1-ACCEPTANCE.md). Python-Setup wie im QUICKSTART.

Das Beispiel `examples/pkg1` enthält vier separate Pakete:
`app → rules → base` und `remaining → rules → base`. `base` implementiert Minimum,
`rules` nutzt es als Kontingentfunktion, `app` liefert den gewährten Anteil und
`remaining` berechnet den verbleibenden Anteil nach der Zuteilung.
Jedes Paket besitzt explizite Exports
und getrennte Vertrags-/Implementierungsdateien. Es gibt keine neue Fachoperation
im Compiler. `call 0` bezeichnet in den konsumierenden Modulen den ersten Import.

Aus dem Repository mit aktivierter `.venv`:

```sh
python -m llmlang lock-pkg --workspace examples/pkg1 --root app \
  --package app=app --package rules=rules --package base=base --out build/pkg1.lock.json
python -m llmlang link-pkg --workspace examples/pkg1 --lock build/pkg1.lock.json \
  --out build/pkg1.bound.json
python -m llmlang check-pkg --workspace examples/pkg1 --lock build/pkg1.lock.json \
  --bound build/pkg1.bound.json --write-certificate build/pkg1.proof.json
python -m llmlang run-pkg --workspace examples/pkg1 --lock build/pkg1.lock.json \
  --bound build/pkg1.bound.json --certificate build/pkg1.proof.json --entry main.run \
  --inputs '[{"type":"Int","value":"7"},{"type":"Int","value":"3"}]'
```

Erwartete Statusfolge: locked → linked → proved → proved/returned, Ergebnis
`{"type":"Int","value":"3"}`. Die Befehle starten keine Modellanfrage und
keinen Webserver. Neue Ausgabedateien werden exklusiv erstellt; für einen neuen
Lauf andere Ausgabepfade verwenden. Vorhandene Locks werden nicht automatisch
erneuert. Fehlende Standardlocks werden als Fehler gemeldet.

## Was die Belege binden

Der Lock bindet exakte Paketversionen und kanonische Quellinhalte. Der Linkcheck
rekonstruiert aus dem separat autorisierten Snapshot alle Export-/Providerplätze,
Verträge, Parameter und Körper. Erst danach prüft der unabhängige P0-Checker den
Gesamtbeleg. Ein korrekter Core-Beweis für ein anderes Quellprogramm wird abgelehnt.

Der Lock ist die vom Host freigegebene Eingabe, nicht die vom Agenten frei
austauschbare Begleitdatei eines Belegs. Bewusst geänderte Quellen erfordern
bewusst neu eingefrorene Locks und neue Belege. Selbst eine semantisch äquivalente
Körperänderung führt zu einer anderen Quell-/Bündelidentität.

## Reproduzierbare M1-Abnahme

```sh
python scripts/demo_pkg1.py
```

Die Abnahme arbeitet ausschließlich mit temporären Kopien der Beispielquellen.
Zwei eigenständige Programme nutzen dabei dieselbe transitive `base`-Bibliothek:
`app` gibt die Zuteilung zurück, `remaining` den verbleibenden Anteil.
Für Anfrage 7 und Vorrat 3 liefern sie entsprechend 3 und 0.
Beide vollständigen gelinkten Programme erhalten unabhängig geprüfte Belege.
Die Beispiele haben reine Integer-Verträge (`requires true`); die Begriffe
Zuteilung/Vorrat sind Anschauung, keine zugesagte Geschäftsregel für negative
Eingaben oder eine produktionsreife Buchungslogik.

Danach ersetzt die Abnahme den Bibliothekskörper durch eine semantisch
äquivalente Variante (Addition von Null). Beide alten Locks werden abgelehnt.
Nach ausdrücklichem Erstellen neuer Locks passen auch beide alten Paketbelege
nicht mehr; neue Gesamtbelege werden erzeugt und erfolgreich geprüft.
Gleiche Fachresultate bedeuten somit nicht gleiche autorisierte Quellidentität.
Die ursprünglichen Beispielquellen bleiben unverändert, wiederholte Läufe sind möglich.

Für den zweiten Verbraucher lassen sich die vier CLI-Befehle oben ebenfalls
verwenden: `--root remaining`, `--package remaining=remaining` statt
`--package app=app`, und jeweils neue Ausgabepfade. Der Einstieg bleibt `main.run`.

## Grenzen

Siehe auch die [Paket-Beweisgrenzen und TCB](PKG1-ASSURANCE.md).

Reine Int-/Bool-Funktionen des P0; keine Rekursion, kein Netzwerk, keine Registry,
keine Plugins, keine w1/w2-Paketkomposition und keine neuen Datentypen. Alle
deklarierten Funktionen im erreichbaren Paketgraph werden mitgeprüft. Eine
erfolgreiche Paketprüfung ist kein formaler Beweis der Python-Toolchain selbst.
Dateisystemschutz über POSIX-dirfd/O_NOFOLLOW ist für Linux geprüft; Windows
ist für diese Paketbefehle nicht freigegeben.

## Abnahmezuordnung

| Anforderung | Nachweis |
| --- | --- |
| Strikte Grammatik, Namen, Versionen, Imports | test_pkg_resolver.py, test_pkg_graph.py |
| Symlinks, FIFO, Pfade, kumulative Budgets | test_pkg_security.py, test_pkg_graph.py |
| Topologie, Diamond, Umnummerierung, Binder | test_pkg_linker.py |
| Falscher Core trotz korrektem Beweis, Vertrag/Export/Binder/Slot, malformed evidence | test_pkg_binding.py |
| Transitive Änderungen, zwei Consumer, Pfadunabhängigkeit | test_pkg_transitive.py |
| Fachlich verschiedene Consumer und M1-Wiederverwendung | test_pkg_reuse.py, scripts/demo_pkg1.py, test_pkg_demo.py |
| Vollständiger CLI-Lauf, kein Überschreiben, alter Lock | test_pkg_cli.py |
| Historische P0-/w1-/w2-Kompatibilität | vollständige vorhandene Suite und m0-v1-Fixtures |

Es wurden keine neuen Compiler-Opcodes für einen der beiden Verbraucher ergänzt.
Diese Abnahme betrifft Quellwiederverwendung; modulare Beweiswiederverwendung
und allgemeine Webbibliotheken gehören nicht zu M1.
