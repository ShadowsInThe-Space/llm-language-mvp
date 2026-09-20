# Beweisgrenzen lokaler Pakete (pkg1, M1)

Ergänzung zum unveränderten historischen [P0-Vertrag](ASSURANCE.md).

Der Host autorisiert einen exakten lokalen Lock. Der Resolver bindet dessen
Quellen in einen unveränderlichen Snapshot. Der Source-to-Core-Checker prüft
die strukturelle Erhaltung von Verträgen, Körpern und Bindern sowie die
Import-/Exportabbildung, bevor ein P0-Gesamtzertifikat akzeptiert wird.
Resolver, kanonische Paketidentität und Bindungschecker erweitern damit die TCB;
auch sie sind nicht in einem Proof Assistant bewiesen.

Wiederverwendung betrifft in M1 Quellbibliotheken, **nicht** modulare Beweise:
jeder Verbraucher wird als vollständiges gelinktes Programm neu geprüft.
Auch eine semantisch äquivalente Änderung des kanonischen Bibliothekskörpers
verwirft alte Locks und Paketbelege. Ein neuer Lock ist eine neue ausdrückliche
Hostautorisierung, kein automatisch akzeptiertes Update. Die zwei Beispielprogramme
belegen diesen begrenzten Mechanismus, nicht allgemeine Webkomposition oder eine
autonome Software-Fabrik. Paketbefehle sind bislang nur auf Linux abgenommen.

Ein unabhängiges KI-Fachreview ist zusätzliche Fehlerkontrolle, kein akademisches
Gutachten und kein mathematischer Beweis der Implementierung.
