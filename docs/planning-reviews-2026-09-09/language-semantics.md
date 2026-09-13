# Beitrag: allgemeiner Sprachkern, Bibliotheken und formale Semantik

Stand: 2026-09-09. Ausschließlich Planung; keine Implementierung oder neue Testergebnisse. Die beschriebenen Erweiterungen sind Entwürfe. Untersucht wurden der vorhandene Compiler unter `/workspace/scratch/a67318291dbe/llm-language-mvp`, insbesondere `src/llmlang/{model,core,symbolic,proof}.py`, `src/llmlang/web/{model,check,build}.py`, `docs/P0.md`, `docs/W1-SPEC.md`, `docs/W2-SPEC.md`, `specs/06-P0-REVIEW-AMENDMENTS.md` und `Log.md`.

## 1. Befund und Entscheidung

P0 ist ein kleiner, reiner Kern mit Bool, mathematischem Int, let, if und nichtrekursiven Funktionen. Multiplikation erfordert mindestens ein syntaktisches Integerliteral. Aufrufe dürfen nur kleinere Funktionsindizes adressieren; Verträge enthalten keine Aufrufe. Die Zertifikatsprüfung rekonstruiert Verpflichtungen und akzeptiert exakte rationale Farkas-Kombinationen. Das ist kein vollständiger Entscheider für quantorenfreie Integerarithmetik: Der Widerspruch `2*x = 1` bleibt mit diesem Zertifikatsschema grundsätzlich außerhalb der entsprechenden rationalen Relaxation.

w1/w2 bilden dagegen ein geschlossenes Formularmodell ab. `WebAction` besitzt nur `read|write` und einen Speicherverweis. Ein allgemeiner Funktionskörper, importierte Typen und zusammengesetzte Queries fehlen. Die Widget-Union ist geschlossen. In w2 beinhaltet `read` sogar den UI-Ablauf „Auswahlliste öffnen und ausgewählten Eintrag laden“. Das ist für die Demo brauchbar, für allgemeine Bibliotheken aber eine zu starke Kopplung.

**Empfehlung:** P0, w1 und w2 unverändert einfrieren. Ein neues allgemeines Profil `a1` (Arbeitsname) mit einem kleinen typisierten Kern und expliziten Fähigkeiten aufbauen. Booking, CRM und Shop werden normale Bibliotheken und Anwendungen. Neue Compileroperationen sind nur für neue fundamentale Semantik oder neue Hostfähigkeiten nötig, nicht für eine weitere Fachdomäne.

Die Profile sind keine drei dauerhaft getrennten Neuentwicklungen. Zunächst bleiben vorhandene Eingänge unverändert. Später können nachgewiesen semantikerhaltende Adapter w1/w2 auf den neuen Kern abbilden. Ein solcher Adapter darf insbesondere `w1.write = ersetzen` nicht mit `w2.write = anhängen` verwechseln.

## 2. Minimaler Kern und Bibliotheksgrenze

| Element | Sprachkern | Bibliothek / deklarative Anwendung |
|---|---|---|
| Werte | Bool, Int, Unit, Text mit Kapazität, Produkte und endliche Summen | Nat als Verfeinerung; Money, Customer, Booking, Error |
| Berechnung | let, if, match, reine Funktionen, Konstruktion und Projektion | Preisregeln, Kontingente, Berechtigungsentscheidungen |
| Wiederholung | endlich begrenztes Iterationskonstrukt mit festgelegter Reihenfolge | map, filter, fold, Tabellenaufbereitung |
| Wiederverwendung | Module, explizite Exporte, qualifizierte Referenzen, endliche Spezialisierung | Option, Result, std.text, std.collection, domain.booking |
| Effekte | explizite Aufrufe zugelassener Fähigkeiten und Reihenfolge | HTTP-Client für einen Anbieter, Mailadapter, Authintegration |
| Web | typisierte View-/Event-/Action-/Schema-Daten und ihre Interpretation | Formulare, Tabellen, Seitengerüste, CRM-Masken, Shopseiten |
| Datenbank | typisierte relationale Ausdrücke, Constraints, Transaktionsvertrag | Kundenlisten, Buchungsqueries, Bestandsverwaltung |

