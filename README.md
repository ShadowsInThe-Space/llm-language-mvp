# LLM-Language MVP — P0 und Webprofile w1/w2

> **English TL;DR:** Version 0.4.0 includes the contract-verified P0 core and a fullstack web compiler. Agent-written `.llapp` programs generate UI, API and database schema, including persistent text history. The web profiles are statically checked and tested; they do not carry P0 proof certificates.

Version 0.4.0 enthält den bisherigen P0-Proof-Core und einen Fullstack-Compiler für
die Webprofile w1 und w2. Agenten schreiben `.llapp`; der Compiler prüft die Quelle
und erzeugt Oberfläche, API und Datenbankschema für das Ziel `vinext-d1`.

## Webanwendung kompilieren

Neu in w2: Jeder Save erzeugt einen Eintrag; Laden öffnet eine paginierte Auswahl
mit Textanfängen. `clear` leert ausschließlich die Anzeige. Bestätigte Einzelabrufe
zeigen Uhrzeit und Abrufnummer. w1 behält seine Einzelwert-Semantik.
Vertrag und Migration: [docs/W2-SPEC.md](docs/W2-SPEC.md).

```bash
llmlang compile-web examples/web/hello-history.llapp --out build/hello-history
```

Bei Umstellung einer bestehenden w1-Site erst das neue Drizzle-Schema generieren.
Die vom Compiler erzeugte `llmlang/migrate-w1-to-w2.sql` nach dem Tabellen-/Index-DDL
in dieselbe neue Migration aufnehmen. Dadurch bleibt der bisherige DB-Text als
Eintrag erhalten. Bestehende Migrationsdateien niemals neu ausführen oder ersetzen.
Die zwei folgenden Beispiele bleiben bewusst im alten Profil:

```bash
llmlang compile-web examples/web/hello.llapp --out build/hello-web
llmlang compile-web examples/web/notes.llapp --out build/notes-web
```

Das Ausgabeziel muss neu oder leer sein. Enthalten sind React/TypeScript-Zielquellen,
Drizzle-Schema, kanonische Quelle, IR und Hashmanifest. Der anschließende Vinext-/D1-
Zielbuild benötigt den dokumentierten Hoststarter; Python allein startet keinen Webserver.

Anleitung, Architektur und Betrieb: [docs/W1-GUIDE.md](docs/W1-GUIDE.md).
Vor der Implementierung eingefrorene Sprache: [docs/W1-SPEC.md](docs/W1-SPEC.md).
Expertenplan: [docs/W1-PLAN.md](docs/W1-PLAN.md).
Browser- und Compilerabnahme: [docs/W1-ABNAHME.md](docs/W1-ABNAHME.md).

w1 ist statisch geprüft und getestet. Es erhält kein P0-Beweiszertifikat und keinen
A3-/A4-Anspruch. Der folgende Abschnitt dokumentiert den weiterhin enthaltenen P0-Core.

## P0-Meilenstein

**Abgenommen am 2026-09-08:** 178 Tests bestanden, zehn Golden Programs geprüft,
Agenten-Hello-World ausgeführt und Agentenreparatur bestätigt.
Details: [docs/ABNAHME.md](docs/ABNAHME.md).

## Schnellstart

