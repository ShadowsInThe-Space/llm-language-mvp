# Fachreview: allgemeine Webanwendungen, Bibliotheken und belastbare Systemgrenzen

Stand: 2026-09-09. Reiner Planungsbeitrag. Untersucht wurden im tatsächlichen Repository `/workspace/scratch/a67318291dbe/llm-language-mvp` insbesondere `docs/W2-SPEC.md`, `docs/ASSURANCE.md`, `docs/web-reviews/security-review.md`, `src/llmlang/web/{model,check,server}.py` und die History-, Server-, Schema- und Hostvorlagen. Keine Implementierung geändert; keine Tests ausgeführt. Die früher berichteten 309 Tests sind historische Abnahmen, kein neues Testergebnis dieses Reviews.

## 1. Istzustand und Architekturentscheidung

W2 besitzt genau eine Root-Seite, begrenzte TextStores, feste Read-/Write-Aktionen und die Widgetvarianten Input/Button/Output/Clear. `emit_server` setzt eine erlaubte Slotkonfiguration in feste TypeScript-Vorlagen ein; SQL-Werte sind gebunden. Die History implementiert UUID-Idempotenz, Keyset-Pagination, App-/Slotfilter und eine additive W1-Migration. Das Target ist Vinext/React im Browser und ein TypeScript-Worker mit D1-Binding. Die Sprachimplementierung selbst bleibt Python.

`app_id` und `store_id` sind Anwendungs-/Speicherzuordnung, **keine Mandanten- oder Benutzerautorisierung**. Die bisherige private Site teilt ihren Bestand unter den zugelassenen Besuchern. Origin-Prüfung ist CSRF-Abwehr, keine Anmeldung. P0 beweist begrenzte reine Verträge; W2, SQL-Ausführung und Codegenerierung sind nicht damit formal bewiesen.

**Entscheidung:** W2 als kompatibles Altprofil erhalten und auf eine gemeinsame typisierte Web-IR abbilden. Künftig sollen neue Aufgaben durch Programme und Bibliotheken entstehen, ohne jeweils ein neues Profil mit fest verdrahteten Geschäftsaktionen einzubauen. Compilerprimitives bleiben auf Semantik, Berechtigungen, Effekte, typisierte Deklarationen und überprüfbare Ausführungspläne begrenzt.

## 2. Präzise Zuordnung von Kern, Bibliothek und Adapter

| Fähigkeit | Sprach-/Compilerkern | Bibliothek in unserer Sprache | Vertrauenswürdiger Targetadapter |
|---|---|---|---|
| Daten und Module | Records, Varianten, Option/Result, gebundene Listen/Texttypen; Module, private Exporte, Signaturen | Fachtypen, Validator-Komposition, Datums-/Geldoperationen über explizite Semantik | Unicode-, Zeit-, UUID- und Wire-Encoding mit geprüften Grenzen |
| UI | Typisierte View-/Event-/State-Werte; client/server-Ort; sichere serialisierbare Grenztypen | Layout, Formular, Datentabelle, Dialog, Pagination, Navigation, Theme, HistoryPicker | Kleine DOM-/React-Primitives, escaping, Routing/Hydration, CSS-Ausgabe |
| Datenmodell | Entity-/Field-/Relation-Symbole, Schlüssel-/Constraint- und Schema-IR | Wiederverwendbare fachliche Datenmodelle; Query-Combinators | SQL-Typabbildung, eindeutige Identifier, Index-/FK-/CHECK-Emission, Migrationen |
| Queries | Typisierte Query-Algebra mit Parametern, Projektion, Prädikat, Join, Sortierung, Aggregat und Limit | Filter, Suchen, paginierte Listen und erlaubte Beziehungen | Parametrisierte SQLite/D1-Abfragen; begrenzter Targetumfang |
| Aktionen | Input-/Output-Typ, Actor-Kontext, Effektmenge, Fehler, Vor-/Nachbedingungen | CRM-Befehle, Buchung/Storno, Kontingent-/Workflow-Regeln | HTTP-Decoder, Auth-Integration, DB-Aufruf, Fehlertransport |
| Autorisierung | Unkonstruierbarer AuthContext/Capability, server-only, policypflichtige Ressourcennutzung | Mandantenmitgliedschaft, Rollen-/Eigentümerregeln, explizite öffentliche Projektionen | Vertrauenswürdige Identitätsprüfung; serverseitige Ressourcenscope-Durchsetzung |
| Transaktion | Expliziter atomischer Command-Plan für **eine** DB; kein beliebiges Await im atomischen Bereich | Idempotenz, fachliche Zustandsübergänge, Buchungsregeln | Conditional Mutation, statischer D1-Batch, constraints; Ablehnung nicht abbildbarer Pläne |
| Externe Dienste | Deklarierte Capability, beschränkter Request-/Response-Typ und Effekt | Zahlungs-/Mail-Workflows und Fehlerbehandlung | Fester Connector, Secretzugriff, Timeout/Limit, Netzwerkpolicy |

