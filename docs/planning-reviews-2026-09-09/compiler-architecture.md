# Compiler-Architektur: Ausbau ab v0.4.0

Planungsbeitrag, 2026-09-09. Grundlage: tatsächlicher Quellstand `c54d3d9` unter `/workspace/scratch/a67318291dbe/llm-language-mvp`. Keine Implementierung verändert; keine Tests für diesen Review ausgeführt. Die bisherigen Testzahlen sind Release-Evidenz, keine neue Ausführung dieses Reviews.

## Empfehlung

Den vorhandenen Python-Compiler schrittweise um ein Modul- und Bibliothekssystem, aufgelöste typisierte Zwischenrepräsentationen und allgemeine Anwendungskonstrukte erweitern. Ziel bleibt zunächst `vinext-d1`: React/TypeScript für Browser und Serverworker, Drizzle für das D1/SQLite-Schema. Browser erhalten HTML/CSS/JavaScript. Ein Python-Anwendungsbackend oder WebAssembly ist für diese Erweiterung nicht erforderlich.

Die Sprache soll einen kleinen stabilen Satz von Konstrukten besitzen. Wiederverwendbare fachliche Funktionen, Komponenten, Datenmodelle und Aktionen werden als gewöhnliche Bibliotheksquellen aus diesen Konstrukten aufgebaut. Eine Buchung, ein Shop oder ein CRM dürfen keine neuen Parserzweige benötigen. Neue externe Fähigkeiten können dagegen einen explizit unterstützten Hostadapter benötigen; Bibliotheken können keine fehlende Runtimefähigkeit herbeideklarieren.

## Nachgewiesener Ausgangspunkt

| Datei/Struktur | Tatsächliche Rolle | Folgerung |
|---|---|---|
| `web/model.py` | Unveränderliche AST-Dataclasses, Spans, feste Textstores/Aktionen/Widgets, eine Seite | Konvention beibehalten; AST ist bisher zugleich Eingabe der Emitter |
| `web/parser.py` | Begrenzter S-Expression-Reader, JSON-Strings, kanonische Ausgabe, statische Prüfung | P0-Parser nicht vorschnell mit Webparser zusammenführen |
| `web/check.py` | Namen, Bindungen, Kapazitäten, erlaubte Widgets/Profile | Neue Phasen zuerst neben bestehendem Validator einführen |
| `web/emit.py` | Erzeugt React/TSX direkt aus `WebApp`; Profilzweige in Buttons/Seiten | Über aufgelöste UiIR arbeiten, bevor weitere Widgets/Seiten vervielfacht werden |
| `web/server.py` | Konfiguration plus feste TS/Drizzle-Vorlagen; W2 durch Text-Ersetzungen/Anhängen | Beim nächsten Ausbau explizite Runtimeauswahl und getypte Server-/Schema-IR statt wachsender Ersetzungsketten |
| `web/build.py::_ir` | JSON-Serialisierung des AST für Artefakte | Noch keine eigenständige typisierte IR und kein Semantic-Lowering |
| `web/build.py::verify_build` | Quelle erneut kompilieren und vollständiges generiertes Dateiset bytegenau vergleichen | Integritätsprüfung, keine semantische Übersetzungsverifikation |
| `model.py`, `core.py`, `symbolic.py`, `proof.py` | P0: `Int`/`Bool`, rückwärts gerichtete Aufrufe, Python-Referenzinterpreter, unabhängiger rationaler Checker | Bestehende Semantik/Zertifikathashes unverändert erhalten |
| `tests/web_runtime/run.mjs` | Unveränderter generierter TS-Handler gegen echte SQLite-Datei; D1-förmiger Adapter | Sehr nützliche Testgrenze; ersetzt keine D1-spezifischen Nebenläufigkeitstests |

W1 ersetzt einen einzelnen Text, W2 hängt Historieneinträge an. Diese unterschiedliche Bedeutung derselben alten `write`-Deklaration wird ausdrücklich durch das Profil gewählt. W1/W2 dürfen nach einer Bibliothekseinführung nicht unbemerkt umgedeutet werden.

Das aktuelle Buildmanifest umfasst generierte Quellartefakte. Externer Sites-Starter, sein Lockfile, konkrete Drizzle-SQL-Migration und finaler Vinext/Vite-Build liegen außerhalb dieses Inventars. Das ist ein konkreter Ausbaupunkt, kein bereits vorhandener End-to-End-Herkunftsnachweis.

## Inkrementelle Pipeline

