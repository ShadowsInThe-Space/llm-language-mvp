# M1-Fachreview: pkg1 / v0.5.0 Developer Preview

Datum: 2026-09-20. Unabhängiger Reviewer, getrennt von den Implementierungsworkern.
Dies ist ein KI-Fachreview mit Schwerpunkt Programmiersprachen und formale
Verifikation, kein akademisches Gutachten und kein Beweis der Implementierung.

## Urteil

Keine offenen fachlichen Release-Blocker gefunden. Für den ausgewiesenen
Developer-Preview-Umfang freigabefähig, vorausgesetzt vollständige Regression,
Ruff, Mypy und GitHub-CI sind am endgültigen Release-Stand grün.

## Umfang und Bewertung

Geprüft: alle `specs/PKG1*`, `src/llmlang/pkg/`, die P0-Typ-/Beleganbindung,
Beispiele, Tests, Demo und Release-/Assurance-Dokumentation sowie Issue #16.

- Autorisierung: Der separat autorisierte Snapshot legt das Quellprogramm fest.
  Selbstkonsistente Hashes und korrekte Beweise eines anderen Core reichen nicht.
- Linking: Explizite Exportprovider, Vorgängerbeschränkung lokaler Calls,
  Zyklusabwehr und deterministische einmalige Einfügung gemeinsamer Abhängigkeiten.
- Binder/Semantik: Nur Call-Indizes dürfen sich ändern. Der unabhängige Checker
  vergleicht Körper, Verträge, Parameter und Binder gegen die Quelle, ohne den
  Linker oder dessen Umschreibungsfunktion aufzurufen.
- Belege: Erst Bindungs-/Hashprüfung, dann der vorhandene P0-Gesamtchecker.
  Solverantworten oder Bibliotheksstatus sind kein alternativer Freigabepfad.
- Ressourcen: Quellen/Graph/Core budgetiert; komponentenweiser No-follow-Zugriff.
  Linux als einzige abgenommene Paketplattform ist angemessen dokumentiert.
- Aussagen: Quellwiederverwendung, Gesamtbeweise und unbewiesene Python-TCB
  klar getrennt. Keine Zusage allgemeiner Webkomposition oder autonomer Fabrik.

## Unabhängige Prüfungen

- 67 Pakettests bestanden; anschließend auch der abgeschlossene Demo-Test.
- Ruff für `src/llmlang/pkg` bestanden.
- Finale Demo separat ausgeführt: app=3, remaining=0; beide alten Locks und
  Belege abgelehnt, beide frischen Belege akzeptiert, Relokation identitätserhaltend.
- Adversarialer In-memory-Fall mit `(Int, Bool, Int)`, `let`, importiertem und
  lokalem Vorgängeraufruf: Bindung/Beleg akzeptiert, Resultate 15/20. Absichtlich
  falsch umgebogener Call bei unverändertem Manifest von `check_binding` abgelehnt.

## Geklärte Zwischenbefunde

Ein früher Demo-Stand verwendete denselben exklusiven Ausgabepfad erneut und
prüfte nach Änderung nur einen Verbraucher. Vor Endreview korrigiert: getrennte
frische Artefaktpfade und Änderungsprüfung beider Verbraucher. Kein offener Befund.

Issue #16 ist fachlich erfüllt: unabhängige gemeinsame Bibliothek, verschiedene
Verbraucher, transitive Abhängigkeit, vollständige Beweise und Invalidierung beider
betroffenen Belege; keine neuen Opcodes. Tests und Review sind empirische
Fehlerkontrolle, keine Verifikation der Python-Implementierung selbst.

## Integrationsabnahme durch Hauptagent

419 Tests bestanden, Ruff sauber, striktes Mypy über 27 Quelldateien sauber.
Wheel in frischer Umgebung installiert; tatsächlicher site-packages-Import,
pkg1-Demo und w2-Kompilierung samt `verify_build` erfolgreich geprüft.
GitHub-PR/main-CI bleibt ein separates Gate vor Veröffentlichung.
