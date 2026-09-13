# Bibliotheken und Module: Expertenbeitrag zum Ausbauplan

Stand: 2026-09-09. Planung, keine Implementierung oder neue Testabnahme. Arbeitsnamen nach Abstimmung mit dem Lead: allgemeines Sprachprofil `a1`, Paketformat `pkg1`, Quelldatei `.llmod`, Interface `.llapi`, Manifest `.llpkg` und maschinenlesbares JSON-Lockfile. Beispiele sind Entwürfe, noch keine ausführbare Grammatik.

## Entscheidung

Wir brauchen ein **Modulsystem mit geprüften Schnittstellen**, keinen Compilerbefehl für jede neue Geschäftsfunktion. Native Bibliotheken bestehen aus normalen Programmen unserer Sprache. Ein Buchungs-, Kontingent- oder CRM-Modul benutzt dieselben allgemeinen Typen, Funktionen, Zustandsübergänge, Abfragen und UI-Komponenten wie eine Anwendung. Es erweitert weder den Parser noch den Beweiskernel.

Das Paketformat transportiert diese Module. Es führt beim Import, Installieren oder Kompilieren keinen Paketcode aus. Keine Buildhooks, Parsermakros, Python-Compilerplugins, frei eingesetzte TS-/SQL-Fragmente oder automatische Netzwerkauflösung. Neue echte Primitive oder Zielplattformen bleiben ausdrücklich versionierte Compiler-/Runtimeänderungen.

## Belegter Ausgangspunkt

- `pyproject.toml`: Compilerstand `0.4.0`, Python >=3.12, Z3/Pydantic als Laufzeitabhängigkeiten. `requirements.lock` hält Versionen des Abnahmelaufs fest, enthält aber keine Download-/Artefakthashes.
- `web/model.py`: genau eine `WebPage`, Textstores, read/write-Aktionen, vier geschlossene Widgetarten. Keine Module, Funktionen mit frei programmierbarem Aktionskörper, Imports, Records oder generischen Komponenten.
- `web/emit.py`: `_page` und `_button` kennen w1/w2 und deren Widgets direkt; Templates sind Teil des Compilerpakets.
- `web/build.py`: `compile_source(source)` verarbeitet eine Quelle; Manifest bindet deren kanonischen Hash und erzeugte Dateien. `verify_build` erzeugt Dateien erneut und vergleicht Bytes. Das ist keine Verifikation transitativer Pakete oder des gesamten nachgelagerten Vinext/npm-Builds.
- `proof.py`: Zertifikate binden den gesamten P0-Vertrag und Kandidaten an `cert-v0.1`; es gibt keine implementierte Assume/Guarantee-Regel für separat bewiesene Imports.
- `specs/01-CANONICAL-SYNTAX.md` und `02-TYPE-PROOF-SYSTEM.md` planen bereits gehashte globale Referenzen und Interfaces; diese älteren Entwürfe sind kein implementierter Paketmanager. Ihre globalen Hashreferenzen sind mit dem nachfolgenden Plan vereinbar, brauchen aber eine präzise Trennung von Interface, Implementierung und Linkbindung.

**Folge:** Nur Imports zu w2 hinzuzufügen würde dessen begrenzte Ausdrucksmächtigkeit nicht beheben. Der allgemeine a1-Ausbau ist Voraussetzung für wiederverwendbare Web-Domänenbibliotheken. Reine P0-Bibliotheken können unabhängig davon früher geliefert werden.

## Erster Meilenstein: lokale Bibliotheken und sicherer Linker

`pkg1` beginnt mit lokalen Workspace-/Vendor-Paketen, exakten Versionen und vollständig gesperrtem Abhängigkeitsgraph. Keine Registry, Versionsbereiche, SAT-basierte Auflösung, Features oder automatische Updates. Pro logischem Paketnamen genau eine Inhaltsidentität im Graph; Versions-/Hashkonflikte werden mit beiden Abhängigkeitspfaden abgelehnt. Derselbe Diamond-Import desselben Inhalts wird dedupliziert.

