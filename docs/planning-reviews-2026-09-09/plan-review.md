# Unabhängiges Gesamtarchitekturreview

Stand: 2026-09-09. Gegenstand: `LLM-Language-Weiterentwicklungsplan.md`, Planrevision 1, und die vier Fachbeiträge unter `reviews/`. Nur Dokumentenreview; keine Compileränderungen, keine ausgeführten Tests und keine neue Abnahme. Plattformfakten werden hier aus dem bereits primärquellenbelegten Web-/Securitybeitrag übernommen; zusätzliche Recherche war für diese Konsistenzprüfung nicht nötig.

## Entscheidung

Die ursprünglichen Befunde R1–R3 wurden während dieses Reviews im Hauptplan konkret behoben: Nulltrefferregel, Receiptbindung, frühe D1-Targetprobe, Aggregate mit Gesamtbelegungsdefinition sowie Snapshot und unabhängiges Source-to-Core-Bindungsgate sind jetzt enthalten. Auch die zunächst abweichende Division ist ausdrücklich aufgelöst. Die folgenden ursprünglichen Befunde bleiben als Reviewhistorie erhalten.

**Abschlussstatus nach erneutem eng begrenztem Dokumentenreview: R1–R6 sind im aktuellen Hauptplan auf Planungsebene geschlossen.** Der interne Invariantenscope, das konkrete M2-Genericsgate und die exakte D1-Treibergrenze sind inzwischen ebenfalls enthalten. Die unten stehenden Befunde und vorgeschlagenen Ergänzungen dokumentieren ihren ursprünglichen Entstehungsstand; sie sind keine verbleibenden Blocker. Normative Spezifikation, Implementierung und die jeweils geforderten Prüfungen bleiben die Arbeit der zugehörigen Meilensteine.

## R6 — Hoch: Zeilensicht des Benutzers darf die Invariantenaggregation nicht verkleinern

**Fundstelle:** aktualisierter Hauptplan 7.2 „Filter/Policies gelten vor Aggregation“ in Verbindung mit 7.3 Gesamtbelegung.

Die Regel ist für öffentlich erlaubte Listen-/Countabfragen richtig. Wird aber dieselbe Eigentümerpolicy automatisch in eine Kapazitätsabfrage eingefügt, berücksichtigt deren SUM nur die eigenen Buchungen. Dann kann jeder Benutzer individuell innerhalb der Kapazität liegen, obwohl die Veranstaltung insgesamt überbucht ist.

**Minimale Ergänzung:**

> Die serverseitige Invariantenprüfung erhält eine ausdrücklich autorisierte, ressourcenbezogene Aggregationsfähigkeit über alle für die Invariante relevanten Zeilen. Sie ist von der Zeilensicht des aufrufenden Benutzers getrennt. Kapazität umfasst alle aktiven Buchungen des Events; die Nutzerquote umfasst alle aktiven Buchungen des betroffenen Nutzers im spezifizierten Geltungsbereich. Diese Fähigkeit gibt dem Client keine Berechtigung, fremde Zeilen oder interne Aggregate abzurufen. Ausgabeprojektion und fachliche Fehler bleiben separat autorisiert.

**DoD:** Mehrere Benutzer dürfen jeweils nur eigene Buchungen auflisten. Ihre gleichzeitigen Reservierungen müssen trotzdem die gemeinsame Eventkapazität einhalten; versteckte fremde Zeilen dürfen den Kapazitätscheck nicht entlasten. Derselbe Test prüft, dass weder Response noch Fehler fremde Details herausgeben.

## R1 — Blocker vor M4: D1-Atomarität, Autorisierung und Receipts sind nicht vollständig miteinander verbunden

**Fundstelle:** Hauptplan 7.3 und 8.2; ausführlicher bereits `web-security.md`, Abschnitte 3 und 4.

Ein Conditional UPDATE mit null betroffenen Zeilen ist kein SQL-Fehler. Ein anschließend ausgeführtes Batchstatement kann dennoch einen Buchungsdatensatz oder ein Erfolgsreceipt schreiben. Die jetzige Formulierung „fester Transaktionsplan“ schließt diesen konkreten Fehler nicht ausdrücklich aus. Außerdem fehlen die unveränderliche Bindung eines Idempotenzschlüssels an seine Parameter und die Unterscheidung zwischen aktuellem Buchungszustand und ursprünglicher Befehlsantwort. Nach einer Stornierung darf ein Replay der ursprünglichen Reservierung weder nochmals reservieren noch eine nachträglich veränderte Bestätigung liefern.

