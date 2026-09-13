# Kosten und Nutzen der Factory gegenüber konventioneller Webentwicklung

Stand 2026-09-09, Compiler 0.4.0, Profile P0/w1/w2.

## Urteil

Für die einzelne Hello-/Textspeicher-Webseite ist kein wirtschaftlicher Vorteil der
Factory nachgewiesen. Eine konventionelle Umsetzung mit etabliertem Framework und
KI-Unterstützung hätte voraussichtlich weniger zusätzlichen Werkzeugbau benötigt.
Das ist eine architektonische Einschätzung, kein gemessener Zeitvergleich.

Der wirtschaftliche Ansatz der Factory ist die Wiederverwendung einer begrenzten,
zentral geprüften Implementierung über viele Anwendungen und Änderungen. Ob die
Einsparungen Entwicklung und Wartung des Werkzeugs übersteigen, ist noch zu messen.

## Was wir tatsächlich wissen

- `examples/web/hello-history.llapp` umfasst 16 Zeilen.
- Der Web-Compiler unter `src/llmlang/web` umfasst 18 Python-/Vorlagendateien mit
  1.769 Zeilen, davon 1.581 nichtleer. P0, Tests und Hoststarter sind darin nicht enthalten.
- Die letzte Gesamtsuite bestand aus 309 erfolgreichen Tests. Diese Zahl umfasst
  auch den P0-Core und ist kein Beleg, dass jede erzeugte Webseite vollständig geprüft ist.
- Der installierte Compiler erzeugt die gehosteten Anwendungsartefakte bytegleich.
- Browserprüfungen belegen die implementierten Speicher-, Auswahl- und Clear-Abläufe.
- Es gibt keine protokollierten vollständigen Modelltoken-/API-Kosten und keinen
  kontrollierten Vergleich der gesamten Arbeitszeit mit einer konventionellen Umsetzung.

Die 16 Zeilen beschreiben die Anwendung innerhalb eines engen Funktionsumfangs.
Die Implementierungskomplexität liegt überwiegend im Compiler und Hoststarter.
Ein Vergleich von Quelltextzeilen allein liefert keine Produktivitäts- oder Kostenquote.

## Faire Vergleichsbasis

Die konventionelle Seite darf ebenfalls Templates, Komponenten, KI-Agenten, CI,
statische Analyse und Tests verwenden. Ein Vergleich gegen ungetesteten, vollständig
von Hand geschriebenen Einzelcode wäre unfair.

Beispielsweise bieten Django-Modelle eine zentrale Datenbeschreibung und eine erzeugte
Datenzugriffs-API; ModelForms können Formulare daraus ableiten. Migrationen und
CSRF-Schutz sind ebenfalls vorhandene Frameworkfunktionen. Diese Leistungen sind
keine Alleinstellungsmerkmale unserer Sprache.

