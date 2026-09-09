# Architektur- und Entscheidungslog

## 2026-08-09 — D-001: Korrektheit ist spezifikationsrelativ

**Entscheidung:** Die Sprache behauptet keine absolute Korrektheit außerhalb expliziter Spezifikationen und Annahmen. `verified` bedeutet, dass der Kernel einen Beweis für den angegebenen Vertrag akzeptiert.

**Mathematische Begründung:** Ein Programm kann nur bezüglich einer formalen Relation zwischen Eingabe und Ausgabe korrekt sein. Aus `p ⊨ S` folgt nicht, dass `S` die tatsächliche menschliche Absicht vollständig beschreibt.

**Folge:** Jeder Release-Bericht muss bewiesene Eigenschaften und Annahmen getrennt zeigen.

## 2026-08-09 — D-002: Totaler Kern, partielle Operationen explizit

**Entscheidung:** Der Proof Core ist total. Erwartbare partielle Operationen liefern algebraische Fehlerwerte oder verlangen einen Beweis ihrer Vorbedingung.

**Begründung:** Totale Funktionen sind kompositionaler zu beweisen. Versteckte Exceptions oder Traps zerstören die einfache Bedeutung von Funktionsverträgen.

**Folge:** Kein `panic` im reinen Core. `Partial` ist ein sichtbarer Effekt und reduziert ohne Zusatzbeweis die Assurance.

## 2026-08-09 — D-003: Arithmetikdomänen werden getrennt

**Entscheidung:** `Nat` und `Int` besitzen mathematische Semantik. Maschineninteger besitzen explizite `checked`, `proved`, `wrap` und `sat` Operationen.

**Begründung:** Ein globaler Überlaufmodus macht lokale Terme kontextabhängig. Getrennte Operatoren geben jedem AST-Knoten genau eine Semantik.

**Folge:** Standardcode wrappt niemals still. Bewiesene Checks können nach Kernelprüfung entfallen.

## 2026-08-09 — D-004: Division durch null und `MIN/-1`

**Entscheidung:** `div.checked` liefert `Err DivZero` beziehungsweise `Err Overflow`. `div.proved` verlangt `NonZero` und bei signed Maschinenintegers den Ausschluss von `MIN/-1`.

**Begründung:** Damit ist Division total oder ihre Definitionsdomäne ist Teil des Typs. Beide Varianten sind formal eindeutig und erzeugen keine plattformabhängigen Traps.

**Folge:** Ein konstantes ungültiges `div.proved` ist ein Compile-Fehler; `div.checked 1 0` ist ein gültiger Ausdruck mit Ergebnis `Err DivZero`.

## 2026-08-09 — D-005: Kanonische Präfixsyntax

**Entscheidung:** Die erste Syntax ist ein einzelnes, geklammertes Präfixformat. Keine Präzedenz, kein syntaktischer Zucker und keine implizite Überladung im Core.

**Begründung:** Der Parsebaum ist direkt aus der Tokenfolge erkennbar. Alpha-Äquivalenz wird durch De-Bruijn-Indizes und globale Hashreferenzen kanonisiert.

**Verworfene Alternative:** rein numerische Opcodes. Sie sparen möglicherweise Bytes, verschlechtern aber vor einer Messung voraussichtlich Modellverständnis, Diagnose und Reparatur.

## 2026-08-09 — D-006: Dependent Types plus affine Ressourcen

**Entscheidung:** Der Kern kombiniert abhängige Typen für funktionale Korrektheit mit Multiplizitäten für Ressourcen und Capabilities.

**Begründung:** Curry-Howard modelliert logische Verträge; lineare/affine Logik modelliert Verbrauch und Exklusivität. Beide adressieren unterschiedliche Fehlerklassen und sind gemeinsam nötig.

## 2026-08-09 — D-007: Kein Vertrauen in Agenten oder Solver

**Entscheidung:** Agenten und Solver liefern Kandidaten. Nur ein kleiner deterministischer Kernel akzeptiert Beweise.

**Begründung:** Synthesequalität beeinflusst Vollständigkeit und Geschwindigkeit, nicht Soundness. Der Checker muss wesentlich einfacher als der Generator sein.