Ein Bibliotheksimport darf neue Kompositionen und Fachlogik liefern, aber keine beliebigen Python-/TypeScript-/SQL-Fragmente, Compilerplugins oder Buildskripte ausführen. Hostbibliotheken sind gesonderte Adapterpakete mit unveränderlichem Hash, expliziten Effekten, Zielplattform und offen ausgewiesener Vertrauensgrenze. Ein Vertrag an einer Fremdfunktion beweist deren Implementierung nicht. Das Importieren einer reinen Bibliothek darf keine Netzwerk- oder DB-Berechtigung verleihen.

Schema-/UI-Deklarationen benötigen erstklassige IR-Werte beziehungsweise deklarative Standardformen; ihre Bibliotheks-APIs dürfen nicht auf String-Makros und unkontrollierter Quelltextersetzung basieren. Die Syntax sollte erst nach Abstimmung mit Typ-/Semantikreview festgeschrieben werden.

## 3. Vollständiger Requestvertrag für neue Anwendungen

1. Compiler trennt Client- und Servergraph. Ein Clientimport darf keine Secrets, DB-Bindings, server-only Funktionen oder implizit eingefangene Hostwerte enthalten. Ausgabe-DTOs bestehen aus ausdrücklich projizierten Feldern; kein automatisches Serialisieren ganzer Entities.
2. Server authentifiziert die Sitzung und erzeugt den Actor. Vom Client vorgeschlagene Tenant-ID ist höchstens eine Auswahl; Mitgliedschaft und Berechtigung werden serverseitig geprüft. Owner-, Rollen-, Preis- und Freigabefelder werden aus vertrauenswürdigen Daten abgeleitet.
3. Strenger generierter Decoder validiert Shape, Duplikatfelder, maximale Tiefe, Unicode und Größen. Clientvalidierung ist nur UX. Record-Patchs haben ausdrücklich erlaubte Felder; Mass Assignment wird ausgeschlossen.
4. Jede Entityzugriffsoperation erhält eine Policy und einen Scope. Auflisten, Detailansicht, Suche, Counts, Beziehungsladen, Mutation und Export müssen dieselbe Grenze respektieren. Policies werden vor Pagination/Aggregation in die Query aufgenommen; nachträgliches Filtern im UI genügt nicht.
5. Mutationsrelevante Policies und Zustandsvorbedingungen werden im selben atomischen DB-Schritt wie die Änderung geprüft. Eine vorherige Prüfung mit späterem unbedingtem UPDATE wäre bei paralleler Rechteänderung ein TOCTOU-Fehler.
6. Erfolg folgt erst auf bestätigten Commit. Ein Timeout nach möglichem Commit ergibt einen unbekannten Ausgang und Wiederholung mit demselben Idempotenzschlüssel, keine behauptete Rücknahme.
7. Nur freigegebene Datenprojektionen verlassen den Server; Listen und Antwortbytes bleiben begrenzt. Interne SQL-/Bindingnamen, Stacktraces und Secrets erscheinen nicht in Nutzerfehlern.