**Minimale Ergänzung in 7.3:**

> Ein Nulltreffer einer bedingten Mutation löst keinen automatischen Batchrollback aus. Alle abhängigen Änderungen und Erfolgsreceipts müssen durch dieselbe geprüfte Bedingung gekoppelt sein; andernfalls lehnt der Compiler den Plan ab. Mutationsrelevante Berechtigungen, Tenantbindung und Zustandsvorbedingungen werden im selben atomischen DB-Plan geprüft. Idempotenz bindet Anwendung, Tenant, Actor, Aktion, Schlüssel und kanonische Parameter. Gleicher Schlüssel mit anderen Parametern ergibt Konflikt. Mutation und unveränderliche Befehlsbestätigung werden atomisch gespeichert; eine spätere Stornierung verändert diese Bestätigung nicht.

**Zusätzliche M4-DoD:** Nulltreffer vor weiteren Batchwirkungen; Constraintfehler mitten im Batch; paralleler Rechteentzug; gleicher Schlüssel mit anderem Payload; Replay der ursprünglichen Reservierung nach Cancel; Transportabbruch nach Commit. Jeweils beobachtbare DB-Wirkung und Antwortsemantik prüfen. Vor dem Ausbau der kompletten Buchungsoberfläche einen kleinen vertikalen D1-Nachweis genau dieses allgemeinen Plans durchführen. Erst anschließend darauf aufbauende Fachbibliothek freigeben.

## R2 — Blocker für M5: Der geplante Queryumfang trägt die konkrete neue Benutzerquote noch nicht ausdrücklich

**Fundstelle:** Hauptplan 6.1, 7.2 und die Library-only-Challenge in 8.2.

Die Query-Algebra nennt Filter, Projektion, Join, Sortierung und Pagination, aber keine Aggregate. M5 verlangt „maximal vier Plätze pro Benutzer, auch über mehrere Buchungen“. Das ist eine Eigenschaft des vollständigen betroffenen DB-Zustands und lässt sich nicht durch Falten einer geladenen Seite prüfen. Ebenso muss der Buchungszähler an die tatsächlich bestätigten Buchungszeilen gebunden sein; `0 <= reserviert <= kapazität` alleine erlaubt einen korrekten Zähler neben falschen Buchungsdatensätzen.

**Minimale Ergänzung:**

> Der erste Queryumfang enthält policygebundene skalare `count`-/`sum`-Aggregate über typisierte Filter und erforderliche Joins. Leeres Aggregat, NULL-/Optionverhalten, exakte Zahlenbereiche und Fehler sind spezifiziert. Policies gelten vor Aggregation; Pagination begrenzt die Antwort und nicht die Menge, über die die fachliche Invariante definiert ist. Die Buchungsinvariante enthält zusätzlich `reserviert = Summe der Mengen aller bestätigten Buchungen des Events`. Ein materialisierter Zähler benötigt diese Erhaltungsbeziehung für jede schreibende Aktion. Auch die Benutzerquote wird im atomischen Mutationsplan geprüft.

Alternativ wäre ein vollständig spezifiziertes allgemeines Modell materialisierter Nutzer-/Eventzähler möglich. Das ist eine technische Entscheidung des Leads; ein spontaner `user-booking-quota`-Opcode oder ungeschützter Vorab-Read ist keine Lösung für M5. Die gewählte generische Fähigkeit muss vor dem Freeze vorhanden sein.

## R3 — Hoch, vor M1: Zertifikatsbindung beginnt am gelinkten P0; die Quelle darf nicht mitbehauptet werden

**Fundstelle:** Hauptplan 4.4, 5.3 und 8.1; ausführlich in `libraries.md` unter „Erster Meilenstein“ und „Hashes“.

