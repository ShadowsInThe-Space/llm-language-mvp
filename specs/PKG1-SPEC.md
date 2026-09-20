# pkg1 — Lokale Pakete (normativ)

Issue #13, auf der grünen M0-Basis 9ba73e1. MUST/MUSS sind verbindlich.
M1 ist eine Modulhülle um unverändertes P0, keine Implementierung von a1.

## Dateien und Syntax

Jedes Paket besitzt `package.llpkg` (striktes JSON, UTF-8):

```json
{"format":"pkg1","name":"app","version":"1.0.0",
 "dependencies":{"math":"1.0.0"},
 "modules":[{"name":"main","names":["run"],
 "imports":[{"alias":"minimum","package":"math","module":"math","export":"min"}],
 "exports":["run"],"spec":"main.llapi","source":"main.llmod"}]}
```

`.llapi` enthält eine vollständige `(spec p0 ...)`, `.llmod` eine vollständige
`(candidate p0 ...)`. `names[i]` benennt Vertrag i und Körper i. Anzahlen stimmen
überein; beide Dateien bleiben physisch getrennt. Öffentliche Exports sind
explizite Namen aus names. Keine Reexports. Leere Import-/Exportlisten sind erlaubt.
Ein Paket hat mindestens ein Modul, ein Modul mindestens eine Funktion.
Namen für Pakete, Module, Funktionen und Aliase: `[a-z][a-z0-9_-]{0,63}`.
Version: drei kanonische nichtnegative Dezimalzahlen mit Punkten, keine Ranges.
Ein Paketname hat im gesamten Build genau eine Version.

Objekte haben exakt die angegebenen Felder. Unbekannte Felder, doppelte JSON-
Schlüssel, doppelte Modul-/Funktions-/Export-/Importaliasnamen sind Fehler.
Importaliase und lokale Funktionsnamen dürfen nicht kollidieren.
Manifest-Modulreihenfolge ist nicht semantisch; Funktionen und Importe sind geordnet.

## Aufrufraum

In jedem Modul bilden zuerst die geordneten Imports, dann die geordneten lokalen
Funktionen dessen numerischen call-Raum. Bei k Imports ist lokale Funktion i
unter `call (k+i)` erreichbar. Nur lokale Vorgänger und Imports sind aufrufbar.
Verträge enthalten keine Calls. Ein Import benennt ein öffentliches Exportziel
eines eigenen Moduls oder eines direkt deklarierten Abhängigkeitspakets.
Transitive Dependencies sind nicht implizit sichtbar. Module dürfen nicht sich
selbst importieren; Paket- und Modulgraph müssen azyklisch sein.
Der Linker schreibt ausschließlich call-Indizes um. Parameterreihenfolge,
var-Indizes, let-Bindung und Verträge bleiben strukturell identisch.

## Lock und autorisierte Eingaben

`ll.lock.json`:

```json
{"format":"pkg1-lock","root":"app","packages":[
 {"name":"app","version":"1.0.0","path":"app","sha256":"64 lowercase hex"},
 {"name":"math","version":"1.0.0","path":"math","sha256":"64 lowercase hex"}]}
```

Alle Pakete sind die exakte transitive Closure der Root-Dependencies, keine
fehlenden oder überzähligen Einträge. Locknamen, Versionen und Pakethashes müssen
mit den Dateien übereinstimmen. Der Lock entsteht nur durch explizites Einfrieren
einer Auswahl name→Pfad; Resolver und Linker aktualisieren ihn niemals automatisch.
Eine neue Baseline mit bewusst geändertem Lock benötigt neue Bindungs-/Core-Belege.
Der Prüfer bekommt den autorisierten Snapshot separat vom angebotenen Beleg.
Ein selbst mitgelieferter Snapshot oder Bibliotheksstatus `proved` ist keine Autorität.

## Pfade und Budgets

Paketpfade sind nichtleere relative POSIX-Pfade im Workspace. Moduldateipfade
sind nichtleere relative POSIX-Pfade innerhalb des Pakets. Absolute Pfade, leere
Komponenten, `.`, `..`, Backslash und NUL sind verboten. Symlinks in allen
Pfadkomponenten und nichtreguläre Dateien sind verboten. Dateien werden begrenzt
eingelesen; Linker/Checker arbeiten anschließend auf einem unveränderlichen Snapshot.
Der Workspace selbst wird einmal als vertrauenswürdige Wurzel aufgelöst. Lokale
gleichzeitige bösartige Dateisystemänderungen erfordern sichere no-follow Reads;
geprüfte Pfade allein genügen nicht für einen atomaren Snapshot.

Defaultbudgets: 64 Pakete, 256 Module insgesamt, 1024 Funktionen insgesamt,
4096 Imports insgesamt, 4 MiB insgesamt gelesene Quellen inklusive Manifest/Lock,
128 KiB pro Datei. Zusätzlich gelten P0-Limits für den gesamten gelinkten Core
(u.a. 12000 AST-Knoten, Tiefe 96, 100000 Schritte, 4096 Beweisbranches).
Keine Inlining-Expansion; jedes Modul/jede Funktion wird einmal eingefügt.
Nichtpositive, boolesche oder über den Defaults liegende Budgetwerte sind ungültig;
kleinere positive Budgets sind für Tests und restriktivere Hosts zulässig.

Das serialisierte gebundene Artefakt (Core plus Herkunftsmanifest) ist auf 16 MiB
begrenzt. Sein zusammengeführter spec-/candidate-Text darf jeweils 4 MiB umfassen;
das 128-KiB-Limit einzelner Quelldateien gilt nicht erneut für deren Verkettung.
AST-, Tiefe-, Integer- und Checkerbudgets bleiben unverändert.

## Kanonische Bytes

JSON ist ASCII-escaped, Schlüssel sortiert, Separatoren `,` und `:`, ohne Newline.
Kanonisches Paket enthält format/name/version/dependencies und nach Modulnamen
sortierte Module mit name/names/imports/exports/spec/source. exports wird sortiert;
spec/source sind kanonische P0-Strings, keine Dateipfade. Imports bleiben geordnet.
Paketdigest = SHA256(`UTF8("pkg1:package\0") || canonical_package`).
Snapshot enthält format=`pkg1-snapshot`, root und nach Namen sortierte kanonische
Pakete. Snapshotdigest = SHA256(`UTF8("pkg1:snapshot\0") || canonical_snapshot`).
Somit ändern transitive Quellen die Snapshotidentität; Workspace-/Dateinamen und
Formatierungswhitespace tun es nicht. Export-/Vertrags-/Importänderungen tun es.
Hashes begründen Integrität, keine mathematische Korrektheit.

## Diagnosen

PkgError verwendet diagnostic-v1, phase ist parse/resolve/link/bind, span null,
symbol optional qualifizierter Name. Stabile Codes:
P_PARSE (JSON/Form), P_DUPLICATE, P_NAME, P_VERSION, P_PATH, P_IO, P_LIMIT,
P_HASH, P_DEPENDENCY, P_CYCLE, P_PRIVATE, P_UNBOUND, P_CALL, P_TYPE, P_BINDING.
Keine Pfad-/Secret-Inhalte in pauschalen I/O-Fehlern. P0-Fehler werden an der
Paketgrenze mit benanntem P-Code und Ursache übersetzt. Kein Netzwerk,
Versionssolver, Plugin oder Installationshook gehört zum pkg1-Lauf.
