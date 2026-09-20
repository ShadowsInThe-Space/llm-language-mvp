# A1 — M2-Abnahme für Collections, Text und integrierte Struktur (normativ)

Dieses Dokument ist die RED-first-Abnahme für Issue #20 und der integrierte
Abnahmevertrag für Issue #31. Es implementiert keine Sprachfunktion. Alle
Ausführungsergebnisse, Beweise, Kompatibilitätsprüfungen und Releasebelege
müssen auf `milestone/m2` entstehen; ein vorbereiteter grüner Test allein
schließt keinen Issue.

## 1. RED-first-Matrix

Vor der kleinsten Implementierung werden die folgenden Fälle als absichtlich
fehlende oder fehlerhafte Fähigkeiten reproduzierbar rot ausgeführt. Jeder
Fall braucht eine stabile Fall-ID, den beobachteten Fehler und den erwarteten
Fail-closed-Status. Ein Test, der wegen eines unklaren Orakels rot wird, ist
kein gültiger RED-Beleg.

| ID | RED-Fall | Erwartete Ablehnung oder Korrektur |
| --- | --- | --- |
| R01 | `List<T,-1>` oder dynamisches `N` | `A1_TYPE_CAPACITY`, keine Spezialisierung |
| R02 | Liste mit `N=0` plus ein Element | Konstruktion ablehnen; leere Liste bleibt gültig |
| R03 | literal/append über `N` | `Err(CapacityExceeded)` bzw. `A1_LIST_BOUNDS`, nie Abschneiden |
| R04 | Index `length`, `length+1` | exakt `None`, kein Trap, kein zufälliger Slotwert |
| R05 | volles `append` mutiert Eingabe | `Err` und bytegleiche unveränderte Eingabe |
| R06 | `map` vertauscht Elemente oder ruft Callback doppelt | Differentialvergleich schlägt fehl; Ordnung ist normativ |
| R07 | `fold` rechts-/parallel statt links/Indexreihenfolge | Differentialvergleich schlägt fehl; Akkumulatorfolge ist sichtbar |
| R08 | falscher Callbacktyp, Effekt oder unbewiesene Vorbedingung | `A1_CALLBACK`, kein dynamischer Fallback |
| R09 | `N`/Instanz-/Schrittbudget überschritten | `A1_BUDGET`, `resource_exhausted`/`unverified`, nie `proved` |
| R10 | ungültige UTF-8-Sequenz, Surrogate oder Überlänge | `A1_TEXT_ENCODING`/`A1_TEXT_CAPACITY` |
| R11 | U+0000, implizites trim oder NFC/NFD-Änderung | `A1_TEXT_NUL` oder bytegleiche Ablehnung des Drift-Orakels |
| R12 | Präfix schneidet `é`/`😀` in der Mitte | Test schlägt den Targetcode fehl; nur vollständige Skalare zulässig |
| R13 | `length(Text)` oder Bytezahl als Codepointzahl | `A1_TEXT_OPERATION` bzw. unterschiedliche Beobachtung |
| R14 | nicht-exhaustive Variante/Option/Result-, Tag- oder Refinementfall | #17/#18/#19-Diagnose; keine Default-/Panic-Behandlung |
| R15 | generischer `map`-Callback consumer-spezifisch gepatcht | integrierter Test entdeckt fehlende Wiederverwendung |
| R16 | Referenz und Target geben verschiedene Werte/Fehler/Budgets aus | Differentialgate rot; keine Freigabe durch nur einen Pfad |
| R17 | alter P0/w1/w2/pkg1-Fall oder Fixture-Hash driftet | Kompatibilitätsgate rot; historische Bytes werden nicht aktualisiert |
| R18 | Wheel nicht installiert, falsches Paket importiert oder Smoke fehlt | Releasegate rot; lokale Source-Ausführung genügt nicht |
| R19 | Reviewmarker, README, CHANGELOG oder Release Notes fehlen | #31 nicht abgeschlossen und `ready` bleibt `false` |

Die RED-Belege werden vor dem GREEN-Beleg in einem unveränderlichen
Abnahmeprotokoll referenziert. Mutationen müssen mindestens falschen Tag,
falsches Feld, vertauschte Reihenfolge, entfernten NUL-Check, abgeschnittenes
UTF-8 und ausgeschaltete Budgetprüfung abdecken.

## 2. Positiver Funktionsumfang

### 2.1 Zwei Consumer, zwei Records, zwei Kapazitäten

Ein gemeinsamer, unveränderter generischer Helfer
`map<T,U,N>(List<T,N>, f)` wird von zwei fachlich verschiedenen Consumern
aufgerufen:

1. `crm.consumer` mappt `List<Customer,2>` auf eine Liste von
   `CustomerLabel`-Records;
2. `orders.consumer` mappt `List<Order,4>` auf eine Liste von
   `OrderSummary`-Records.