Der Linker löst ausdrücklich exportierte Funktionen auf, prüft das azyklische Modul-/Aufrufnetz, erzeugt eine deterministisch geordnete P0-Einheit und schreibt Aufrufindizes korrekt um. Die bestehende P0-Prüfung rekonstruiert danach **alle** Verpflichtungen des gelinkten Programms erneut. Ein importiertes Zertifikat ersetzt diesen Schritt nicht. Der Linker erhält Eigentests für Binder/Indizes und einen expliziten Source-to-Core-Vertrag; die bisherige Garantie über den Core beweist seine Implementierung noch nicht.

Damit entsteht sofort echter Nutzen: zwei verschiedene Programme können dieselbe mathematische Bibliothek verwenden, ohne Funktionen zu kopieren oder den Compiler zu verändern. Modulare Beweiswiederverwendung wird erst danach gebaut; sie ist keine stillschweigende Annahme des ersten Meilensteins.

## Paketlayout und Schnittstellen

| Pfad relativ zum Workspace | Zweck |
|---|---|
| `apps/booking/app.llpkg` | App-Manifest mit direkten Paketaliasen und Zielprofil |
| `apps/booking/src/app.llmod` | Anwendungscode in der eigenen Sprache |
| `packages/quota/quota.llpkg` | Deklaratives Bibliotheksmanifest |
| `packages/quota/src/capacity.llapi` | Autoritativer typisierter Vertrag, getrennt vom generierten Körper |
| `packages/quota/src/capacity.llmod` | Implementierung und explizite Imports |
| `llm.lock.json` | Gesamter festgelegter Abhängigkeitsgraph |
| `out/interfaces/<hash>.llapi` | Kanonische, erneut geprüfte Interfaces |
| `out/proofs/<key>.json` | Belegartefakte, keine Autoritätsquelle |
| `out/link-manifest.json` | Konkrete Provider, Targets, Annahmen und erzeugte Artefakte |

Manifestentwurf einer reinen Bibliothek:

```text
(package pkg1
  (name "sonny.quota")
  (version "0.1.0")
  (language p0)
  (module capacity
    (interface "src/capacity.llapi")
    (implementation "src/capacity.llmod")
    (placement pure)
    (exports available allocate))
  (dependencies))
```

Direkte Abhängigkeit im App-Manifest:

```text
(dependency quota
  (package "sonny.quota")
  (version "0.1.0")
  (workspace "packages/quota/quota.llpkg"))
```

Diese Workspaceadresse ist ausschließlich ein durch den Root-Build zugelassener, workspace-relativer Locator. Paketcode darf daraus keinen frei wählbaren Dateipfad erzeugen. Release-Builds verwenden einen unveränderlichen Snapshot mit dem Hash aus dem Lockfile.

Autorensyntax eines Imports, vorbehaltlich der einheitlichen Grammatik des Leads:

```text
(import cap (from quota capacity) (only available allocate))
```

Regeln:

1. Keine implizite Prelude, Wildcardimporte oder transitive Namenssichtbarkeit. Ein Import darf nur ein direkt deklariertes Paket oder eigenes Modul adressieren. `quota` ist ein lokaler Alias, keine Suche in einer Registry.
2. Exports sind explizit; private Symbole sind über externe Referenzen unerreichbar. Für M1 ordnet eine Modulhülle Exportnamen ausdrücklich lokalen P0-Funktionsindizes zu; sie erfindet keine bereits vorhandenen Funktionsnamen im heutigen Core. Mehrdeutige Aliase, doppelte Exports, Schattenbindung und Zyklen sind Fehler. Re-Exports kommen erst bei Bedarf und bleiben explizit.
3. Interfaces enthalten Typen, Parameterreihenfolge, Vor-/Nachbedingungen, benötigte Effekte, Platzierung und gegebenenfalls geprüfte Theoreme. Kein Paket darf sich durch `verified=true` selbst zertifizieren.
4. Öffentliche Exportnamen sind Teil der API-Auflösung. Die kanonische Coreform nutzt feste Exportslots und gehashte Referenzen. Die Interfaceidentität bindet auch die öffentliche Exporttabelle; Umbenennen kann daher Quellimporte brechen. Private lokale Namen bleiben diagnostische Information. Das präzisiert den historischen Satz „Namen sind nicht semantisch“.
5. Typen und Funktionsverträge werden nicht aus fremden Körpern opportunistisch erschlossen. Der Compiler liest und validiert den autoritativen Vertrag selbst. Factory-Aufträge frieren Vertrag, zulässige Imports und Autoritätsgrenzen vor Kandidatenannahme ein.
6. Fehler nennen Paket, Modul, Export, Source-Span und vollständigen problematischen Abhängigkeitspfad in maschinenlesbarer Form.

