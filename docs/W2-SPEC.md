# w2: gespeicherte Einträge auswählen und Anzeige leeren

Vor Implementierung festgelegt, 2026-09-09. Nutzeranforderung: Anzeige lokal leeren;
beim Laden eine Auswahl mit Textanfängen mehrerer gespeicherter Einträge anbieten.

## Sprachvertrag

Profil `(app w2 ...)` übernimmt die Syntax und Limits von w1. In w2 deklariert `store`
eine Folge unveränderlicher Texteinträge. `write` hängt einen Eintrag an, `read` öffnet
eine vom Ziel generierte Auswahl und lädt den gewählten Eintrag in das gebundene Output.
w1 behält seinen Einzelwert-/Ersetzen-Vertrag unverändert.

Neues rein lokales Widget: `(clear reset "Anzeige leeren" (output result))`.
Der Compiler prüft Namen und dass `result` ein TextOutput ist. w1 lehnt `clear` ab.
Clear verändert ausschließlich UI-Zustand, schließt die Auswahl und sendet keinen Request.
Während einer laufenden Anfrage sind Clear und andere Aktionen gesperrt.

Jeder bestätigte Einzelabruf zeigt Uhrzeit des Empfangs und fortlaufende Abrufnummer
dieser Seitensitzung, auch bei identischem Text. Schreiben wird als Schreibbestätigung
kenntlich gemacht. Fehlgeschlagene Anfragen erzeugen keine neue Bestätigung.

## HTTP und Daten

Bestehende private Site und DB-Bindung DB bleiben. Neues Schema `w2_entries`: global
aufsteigende interne Sequenz, App-/Slotkennung, Eintragskennung, Text und Erstellungszeit.
Eintragskennung ist eine UUID aus dem Idempotency-Key; sie wird serverseitig validiert.
UNIQUE(app_id,store_id,id), CHECK-Textconstraints wie w1 und Index auf App/Slot/Sequenz.

- POST /api/store/{slot}, JSON exakt {value:string}, verpflichtender UUID-Idempotency-Key.
  Gleicher Schlüssel und gleicher Inhalt ergeben denselben Eintrag; abweichender Inhalt
  wird 409 abgelehnt. Origin-, UTF-8-, JSON- und Byteprüfungen aus w1 bleiben.
- GET ?entries=1&before=SEQUENZ: höchstens 20 Einträge, neueste zuerst; pro Eintrag ID,
  erste höchstens 80 Unicode-Codepoints und Zeit, plus nextCursor. Gebundene Keyset-Abfrage.
- GET ?id=KENNUNG: exakt ein Eintrag, immer auf die konfigurierte App und den Slot begrenzt.
  Antwort wie w1: found und value; unbekannte Kennung 404. Keine Delete-API.
- Antworten no-store, keine clientseitig erfundenen DB-Werte. Unbekannte Queryformen 400.

Die bestehende w1-Tabelle bleibt erhalten. Eine additive Migration übernimmt jeden
vorhandenen Einzelwert einmal als Eintrag `legacy`; kein Defaulttext wird eingefügt.
Bereits früher überschriebene Werte können nicht rekonstruiert werden. Neue Saves sind
neue Einträge; Wiederholen einer unbestätigten Schreibanfrage verwendet denselben Schlüssel.

## UI und Abnahme

Laden fragt zuerst die Liste ab und öffnet ein natives Auswahlfeld beim geklickten Button.
Optionen zeigen Textanfang, Zeit und eine kurze Kennung zur Unterscheidung. Auswahl lädt
den vollständigen Text erneut vom Server. Weitere Einträge werden seitenweise nachgeladen.
Leere Liste und leere Strings sind unterscheidbar. HTML-artiger Inhalt bleibt React-Text.

Tests vor Code: Profil-/Clear-Validierung, zwei Saves bleiben getrennt, Idempotenz,
Migration des vorhandenen Wertes, Pagination, Zugriffstrennung, Ablehnung ungültiger
Anfragen ohne Mutation. Browser: wiederholtes Laden ändert Bestätigung; Clear entfernt
Ausgabe; anschließende Liste und Auswahl stellen denselben DB-Eintrag wieder her.
