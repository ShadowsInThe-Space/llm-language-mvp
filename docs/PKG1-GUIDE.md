# Lokale P0-Bibliotheken: pkg1

Umgesetzt für Issues #13–#15. Es gelten
[Paketformat](../specs/PKG1-SPEC.md), [Linking](../specs/PKG1-LINKING.md) und
[Abnahme](../specs/PKG1-ACCEPTANCE.md). Python-Setup wie im QUICKSTART.

Das Beispiel `examples/pkg1` enthält drei separate Pakete:
`app → rules → base`. `base` implementiert Minimum, `rules` nutzt es als
Kontingentfunktion, `app` ruft diese auf. Jedes Paket besitzt explizite Exports
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

## Grenzen

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
| Vollständiger CLI-Lauf, kein Überschreiben, alter Lock | test_pkg_cli.py |
| Historische P0-/w1-/w2-Kompatibilität | vollständige vorhandene Suite und m0-v1-Fixtures |

Issue #16 bleibt als eigener Wiederverwendungs-Abnahmeschritt bestehen; die
Integrationsfixtures bereiten dessen Szenario vor.