Die Gesamtprüfung des gelinkten P0 ist richtig. Ein Fehler bei Exportauflösung, Callindex-Umschreibung oder Bindern kann aber ein anderes Programm erzeugen, dessen Vertrag anschließend korrekt bewiesen wird. Der allgemeine Hashabschnitt bindet Inhalte, definiert jedoch noch keinen Source-to-Core-Linkvertrag oder das Verhalten bei Dateiaustausch zwischen Hashprüfung und Verwendung.

**Minimale Ergänzung der normativen M1-Dateien und DoD:**

> Der Linkvertrag definiert Exportname→lokaler Funktionsindex→globaler Funktionsindex, Parameter-/Bindererhaltung, Callziel und Topologie eindeutig. Der Build liest Quellen einmal begrenzt ein und arbeitet danach ausschließlich auf einem unveränderlichen, gehashten Snapshot. Das Linkmanifest bindet autorisierte Quellspezifikation, genaue Quellen, Exportauflösung und gelinkten Core. Das P0-Zertifikat belegt zunächst den benannten Vertrag des gelinkten Core; eine formal bewiesene Quellübersetzung wird damit nicht behauptet.

Verbindliche Negativfälle: gleich typisierte, semantisch verschiedene Exportziele vertauschen; Parameter/Binder vertauschen; falschen Callindex nach einem Diamond-Import erzeugen; Quelle nach Snapshotbildung austauschen. Positiv: zwei Consumer plus mindestens eine transitive Abhängigkeit, Rebuild in unterschiedlich benannten Verzeichnissen und identische semantische Linkartefakte. Ein späterer unabhängiger Link-/Loweringchecker kann die formale Aussage erweitern; M1 muss dafür keinen unbelegten Beweisanspruch erheben.

## R4 — Mittel: M2 ist gegenüber M1 und M4 noch zu vage abnehmbar

**Fundstelle:** Hauptplan Meilensteintabelle, M2 „Mehrere Fachfunktionen ausdrückbar“.

Dieser Satz könnte schon durch zwei spezialisierte Beispiele erfüllt werden. Er prüft weder erststufige Generics noch die begrenzte Iteration, auf denen tatsächliche Bibliotheksflexibilität beruht. Ein Featureinventar muss vor dem jeweiligen Implementierungsmeilenstein feststehen, ohne jetzt die vollständige a1-Grammatik auszuarbeiten.

**Minimales M2-Gate:** Ein generisches natives Modul mit Records, Varianten/Result, begrenzter Liste und statisch gebundenem `fold`-/`map`-Callback wird mit zwei nominal unterschiedlichen Fachtypen instanziiert. Getrennte Beispiele prüfen Textkomposition und exakte große Ganzzahlen. Falscher Callbackeffekt, nominal falscher Typ, nicht abgedeckter Matchzweig und überschrittenes Instanz-/Schrittbudget werden abgewiesen. Ununterstützte Beweistheorie bleibt explizit unbewiesen und kann eine verpflichtende Proofpolicy nicht passieren. Diese Module entstehen ohne neue Fachprimitiven.

## R5 — Mittel: Exakte Int-Repräsentation muss auch den DB-Treiber umfassen

**Fundstelle:** Hauptplan 4.2 und M3 Targetcodec.

`bigint` im TS-Code und Dezimalstrings im HTTP-Format reichen nicht aus, wenn zwischen SQLite/D1 und TS ein ungenauer Zahlenwert entsteht. Der Plan verlangt exakte Semantik, benennt aber noch keine harte Strategie an dieser Grenze.

**Minimale M3-Festlegung:** Jeder persistierbare Zahlentyp erhält eine eindeutige SQL-/Treiber-/Wireabbildung. Entweder wird der DB-Zahlentyp auf den exakt transportierbaren Bereich eingeschränkt, oder die DB liefert für größere Werte ausdrücklich eine kanonische Textdarstellung, die ohne `number`-Zwischenschritt decodiert wird. Boundaries um `2^53`, I64-Endpunkte, negative Werte und Aggregatüberlauf gehören zur Targetabnahme. Kein automatisches Casting unbeschränkter Ints auf SQL-Integer.

## Konsistenzentscheidungen ohne Blocker