## Allgemeine Parametrisierung nach dem ersten Meilenstein

Für a1 empfehle ich explizite, begrenzte Typ-/Konstantenparameter und überprüfte Signaturen für übergebene Funktionen. Kein Textpräprozessor und keine beliebigen Compile-Time-Programme. Typisierte Recordkonfiguration deckt Laufzeitvariation ab; eine andere Konfiguration darf den Compiler nicht erweitern müssen.

Erste generische Beispiele: `Option T`, `Result T E`, begrenzte Listen, UI-Komponenten mit Props, Pagination und ein Zustandsübergangsmodul mit explizitem Zustandstyp. Monomorphisierung ist für den ersten Zielcodegenerator ausreichend. Anzahl und Größe der Instanziierungen sind budgetiert; zyklische oder expandierende Instanziierung wird abgelehnt. Anfänglich wird jede konkrete Instanz erneut geprüft. Universelle Generikbeweise und zertifizierte Substitution sind ein späteres Optimierungs-Gate.

Geschäftsregeln wie „belegte Plätze plus Anfrage überschreiten Kapazität nicht“ gehören in `domain.booking`, nicht als neuer Operator in den Compiler. Das Paket darf Datenmodelle, reine Regeln, Aktionen und UI zusammensetzen, sobald a1 diese allgemeinen Konstrukte trägt. Eine Bibliothek kann SQL-/Transaktionsgarantien nicht durch einen Namen wie `atomic_booking` erzeugen; diese benötigen das tatsächliche DB-Effektmodell und einen dazu passenden Adapter.

## Browser, Server, Effekte und Autorität

Platzierung wird je Modul/Export geprüft: `pure`, `browser` oder `server`. `pure` bedeutet effektfrei und für mehrere Targets nur dann verwendbar, wenn deren Zahlen-/Textsemantik den Typvertrag erfüllt. Ein `Int` darf beispielsweise nicht unbemerkt auf ungenaue JS-Number-Arithmetik abgesenkt werden.

Browsercode darf keine servergebundenen Implementierungen importieren, auch nicht über mehrere Bibliotheken. Der Compiler kann aus einer deklarierten Serveraktion einen eigenen typisierten RPC-Client erzeugen; dies ist ein Transportstub und kein direkter Funktionsimport. Nur explizit serialisierbare Daten passieren diese Grenze. DB-Capabilities, Geheimnisse und authentifizierte Principals sind nicht als Clientwerte konstruierbar oder transportierbar.

Bibliotheken deklarieren benötigte Effekte; das Root-Programm bzw. sein Host bindet die konkreten Capabilities. Ein Manifest erzeugt keine Rechte. Aufrufgraph und übergebene Callbacks müssen die transitive Effektmenge sichtbar machen. `DB.Read tenant_accounts` oder `Net configured_service` ist präziser als globales `IO`. Der Compiler weist Effekte außerhalb der Funktions-/App-Grenze zurück. Die Serverruntime beschränkt tatsächliche Ressourcen und Endpunkte entsprechend; ein statischer Effektname allein ist keine Sandbox.

Reine Module erhalten keine Netzwerk-, Datei-, Uhrzeit- oder Zufallszugriffe. Zeit und Zufall werden später über explizite APIs oder Eingabewerte eingeführt und in Verträgen/Annahmen sichtbar gemacht. Echte lineare/affine Ressourcen folgen nur mit dazugehörigem Typ- und Laufzeitmodell; sie werden nicht durch ein dekoratives Manifestfeld behauptet.

## Native Bibliotheken und externe Adapter