Python 3.12 oder neuer:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python scripts/demo.py
```

Die Demo prüft zehn Golden Programs, führt das tatsächlich von einem Session-Agenten
geschriebene Hello-World-Programm aus und wiederholt dessen echte Reparatur eines falschen
Kontingentprogramms. Erwartete Ausgabe:

```text
Hello World
Definition of Done passed: 10 golden programs, agent Hello World, agent repair.
```

Sie speichert die neu geprüften Belege und Ergebnisse unter `build/demo/`.
Die mitgelieferten Agentenantworten sind ein nachvollziehbarer Replay; neue Generierung
über ein konfiguriertes Modell ist ebenfalls möglich.

## Ein Programm prüfen und ausführen

```bash
llmlang check --spec examples/golden/minimum.llspec --candidate examples/golden/minimum.ll --write-certificate build/minimum-proof.json
llmlang run --spec examples/golden/minimum.llspec --candidate examples/golden/minimum.ll --certificate build/minimum-proof.json --inputs '[{"type":"Int","value":"7"},{"type":"Int","value":"3"}]'
llmlang hello --spec examples/hello/hello.llspec --candidate examples/hello/hello.ll
```

`run` prüft vorhandene Zertifikate unabhängig erneut; ohne Zertifikat sucht und prüft
es einen neuen Beleg. Ein beschädigtes Zertifikat wird abgelehnt und nicht still ersetzt.
Die Textausgabe stammt aus zwölf vom P0-Programm berechneten Zeichencodes. Der Host
übernimmt stdout. P0 selbst besitzt keine Strings oder versteckten I/O-Effekte.

## Automatische Generierung und Reparatur

Mit den echten, mitgelieferten Agentenantworten:

```bash
llmlang factory --spec examples/agent-repair/grant.llspec --candidate-file examples/agent-repair/wrong.ll --candidate-file examples/agent-repair/repaired.ll --output build/grant.ll --report build/repair.json
```

Mit einem vorhandenen lokalen OpenAI-kompatiblen Server:

```bash
llmlang factory --spec examples/golden/minimum.llspec --endpoint http://127.0.0.1:8080/v1/chat/completions --model local-model --output build/minimum.ll --report build/model-run.json
```

Der Endpoint ist die vollständige Chat-Completions-URL. Externe Endpoints brauchen HTTPS.
Falls erforderlich wird der Schlüssel aus `LLMLANG_API_KEY` gelesen; mit
`--api-key-env NAME` lässt sich eine andere vorhandene Umgebungsvariable auswählen.
Der Schlüssel gehört nicht in Quelltext oder Kommandoargumente. Das Modell erhält
die Grammatik, den festen Vertrag und tatsächliches Feedback. Höchstens drei Kandidaten
sind erlaubt. Modellnutzung kann abhängig vom konfigurierten Anbieter Kosten verursachen.
Diese Abnahme verwendete reale Session-Agents und einen lokal getesteten HTTP-Adapter;
es wurde kein kostenpflichtiger externer Modellaufruf durchgeführt.

## Enthaltene Sprache

`Int`, `Bool`, unveränderliche Werte, De-Bruijn-Binder, `let`, `if`, exakte lineare
Arithmetik, strikte boolesche Operatoren und ausschließlich rückwärts gerichtete
Funktionsaufrufe. Jeder öffentliche Einstieg besitzt Vor- und Nachbedingungen.
Verträge und Kandidaten stehen in getrennten Dateien; der Kandidat kann Verträge nicht ersetzen.

Grammatik und Regelübersicht: [docs/P0.md](docs/P0.md).
Beispielaufgaben: [docs/GOLDEN-PROGRAMS.md](docs/GOLDEN-PROGRAMS.md).
Architektur und Vertrauensgrenzen: [docs/ASSURANCE.md](docs/ASSURANCE.md).

## Prüfungen

```bash
python -m pytest -q
python -m ruff check src tests scripts
python -m mypy --no-incremental src
python scripts/demo.py
```

`requirements.lock` hält die in der Entwicklungsumgebung tatsächlich verwendeten
Abhängigkeitsversionen fest. Der native mypy-Build dieser Umgebung verursachte beim
Start einen Bus Error; die Typprüfung wurde deshalb mit den unveränderten mitgelieferten
Python-Sourcen derselben mypy-Version ausgeführt. Es wurden keine Typregeln abgeschaltet.

## Reichweite

`proved` bedeutet: Der Checker hat den konkreten Core-Vertrag im P0-Modell akzeptiert.
Das ist ein A2-Anspruch relativ zur dokumentierten TCB, kein Beweis der Python-Implementierung,
kein nativer Compiler und kein A3/A4-Release. Ein fehlender Beleg bleibt `unverified`.
Vertragsdomäne und tatsächlicher Laufstatus werden getrennt ausgegeben.
Beispielsweise bleibt `2*x=1` in dieser beschränkten Zertifikatssprache `domain_unknown`.

Prüfprotokolle und die Herkunft der echten Agentenprogramme stehen in `evidence/`.

## Quellpaket und Entwurfshistorie

Das Release-Paket enthält zusätzlich das installierbare Wheel unter `dist/` und
den lokalen Git-Verlauf als `history/llm-language-mvp.bundle`. Ein Git-Checkout lässt
sich mit `git clone history/llm-language-mvp.bundle checkout` erstellen.

`specs/` und `REVIEW-2026-09-08.md` bewahren den Gesamtentwurf und sein Architekturreview.
Für die konkret implementierte P0-Syntax gilt `docs/P0.md`; die darüber hinausgehenden
Sprachmerkmale der Entwurfshistorie sind Ausbauziele. `Log.md` hält die Entscheidungen fest.

## GitHub-Stand und Archiv

Der Quellstand enthält v0.4.0 und den Weiterentwicklungsplan vom 09.09.2026.
Die Bibliotheks- und allgemeinen Spracherweiterungen sind geplant, noch nicht implementiert.
`RELEASE.json` und `history/llm-language-mvp.bundle` stammen aus dem ursprünglichen
v0.2.0-Archiv und beschreiben ausschließlich diesen historischen Stand.

Bei der GitHub-Synchronisierung am 13.09.2026 wurden 309 Tests und Ruff erneut
erfolgreich ausgeführt. Ein neuer Browser- oder Deploymenttest fand dabei nicht statt.