`Customer` und `Order` sind nominal verschiedene Records mit jeweils
mindestens zwei Feldern. Die beiden Consumer müssen dieselbe exportierte
Bibliotheksfunktion nutzen, ohne Parser-, Checker-, Emitter- oder
Compilerpatch. Die Spezialisierungen unterscheiden sich sowohl im Recordtyp
als auch in der Kapazität. Die Instanzliste und ihre kanonischen IDs müssen
deterministisch und budgetiert sein. Ein dritter Test mit `N=0` deckt zusätzlich
die leere Abbildung ohne Callback-Aufruf ab.

Jeder Consumer muss mindestens ausführen:

- Recordkonstruktion und Projektion;
- eine geschlossene Variante mit vollständigem `match`;
- `Option` aus einem Listenindex und `Result` aus `append`;
- `Nat`-Refinement für die Kapazität oder einen Index;
- Unicode-`Text<N>` mit mindestens einem mehrbyteigen Skalar;
- denselben generischen `map`-Vertrag und eine deterministische `fold`-Ausgabe.

Die sichtbaren Ergebnisse, die verwendeten Records, Varianten und Textwerte
werden als kanonische Werte aufgezeichnet. „Consumer“ bedeutet ein getrenntes
fachliches Modul/Programm mit eigener Eingabe und eigenem Vertrag, nicht nur
zwei Aufrufe im selben Testkörper.

### 2.2 Differentialausführung

Für jeden positiven und negativen Fall laufen unabhängiges Referenzmodell und
tatsächlich erzeugter Zielcode mit denselben kanonischen Bytes, Eingabewerten,
Seeds (falls ein Generator verwendet wird) und Budgets. Abgenommen werden
bytegleiche Werte, Variante/Option/Result-Tags, Listenreihenfolge,
Text-UTF-8-Bytes, Byte-/Codepointzahlen, Lauf-/Fehlerstatus und stabile
Diagnosecodes/-phasen. Menschliche Fehlermeldungen, Stacktraces und
Targetdateipfade werden nicht verglichen.

Die Abnahme muss mindestens diese Randfälle enthalten:

- leere, volle und teilweise volle Listen;
- Index `0`, letzter gültiger Index und mehrere ungültige Indizes;
- `append` bei `N=0`, `N=1` leer/voll und unveränderter Err-Eingabe;
- map/fold mit nichtkommutativer Operation, damit Reihenfolge beobachtbar ist;
- unterschiedliche Records und Kapazitäten aus Abschnitt 2.1;
- leerer Text, ASCII, 2-/3-/4-Byte-Skalare und kombinierte, nicht normalisierte
  Sequenzen;
- U+0000, Surrogate, ungültige UTF-8-Bytes, Bytegrenze und
  `prefix_codepoints(0)`, genau am Ende und darüber hinaus;
- jede einzelne Instanz-, Kapazitäts-, Schritt- und Kanonisierungsgrenze.

„Ausgeführt“ und „formal bewiesen“ werden in den Ergebnissen getrennt
ausgewiesen. Ein erfolgreicher Test darf `proved` nicht simulieren; ein
`proved`-Zertifikat darf keinen fehlenden Differentiallauf verdecken.

## 3. Integrierte Negativabnahme (#31)

Die integrierte M2-Suite muss fail-closed zeigen, dass folgende Änderungen
nicht versehentlich akzeptiert werden:

- falscher Recordfeldtyp oder nominal vertauschte `CustomerId`/`OrderId`;
- ungültiger Variantentag, Payload oder nicht-exhaustiver `match`;
- negativer/unbewiesener `Nat`-Refinement und Indexzugriff außerhalb der
  aktuellen Länge als etwas anderes als `None`;
- falscher generischer Callbacktyp, unerlaubter Effekt, dynamische Referenz
  oder nicht bewiesene Callback-Vorbedingung;
- geschwächter/entfernter `List`-Bounds-, UTF-8-, NUL- oder Textkapazitäts-
  check, implizites trim oder Normalisierung;
- fehlendes Element, vertauschter Map-/Fold-Schritt oder ausgelassene
  Callbackausführung;
- defektes/inkomplettes Beweisdokument, unbekannte Checkerregel oder
  ausgeschöpftes Expansion-/Instanzbudget;
- Divergenz zwischen Referenzinterpreter und Target bei Wert, Fehler,
  Reihenfolge, UTF-8 oder Status.

Keiner dieser Fälle darf durch `try`, Defaultwerte, Hostexception,
Targetoptimierung oder einen behaupteten Solverstatus in einen grünen
Abschluss umgewandelt werden. Ein Timeout oder Budgetfehler bleibt
`unverified`/`resource_exhausted`, nicht „falsch bewiesen“.

## 4. Kompatibilität und Release-Evidenz