| Art | Wie erweitert sie die Factory? | Garantie und Grenze |
|---|---|---|
| Native `.llmod`-Bibliothek | Normale Programme und deklarative Komponenten | Statische Prüfung; Funktionsbeweise nur im unterstützten Fragment |
| Standardruntime | Versionierte primitive Implementierungen für DB, HTTP, UI | Expliziter Teil der TCB bzw. separat getesteter Übersetzungs-/Runtimegrenze |
| TypeScript/npm-Adapter | Schmaler, typisierter Adapter gegen eine konkrete Fremdbibliothek | Eingabe-/Ausgabedecoder und Integrationsprüfungen; behauptete Fremdverträge bleiben Annahmen |
| Python-Adapter | Späteres Python-Serverziel oder expliziter Remote-Dienst | Kein lokaler Pythonaufruf im heutigen Vinext/Worker-Target; Remotezugriff bringt Netz-, Auth- und Fehlersemantik mit |

Ein externer Adapter bindet exakte Paket-/Runtimeversionen, Artefakthashes, Zielsupport, Effektumfang, ABI/Wire-Schema, Fehlerfälle, Timeout-/Größenlimits und Herkunft aller Annahmen. Postcondition-Monitoring kann bei einem Aufruf eine prüfbare Rückgabe kontrollieren; es beweist weder alle Aufrufe noch das Ausbleiben fremder Seiteneffekte. Arbiträrer JS-/Python-Code im selben privilegierten Prozess kann die deklarierten Rechte umgehen: er gehört zur Vertrauensgrenze oder braucht wirkliche Isolation. Untrusted Browserplugins im gleichen Origin sind ebenso keine isolierte Vertrauenszone.