## 2026-08-09 — D-008: Übersetzung wird bewiesen oder validiert

**Entscheidung:** Proof-Core-Korrektheit allein genügt nicht für Binärkorrektheit. Compilerpässe sind allgemein bewiesen oder erzeugen konkrete Translation-Validation-Zertifikate.

**Begründung:** Ein korrekter Quellterm kann durch einen fehlerhaften Optimierer oder Backendpass verfälscht werden.

## 2026-08-09 — D-009: TDD für den Fabrik-Bootstrap

**Entscheidung:** Die erste Implementierung von Parser, Kernel, Compiler und Fabrik wird mit TDD, Fuzzing, Property- und Differential-Tests gebaut. Formale Beweise werden schrittweise ergänzt.

**Begründung:** Vor dem selbstverifizierten Bootstrap existiert noch keine vollständige Beweisinfrastruktur. Tests liefern schnelles Feedback, ersetzen aber keine spätere formale Vertrauensreduktion.

**Folge:** Erzeugte A2+-Programme benötigen für bewiesene Eigenschaften keine klassischen Unit-Tests. Systemgrenzen und nicht modellierte Eigenschaften bleiben test- oder messpflichtig.

## 2026-08-09 — D-010: Working name und Versionsstatus

**Entscheidung:** `LLM-Language` ist nur der Projektname. Die Dokumente tragen `v0.1-draft` und sind noch kein stabiler Sprachstandard.

**Folge:** Namen, Mnemonics und konkrete Core-Calculus-Auswahl bleiben bis zum P0-Prototyp änderbar.

## 2026-09-08 — MVP-Abgrenzung, Status: Architekturvorschlag

**Anlass:** Sonny fragt nach dem MVP der neuen Sprache. Die folgenden Einträge dokumentieren den empfohlenen Umsetzungsschnitt; sie behaupten keine Implementierung oder ausgeführten Tests. Die Entscheidungen D-001 bis D-010 bleiben bestehen. Die breite v0.2-Liste aus der Projektübersicht wird in P0 und nachfolgende Erweiterungen aufgeteilt.