1. **Begrenztes Lesen:** Quellen und deklarierte lokale Bibliothekspakete einlesen, Größengrenzen je Datei und für die gesamte Abhängigkeitsmenge anwenden. Compilerkompilierung führt keine Downloads oder Installationsskripte aus.
2. **Parsing:** versionierten Quell-AST erzeugen; Importdeklarationen sind Daten. P0/W1/W2 besitzen weiterhin ihre dokumentierten Parser/Decoder.
3. **Auflösen:** Paketlock prüfen, explizite Exporte/Importe binden, kanonische Symbol-IDs zuweisen, private Symbole abschirmen. Zunächst azyklischer Modulgraph und keine dynamischen Imports.
4. **Typen und Ausführungsorte prüfen:** vollständige Typen, Argumente, Effekte und Orte `pure`, `client`, `server` bestimmen. Clientcode erhält keine Datenbank-/Secret-Fähigkeit. Typinformationen auf Clientseite sind keine serverseitige Eingabevalidierung.
5. **Linken und spezialisieren:** erreichbare Bibliotheksinstanzen zusammenstellen, Kollisionen und ABI-/Profilkonflikte ablehnen. Generische Bibliothekskonstrukte zunächst monomorphisieren; eine kleine geschlossene Typparametrisierung reicht, kein dynamisches Plugin-System.
6. **Spezifikations- und Beweisgates:** P0-Teilprogramme mit unverändertem Checker prüfen. Andere Konstrukte erhalten ihren tatsächlichen Status: statisch geprüft, getestet oder später durch eine gesonderte Beweisregel abgedeckt. `unknown`, Timeout oder fehlender Beleg sind keine Freigabe für eine geforderte bewiesene Eigenschaft.
7. **Getyptes Lowering:** gemeinsame AppIR enthält Verknüpfungen zu kleinen Teil-IRs; vor jedem Zielbackend werden deren Invarianten geprüft.
8. **Zielausgabe:** UiIR → React/TSX und CSS; ActionIR → TS-Server und Decoder; SchemaIR → Drizzle-Schema und geplanter Migrationsschritt; gemeinsame API-Typen/Codecs aus derselben aufgelösten Definition.
9. **Externer Zielbuild und Abnahme:** vorhandener Starter/Lockfile, TypeScript, Vinext/Vite, Drizzle. Release-Evidenz bindet diese Ausgaben an denselben kompilierten Stand.

Phasen als kleine Python-Funktionen und eingefrorene Dataclasses organisieren. Ein allgemeines Plugin-Framework, Klassenerbhierarchien für jede Phase oder ein universeller Compiler-Passmanager sind dafür nicht erforderlich.

## Welche IRs wir wirklich brauchen

| Teil | Minimaler Inhalt | Was bewusst nicht hineingehört |
|---|---|---|
| Gemeinsame Typ-/Symboltabelle | Qualifizierte IDs, Typdefinitionen, Herkunft, Signaturen, Effekte/Orte | Z3-Ausdrücke, React-Nodes, offene Pythonobjekte |
| `CoreIR` | Geprüfte reine Funktionen, Verträge, explizite Arithmetic-Semantik | DB-Verbindungen, HTTP, UI-Zustand |
| `SchemaIR` | Entities, stabile Feld-IDs, Datentypen, Keys, Constraints, Indizes | Requestzeit-DDL, frei eingebettetes SQL |
| `ActionIR` | Parameter/Result, Authorisierungsanforderung, validierte Query/Mutation, Transaktionsgrenze, Fehlerfälle | Versteckte Clientidentität, beliebige JS-Fragmente |
| `UiIR` | Komponenten, Props, Zustand, gebundene Ereignisse, Routen, Listen, Bedingungen, Layout/Design-Tokens | Serverfähigkeiten oder SQL |
| `AppIR` | Getypte Zusammenstellung samt aufgelösten Symbolreferenzen und Target-Anforderungen | Monolithischer Baum mit jedem Backenddetail |

Die Teil-IRs werden erst mit ihrem jeweiligen Sprachmerkmal eingeführt. Im ersten Refactor genügen ein aufgelöster W1/W2-Zustand und die bestehenden Store-/Action-/Widget-Bedeutungen. W3 wird dann auf diesen echten Bedarf aufgebaut.

P0 bleibt ein eigener geschlossener Core. Ein neuer Record-/Variantentyp in der Anwendung erweitert nicht automatisch seine Beweissprache. Brücken müssen eine präzise Projektion zulässiger Felder auf P0-Parameter definieren; unbeweisbare String-/Collection-Eigenschaften erhalten keinen pauschalen P0-Status.