Kein npm-/Python-Paket wird während unserer Quellkompilierung importiert und ausgeführt. Nachgelagerte Zielbuilds benutzen ein festgelegtes Werkzeugrezept. Installations-/Buildskripte externer Pakete sind executable code und daher kein Bestandteil einer vermeintlich „reinen“ Paketauflösung; npm dokumentiert solche Lifecycle-Skripte ausdrücklich. [npm: Scripts](https://docs.npmjs.com/cli/v11/using-npm/scripts/)

Das Vorbild expliziter Import-/Exportgrenzen im WebAssembly Component Model ist hilfreich. Wir übernehmen die Idee typisierter Zusammensetzung, machen WebAssembly oder WIT aber nicht zur Voraussetzung des nächsten Meilensteins. Ein Interface beschreibt zudem noch keinen Beweis des internen Verhaltens. [WebAssembly Component Model: Worlds](https://component-model.bytecodealliance.org/design/worlds.html)

## Hashes, Lockfile und deterministische Builds

Wir unterscheiden mindestens folgende Identitäten:

- **Paketinhalt:** kanonisches Manifest plus geordnete, längengerahmte Dateipfade und Dateiinhalte der ausdrücklich deklarierten Quellen/Assets. Der Build liest keine anderen Paketdateien. Domain Separation und Formatversion gehören in den Hash; ein Eigenhashfeld wird ausgeschlossen.
- **Interface:** normalisierte Exporttabelle, Typen, Verträge, Effekte, Platzierung, Profil-/Semantikversion und benötigte Interfaceidentitäten. Ein Hash ist Integrität, kein Beweis und keine Herausgebersignatur.
- **Implementierung:** kanonischer Modul-Core einschließlich konkret gebundener Abhängigkeiten. Private Körperänderungen ändern diese Identität.
- **Build-/Linkmanifest:** vollständiger transitiver Inhaltsgraph, Compiler-/Checker-/Target-/Runtimeidentitäten, Optionen und Ergebnisartefakte. Konkrete Provider werden an die tatsächlich ausgeführten Bytes gebunden.

Lockfile-Ausschnitt, Hashwerte ausdrücklich Platzhalter:

```json
{
  "format": "pkg1-lock",
  "packages": [{
    "name": "sonny.quota",
    "version": "0.1.0",
    "source": "workspace:packages/quota",
    "content_hash": "sha256:<64-hex>",
    "interfaces": {"capacity": "sha256:<64-hex>"},
    "dependencies": []
  }],
  "compiler_artifact": "sha256:<64-hex>",
  "target_profile": "p0-interpreter"
}
```

`version` ist ein Releasebezeichner, kein Korrektheitsbeweis und keine automatische Kompatibilitätsgarantie. Der Root-Lock bindet alle transitiven Pakete; ein fremdes Paket-Lockfile darf diese Wahl nicht überschreiben. Build und Update sind getrennte Operationen. Der normale Abnahmebuild ändert weder Manifest noch Lockfile und arbeitet offline. Eine fehlende Abhängigkeit wird als Fehler gemeldet; es gibt keinen Onlinefallback. Cargo trennt ebenfalls gesperrte Auflösung und Offlinebetrieb über `--locked`, `--offline` und `--frozen`; das ist hier ein Designvorbild, keine neue Dependency. [Cargo: Build options](https://doc.rust-lang.org/cargo/commands/cargo-build.html)

Gleiche Inputs müssen dieselben kanonischen IR-/Generatorartefakte ergeben: feste Traversierungsreihenfolge, stabile Sortierung unabhängiger Module, unveränderte Reihenfolge semantisch geordneter Deklarationen/Widgets, keine Zeitstempel, absoluten Workspacepfade oder Zufallswerte in semantischen Artefakten. Entwicklerdiagnosen dürfen getrennte Umgebungsmetadaten enthalten. Quelldateien werden einmal als begrenzte Bytes gelesen, verifiziert und als unveränderlicher Snapshot weiterverarbeitet; spätere Dateiaustausche ändern den akzeptierten Input nicht.

Für vollständige Zielbuild-Reproduzierbarkeit müssen zusätzlich Compilerwheel, Python-/Node-Version, alle transitiven npm-/Python-/Runtimeartefakte und Zielbuildrezept festliegen und lokal vorhanden sein. Der erste Paketmeilenstein verspricht reproduzierbares Linking und Generatoroutput; daraus folgt noch kein reproduzierbarer Browserbundle- oder A4-Nachweis.

## Modulare Verifikation und Invalidierung

**Zunächst:** Jede Änderung am gelinkten P0-Inhalt erzeugt einen neuen Gesamtkandidaten und benötigt eine neue Prüfung. Alte Zertifikate bleiben nur für ihre exakt alten Artefakte gültig. Cacheeinträge sind untrusted; der unabhängige Checker muss ihre Bindungen und Inhalte akzeptieren.

**Späteres eigenes Gate:** Der Caller beweist die Vorbedingung jedes Imports und darf dessen Nachbedingung als Annahme verwenden. Der Linkchecker akzeptiert die Zusammensetzung erst, wenn der konkrete Provider genau dieses Interface implementiert und sein Zertifikat für diesen Körper geprüft ist. Domainstatus und tatsächliche Annahmen bleiben sichtbar. Die Assume/Guarantee-Regel, ihr Substitutionsmodell und die Azyklizität brauchen eine spezifizierte und unabhängig geprüfte Umsetzung.

| Änderung | Reaktion |
|---|---|
| Körper eines Providers, Interface identisch | Zunächst vollständige Neuprüfung; später Provider neu beweisen, Callerbelege eventuell behalten, Linkmanifest und betroffene Zielartefakte immer erneuern |
| Exporttyp, Vertrag, Effekt, Platzierung oder erforderliche Annahme | Interfacehash ändert sich; betroffene Caller erneut prüfen |
| Transitive Providerimplementierung | Konkrete Ausführungsbindung und Build ändern sich; kein unverändertes altes Release-Siegel |
| Compiler-/Backendänderung | Zielartefakte und Übersetzungsabnahme erneuern; ein identischer Corebeweis kann nur bei kompatibler Checker-/Semantikbindung weiter akzeptiert werden |
| Checker-/Semantikversion | Akzeptanz neu prüfen; keine Wiederverwendung allein aufgrund gleicher Paketversion |
| Reine Dokumentation außerhalb der deklarierten Buildinputs | Kein semantischer Neu-Beweis erforderlich; ihre Nichtverwendung muss durch Buildinputregeln stimmen |

Insbesondere darf ein Implementierungswechsel bei gleichem Interface erst dann Callerbeweise sparen, wenn die spätere modulare Regel tatsächlich existiert. Heute inlined P0-Aufrufe haben diese Eigenschaft noch nicht.

## Definition of Done und feindliche Imports

M1 ist erreicht, wenn zwei unterschiedlich aufgebaute P0-Programme dieselbe ausgelagerte Bibliothek und mindestens eine transitive Abhängigkeit benutzen; der Compiler muss dafür unverändert bleiben. Beide Programme werden getrennt vollständig geprüft und im Referenzinterpreter ausgeführt. Paketgraph, kanonische Linkausgabe und Quellzuordnung sind maschinenlesbar vorhanden. Builds aus zwei unterschiedlich benannten Workspaceverzeichnissen ergeben dieselben semantischen Artefakte. Ein abweichender Bibliothekskörper kann kein altes Gesamtzertifikat wiederverwenden.

Die Bibliotheks-/Linkerimplementierung wird per RED → GREEN → REFACTOR entwickelt. Adversarielle Fälle gehören in Verhaltenstests bzw. Property-/Fuzztests:

| Angriff oder Fehler | Erwartung |
|---|---|
| Fehlender direkter Import, Zugriff auf nur transitive oder private Exports | Deterministischer Bindungsfehler mit Importpfad |
| Typ-/Parametervertauschung beim Linken, Vorbedingung nicht erfüllt | Typ- oder Beweisfehler; kein stiller Indexwechsel |
| Zwei Pakete mit gleicher Version, aber anderem Inhalt; widersprechender Diamond | Hash-/Auflösungskonflikt, kein stilles Ersetzen |
| Modul-/Funktionszyklus und extrem großer Graph | Zyklus-/Budgetdiagnose, keine Rekursion ohne Terminierungsregel |
| Pfad mit `..`, absoluter Pfad, Backslashalternative, Symlink, Dateiaustausch | Kein Lesen außerhalb deklarierter Roots oder Wechsel der bereits akzeptierten Bytes |
| Unbekannte Manifestfelder wie `build-hook`, doppelte Schlüssel, übergroße Texte | Ablehnung, keine fremde Codeausführung |
| Geänderter Body, unveränderter angeblicher Paket-/Interfacehash | Neu berechnete Bindung widerspricht Behauptung |
| Fremdes Zertifikat, veralteter Checker, manipulierte Cacheantwort | Keine Freigabe; Checker entscheidet über genaue Artefakte |
| Fehlendes Offlinepaket | Abbruch ohne Netzwerkfallback oder Lockänderung |
| Semantisch geordnete Deklarationen/Widgets anders sortiert | Nicht als äquivalent kanonisiert |

Zusätzliche a1-Gates: transitiver Serverimport im Browser; versteckter Netz-/DB-Effekt über einen Callback; gefälschte Capability; Fremdrückgabe außerhalb des Schemas; falscher Target-Adapter; unbegrenzte generische Instanziierung. Diese Tests werden mit dem entsprechenden Feature verpflichtend und sind keine behaupteten Fähigkeiten von M1.

Für den ersten a1-Bibliotheksnachweis: Eine History-/Formularbibliothek wird in zwei Apps komponiert; anschließend entsteht eine neue kleine Domänenbibliothek durch Änderungen ausschließlich an `.llmod`/`.llapi`/`.llpkg` und Tests. Kein neuer Python-Emitterzweig, kein Domänenkeyword und kein manuell nachbearbeiteter generierter Zielcode ist zulässig. Die allgemeinen Primitiven dürfen dabei noch durch den vorangehenden a1-Meilenstein ergänzt worden sein; erst der anschließende Domänenwechsel ist der eigentliche Flexibilitätsnachweis.

## Reihenfolge und bewusst spätere Arbeit

1. `pkg1`: lokale P0-Bibliotheken, explizite Schnittstellen, exakte Pins, DAG-Linker, Gesamtprüfung, deterministische Artefakte.
2. a1-Grundtypen/Funktionen und allgemeine UI-/Daten-/Effektprimitiven; daraus native Standard- und Domänenbibliotheken. Typ-/Konstantenparameter zunächst explizit und budgetiert.
3. Schmale freigegebene Adapter für tatsächlichen Bedarf, mit targetgebundener Runtime und sichtbaren Fremdannahmen.
4. Separate modulare Beweise und gezielte Cachewiederverwendung nach eigenem Soundness-Gate.
5. Registry, Signierung/Publisheridentitäten, Versionsbereiche, mehrere Versionen im selben Graph, dynamisches Laden, compilerseitige Erweiterungen und zusätzliche Backends nur bei belegtem Produktbedarf.

Das Zielbild ist eine kleine versionierte Semantik plus komponierbare Bibliotheken. Die nächste sinnvolle Arbeit ist der prüfbare Linker und allgemeine Sprachbausteine; ein großer Paketmarktplatz würde diese Grundlagen nicht ersetzen.
