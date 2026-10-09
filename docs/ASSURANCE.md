# Assurance und bekannte Grenzen

## Akzeptierte Aussage

Für jede öffentliche Funktion und jeden typkorrekten Input gilt im abstrakten P0-Modell:
Unter ihrer Vorbedingung erfüllt das Ergebnis ihre Nachbedingung, und alle erreichten
Aufrufe erfüllen ihre Vorbedingungen. Der vollständige geordnete Core gehört zur Aussage.
Die mathematische Terminierung folgt aus fehlender Rekursion und endlichen Termen.

## Unabhängige Belegprüfung

Z3 sucht Integerzeugen und nichtnegative rationale Koeffizienten. Sein `UNSAT` ist
keine Freigabe. `check_certificate` rekonstruiert die Pflichten selbst und ruft keinen
Solver auf. Die Tests lassen den Solver absichtlich ausfallen und prüfen vorhandene
Zertifikate trotzdem erneut.

Normierte Zeilen lauten `a_i*x <= b_i` mit ganzzahligen Koeffizienten. Der Checker
akzeptiert rationale Gewichte nur, wenn sie nichtnegativ sind, die gewichteten
Variablenkoeffizienten exakt verschwinden und die gewichtete Schranke negativ ist.
Das ergibt `0 <= c` mit `c < 0`. Keine Gleitkommatoleranz oder Integer-Cuts.

Die Rekonstruktion schließt zwei triviale Fälle intern: eine konstante negative
Schranke oder zwei exakt entgegengesetzte Koeffizientenvektoren mit negativer Summe
der Schranken. Das sind dieselben Farkas-Regeln mit Gewichten 1 beziehungsweise 1,1.
Andere, zum Beispiel dreizeilige Transitivitätsbeweise, benutzen explizite Zertifikate.
Ein leeres `obligations`-Objekt kann daher korrekt sein: Der unabhängige Checker
hat alle Pflichten bei erneuter Rekonstruktion selbst geschlossen. Hashes allein genügen nie.

## Trusted Computing Base

- Kanonischer Parser/Decoder, Typ- und Binderprüfung.
- Symbolische Auswertung, vollständige Fallunterscheidung und interne Widerspruchsregel.
- Zertifikatschecker, exakte Python-Integer-/Fraction-Arithmetik und Hashbindung.
- Für reale Ausführung zusätzlich Referenzinterpreter, Hostadapter und Python-Runtime.
- Betriebssystem und Hardware als Umgebungsannahmen.

Die Implementierungen dieser Komponenten sind getestet und geprüft, aber nicht in
einem Proof Assistant formal bewiesen. Deshalb sprechen wir von A2 relativ zu dieser
TCB. Es gibt keinen nativen Codegenerator, kein bewiesenes Backend und kein A3/A4-Siegel.

Agenten, Modellantworten und Solver stehen außerhalb der formalen Akzeptanzentscheidung.
Die Bedeutung der autorisierten Fachspezifikation bleibt Verantwortung des Auftraggebers
und Architekten. Ein korrekter Beweis kann eine falsche Produktanforderung nicht erkennen.

## Host- und Providergrenzen

HTTP-Antworten sind begrenzte, streng validierte Daten. Es gibt weder Shell-Kommandos
aus Modellantworten noch frei ausführbare Hostfragmente. Konfiguration stammt vom Host;
eine HTTPS-URL kann explizit ein Unternehmens- oder lokaler Dienst sein. Dies ist kein
öffentlicher Proxy-Service. Redirects und eingebettete URL-Zugangsdaten sind verboten.

Die Factory prüft ihre Deadline vor und nach synchronen Schritten. Der Netzwerkadapter
begrenzt Socketoperationen und Antwortgröße. Beliebige eigene Python-Provider sind
vertrauenswürdige Hostplugins und werden nicht durch Prozessisolation hart unterbrochen.
Diese Bibliothek ist keine Sandbox zur Ausführung fremder Python-Plugins.

Physische RAM-Verfügbarkeit und Hostfehler sind nicht bewiesen. Sehr große Eingaben,
Zertifikate und Verzweigungen werden budgetiert; reale Ausführung kann resource_exhausted
melden, obwohl der mathematische Core-Vertrag bewiesen ist.

## Nicht unterstützte Spracheigenschaften

Strings, allgemeine Rekursion, Schleifen, Arrays, I64/Overflow/Division, abhängige Typen,
affine Ressourcen, Nebenläufigkeit und FFI bleiben spätere Profile. Die rationale
Zertifikatssprache ist für Integerarithmetik absichtlich unvollständig; `2*x=1` wird
ohne zulässigen Leerheitsbeleg nicht als contract_empty gemeldet.

Keine dieser Grenzen wird durch das erfolgreiche Hello World oder Agentenkonsens aufgehoben.