## Bibliotheken und Linker

Ein Bibliotheksexport besteht aus einer geprüften Signatur, Typen, Effekt-/Ortinformation und optional einem Vertrag. Eine Paketversion allein genügt nicht: Lockfile bindet den konkreten Inhalt, ABI und transitive Abhängigkeiten. Bibliotheksquellen durchlaufen denselben Parser und Checker wie die App; sie können keine eigene Compilersemantik installieren.

Für die erste Implementierung sind lokale, projektinterne Pakete mit expliziten Pfaden und Inhaltsdigest ausreichend. Ein Registrydienst, allgemeines SemVer-Solving und binäre Plugins sind kein erster Meilenstein. Ein vorbereitender Paketbezug kann später getrennt erfolgen; die eigentliche Kompilierung ist geschlossen und netzwerkfrei.

Modul- und Symbol-IDs sind qualifiziert, z. B. aus Paketinhalt, Modul und Export. Quelldeklarationsreihenfolge bleibt überall erhalten, wo sie Bedeutung hat (Widgets, Auswertung). Unabhängige Module werden in stabiler topologischer Reihenfolge gelinkt. Nicht auf die Iterationsreihenfolge von Dateisystem oder Hashmaps vertrauen.

**P0-Zertifikate sind an den vollständigen geordneten Core gebunden.** Bibliotheksbodies aneinanderzuhängen und alte Zertifikate weiterzuverwenden wäre falsch. Für die erste P0-Bibliotheksintegration den zusammengefügten Core nach deterministischer Indexauflösung erneut prüfen; Cache nur für den identischen vollständigen Core, Vertrag und Checkerstand. Echte getrennte modulare Beweisführung benötigt später Regeln für importierte Verträge und deren Annahmen.

Getrennte Kompilierung und Cache sind eine spätere Optimierung. Korrekte deterministische Komplettkompilierung einer kleinen Abhängigkeitsmenge kommt zuerst.

## P0-Ausführung im vorhandenen TS-Backend

Der Python-Compiler rechtfertigt keinen Python-Server. Für P0-Aufrufe im vorhandenen Worker einen kleinen TS-Zielpfad festlegen: mathematische Integer werden ausschließlich als `bigint` verarbeitet, nach außen über kanonische dezimale Strings mit Typcodec. Kein impliziter Weg über JS-`number`. SQL-Integer erhalten explizite Bereichsprüfungen; unbeschränktes `Int` ist nicht einfach eine SQLite-Integer-Spalte.

P0 hat derzeit eager Auswertung von `and`/`or` über vorher ausgewertete Argumente, aber bedingte Auswertung bei `if`. Diese Semantik einschließlich Fehler-/Budgetverhalten darf ein TS-Emitter nicht durch bequemes JavaScript-Short-Circuiting ändern. Funktionsvorbedingungen werden im Referenzinterpreter an Aufrufen geprüft. Runtime-Checks zunächst beibehalten; keine Elimination, bevor Übersetzung und jeweilige Vorbedingung abgesichert sind.

Entscheidung für die erste Brücke: ein einfacher strukturtreuer TS-Emitter für das geschlossene P0-Subset, ohne Optimierungen, plus kleine Runtimefunktionen für exakte Decodierung, Bereichs-/Budgetprüfung und Fehler. Explizite temporäre Bindungen erhalten die Auswertungsreihenfolge. So benötigen wir neben dem vorhandenen Python-Referenzinterpreter keinen zweiten allgemeinen Interpreter. Pflicht sind identische exakte Werte und explizite Ressourcenfehler. Der emittergenerierte TS-Code ist zunächst getestet, nicht formal übersetzungsvalidiert.

## Absicherung der Übersetzung

Jetzt verbindlich:

- RED → GREEN → REFACTOR für neue Semantik und reproduzierbare Bugs.
- Kanonische Parse/Print-Roundtrips und Metamorphietests; äquivalente Literale/Whitespace liefern gleiche semantische Ausgaben.
- Property-Based-Tests für zulässige getypte Programme und ungültige Bindungen/Typgrenzen.
- Differentialtests: Python-P0-Referenz gegen ausgeführten TS-Core, eingeschlossen große Integer, negative Werte, Zweige, Aufrufe und Grenzfehler.
- Modellbasierte Aktionsfolgen gegen echte DB-Runtime; nicht nur Textsuche in erzeugtem Code.
- Generiertes Drizzle-SQL zusätzlich zum unabhängigen Referenz-DDL testen. Der Referenzschema-Test beweist nicht, dass der reale Generator dieselben Constraints ausgegeben hat.
- Tatsächlicher Ziel-Typecheck/Build sowie Browserabnahme, Client/Server-Trennung und negative Zugriffs-/Race-Fälle.