OWASP verlangt objektbezogene Berechtigungsprüfungen bei Zugriffen über clientseitig übermittelte Kennungen; UUIDs sind kein Ersatz. Diese Empfehlung trägt insbesondere die Scope-Anforderung für Detail- und Mutationsrouten. [OWASP BOLA](https://owasp.org/API-Security/editions/2023/en/0xa1-broken-object-level-authorization/)

Die erste Authbibliothek bindet **einen** tatsächlich verfügbaren Identitätsadapter an. Privates Sites-Hosting allein liefert noch kein Mehrmandantenmodell. Ein Demo-Actor ist ausschließlich Testfixture und darf kein deploybares Produktions-Login ersetzen.

## 4. D1-/SQLite-Semantik und Buchung ohne Überbuchung

### Tatsächlich verfügbare Primitive

D1 unterstützt vorbereitete, gebundene Statements und `batch()`; bei Fehler eines Statements wird die ganze Batchsequenz zurückgerollt. Eine Menge von Host-`await`-Aufrufen ist deshalb noch keine atomische Transaktion. Für die erste Version erlauben wir nur einen bedingten SQL-Mutationsschritt oder einen vollständig vorab konstruierten Batch; benötigen spätere Operationen ein Host-Zwischenergebnis, muss der Plan zurückgewiesen oder in SQL ausgedrückt werden. [D1 Database API](https://developers.cloudflare.com/d1/worker-api/d1-database/)

D1 beschreibt jede DB als einzeln nacheinander arbeitend. Das schützt nicht zwei getrennte Read-/Write-Requests vor Interleaving. D1-Session-Bookmarks gewährleisten die dokumentierte sequentielle Konsistenz; sie sind weder Nutzeridentität noch eine offengehaltene Transaktion. Zunächst Primärabfragen ohne Sessions beibehalten. Read-Replicas wären ein späterer Adapterausbau mit nachgewiesener Read-after-write-Semantik. [D1 Limits](https://developers.cloudflare.com/d1/platform/limits/), [D1 Read Replication](https://developers.cloudflare.com/d1/best-practices/read-replication/)

D1 erzwingt Foreign Keys und führt Queries in impliziten Transaktionen aus. Das Schema muss Mandantenbeziehungen durch zusammengesetzte Schlüssel absichern, beispielsweise `FOREIGN KEY(tenant_id, customer_id) REFERENCES customers(tenant_id,id)`. Local-SQLite-Tests müssen Foreign Keys aktivieren; sonst wäre die lokale Abnahme schwächer als das Deployment. [D1 Foreign Keys](https://developers.cloudflare.com/d1/sql-api/foreign-keys/)

**Kein `SELECT FOR UPDATE`, keine PostgreSQL-RLS- oder PostgreSQL-Isolationszusage für diesen Adapter.** Fehlende Fähigkeiten werden als Targetdiagnose sichtbar, nicht still durch schwächere Semantik ersetzt.

### Empfohlener erster Buchungsumfang

Die Buchungsbibliothek modelliert Event, Kapazität und Reservierung; Zustand `confirmed | cancelled`. Sie verlangt `quantity > 0` und `sum(confirmed.quantity) <= capacity`, begrenzte ganzzahlige Werte und eindeutige Befehlsidentität. Kapazitätsänderungen und Reaktivierung sind eigenständige zustandsgeprüfte Befehle.

Erster D1-Pfad: **Prüfen und Einfügen einer Reservierung in einem bedingten `INSERT … SELECT`** mit aggregierter aktueller Belegung, Tenant-/Actorpolicy und Unique-Key im selben Statement. Bei keiner eingefügten Zeile wird separat ermittelt, ob bereits ein gleichlautender Auftrag bestätigt wurde oder keine Reservierung möglich war. Dieser Nachleseschritt entscheidet nur über die Antwort; er darf keine zweite Kapazitätsänderung auslösen. Die Abfrageform ist eine Designempfehlung, noch kein verifiziertes Lowering.

Idempotenzschlüssel werden mindestens nach Anwendung, Tenant, Actor und Aktion gescoped und an kanonische Auftragsparameter gebunden. Gleicher Schlüssel und gleiche Parameter führen zur selben unveränderlichen Bestätigung; andere Parameter ergeben Konflikt. Eine eigene Receipt-/Command-Tabelle wird nötig, sobald Reservierungszustand und ursprüngliche Befehlsantwort auseinanderlaufen. Deren Speicherung muss atomisch mit der Mutation erfolgen. Ein bloßes Vorab-SELECT auf den Schlüssel genügt nicht.

DB-Constraints schützen lokale Typ-/Schlüsselregeln. Aggregatinvarianten über mehrere Zeilen sind keine normalen SQLite-CHECK-Ausdrücke. Eine zusätzliche generierte Triggerabsicherung ist möglich, benötigt aber einen eigenen engen Adaptervertrag und D1-Konformitätstests; sie wird nicht beiläufig als bereits gesicherte Universalübersetzung versprochen. [SQLite CREATE TRIGGER](https://www.sqlite.org/lang_createtrigger.html)

Ein allgemeiner Transaktionsplan darf nicht versehentlich nach einem Conditional UPDATE mit null betroffenen Zeilen weitere Wirkung ausführen: **null Treffer sind kein SQL-Fehler** und lösen allein keinen Batch-Rollback aus. Abhängige Statements müssen dieselbe Bedingung tragen oder durch eine nachgewiesene Constraint-/Abort-Abbildung gekoppelt sein. Das ist ein verpflichtender Compiler-Negativtest.

## 5. Datenmodell, Migrationen und Erweiterbarkeit

Start mit Bool, bounded Integer, Text(N), UUID, Option und Records/Varianten; keine impliziten Float-/Integerkonversionen. Geld später als Betrag in Untereinheiten plus Währung und expliziter Rundung. Python-BigInt, JS-Number und SQLite-Integer haben verschiedene Grenzen: Export/DB-Abbildung muss Wertebereiche prüfen und gegebenenfalls einen kanonischen String-Wiretyp verwenden. Keine unbemerkte Präzisionsänderung.

Relationaler erster Umfang: 1:n und n:m über ausdrückliche Join-Entity; NOT NULL, UNIQUE, FK, CHECK und deklarierte Indizes. Delete ist standardmäßig eingeschränkt, Cascade ausdrücklich. Datenbeziehungen sind nicht automatisch API-Exporte. Listen: stabile Sortierung mit eindeutigem Tie-Breaker, Keyset-Cursor, feste Seitengröße; Cursor bleibt ein Datenwert und verleiht keine Autorisierung. Kein N+1-Laden pro UI-Zeile.

Schemaänderungen entstehen aus altem und neuem kanonischem Schema, nicht aus einer frisch angelegten Datenbank. Ein Rename benötigt stabile Feldidentität oder explizite Rename-Absicht. Für V1 nur additive, nachweislich verträgliche Migrationen automatisch planen; Löschen, Typverengung und datenabhängige Umformung mit Backfill-/Rollback- oder Forward-Recoveryplan separat liefern. Kein automatischer DB-Reset. Die w1/w2-Übernahme muss weiterhin idempotent sein. D1 dokumentiert versionierte SQL-Migrationen und eine Anwendungshistorie; unsere Schema-/Artefaktbindung ergänzt diese, ersetzt sie nicht. [D1 Migrations](https://developers.cloudflare.com/d1/reference/migrations/)

## 6. Sicherheits- und Ressourcenregeln der Standardbibliotheken

- UI: Text ist ein Textknoten; kein `innerHTML`, kein Raw-HTML-/Eventhandler-String. URL-Werte haben erlaubte Protokolle, Navigationsziele werden typisiert. Ein späterer Rich-Text-Adapter erhält einen eigenen Sanitizervertrag. CSP am wirklichen Produktionsbundle prüfen.
- Cookieauth: sichere Cookieattribute, Origins gegen Deploymentkonfiguration prüfen, Mutationen auf expliziten Methoden, keine offene CORS-Freigabe. Geeignete CSRF-Token-Integration mit dem Authadapter und Fetch-Metadata ergänzend planen; kein `SameSite`-Alleinbeweis. [OWASP CSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)
- Externe HTTP-Effekte: kein generischer vom Browser steuerbarer Fetch-Proxy. Connectorziel aus Hostkonfiguration, gebundene erlaubte Operationen, Authdaten serverseitig, Redirectregeln und Request-/Response-/Zeitlimits. Ein freier URL-Fetch wäre ein eigenes Produktfeature samt SSRF-Modell. [OWASP SSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)
- Vorhandene Quelltext-/AST-/Unicode-/Bodylimits übernehmen und pro Paketgraph, Instanziierung, Queryplan und Buildausgabe ergänzen. Imports dürfen Compilerlimits nicht vervielfachen.
- Querypläne erhalten deklarierte Limits für Zeilen, Antwortbytes, Parameter, Joins, Batchlänge und Aufwand. Das Begrenzen von Ergebniszeilen begrenzt einen Fullscan nicht; Index-/Queryplanabnahme ist für Filter, Policies und Pagination erforderlich.
- Der Targetmanifest prüft veröffentlichte D1-Grenzen, u.a. 100 gebundene Parameter und 100 Spalten pro Tabelle, statt sie erst im Betrieb zu entdecken. Diese Werte sind Targetversionen, keine ewigen Sprachkonstanten. [D1 Limits](https://developers.cloudflare.com/d1/platform/limits/)
- Deadline und Cancellation eines HTTP-Aufrufs beweisen keinen DB-Rollback. Server-/Connectorbudgets und Replaysemantik müssen deshalb zusammenpassen.

## 7. Reihenfolge mit konkreter Definition of Done

| Meilenstein | Freigabekriterium |
|---|---|
| A: Bibliotheksfähige Grundlage | Module und Signaturen; klare Client-/Server-/Effektgrenzen; deterministische Importauflösung; gleiche W2-App über gemeinsame IR erzeugt; alte Quelldateien unverändert nutzbar. Reine Drittbibliothek ergänzt einen Validator oder zusammengesetztes UI-Element, ohne Compiler-/Hoständerung. |
| B: Daten und allgemeine Oberfläche | History mit Library-Formular, Liste/Picker und mehreren Seiten; neues zweites Datenmodell mit Relations und mindestens zwei Feldern pro Record; End-to-end CRUD, Reload, Persistenz und Migration aus befülltem Altstand. Keine manuelle Änderung generierter Appdateien. |
| C: Mandantenfähiges CRM | Zwei Tenants, mindestens drei Rollen-/Actor-Kontexte, Kontakte und Notizen in 1:n; Liste, Detail und Formular. Unerlaubte Detail-/Listen-/Count-/Relations-/Update-Anfragen liefern keine Fremddaten und ändern nichts. Echter Authadapter auf dem deployten Target. |
| D: Buchung | Capacity 10 und 100 gleichzeitig gestartete Anfragen mit quantity 1 ergeben nach erlaubten transienten Retries exakt 10 bestätigte Reservierungen; nie mehr. Gemischte Gruppenanfragen, Storno und Kapazitätsänderung erhalten Invarianten. Gleichzeitige Replayanfragen erzeugen nur eine Wirkung. Nach Prozessneustart sind Receipts und Zustand unverändert. |
| E: Shop ohne echte Zahlung, anschließend Sandboxconnector | Produkt-/Preis-/Bestellmodelle als Libraries; Betrag und Berechtigung serverseitig. Order plus Outbox atomisch; Sandboxzahlung über begrenzten Adapter, signaturgeprüfte Webhooks, doppelte/vertauschte Ereignisse und Timeout nach Zahlung führen zu konsistentem Zustand. Echte Geldbewegung ist ein eigener späterer Produktfreigabeschritt. |

Die Wiederverwendungsabnahme muss den Compilerkern **vor** Erstellung mindestens einer neuen Fachfunktion einfrieren: Ein Agent baut Gruppenbuchung oder ein neues CRM-Modul nur aus freigegebenen Bibliotheken, und ein weiterer Agent schreibt einen unbekannten Library-Consumer. Muss dafür erneut ein Geschäfts-Spezialfall im Compiler entstehen, ist die Flexibilitäts-DoD nicht erfüllt.

Jeder Browsermeilenstein läuft mindestens in Chromium, Firefox und WebKit, sofern die Testumgebung sie bereitstellt; konkrete Versionen/Engine und tatsächlich ausgeführte Flows protokollieren. WebKit-Tests sind keine automatische Safari-Abnahme auf sämtlichen Apple-Geräten. Responsive Darstellung, Tastaturbedienung, Labels, Fokus-/Fehlerzustände und frühe Klicks vor Hydration gehören zur UI-Abnahme.

## 8. Verbindliche negative und modellbasierte Tests

| Angriff/Fehler | Erwartetes Verhalten |
|---|---|
| Client behauptet anderen tenant_id, owner_id, is_admin oder Preis | Vertrauenskontext entscheidet; unbekannte/verborgene Felder abgewiesen; keine Mutation |
| Fremde UUID in Liste, Detail, Cursor, Beziehung, Bulk-Aktion oder Export | Keine Daten/Counts fremder Tenants; gleiche Policy wie bei normaler Route |
| Kontakt in Tenant A mit parent_id aus B | Querypolicy und zusammengesetzter FK blockieren |
| Rechteentzug parallel zur Änderung | Commit nur entsprechend Policy im atomischen Mutationsschritt; kein unbedingter Schreibschritt auf Basis alter Hostprüfung |
| Import einer server-only Funktion in Browsercode, Secret in Return-/Closure-Wert | Statischer Fehler und Bundle-/Response-Regressionstest |
| Gespeicherte Script-/HTML-/SQL-Angriffsstrings | Exakter Textroundtrip; kein Code-/Queryverhalten |
| Fremde/null/fehlende Origin, Cross-Site-Cookieanfrage, falscher Content-Type | Definierte Ablehnung, keine Mutation |
| Zusätzliche JSON-Felder, Duplicate Keys, Surrogate, NUL, Oversized-Stream ohne Content-Length | Begrenzter Decoder; stabile Diagnose; keine DB-Wirkung |
| Replay gleicher Schlüssel gleichzeitig / Schlüssel mit anderem Auftrag | Eine Wirkung / Konflikt; kein weiteres Dekrement oder zweite Zahlung |
| Conditional UPDATE trifft null Zeilen, späteres Batchstatement würde schreiben | Lowering zurückgewiesen oder gesamte fachliche Wirkung bleibt aus |
| Constraintfehler mitten im Batch | Vorherige Batchänderungen nicht sichtbar; realer D1-Konformitätstest |
| Netzunterbrechung nach Commit, Reload, Wiederholung | Keine falsche Rollbackmeldung; gespeicherte Bestätigung reproduzierbar |
| Reservieren/Stornieren/Kapazität ändern in zufälligen Sequenzen | Referenzmodell und SQLzustand stimmen; `0 <= confirmed <= capacity` bleibt gültig |
| Manipuliertes/zyklisches Paket, tiefe Generics/AST, huge Query/Result | Deterministische begrenzte Diagnose; kein Tool-/Netz-/Hostcodeeffekt |
| Migration eines befüllten Altstands, Wiederanwendung, Abbruch/Neustart | Kein Verlust bestätigter Daten; eindeutige Schemaversion; keine stille Datenverengung |

Tests prüfen beobachtbares Verhalten. Reine Geschäftsverträge erhalten unabhängige Proof-Obligations; SQL-/JS-Lowering wird zunächst durch Differential-/Propertytests und Target-Konformität geprüft. Die Produktionsfreigabe darf einen vollständigen Webbeweis erst behaupten, wenn auch die dafür erforderlichen Übersetzungs- und Adapterannahmen tatsächlich nachgewiesen sind. Testanzahl allein ist kein Abnahmekriterium.

## 9. Externe Zahlungen und länger laufende Abläufe

Eine DB-Transaktion kann einen externen Zahlungsdienst nicht atomisch zurückrollen. Der spätere Workflow nutzt Zustände wie pending/confirmed/failed, eine zusammen mit der Bestellung persistierte Outbox, begrenzte Wiederholungen, stabile Connector-Idempotenz und eine Inbox mit eindeutiger Provider-Event-ID. Webhooksignatur und aktuelle Order-/Amount-/Currency-Zuordnung werden vor Zustandsänderung geprüft; Payloads bleiben externe Daten. Es gibt kein pauschales Exactly-once-Versprechen. Unklare Providerantworten benötigen Abgleich statt blindem Neusenden. Dies ist Library plus ausdrücklich vertrauenswürdiger Connector, keine neue Syntax `buy` im Compiler.

## Empfehlung an den Lead

Zuerst allgemeine Module/Typen/Effekte und die gemeinsame Web-IR schaffen, dann dieselbe bestehende History-App als Bibliotheksconsumer migrieren. Anschließend CRM als Test der Berechtigungs- und Datenmodellflexibilität, danach Buchung als Test der atomischen Zustandslogik. Einen weiteren Backendstack oder freien FFI-Pluginmarkt jetzt nicht ergänzen. Die wichtigste Architekturgrenze ist ein kleiner überprüfbarer Plan, dessen konkretes D1-Lowering die versprochenen Wirkungen tatsächlich erhalten kann.