Primärquellen: [Django-Modelle](https://docs.djangoproject.com/en/6.1/topics/db/models/),
[ModelForms](https://docs.djangoproject.com/en/6.1/topics/forms/modelforms/),
[Migrationen](https://docs.djangoproject.com/en/6.1/topics/migrations/),
[CSRF](https://docs.djangoproject.com/en/6.1/ref/csrf/).

Unsere aktuelle Runtime ist außerdem kein Python-Webbackend: Der in Python geschriebene
Compiler erzeugt React/TypeScript, einen Worker und SQL für D1. Ein Vergleich mit einem
Python-Server vermischt Factory-Effekt, Frameworkwahl und Hostingarchitektur. Deshalb
sollte ein belastbarer Versuch zusätzlich dieselbe Zielplattform ohne eigene Sprache nutzen.

## Gegenüberstellung

| Bereich | Konventionell mit Framework und KI | Unsere heutige Factory |
| --- | --- | --- |
| Erste kleine Anwendung | Bestehende Werkzeuge direkt einsetzen | Zusätzlicher Sprach-/Compilerbau; wirtschaftlich zunächst ein Aufwand |
| Weitere passende Anwendungen | Templates und Komponenten wiederverwenden | Kleine deklarative Quelle, deterministische Erzeugung der unterstützten Funktionen |
| Neue Funktion außerhalb des Umfangs | Funktion in normalem Anwendungscode ergänzen | Sprache, AST, Prüfung, Generatoren, Tests und eventuell Migrationen erweitern |
| Zusammenpassen von UI/API/DB | Framework, gemeinsame Schemas und Tests können helfen | Gemeinsame Quelle bindet unterstützte UI-Aktionen, API-Fähigkeiten und Speicher |
| Agentenfreiheit | Agent kann viele Libraries und Implementierungswege wählen | Begrenzte erlaubte Konstrukte; unbekannte Namen, falsche Bindungen und unpassende Typen werden abgewiesen |
| Security | Reife Frameworkmechanismen plus projektspezifische Prüfung | Zentrale geprüfte Muster, aber auch eigene Compiler-/Runtimefehler möglich |
| Wartung | Abhängigkeiten und Appcode pflegen | Zusätzlich Sprache, Compiler, Vorlagen und Kompatibilität pflegen |
| Zentraler Fix | Geteilte Komponenten/Bibliotheken aktualisieren | Generator reparieren, betroffene Apps neu erzeugen, prüfen und ausrollen |
| Hosting und Laufzeit | Abhängig von Stack und Last | Keine gemessene Einsparung durch die Sprache selbst |
| Personal und Ökosystem | Bestehende Dokumentation und breite Werkzeugkenntnis | Zusätzliche Einarbeitung, kleines Ökosystem und eigene Dokumentationspflicht |

Ein zentraler Generatorfehler kann viele erzeugte Anwendungen betreffen. Zentralisierung
vereinfacht die Korrektur, vergrößert aber zugleich die Reichweite eines Fehlers.

## Der konkrete Vorteil an unserem Beispiel

Eine Deklaration `(store greeting (Text 4096))` liefert den gemeinsamen Speichertyp
für Eingabe, Aktionsbindung und serverseitige Prüfung. Der Agent muss diese
Informationen nicht für jeden unterstützten Teil der Anwendung unabhängig neu erfinden.

`(clear reset "Anzeige leeren" (output result))` beschreibt eine lokale Anzeigeaktion.
Der Compiler prüft, dass das Ziel eine Ausgabe ist. Der aktuelle Generator erzeugt
dafür keine DB-Anfrage; die Browserabnahme prüfte, dass der Eintrag danach weiterhin
ladbar ist. Daraus folgt noch kein formaler Beweis der Codegenerierung.

Die jüngste Erweiterung zu mehreren Einträgen zeigt zugleich die Kosten: Wir mussten
den Sprachvertrag, AST, Validator, Frontend-/Servergenerator und Datenmigration
erweitern. Bei einer normalen Webseite wäre keine Erweiterung einer eigenen Sprache
nötig gewesen. Künftige Anwendungen mit derselben Textlistenfunktion können diese
Arbeit nun wiederverwenden.

Ein Schemaformat oder eine herkömmliche DSL mit Generator könnte viele dieser
Wiederverwendungsvorteile ebenfalls erreichen. Die neue Syntax allein ist kein
wirtschaftlicher Vorteil. Unser weitergehendes Ziel ist die Verbindung von enger
Agentensynthese, unabhängigen Prüfungen und formal spezifizierter Businesslogik.

## Kostenmodell

Für einen festgelegten Zeitraum seien:

- F: zusätzliche anfängliche Factorykosten gegenüber einer wiederverwendbaren Standardbasis;
- W: zusätzliche Wartungskosten der Factory in diesem Zeitraum;
- E: Kosten für erforderliche Funktionen außerhalb des vorhandenen Sprachumfangs;
- D: durchschnittliche Kosten je konventioneller, gleichwertig geprüfter Anwendung;
- A: durchschnittliche Kosten je Factory-Anwendung einschließlich Generierung,
  Review, Reparatur, Verifikation und Auslieferung;
- n: Anzahl vergleichbarer Anwendungen.

Dann ist der Kostenvorteil der Factory gegenüber der gemeinsamen Standardbasis:

`Vorteil(n) = n × (D − A) − F − W − E`

Wenn D kleiner oder gleich A ist, amortisiert die Wiederholung die Mehrkosten nicht.
Bei D größer A liegt die Kostengleichheit bei `(F + W + E) / (D − A)` Anwendungen.
Modellkosten können in die jeweiligen Kostenpositionen eingerechnet werden. Bei einem
Stundenmodell müssen API-/Betriebskosten separat berücksichtigt werden.

### Rein illustratives Stundenbeispiel — keine Messung unseres Projekts

Annahmen: 40 Stunden zusätzlicher Werkzeugbau, 10 Stunden zusätzliche Wartung,
keine weiteren Sprachextensionen; konventionell 4 Stunden je Anwendung, Factory
1 Stunde je Anwendung. Beide Wege erfüllen dieselben Abnahmekriterien.

| Anwendungen | Konventionell | Factory inkl. zusätzlicher Fixkosten | Vorteil der Factory |
| ---: | ---: | ---: | ---: |
| 1 | 4 h | 51 h | −47 h |
| 10 | 40 h | 60 h | −20 h |
| 20 | 80 h | 70 h | +10 h |
| 50 | 200 h | 100 h | +100 h |

Unter genau diesen angenommenen Werten wird die Factory ab 17 Anwendungen günstiger.
Diese Zahl ist keine Prognose. Häufige Sprachextensionen oder ein besseres konventionelles
Template können den Vorteil reduzieren oder ganz aufheben. Eurobeträge ergeben sich
erst mit einem festgelegten Kostensatz und tatsächlichen Modell-/Betriebskosten.

## Welche Vorteile noch nicht belegt sind

- Weniger Modelltoken oder günstigere Modelle: Die kleine Quelle hilft möglicherweise;
  Sprachbeschreibung, Beispiele und Reparaturversuche kosten ebenfalls Token. Modelle
  sind mit verbreiteten Sprachen bereits vertraut. Ein Qualitäts-/Kostenvergleich fehlt.
- Allgemein weniger Fehler: Einige Fehlerklassen werden abgefangen, eine vergleichende
  Fehlerquote gegenüber Frameworkcode wurde nicht gemessen.
- Vollständige Webbeweise: P0 prüft begrenzte Core-Verträge. Die w2-Webanwendung,
  Codegeneratoren, Browser und DB sind nicht formal bewiesen. P0-Garantien übertragen
  sich nicht automatisch auf w2.
- Vollautonome Webfactory: Die bisherige Arbeit wurde durch den Lead orchestriert;
  Sprachextension, Migrationseinbindung und Auslieferung benötigen noch bewusste Schritte.

## Empfehlung und nächster belastbarer Nachweis

Die Factory zunächst für wiederkehrende, eng umrissene Anwendungen weiterentwickeln.
Für beliebige Kundenwebseiten bietet die heutige w2-Sprache noch zu wenig Umfang.

Vor einer Wirtschaftlichkeitsaussage dieselben Aufgaben mit identischen Abnahmekriterien
über drei Wege bearbeiten: konventionell mit Python-Framework, direkt auf unserer
aktuellen Zielplattform und mit der Factory. Alle Wege dürfen KI und wiederverwendbare
Basen nutzen. Das trennt den Stackwechsel vom Effekt der Sprache.

Mehrere vergleichbare Aufgaben verwenden und die Reihenfolge variieren, damit der
zweite Versuch nicht allein durch Wissen aus dem ersten gewinnt. Bestehende Fähigkeiten
und notwendige neue Sprachextensionen getrennt auswerten.

Zu erfassen sind tatsächliche Eingabe-/Ausgabetoken und API-Kosten, Agenten-/Werkzeug-
Durchlaufzeit, menschliche Reviewzeit, Reparaturrunden, nicht erfüllte Abnahmekriterien,
gefundene Fehler und Aufwand einer späteren gemeinsamen Änderung. Auch Einrichtung,
Compilerpflege und Migrationen zählen. Fehlende Metriken werden als unbekannt ausgewiesen.

Das Ziel ist ein belastbarer Vorteil bei gleicher Qualität und gleichem Funktionsumfang,
nicht lediglich weniger sichtbarer Anwendungscode.