Diese Gates geben belastbare Testevidenz. Sie sind keine mathematischen Übersetzungsbeweise.

Späterer separater Forschungsmeilenstein: für ein kleines pure-Core-Lowering eine **tatsächliche Translation Validation**. Der Validator liest den konkreten Zielcode oder eine aus genau diesem Code unabhängig rekonstruierte Ziel-IR, prüft seine Eingabe-/Fehlersemantik gegen den Quell-Core und gibt eine prüfbare, an beide Inhalte gebundene Evidenz aus. Ein Vergleich zweier vom selben Emitter behaupteter IRs oder alleiniger Hashes genügt nicht. Wenn ein SMT-Solver äquivalente Ausdrücke sucht, muss die Akzeptanzregel samt TCB klar definiert sein; P0-Checker deckt neue TS-BigInt-Semantik nicht automatisch ab.

Ein solches Core-Gate würde weiterhin keine Eigenschaften von DOM, HTTP, D1-Transaktionsisolation, Authprovider oder CSS beweisen. Keine allgemeine A3/A4-Aufwertung der gesamten Anwendung.

## Reproduzierbarkeit und Provenienz

Zwei Ebenen unterscheiden:

1. **Compiler-Build:** kanonische Quellen aller Module, Inhaltslock, Semantikprofil, Compiler-/IR-/Runtime-ABI-Version, Target-Capabilities, Template/Adapter-Inhalte und sämtliche generierten Artefaktdigests. `verify_build` löst nur die gebundenen Pakete auf und vergleicht den vollständigen Output erneut.
2. **Release-Build:** zusätzlich exakter Starter-Gitstand, Target-Lockfile, Toolchainversionen, tatsächlich ausgeführte Buildbefehle, Drizzle-Migrationsdateien, Worker-/Browserartefakte und Prüfberichte. Deployevidenz nennt deren Digest und Schema-Migrationsstand. Infrastrukturadressen/Geheimnisse gehören nicht in Compilerquellen.

Source-Spans brauchen eine definierte Einheit. Bestehendes `Span` benutzt Python-Zeichenoffsets; ein späteres sourcemap darf diese nicht als UTF-8-Bytes ausgeben. Semantischer Build und Debug-Provenienz sind zu trennen: eine Rohquell-Sourcemap ändert sich bei Whitespace, während der kanonische semantische Build identisch bleiben soll. Vorschlag: semantische Zuordnung über stabile Node-IDs zur kanonischen Quelle im Build; optionaler Rohquellindex als gesondertes Evidenzartefakt mit Rohquellhash.

Keine Zeitstempel, Zufalls-IDs oder absolute Arbeitsverzeichnisse in deterministischen Codeausgaben. Datenbank-Migrationsausführung darf Laufzeitwerte wie `created_at` erzeugen; das ist kein Versprechen identischer DB-Inhalte bei wiederholtem Build. Drizzle-/Bundlerausgaben erst nach einem echten Zwei-Verzeichnisse-Rebuild als byteidentisch bezeichnen. Bis dahin reproduzierbare Compilerquellen von ungeprüften finalen Targetbytes unterscheiden.

## Dateiplan und Reihenfolge