Vor dem Abschluss von #31 müssen auf exakt demselben Worktree und Commit
folgende Gates grün und als Artefakte verlinkt sein:

1. vollständige bestehende Pytest-Suite einschließlich M0-Kompatibilitäts-,
   Golden-, Web- und pkg1-Tests;
2. `.venv/bin/python -m ruff check src tests scripts`;
3. `.venv/bin/python -m mypy --no-incremental src`;
4. die A1-RED/GREEN-, Property- und Differentialmatrix;
5. Build und Installation des Wheels in eine frische, getrennte virtuelle
   Umgebung; Import muss nachweislich aus `site-packages` erfolgen;
6. installierte-Wheel-Smoke für beide Consumer, beide Recordtypen, beide
   Kapazitäten und mindestens eine negative Diagnose;
7. P0/w1/w2/pkg1-Kanonik, historische Fixture-Hashes und alte Zertifikate
   unverändert grün.

Der Wheel-Test muss die tatsächlich veröffentlichbare Paketversion und die
mitgelieferten Templates/Metadaten prüfen. Ein Test aus dem Quellcheckout,
ein lediglich gebautes Wheel oder ein Import aus dem Arbeitsverzeichnis ist
kein installierter-Wheel-Beleg.

## 5. Review-, Dokumentations- und Abschlussvertrag

Issue #31 darf erst als abgeschlossen markiert werden, wenn zusätzlich:

- ein unabhängiger Sprach-/Verifikationsreview mit Scope, Findings, behobenen
  Punkten und Evidenz in `docs/reviews/M2-REVIEW.md` vorliegt;
- die Datei erst nach tatsächlicher Freigabe exakt `Release-Review: approved`
  enthält; eine KI-Prüfung wird als solche bezeichnet und nicht als reale
  akademische Begutachtung ausgegeben;
- README, `CHANGELOG.md` und `docs/releases/v0.6.0.md` die Benutzerwirkung,
  Kompatibilität, bekannte Grenzen und die sechs M2-Issues (#17, #18, #19,
  #20, #30, #31) beschreiben;
- `release-plan.json` bis zur vollständigen Evidenz `ready: false` behält und
  erst danach gemeinsam mit Review und Release-Dokumenten geprüft wird;
- `Log.md` die RED-first-Entscheidung, semantischen Schnittstellen,
  gemessenen Test-/Wheel-/Reviewbeleg und offene Einschränkungen festhält;
- der Abschlusskommentar von #20 die exakten Tests und #31 die integrierte
  Consumer-/Kompatibilitäts-/Releaseevidenz nennt; kein Issue wird als
  `not_planned` geschlossen.

Die Freigabe erfolgt ausschließlich über den in
`docs/RELEASE-WORKFLOW.md` beschriebenen gemeinsamen Abschluss-PR und das
Release-Gate. Ein grüner lokaler Branch, ein einzelner geschlossener Issue,
ein vorab gesetzter Reviewmarker oder eine vorbereitete Datei ersetzt weder
die unabhängige Prüfung noch die Veröffentlichung auf dem exakten Main-SHA.

## 6. Bekannte Schnittstellen und mögliche Konflikte

- `specs/01-CANONICAL-SYNTAX.md` nennt NFC für Stringliterale; dieser
  A1-Vertrag hebt das nur für `Text<N>` auf. Eine Implementierung muss diese
  Profilauflösung im Parser/Kanonisierer sichtbar testen.
- Die alten M0-Webprofile haben bereits Byte-/Codepoint-Grenzen, sind aber
  keine A1-`Text`-/`List`-Werte. Ihre eingefrorenen Hashes und Quellen dürfen
  nicht auf das neue Format umgeschrieben werden.
- #18 verlangt statisch auflösbare Funktionsreferenzen und deterministische
  Spezialisierung. A1 ruft keine dynamischen Closures ein und braucht daher
  eine kanonische Generic-Instance-ID aus Funktions-ID, Typ-IDs und Kapazität.
- #19 muss die Checker-Regeln und #20 die Semantik für Listenindex, `append`, `map`, `fold`, UTF-8-Decoding,
  Byte-/Codepointmessung und scalar-sichere Präfixe explizit registrieren.
  Ein Zielcode-Emitter oder eine Hostbibliothek darf diese Regeln nicht
  ersetzen.
- `a1-ir-v1` fuehrt `list_append`/`CapacityError`, `text_prefix_codepoints`
  und `text_concat` explizit. Ein stilles Lowering auf Host-`push`, `slice`
  oder UTF-16-Indizes ist nicht kompatibel.
- `diagnostic-v1` behandelt menschenlesbare Meldungen nicht als stabil. Die
  A1-Codes/-Phasen in `A1-COLLECTIONS-TEXT.md` sind der maschinenlesbare
  Vergleichsvertrag; eine Implementierung muss unbekannte Zusatzfelder
  weiterhin additiv tolerieren.
