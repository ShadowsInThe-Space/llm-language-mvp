# Umsetzungsplan des Fullstack-Compilers

Vor Implementierung festgelegt, 2026-09-08. Autoritative Regeln: W1-SPEC.md.

1. Expertenabgleich Sprache, Codegenerierung, DB/Security und Abnahmetests; FreezeCommit.
2. Parallel nachFreeze: Parser/Typen; Frontendemitter; Server-/Schemaemitter;
   unabhängige Runtime-/Negativtests. Lead: Build/CLI/Integration.
3. Ein neuer Syntheseagent schreibt ausschließlich die .llapp-Programme aus der Spec.
4. Compiler generiert Zielquellen; Lead integriert unveränderte Artefakte in Site.
5. Drizzle erzeugtSQL, Vinext erzeugtWorker/Browsercode. EchteD1PreviewMigration.
6. ChromeAbnahme mit speichern/laden/reload/Neustart und hostileText; Evidenz sichern.
7. PrivateBereitstellung, SourcePakete und dokumentierterScope.

Vorausgesetzte technische Defaults wurden vom Lead entschieden; keine offene
Produktentscheidung blockiert den Start. Ein Textspeicher ersetzt atomisch seinenWert,
keineHistorie oderKonten. Quellsyntax bleibt S-Expression mit JSONStringliteralen.

Compilerrepo: llm-language-mvp. Die separat gehostete Site ist generierterOutput;
Compilerbugs werden am Generator repariert und danach erneut kompiliert.
