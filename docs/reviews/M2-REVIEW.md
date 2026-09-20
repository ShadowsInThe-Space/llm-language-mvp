# M2-Fachreview: A1 / v0.6.0 Developer Preview

Datum: 2026-09-20  
Gegenstand: `milestone/m2` bis Commit `5cf36e9`  
Methode: unabhängiger KI-Fachreview im Stil eines Professors für
Programmiersprachen und formale Verifikation. Dies ist keine reale akademische
Begutachtung oder institutionelle Bestätigung.

## Ergebnis

Release-Review: approved

Keine offenen Release-Blocker im eingefrorenen M2-Umfang.

## Geprüfte Grenzen

- Nominale Records, geschlossene Varianten, Option/Result und exhaustive match.
- Explizite Funktions-/Resulttypen, azyklische Calls, statische Callbacktypen,
  Nat-Evidence und deterministische begrenzte Spezialisierung.
- Exaktes `a1-ir-v1`-Dokumentschema und gerahmter kanonischer Hash.
- Getrennte Zertifikatsproduktion und unabhängige Evidenzrekonstruktion.
- SSA-Bindungen, Operanden-/Payload-/Returntypen und geschlossene Laufzeitwerte.
- Hostgrenzen für Records, Varianten, Listen, Option/Result, Nat und UTF-8-Text.
- Fail-closed JavaScript-Ziel für unsichere Integer, Unicode-Skalare und
  Kapazitäten sowie Referenz-/Target-Differentialtests.
- P0/w1/w2/pkg1-Regressionsschutz und installierte Paketoberfläche.

## Adversarialer Reviewverlauf

Die erste Prüfung verweigerte die Freigabe wegen gemeinsamer Produzenten-/
Checkerlogik, fehlender statischer IR-Typsoundness, Schema-/Hashabweichung und
Text-/Integer-Divergenzen im Target. Weitere Durchgänge fanden und schlossen
Hostgrenzen für Option/Result und Targetargumente, unbekannte Nominaltypen,
implizite Typdefaults, Callback-Elementtypen, verschachtelte Variantauflösung,
zusätzliche Felder geschlossener Werte und einen untypisierten `list_empty`-
Wildcardpfad. Jeder Befund erhielt einen Negativtest vor der Freigabe.

Finale lokale Evidenz: 530 Tests bestanden; Ruff und striktes Mypy sauber.

## Nicht behauptet

Der Review beweist weder die Python-TCB noch Node.js oder den JavaScript-Target
formal. Differentialtests sind kein Äquivalenzbeweis. A1-v1 umfasst keine
allgemeine Rekursion, Mutation, dynamische Dispatches, unbeschränkte Daten,
allgemeine CFGs oder Source-to-IR-Korrektheit. `proved` gilt nur für die
versionierten strukturellen und unterstützten lokalen Regeln des geprüften
kanonischen IR-Dokuments.