Option und Result brauchen keine Sonderfälle im Compiler jenseits der allgemeinen Summenbildung. Beispielsweise ist `Option<T>` die Summe `None(Unit) | Some(T)`. Views müssen ebenfalls komponierbare typisierte Werte oder Deklarationen werden. Ein Button erhält dann ein Ereignis; `std.ui.history_picker` kombiniert Listenaktion, Auswahl und Einzelabruf als Bibliothek. Der neue DB-Leseeffekt öffnet selbst keine UI.

Bibliotheken sind zunächst Quellmodule unserer Sprache. Sie dürfen keine Python-/JS-/SQL-Fragmente, Installationsskripte oder selbstregistrierte Compileropcodes enthalten. Das schließt spätere Fremdbibliotheken nicht aus: Eine Fremdbibliothek tritt als gesonderter, zugelassener Adapter mit explizitem Vertrag und eigener Vertrauensgrenze auf.

Eine Bibliothek kann keine physische Fähigkeit aus dem Nichts schaffen. Ein Zahlungsadapter benötigt eine Netzwerkfähigkeit; UI-Bausteine benötigen den vorhandenen Renderer; SQL-Queries benötigen einen DB-Adapter. Diese kleine Plattformschicht bleibt erforderlich und muss von gewöhnlichen Fachbibliotheken unterschieden werden.

## 3. Typen, Funktionsmodell und Generika

### 3.1 Records und Varianten

- Geschlossene, unveränderliche Records mit benannten Feldern und nominaler Typidentität. Ein CustomerId darf nicht allein wegen gleicher Repräsentation als TenantId gelten.
- Endliche Varianten; jeder match muss alle Konstruktoren behandeln. Kein implizites null, keine unkontrollierte Ausnahme und kein stillschweigender Default bei unbekannten Daten.
- Rekursive Datentypen, offene Row-Typen, Vererbung und dynamische Reflection zunächst zurückstellen.
- Öffentliche Schnittstellen deklarieren Parametertypen und Rückgabetypen explizit. Typinferenz darf örtliche Schreibarbeit reduzieren, aber keine externe Vertragssignatur erraten.
- Verfeinerungen sind reine Prädikate über bereits typisierte Werte, kein beliebiger abhängiger Typenkalkül. `Nat` bedeutet zunächst `Int` mit `x >= 0`. Sicherheitsrelevante Refinements werden an externen Eingängen validiert.

### 3.2 Funktionen und Generika

- Statisch bekannte Funktionen und azyklischer Aufrufgraph; keine allgemeine Rekursion. Im neuen Profil werden Namen aufgelöst und deterministisch zu internen IDs geordnet. P0 behält seine bestehenden De-Bruijn-Binder und Deklarationsreihenfolgen.
- Explizite Typparameter und nichtnegative Kapazitätsparameter; zunächst keine Typeclasses oder offene Instanzsuche.
- Monomorphisierung nur für tatsächlich verwendete Kombinationen. `Option<Customer>`, `Result<Order,Error>` oder `Seq<Text<128>,20>` benötigen keine neuen Compilerschritte.
- Erste Beweisversion prüft jede tatsächlich verwendete Instanz; ein universeller Beweis über alle denkbaren Typen ist dafür nicht notwendig. Instanzzahl und expandierte Größe werden budgetiert.
- Funktionen als Argumente für Collection-Bibliotheken nur als statisch auflösbare Funktionsreferenzen. Keine dynamischen Closures oder beliebige Codewerte. `map` und `fold` spezialisieren den Callback und dessen Vertrag.
- Verträge dürfen später benannte reine Prädikatdefinitionen benutzen, sofern diese endlich und capture-vermeidend expandiert werden. Das ist eine explizite Erweiterung; P0-Verträge bleiben aufruffrei. Zirkuläre Verträge und frei behauptete Axiome sind verboten.