- P0, w1 und w2 bleiben eigenständige versionierte Semantik; insbesondere ersetzen und anhängen sind klar getrennt. Die vorgeschlagene Gesamtneuprüfung importierter P0-Bündel vermeidet unzulässige modulare Beweiswiederverwendung.
- Allgemeine Sprache plus native Module deckt die geforderte Richtung ab. Keine freien Fremdcodefragmente und das eingefrorene Library-only-Gate verhindern den offensichtlichen Ausweg über versteckte Fachopcodes. Gewöhnliche Bibliotheken dürfen sich für M5 ändern; Compiler, primitive Standardruntime und Adapter müssen identisch bleiben.
- `compiled`, getestete Übersetzung, formaler Corevertrag und Artefaktintegrität sind im Hauptplan richtig getrennt. Keine zusätzliche Vollbeweisbehauptung ergänzen.
- Die zunächst unterschiedliche Division ist im aktuellen Hauptplan aufgelöst: `int.divmod` ist euklidisch mit `0 <= r < abs(b)`; `i64.div_checked` rundet gegen null und behandelt Null sowie `MIN_I64 / -1` als Fehler. Das ist ausdrücklich als Expertenentscheidung protokolliert. Die früher im Review beschriebene einheitlich gegen null gerundete Division gilt nicht mehr.
- Ein geschlossenes, beschränktes Profil ist keine beliebig mächtige Universalprogrammiersprache. Diese Grenze wird offen benannt und passt zum inkrementellen Ziel. Vor M3 muss feststehen, wie UI-/Querykomposition als getypte Werte beziehungsweise deklarative Konstruktion funktioniert; daraus darf keine bloße Widgetliste mit einem neuen Namen werden.

## Abschlussprüfung der Befunde

Der aktuelle Hauptplan wurde ausschließlich auf die Schließung der bereits benannten R1–R6 erneut gelesen. Es wurden keine zusätzlichen Untersuchungen oder Implementierungstests durchgeführt.

| Befund | Status auf Planungsebene | Konkrete Schließung im Hauptplan |
| --- | --- | --- |
| R1: D1-Atomarität und Idempotenz | Geschlossen | 7.2 fordert Policies atomar mit Mutation; 7.3 legt Nulltrefferregel, Bindung an kanonische Parameter, dauerhafte Befehlsresultate, atomare Kopplung vor M4, Replay nach Cancel und frühe M3-Targetprobe fest. |
| R2: Aggregate und vollständige Belegung | Geschlossen | 7.2 enthält getypte `sum`-/`count`-Aggregate samt Leerwert-/Integerregeln; 7.3 definiert `reserviert` unmittelbar als Summe aktiver Buchungsmengen, ohne zweiten Zähler. |
| R3: Quelle→gelinkter Core | Geschlossen | 5.2/5.3 definieren Export-/Index-/Bindererhaltung und unveränderlichen Snapshot; 8.1 enthält einen unabhängigen Source-to-Core-Linkcheck, Mutationen und transitive Zweiconsumerabnahme. |
| R4: M2-Genericsabnahme | Geschlossen | 8.2 verlangt dieselbe generische `map<T,U,N>`-Bibliothek für zwei Recordtypen und zwei Kapazitäten, konkrete Negativfälle sowie einen generischen Zustandshelfer für zwei Fachmodule. |
| R5: Exakte DB-Treibergrenze | Geschlossen | 4.2 begrenzt native numerische Bindungen/Rückgaben samt Zwischen-/Aggregatwerten auf den sicheren Bereich; größere Zahlen gehen als kanonischer Text durch die Grenze. Die tatsächliche Treiberabnahme enthält Werte um `2^53`, negative Gegenstücke, I64-Endpunkte und ungültige Dezimalformen. |
| R6: Interner Invariantenscope | Geschlossen | 7.2/7.3 trennen öffentliche Lesesicht und autorisierte interne Gesamtaggregation ausdrücklich; Mehrbenutzerabnahme prüft gemeinsame Kapazität trotz persönlicher Zeilensicht sowie fehlende Offenlegung fremder Details/Counts. |

**Ergebnis:** Innerhalb dieses eng begrenzten Abschlussreviews bleiben keine der sechs Planungsbeanstandungen offen. Die beschriebenen Gates sind Anforderungen an die künftige Umsetzung, keine bereits bestandenen Prüfungen. Nächste Implementierungsarbeit bleibt M0/M1.