| Schritt | Bestehende Stellen | Kleine neue Bausteine | Abnahme |
|---|---|---|---|
| 0. Baseline einfrieren | `docs/W1-SPEC.md`, `W2-SPEC.md`, `ASSURANCE.md`, `Log.md`; Testevidenz | Profil-/ABI-Kompatibilitätsmatrix, Golden-Ausgaben | P0-Zertifikate und W1/W2-Verhalten unverändert; unklare Doku korrigiert |
| 1. Pipeline extrahieren | `web/build.py`, `emit.py`, `server.py` | `web/ir.py`, `web/lower.py`; kleine Emittergrenzen | Echte W1/W2-Verhaltenssuite; kanonische Artefakte deterministisch; geänderte Bytes nur erklärter Refactor |
| 2. Module und Bibliotheken | `web/parser.py`, `check.py`, `cli.py`, `build.py` | z. B. `modules.py`, `linker.py`; Manifest/Lock als Daten | Imports/Exports, Zyklen-/Collision-/Capability-Ablehnung; unveränderte Compilerquellen für zweite Library-App |
| 3. Allgemeine Daten/UI | Neues additives W3-Profil; W1/W2-APIs bleiben | Getypte Records/Varianten, SchemaIR, UiIR, begrenzte Komponentenparametrisierung, mehrere Routen | Zwei fachlich verschiedene Anwendungen mit gemeinsamen Komponenten und Beziehungen |
| 4. Aktionen und Core-Brücke | Neue ActionIR und Zielruntime; P0 nicht umdeuten | Decoder, Query/Mutation, explizite Fehler/Transaktionsmuster, P0-Aufrufbridge | DB-Constraints, echte gleichzeitige Zugriffe auf Zielsystem, Auth/IDOR, Core-Differentialtests |
| 5. Factory-Generalisation | `factory.py` derzeit P0-spezifisch | Paket-/App-Syntheseadapter mit immutablem Spec-/Lock-Hash und Diagnoseformat | Agent darf Implementation/Lib ändern, vereinbarte Verträge nicht lockern; Reparaturfeedback reproduzierbar |
| 6. End-to-End-Flexibilitätsgate | CLI/Evidenz, Targetintegration | Releaseprovenienz und Library-only-Änderungsprüfung | Zwei unterschiedliche Apps plus neue Fachfunktion ausschließlich durch App-/Libraryquellen |
| Später | Separates reines Backendteil | Unabhängiger Translation-Validator für genau benanntes Subset | Reale konkrete Zielübersetzung durch Checker akzeptiert; Grenzen weiter dokumentiert |

Dateinamen sind Vorschläge. Kein Großumbau nur zur Umbenennung; gemeinsame Module erst extrahieren, wenn mindestens zwei reale Verbraucher denselben semantischen Gegenstand benötigen.

## Verbindliches Zwei-App-/Library-only-Gate

Nach einem dokumentierten Freeze von Compiler, Core-Standardbibliothek, Hostadaptern und Targettoolchain schreibt ein unabhängiger Agent eine zweite Anwendung aus einer neuen Fachspezifikation. Geeignete Kombination: Kunden-/Aufgabenverwaltung und Veranstaltungsbuchung mit Kapazität/Stornierung. Unterschiede müssen echte Datenbeziehungen, Berechtigungen und Zustandsübergänge betreffen, nicht nur Titel/Feldnamen.

Gemeinsame UI-/Datenbausteine werden aus gleichen Bibliothekspaketen importiert. Danach wird etwa Gruppenbuchung als zusätzliche Fachbibliothek ergänzt. Erlaubter Diff: Appquellen, normale Bibliotheksquellen, deren Tests/Verträge und Inhaltslock. Verboten für dieses Gate: neue Parserfälle, neue Compiler-IR-Opcodes, veränderte Emittervorlagen oder neue manuell geschriebene Hostfunktionen. Ein fehlender allgemeiner Sprachbaustein wird als Gate-Fehlschlag dokumentiert, dann separat spezifiziert; nicht als Library-only-Erfolg umetikettiert.

Beide Apps müssen aus leerem Ausgabeordner reproduzierbar entstehen, unverändert targetbauen, ihre Daten nach Neustart erhalten und die fachlichen E2E-/Negativtests bestehen. Nach einer Bibliothekskorrektur werden alle abhängigen Apps neu geprüft. Das ist der konkrete Flexibilitätsnachweis; Zeilenzahl oder Expertenzustimmung alleine reichen nicht.

## Explizite Grenzen

- Ein effecttypisiertes `transaction` garantiert noch keine D1-Fähigkeit. Das Zielbackend muss das verlangte atomare Muster tatsächlich unterstützen oder die Kompilierung für dieses Muster ablehnen; keine stillen Mehrrequest-Fallbacks.
- W1/W2-Slots sind geteilte Site-Daten, keine vorhandene Mandanten-/Benutzerautorisierung. Neue benutzerbezogene Apps brauchen serverseitige Identitätsbindung und eigene Abnahme.
- Native Hostbibliotheken bleiben explizite Vertrauensgrenzen. Deren externe Verträge werden nicht allein durch Import mathematisch wahr.
- Rich-UI, Rekursion, komplexe Queries und beliebige Web APIs werden nicht durch ein unbegrenztes `foreign-js` freigeschaltet. Das würde zentrale Prüfbarkeit unterlaufen.
- Eine Bibliothek kann vieles wiederverwenden; unbekannte Fachlogik erfordert weiterhin Spezifikation, Implementierung und Prüfung. Der Compiler muss dabei nur für neue allgemeine Semantik erweitert werden.