### 3.3 Begrenzte Collections

`Seq<T,N>` ist eine geordnete Folge von 0 bis N Werten. Reihenfolge ist Teil der Semantik. Zugriff liefert Option<T>, Anhängen bei ausgeschöpfter Kapazität Result<Seq<T,N>,CapacityError>. Keine stille Abschneidung.

Ein generischer, beschränkter Fold verarbeitet Indizes von 0 bis `length-1`. Initial kann der Verifier bis N expandieren, jeweils mit der Bedingung `i < length`; der Zielcode darf eine Schleife mit derselben Ordnung verwenden. Der Checker muss vollständige Abdeckung und unveränderte Akkumulatorabhängigkeiten prüfen. Große N verursachen Beweisaufwand; bloße Endlichkeit macht sie nicht praktisch günstig.

Datenbanktabellen sind deshalb **keine** `Seq<T,N>` mit einer impliziten globalen Maximalgröße. Eine Query liefert eine begrenzte Seite mit Cursor. Eine globale Invariante über alle Buchungen entsteht nicht durch das Prüfen der gerade geladenen 20 Zeilen.

## 4. Deterministische Arithmetik und Text

### 4.1 Zahlen

1. **Int bleibt mathematisch exakt.** Kein IEEE-754-Transport und kein stiller I64-Overflow. Im JS-Ziel ist dafür BigInt beziehungsweise eine exakt spezifizierte Darstellung nötig; JSON verwendet kanonische Dezimalstrings. SQL-I64 erfordert eine explizite geprüfte Einengung.
2. **Nat ist eine Verfeinerung, kein zweiter Rechenkern.** `Nat - Nat` liefert nicht automatisch Nat. Ein Subtraktionsresultat braucht einen Beweis der Nichtnegativität oder einen Result-Fehler.
3. **I64 kommt als expliziter Begrenzungstyp.** checked add/sub/mul/div liefern Result. Erfolg verlangt `-2^63 <= result <= 2^63-1`; `MIN_I64 / -1` ergibt Overflow. Wrap und Sättigung werden nicht implizit angeboten.
4. **Division wird total durch Result.** Empfehlung für den neuen Int-Kern: euklidisches `divmod`, bei Nenner 0 `Err(DivisionByZero)`, sonst genau ein Paar q,r mit `a=b*q+r` und `0<=r<abs(b)`. Insbesondere `divmod(-7,3)=(-3,2)` und `divmod(-7,-3)=(3,2)`. Die API wird bewusst so benannt. Targeteigene `/`, `%` oder `//` sind ohne Korrektur nicht automatisch äquivalent. [SMT-LIB Ints](https://smt-lib.org/theories-Ints.shtml)
5. Allgemeine Multiplikation und variable Division sind für Shoplogik nützlich. Sie dürfen im neuen auswertbaren Profil existieren; ihre Einführung erweitert aber nicht heimlich den P0-Beweismodus. Die Factory muss fehlende Zertifikatsunterstützung als `unverified` sichtbar halten. Für releasekritische Eigenschaften ist das ein Blocker, kein Anlass zur Vertragsabschwächung.
6. Geld ist eine Bibliothek aus Währungstag, ganzzahligen Untereinheiten und expliziten Rundungsfunktionen. Rabatte, Steuern und Mengenskalen bekommen konkrete Rundungsverträge. Floats, implizite Wechselkurse und lokale Datumsinterpretationen bleiben außerhalb des ersten Kerns.

Lineare Formeln sind von nichtlinearen Formeln zu unterscheiden; die SMT-LIB-Definition linearer Integerlogik lässt nur konkrete Koeffizienten zu. Daraus folgt für uns die Notwendigkeit eigener Beweisfähigkeitserkennung statt eines pauschalen „Z3 kann es schon“. [SMT-LIB Logics](https://smt-lib.org/logics-all.shtml)

### 4.2 Text

- `Text<N>` übernimmt w1: gültige Unicode-Skalarfolgen ohne U+0000, höchstens N UTF-8-Bytes, keine implizite Normalisierung und kein trim.
- Namen müssen Maße ausdrücken: `utf8_bytes`, `codepoint_count`, gegebenenfalls später `grapheme_count`; kein mehrdeutiges `length`.
- `concat` erhält eine statisch berechnete Obergrenze N+M oder liefert bei einer gewünschten kleineren Kapazität einen Result-Fehler. `prefix_codepoints` erhält nur vollständige Unicode-Skalare; kein Schneiden innerhalb eines UTF-8-Zeichens.
- Anzeige als Text ist eine Renderregel. Ein Texttyp ist weder HTML noch URL noch SQL. HTML-Rohwerte sind keine Kernbibliotheksfunktion.
- Textgleichheit und Recordgleichheit mit Textfeldern lassen sich nicht ohne Begründung auf P0-Integergleichheit reduzieren. Erste strukturelle Regeln können Konstruktor-/Projektionsidentitäten und dieselben symbolischen Textwerte behandeln. Allgemeine Stringtheorie benötigt zusätzliche nachprüfbare Regeln oder bleibt als geprüfte Runtime-Grenze ausgewiesen.
- SMT-Stringlänge ist nicht unsere UTF-8-Bytekapazität. Die Abbildung muss explizit erfolgen; `str.len(s) <= N` allein beweist nicht `utf8_bytes(s) <= N`. [SMT-LIB UnicodeStrings](https://smt-lib.org/theories-UnicodeStrings.shtml)

## 5. Effekte, Ausführungsorte und Zustandsübergänge

Typurteil als Entwurf: `Γ ; capabilities ; location ⊢ expression : T ! effects`.

- `location` ist shared, client oder server. Shared bedeutet rein und auf beiden Zielen mit derselben Wertsemantik ausführbar; es bedeutet nicht vertrauenswürdig, wenn der Browser ein Ergebnis zurücksendet.
- Pure Funktionen besitzen keine Effekte. Uhrzeit, Zufall, Netz, Identität und Persistenz werden als Inputs oder explizite Capability-Aufrufe modelliert.
- Effektmengen sind endliche deklarierte Mengen mit konkretem Bezug: beispielsweise Lesen/Schreiben bestimmter Tabellen und Aufruf einer bestimmten Integration. Die transitiven Effekte eines Bibliotheksaufrufs müssen eine Teilmenge der erlaubten Fähigkeiten des Callers sein.
- Fähigkeiten sind nicht als JSON serialisierbar und vom Browser nicht konstruierbar. Ein externes `isAdmin=true` oder eine ausgedachte UserId erzeugt keine authentifizierte Fähigkeit. Authentifizierung bleibt ein Adaptervertrag; Autorisierung wird serverseitig geprüft.
- DB-Transaktionshandles bleiben in ihrem lexikalischen serverseitigen Bereich und dürfen nicht entkommen. Das braucht noch kein allgemeines Borrow-System; eine gezielte Typ-/Escape-Prüfung genügt.
- Der erste Transaktionskörper erlaubt nur passende DB-Effekte und reine Berechnung. Kein Netzwerk, keine E-Mail und kein nichtdeterministischer Aufruf mitten in einem potenziell wiederholten Transaktionslauf.
- Ein Auftrag an ein externes System wird später über eine Outbox mit Idempotenz ausgelöst. Ein DB-Rollback darf keine schon gesendete Zahlung oder E-Mail „zurücknehmen“ müssen.

Eine Bookingbibliothek kombiniert den reinen Schritt `reserve(state, amount)` mit dem deklarativen Transaktionsadapter. Ihre Zustandsinvariante ist zum Beispiel `0 <= used <= capacity`. Die Verpflichtungen sind: Anfangszustand erfüllt I; jeder erfolgreich commitbare Übergang aus I führt wieder nach I; Fehler schreibt keinen Teilzustand. Konkurrenzsicherheit benötigt zusätzlich einen zugelassenen atomaren Adaptervertrag. Eine bloße Effektannotation `transaction` beweist keine Serialisierbarkeit.

## 6. Beweisregeln und solverfreundliche IR

### 6.1 Darstellungsentscheidung

Eine kleine typisierte IR mit unveränderlichen, nummerierten Werten in A-Normalform genügt zunächst. Ein Ausdruck besitzt genau einen expliziten Typ, Ausführungsort, seine Wirkung und strukturierte Verzweigungen. Der reine Teil benutzt let, call, construct, project, match sowie eine kleine Primitiventabelle. Der Effektteil hat explizite Reihenfolge und Transaktionsgrenzen. Kein generisches ungetyptes JSON-AST als dauerhafter Vertrag.

Der P0-Core ist nicht diese gesamte IR. Er bleibt ein präziser Teilbereich. Der neue Verifier zerlegt Strukturen und erzeugt nach Möglichkeit lineare P0-kompatible Blätter. Ein IR-DAG vermeidet unnötige Verdopplung; die Prüfpflichten müssen trotzdem alle Pfade abdecken. Hashes binden die kanonische strukturierte Semantik, nicht Arbeitsspeicheradressen oder die zufällige Iteration eines Hashmaps.

### 6.2 Konkrete neue Regeln

| Regel | Verpflichtung / zulässiger Schluss |
|---|---|
| Recordkonstruktion | Jedes Feld hat den deklarierten Typ; recordweite Refinements gelten |
| Projektion | `get_i(make(v1,...,vn)) = vi`, bei exakt passender nominaler Typidentität |
| Variantenkonstruktion | Tag und Payload passen; verschiedene Konstruktoren sind disjunkt |
| Match | Jeder zulässige Konstruktor wird genau einmal abgedeckt; Payloadbindungen und Zweigresultate sind typkorrekt |
| Call | Aus Pfadbedingungen folgt callee.requires für konkrete Argumente; nur der zuvor nachgeprüfte callee-Vertrag darf anschließend angenommen werden |
| Spezialisierung | Typ-/Kapazitätssubstitution ist wohlsortiert und capture-vermeidend; Körper und Vertrag werden gemeinsam gebunden |
| Refinement | Aus aktuellem Kontext folgt das Zielprädikat; externe Werte benötigen den Runtime-Decoder |
| Begrenzte Iteration | Alle Schritte bis Kapazität sind repräsentiert; Schritte außerhalb tatsächlicher Länge verändern nichts |
| Effektaufruf | Bekannte Capability, erlaubter Ort, passende Argumente und explizites Fehlermodell |
| Transaktion | Invariante vor/nach Commit, keine partielle Fehlerwirkung; Adapterannahmen separat gebunden |

Die neue strukturelle Prüfmaschine ist eine TCB-Erweiterung mit eigener Version und eigenem Audit. Ein Solver darf weiterhin keine zusätzlichen Voraussetzungen, nicht bewiesenen Bibliotheksverträge oder ausgelassenen match-Zweige einschmuggeln.

Für geteilte Bibliotheksbeweise zunächst einen DAG von überprüften Modulen verwenden. Alle importierten Verträge werden vor Benutzung aus genau ihren gebundenen Implementierungen geprüft. Kein zyklisches „A nimmt B an, B nimmt A an“. Der bisherige P0-Prüfer expandiert konkrete Aufrufe; ein modularer Call-Summary-Checker ist eine neue, ausdrücklich abzunehmende Regel und kein bereits vorhandenes Feature.

### 6.3 Grenzen

- Vollautomatische Beweise für alle allgemein ausdrückbaren Programme werden nicht versprochen. Allgemeine Rekursion und Quantoren sind zunächst ausgeschlossen; unterschiedliche SMT-Theorien werden nicht ungeprüft vermischt.
- Endliche Kapazitäten, azyklische Aufrufe und Monomorphisierung sichern einen endlichen Übersetzungs-/Entfaltungsraum nur zusammen mit Größenbudgets. Zeit- oder Speichererschöpfung bleibt `unverified`/`resource_exhausted`, niemals `proved`.
- `compiled`, `contract_proved` für konkrete Eigenschaften, `target_validation_passed` und `integration_tested` bleiben getrennt. Ein Webapp-Manifest listet genau, welche Funktionen und Eigenschaften bewiesen und welche Komponenten angenommen sind.
- Ein Beweis des neuen Core-Vertrags rechtfertigt keine beliebige Source→Core-Umschreibung. Die autorisierte Spezifikation und ihr Lowering müssen selbst gebunden und geprüft sein. Ebenso macht ein erfolgreiches Target-Typchecking den Codegenerator nicht semantikerhaltend.
- Runtime-Checks werden erst entfernt, wenn genau ihre Voraussetzung unter allen relevanten erreichbaren Zuständen nachgewiesen und die Übersetzung gebunden ist. Externe Decoder und Autorisierungsprüfungen verschwinden nicht aufgrund von Browser-Typen.

## 7. Bibliotheksskizze: Entwurf, nicht ausführbar

Die Syntax ist rein illustrativ. Die nächste Normfassung muss Operator-/Stelligkeitstabellen und Canonicalisierung vor Implementierung fixieren.

```text
(module domain.booking a1
  (export capacity booking_error reserve)
  (type capacity
    (record (total Nat) (used Nat)))
  (type booking_error
    (variant (sold_out Unit) (invalid_quantity Unit)))
  (signature reserve
    (params (s capacity) (amount Nat))
    (returns (Result capacity booking_error))
    (effects pure)
    (requires (int.le (get s used) (get s total)))))
```

Der autorisierte Vertrag ergänzt getrennt: Bei amount=0 `invalid_quantity`; bei amount>total-used `sold_out`; sonst Erfolg mit unverändertem total und used+amount. Die bewiesene Nachbedingung umfasst insbesondere `used'<=total'`. Der Kandidat liefert ausschließlich den Körper:

```text
(implementation domain.booking
  (body reserve
    (if (int.eq amount 0)
      (Err (invalid_quantity unit))
      (if (int.le amount (int.sub (get s total) (get s used)))
        (Ok (make capacity
          (total (get s total))
          (used (int.add (get s used) amount))))
        (Err (sold_out unit))))))
```

Die Tokens `reserve`, `capacity` und `sold_out` sind Bibliotheksdefinitionen, keine Compilerfälle. Eine CRMbibliothek kann denselben Kern für Leadstatusübergänge benutzen. Eine Shopbibliothek definiert Bestellvarianten und Geldregeln. HTTP, DB und UI werden durch weitere importierte Bibliotheken komponiert. Autorisierte Verträge werden vor Synthese eingefroren; das gemeinsame Darstellen einer Signatur und Typen ändert diese Trennung nicht.

## 8. Reihenfolge und messbare Abnahme

1. **M1 — Kompatibilitätsbasis und Module:** P0/w1/w2-Verhalten festhalten, unabhängiges Paketschema `pkg1`, neue Profil-/Interface-/Manifestnorm, azyklische Imports und explizite Exporte. M1 bündelt zunächst P0-Funktionsmodule und zertifiziert das vollständige gebundene Programm erneut; modulare Beweiszusammenfassungen sind noch nicht nötig. Abnahme: alte Quellen behalten Verhalten und Hashregeln; Importwechsel invalidiert genau betroffene Nachweise; Zyklen, unzulässige Pfade und unerwartete Exporte werden abgelehnt.
2. **M2 — Allgemeine reine Werte:** Records, Varianten, Option/Result, benannte nichtrekursive Funktionen, Nat-Refinement, deterministische Spezialisierung. Abnahme: reserve- und CRM-Übergangsregeln als externe Module ohne Compilerpatch; Mutation von Tag, Feldtyp, Vertrag oder Librarykörper wird erkannt; Gegenbeispiele werden konkret nachgerechnet.
3. **M2 — Semantikbrücke und strukturierter Checker:** IR-Interpreter, explizite strukturelle Regeln, P0-Blätter, belegte Call-Summaries. Abnahme: unabhängiges Referenzmodell, Propertytests für Substitution/Roundtrip/Projektionsregeln, falsche und unvollständige Belege abweisen. Kein neu eingeführter `proved`-Pfad ohne Checkerregel.
4. **M2/M3 — Begrenzte Collections und Textbibliothek:** Abnahme: null/volle Kapazität, Unicode über mehrere UTF-8-Bytes, leere Texte, Callback-Vorbedingungen, Reihenfolge und Budgetüberlauf. Differenztests vergleichen Referenzinterpreter und tatsächlich erzeugten Zielcode.
5. **M3 — Allgemeines Web-/Schema-/Effektprofil:** Viewkomposition, lokale UI-Zustände, deklarierte Aktionen und Queries, Capability- und Ortsprüfung. Abnahme: historisches Textbeispiel als Bibliothekskomposition; zweite App mit anderem Datenmodell; DB-Fähigkeiten dürfen nicht in den Clientgraph gelangen.
6. **Nach M3 — Transaktionen und Fachbibliotheken:** Booking, CRM und kleiner Shop im selben Compilerrelease. Abnahme: konkurrierende Buchungen, Abbruch/Rollback, fremde IDs, wiederholte Requests und Wiederanlauf. Die Fachmodule dürfen weder Compilerprimitiventabelle noch Parser noch Generator ändern.
7. **Gezielte Beweiserweiterungen, nach konkretem Bedarf:** I64, variable Multiplikation, Division und größere Collections nur entlang realer gescheiterter Verpflichtungen priorisieren. Je Theorie eigene Soundnessbegründung, Zertifikatsregeln, Counterexample-Decoder und TCB-Differenz. Keine vorweggenommene Generalvollständigkeit.

Der erste Zielstack bleibt der vorhandene TypeScript-/D1-Stack. Ein neuer Python-Server oder weiterer Targetcodegenerator ist keine Voraussetzung dieser Sprachplanung. Die Reihenfolge bezeichnet Abhängigkeiten; insbesondere benötigen Records im auswertbaren Prototyp noch keine sofort vollständige automatische Verifikation. Eine produktive Freigabe kritischer Invarianten wartet jedoch auf den zugehörigen überprüfbaren Nachweis und die Integration des passenden Adapters.

## 9. Einwände gegen naheliegende Überdehnung

- **Nicht jedes Fachfeature als neues Profil:** w3_booking, w4_shop usw. würden den aktuellen Engpass fortsetzen. Generalität muss durch eine neue Domainbibliothek bei unverändertem Compiler nachgewiesen werden.
- **Kein frei ausführbarer Makro-/Pluginmechanismus:** Er verschiebt Sondercode und Vertrauen nur in Packages. Typisierte Komposition plus ein kleiner Capability-Katalog reicht zunächst.
- **Kein voller abhängiger Typenkalkül als Voraussetzung:** Die älteren Forschungsdokumente schlagen sehr große Möglichkeiten vor. Der tatsächlich erreichte P0-Stand braucht jetzt Produkte, Summen, Module und klare Effekte; Universen, Borrowing, Sessiontypen und Selbsthosting lösen den aktuellen Anwendungsbedarf nicht zuerst.
- **Keine automatische Übernahme fremder Vertragsbehauptungen:** Ein npm-/Python-/SQL-Adapter wird nicht durch einen handgeschriebenen requires/ensures-Block bewiesen. Seine Annahmen stehen sichtbar im Manifest.
- **Kein Gleichsetzen von begrenzter Folge und kompletter Datenbank:** Für globale und konkurrierende Invarianten wird ein passendes Zustands-/Transaktionsmodell benötigt.
- **Kein unbelegter Tokenvorteil:** Für S-Expressions, Namen/Indizes und Bibliotheksinterfaces werden tatsächliche Modelltoken, Erfolgsquote und Reparaturen gemessen. Kürzere Zeichenfolgen sind noch keine besseren Syntheseergebnisse.