**Ausführlicher Entwurf:** [MVP P0 — Verifizierte Funktionen und Reparaturschleife](https://app.notion.com/p/3d52a8c323a2819687a1c1e385f9e6f8).

### D-011: Durchgängiger P0 für reine, totale Funktionen

**Vorschlag:** CLI mit JSON-Ein- und Ausgaben. Ein unveränderlicher Vertrag führt über Kandidatensynthese, Prüfung, Gegenbeispiel und begrenzte Reparatur zu einem kernelgeprüften Core, der im Referenzinterpreter ausgeführt wird. Erstes Beispiel: Kontingentfreigabe als Minimum aus Anfrage und Verfügbarkeit.

**Sprachumfang:** Bool, mathematisches Int, unveränderliche Werte, let, if, Vergleiche, boolesche Verknüpfungen, Addition, Subtraktion und Multiplikation mit Integerkonstanten. Nichtrekursive Funktionen innerhalb einer unit, leere Effektmenge, Multiplizität `*`, quantorenfreie lineare Verträge. Rekursionszyklen und nicht unterstützte Operatoren werden abgewiesen. Bool und Int bleiben auch in einer Python-Implementierung strikt getrennt.

**Mathematische Begründung:** Ein endlicher Core mit azyklischem Aufrufgraphen ist strukturell terminierend. Lineare Integerarithmetik begrenzt die Beweissuche; allgemeine nichtlineare Integerarithmetik ist unentscheidbar. Quelle: [Z3 Arithmetic](https://microsoft.github.io/z3guide/docs/theories/Arithmetic/).

**Abgrenzung:** Nat, I64, Result und die beschlossenen Division-/Overflow-Operatoren folgen in P1. Abhängige Typen, affine Ressourcen, Arrays und nachweislich terminierende Iteration bleiben Ausbauziele. P0 implementiert nur ein ausgewiesenes Fragment, keine neue abweichende Gesamtsemantik.

### D-012: Belegprüfung ist Teil der MVP-Abnahme

**Vorschlag:** Z3 bleibt untrusted und sucht Gegenbeispiele sowie Belegkandidaten. `UNSAT` allein führt nicht zu `proved`. Der kleine Kernel prüft den Vertrag relativ zum exakt gebundenen Core; er rekonstruiert Typen, symbolische Auswertung und Verpflichtungen selbst. Eine extern gelieferte Formel darf nicht ungeprüft als Programmbedeutung gelten.

**Erster Zertifikatsumfang:** Boolesche Fallunterscheidung mit geprüfter Abdeckung, Gleichheitsumformungen und lineare Widerspruchsbelege. Exakte rationale Koeffizienten kombinieren normierte Ungleichungen zu einem Widerspruch. Integer-Striktheit wird korrekt normiert. Nicht unterstützte Integralschlüsse oder Solverbeweisformen bleiben `unverified`.

**Mathematische Begründung:** Nichtnegative Linearkombinationen gültiger Ungleichungen bleiben gültig. Widerspruch über der reellen Relaxation schließt auch ganzzahlige Lösungen aus; die Umkehrung wird nicht behauptet. Vollständigkeit des ersten Zertifikatsformats für alle linearen Integerprobleme ist kein P0-Ziel. Der Kernel muss die gesamte Herleitung einschließlich Zweigabdeckung prüfen.

**Vertrauensgrenze:** Der Bootstrap-Kernel ist Teil der TCB; Tests machen seine Implementierung nicht selbst formal bewiesen. Das ist ein eingeschränkter Vorläufer des geplanten Proof Core. Ein bereits implementierter vollständiger Checker für das interne Z3-Beweisformat wird nicht vorausgesetzt.

### D-013: Ausführung des geprüften Core und ehrliche Assurance

**Vorschlag:** Referenzinterpreter statt nativem Backend im MVP. Host-Eingaben werden typvalidiert und auf die Vorbedingung geprüft. Interpreter, Python-Runtime, Betriebssystem und Hardware bleiben dokumentierte Annahmen. Endliche mathematische Auswertung garantiert kein unbegrenztes physisches RAM.

**Begründung:** Jeder zusätzliche Übersetzungspass vergrößert die Lücke zwischen bewiesenem Core und ausgeführtem Artefakt. P0 vermeidet diesen Pass, beweist dadurch aber nicht die Implementierung des Interpreters.

**Folge:** Ziel ist A2 innerhalb des P0-Profils. Ohne Target-Validierung und vollständigen Build-Sealer keine A3-/A4-Behauptung. Ein Manifest bindet Profil, Vertrag, Core, Zertifikat und Checker-Version; es ersetzt keine Beweise.

**Kanonisierung:** De-Bruijn-Binder und normalisierte Literale bleiben gesetzt. P0-interne Aufrufe verwenden Deklarationsindizes; externe Hashreferenzen folgen mit Imports. Inhalts-Hashes werden domänengetrennt ohne eigenes Hashfeld berechnet, um Selbstreferenz zu vermeiden. Die Deklarationsreihenfolge muss deterministisch sein.

### D-014: Unveränderliche Verträge und nachvollziehbare Fehler

**Vorschlag:** Der Syntheseprozess erhält keine Schreibrechte auf Vertrag oder Prüfer. Er darf Körper und Belegkandidaten ändern. Jeder Versuch bindet die exakten Artefakte; jede Änderung invalidiert die alte Freigabe. Für die erste Demo höchstens drei Kandidaten je Aufgabe, zusätzlich explizite Zeit- und Größenbudgets.

**Diagnosen:** `invalid`, `counterexample`, `unverified`, `proved`; leere Vertragsdomänen werden als `contract_empty` gesondert gemeldet. Ein erfüllendes konkretes Eingabebeispiel wird für die MVP-Demo nachgerechnet. `ensures true` bleibt gemäß v0.1 zulässig, wird aber nicht als substantieller Funktionsnachweis dargestellt. `unknown`, Timeout oder abgelehntes Zertifikat liefern keine Freigabe.

**Mathematische Begründung:** Der Nachweis lautet für alle Eingaben: Vorbedingung impliziert Nachbedingung des ausgewerteten Core. Eine widersprüchliche Vorbedingung macht diese Aussage trivial; nur Obergrenzen lassen unter Umständen die bedeutungslose Nullfunktion zu. Daher verlangt die Kontingentdemo zusätzlich, dass das Ergebnis einer der beiden Eingaben entspricht. Zusammen mit beiden Obergrenzen legt dies das Minimum fest.

**Beispiel, nicht ausgeführter Solverlauf:** Der falsche Körper `requested` verletzt bei requested=7 und available=3 die Verfügbarkeitsgrenze. Solver-Gegenbeispiele müssen später im Referenzinterpreter nachgerechnet werden.

### D-015: Beweis-Gate vor Modellintegration

**Vorschlag:** Reihenfolge: (1) Parser/Core/Typen/Interpreter, (2) Verträge und Gegenbeispiele, (3) Zertifikatskernel, (4) ein Modelladapter und Reparaturschleife. Der anspruchsvollste Teil ist die Soundness der Belegprüfung, nicht die Modellauswahl.

**Abnahme:** Zehn Golden Programs: Identität, Minimum, Maximum, Betrag, Clamp, nichtnegative Differenz, Intervallüberschneidungslänge, Kontingentfreigabe, gestaffelte Ganzzahlgebühr und boolesche Zugangsregel. Korrekte Referenzprogramme müssen akzeptiert, Gegenbeispiele validiert, gefälschte Belege und veraltete Bindungen abgelehnt werden. Die Reparaturdemo hält den Vertrag konstant. Kein universelles Lösungsversprechen für drei Modellversuche.

**Prüfstrategie:** TDD mit pytest, Type Hints, Ruff und Typchecker für die Implementierung; Property-Tests für Kanonisierung, Binder, deterministische Auswertung und Arithmetik; strukturiertes Fuzzing für Parser und Checker. Tests bleiben für den Fabrik-Bootstrap erforderlich. Bewiesene Eigenschaften erzeugter Funktionen brauchen keine redundanten klassischen Unit-Tests.

**Messung:** Erfolgsquote, Modelltoken, Reparaturversuche, Prüfzeit, Gesamtzeit und tatsächlich angefallene Kosten. Tokenoptimalität von S-Expressions wird nicht vorausgesetzt. Die Modellintegration nutzt einen vorhandenen Zugang, dessen tatsächliche API-Nutzbarkeit separat geprüft wird. Keine neue Subscription und kein eigenes Modelltraining als MVP-Voraussetzung.

### D-016: Geometric Reasoning bleibt Hintergrundidee

**Status:** Explizite Nutzervorgabe aus diesem Gespräch.

**Entscheidung:** Sophontics Ansatz beeinflusst die MVP-Architektur vorerst nicht. Ein späterer Synthesemechanismus darf ausgetauscht werden, sofern Verträge, Prüfer und Akzeptanzkriterien unverändert bleiben.

## 2026-09-08 — Architekturreview mit zwei Subagents

**Auftrag:** Erneutes Gesamtreview und Diskussion mit zwei Subagents. Beteiligte: Lead-Architekt, `formal_semantics_review` und `compiler_factory_review`. Alle neun v0.1-Dateien, dieser aktuelle Log und der neuere P0-MVP wurden einbezogen. Befunde: [Reviewbericht](REVIEW-2026-09-08.md). Präzisierungen: [P0-Addendum](specs/06-P0-REVIEW-AMENDMENTS.md).

**Status:** Die folgenden technischen Entscheidungen konkretisieren den Entwurf. Keine Compilerimplementierung, bestandene Test-Suite oder formaler Soundness-Beweis wird behauptet. Das Addendum hat für P0 Vorrang vor widersprechenden älteren Formulierungen.

### D-017: Autoritativer Contract-AST statt Vertrauen in den Elaborator

**Entscheidung:** Profil, Signaturen, Parameterreihenfolge und Verträge werden als kanonische Baseline eingefroren und vom TCB-Parser/Checker selbst rekonstruiert und typgeprüft. Kandidaten dürfen nur Körper und Zertifikate liefern. Keine generative Autoren-Elaboration in der P0-Beweiskette.

**Begründung:** Aus einem Beweis für einen elaborierten Satz folgt nicht, dass dies der beabsichtigte ursprüngliche Satz ist. Ein Elaborator könnte `ensures result=x` in `true` verwandeln. Hashbindung allein verhindert dies nicht. Der Schritt von menschlicher Absicht zum autorisierten Contract-AST bleibt sichtbar spezifikationsabhängig.

**Alternative:** Source→Core-Übersetzung gleich separat beweisen oder validieren. Für P0 unnötiger Zusatzumfang; später erforderlich, wenn die Garantie ausdrücklich den Autorentext einschließen soll.

### D-018: Geschlossener Zertifikatsumfang cert-v0

**Entscheidung:** Der Checker erzeugt alle Verpflichtungen und booleschen Zweige selbst. Zertifikate liefern gebundene Blatt-IDs und nichtnegative rationale Gewichte für ganzzahlige lineare Zeilen. Akzeptanz verlangt exakt verschwindende Variablenkoeffizienten und eine negative kombinierte Schranke. Keine erfundenen Prämissen, ausgelassenen Zweige, neuen Cut-Atome, GCD-/Rundungsschlüsse oder Gleitkommatoleranzen.

**Mathematische Begründung:** Nichtnegative Kombinationen von `a_i*x <= b_i` mit `Sum(lambda_i*a_i)=0` und `Sum(lambda_i*b_i)<0` ergeben einen Widerspruch. Ganzzahlige Striktheit wird vorab exakt normiert. Aufrufvorbedingungen sind eigene Pflichten; bloße Inlining-Korrektheit der äußeren Nachbedingung genügt nicht.

**Diskussion:** Der Lead korrigierte die zuerst zu allgemeine Aussage, `2*x=1` sei mit linearen Belegen nicht schließbar: Ein zusätzlicher Split `x<=0`/`x>=1` würde genügen. Erst die gemeinsam beschlossene Einschränkung auf vorhandene VC-Atome macht dies zu einem erwarteten unvollständigen Fall. Freie Splits bleiben eine mögliche spätere, separat versionierte Erweiterung.

### D-019: Beweis, Vertragsdomäne und Laufstatus getrennt

**Entscheidung:** `proved` beschreibt den Core-Vertrag. `domain_nonempty` verlangt einen konkret geprüften Zeugen; `contract_empty` einen akzeptierten Unerfüllbarkeitsbeleg; andernfalls `domain_unknown`. Konkrete Ausführung meldet separat Rückgabe, Eingabefehler, Ressourcenende oder Hostfehler.

**Begründung:** Fehlende Evidenz für Erfüllbarkeit ist keine Evidenz für Unerfüllbarkeit. Ein vakuoser Beweis zählt nicht als erfolgreiche MVP-Demo; ein Host-Budgetabbruch widerlegt dagegen nicht automatisch abstrakte Terminierung.

### D-020: Geordnete P0-Deklarationen und explizite Binder

**Entscheidung:** P0 erhält Deklarationsreihenfolge und erlaubt nur Aufrufe früherer Deklarationen. Damit entfällt dort die allgemeine Abhängigkeitssortierung aus v0.1. `result` ist ein separater Nachbedingungsplatz; `let` erweitert nur den Körperkontext. Verträge bleiben frei von Funktionsaufrufen.

**Begründung:** Streng absteigende Aufrufindizes geben eine endliche Auswertungsstruktur. Geordnete ASTs vermeiden unnötige Permutationskanonisierung und Indexdrift. Präzise Kontextregeln sind Voraussetzung korrekter Substitution und Gegenbeispiele.

### D-021: Verlustfreier Integertransport und identischer Ausführungs-Core

**Entscheidung:** JSON transportiert mathematische Integer als typisierte kanonische Dezimalstrings, rationale Gewichte als exakte Brüche. Bool bleibt getrennt. Prüfung und Ausführung verwenden dieselben unveränderlichen Core-Bytes bzw. denselben geprüften AST. Keine Wiederverwendung von Freigaben nach Artefaktänderungen.

**Begründung:** JSON-Zahlen können in üblichen Adaptern auf binary64 reduziert werden; `9007199254740993` ist dann nicht exakt. Ein geprüftes Artefakt kann außerdem durch nachträgliches Neuladen einer veränderten Datei ersetzt werden. Weder Rundung noch Dateiaustausch darf die Bindung brechen.

### D-022: P0 bestätigt; Gesamtsprachkern und A3/A4 bleiben spätere Arbeit

**Entscheidung:** D-011 bis D-015 bleiben der Umsetzungsschnitt, ergänzt um D-017 bis D-021. Zuerst präzise Grammatik und Operatorregeln, danach Parser/Interpreter, Verpflichtungen, Zertifikatsprüfung und Golden-Fixtures, zuletzt Modelladapter. Keine neue Subscription, UI, Backend- oder Proof-Assistant-Pflicht für P0.

**Begründung:** Der spezialisierte Checker begrenzt die gleichzeitig zu lösenden Soundness-Fragen. Abhängige Typen mit Ressourcen und Erasure, Corekursion, FFI und Translation Validation brauchen eigene Modelle. Der A2-Anspruch bleibt profil- und TCB-relativ; ein Review ist kein Beweis.

**Später zu korrigieren:** Das v0.1-Divisionsbeispiel enthält einen I64/Int-Vergleich ohne Konversion und unvollständige Beweisbinder. P1 muss toward-zero-Semantik ausdrücklich gegenüber SMT-LIB-Division abbilden. Diese Punkte werden nicht stillschweigend als gültige Golden Programs übernommen.

## 2026-09-08 — P0-MVP umgesetzt und abgenommen

**Auftrag:** Sonny beauftragt die vollständige MVP-Umsetzung mit einem Agent Swarm. Definition of Done: Das erste Hello-World-Programm wurde tatsächlich von Agenten in der neuen Sprache geschrieben, geprüft und ausgeführt.

**Beteiligte:** Lead sowie `mvp_core`, `mvp_proof`, `mvp_factory`, `mvp_examples`, `mvp_security` und `hello_synthesis`. Getrennte Implementierung, Gegenprüfung und Integration; Agentenkonsens ersetzt keinen Beleg.

### D-023: Konkrete P0-Implementierung v0.2.0

**Umgesetzt:** Python 3.12, strenger Präfixparser, unveränderlicher Core, Bool/Int-Typprüfung, De-Bruijn-Binder, reine lineare Arithmetik, Rückwärtsaufrufe, Vor-/Nachbedingungen und Referenzinterpreter. Dateien `(spec p0 ...)` und `(candidate p0 ...)` sind getrennt. Der CLI bietet `check`, `run`, `hello` und `factory`.

**Folge:** Die konkrete Grammatik in `docs/P0.md` des Projektpakets präzisiert den früheren Syntaxvorschlag. Strings, I/O-Effekte, Nat/I64/Result und der breite v0.1-Sprachkern sind keine stillschweigend implementierten P0-Eigenschaften.

### D-024: cert-v0.1 und exakter früher Widerspruch

**Umgesetzt:** Solverfreie Rekonstruktion aller Pflichten im Checker; Z3 liefert ausschließlich untrusted Integerzeugen und rationale Farkas-Gewichte. Hashbindung umfasst Profil, unveränderlichen Vertrag und Kandidaten; fehlende, zusätzliche oder manipulierte Belegteile werden abgewiesen.

**Integrationsbefund:** Das echte Hello-World-Programm überschritt zunächst die Zweiggrenze. Eine interne Regel schließt jetzt konstante negative Schranken sowie exakt entgegengesetzte vollständige Koeffizientenvektoren mit negativer Schrankensumme. Dies sind die bereits zulässigen Farkas-Regeln mit Gewichten 1 beziehungsweise 1,1, keine neuen Cuts oder Prämissen. Programm und Spezifikation blieben unverändert. Eine zuvor fehlschlagende Regression besteht nun; Negativfälle mit Summe null und verschiedenen mehrdimensionalen Vektoren bleiben offen.

### D-025: Ressourcen- und Hostgrenzen sind explizit

**Umgesetzt:** Größen-, Baumtiefen-, Parameter-, Integer-, Schritt-, Zweig- und Zertifikatsbudgets; ein globales Solver-Suchbudget von standardmäßig drei Sekunden; höchstens drei Factory-Versuche. Verifikations-, Domänen- und Ausführungsstatus sind getrennt. JSON-Integer werden als kanonische Dezimalstrings transportiert, Bool bleibt strikt separat.

**Grenze:** Die Factory-Deadline wird zwischen synchronen Schritten geprüft. Eigene Python-Provider sind vertrauenswürdige Hostplugins, keine hart isolierten Fremdprozesse. Der HTTP-Adapter begrenzt Socketoperationen und Antwortgröße, lehnt Redirects und eingebettete URL-Credentials ab und akzeptiert HTTP nur für explizite Loopback-Adressen. Physische Ressourcen und die Python-TCB sind nicht formal bewiesen.

### D-026: Echte Agentensynthese und Reparatur nach Gegenbeispiel

**Ausgeführt:** `hello_synthesis` schrieb `examples/hello/hello.ll` aus dem festen Vertrag. Der Interpreter berechnete zwölf Zeichencodes, der Host gab exakt `Hello World\n` aus. Es gibt keinen hart codierten Text-Fallback im Host.

**Ausgeführt:** Ein absichtlich fehlerhafter Kontingentkörper erzeugte das nachgerechnete Gegenbeispiel requested=1, available=0, result=1. Der Agent erhielt diese Diagnose und schrieb den korrigierten Körper mit einem Aufruf des Minimum-Helfers. Die Factory akzeptierte den zweiten Kandidaten bei unverändertem Vertrags-Hash; Ausführung 7,3 ergab 3.

**Herkunft:** Originalauftrag, Feedback, Agentenquellen, Hashes und Ergebnisse sind in `evidence/` protokolliert. Die wiederholbare Demo nutzt diese echten Antworten als Replay. Der Modelladapter wurde über echte lokale HTTP-Anfragen getestet; kein kostenpflichtiger externer API-Aufruf wird behauptet. Modelltoken und Sitzungskosten sind mangels Hostmetrik nicht ausgewiesen.

### D-027: Tatsächlich bestandene Abnahme

**Ergebnis:** 178 Tests bestanden in 8,65 Sekunden, Ruff ohne Befunde, strenge mypy-Prüfung ohne Befunde in zwölf Quelldateien. Alle zehn Golden Programs sind akzeptiert, 58 Beispielauswertungen stimmen. Hello World und Reparaturdemo bestanden. Das gebaute Wheel wurde isoliert installiert und führte das Agenten-Hello-World erfolgreich aus.

**Umgebungsbefund:** Der native mypy-Build verursachte schon beim Start SIGBUS. Die Typprüfung lief erfolgreich mit den unveränderten Python-Sourcen derselben installierten mypy-Version; keine Typregel wurde dafür abgeschaltet. Die Abnahmeprüfung verwendet explizite Fehler und bleibt unter `python -O` wirksam.

**Belege:** `docs/ABNAHME.md`, `evidence/validation.json`, `evidence/wheel-smoke.json` und `evidence/acceptance/` im vollständigen Projektpaket `LLM-Language-MVP-v0.2.0.zip`.

### D-028: P0 abgeschlossen; Assurance bleibt TCB-relativ

**Entscheidung:** Die vom Nutzer gesetzte Definition of Done ist erfüllt. Quellstand, Abhängigkeitspins, Beispiele, Tests, Dokumentation, Wheel und lokaler Git-Verlauf werden als ausführbarer Meilenstein bereitgestellt. Ein Git-Commit und Datei-Hashes sind kein A4-Siegel.

**Reichweite:** `proved` bestätigt den P0-Core-Vertrag relativ zur dokumentierten TCB. Die Implementierung des Checkers und Interpreters ist nicht formal bewiesen. Nächster Ausbau ist P1 mit Nat, I64, Result und expliziter Division-/Overflow-Semantik; kein offener P1-Punkt verhindert die erreichte P0-Abnahme.
