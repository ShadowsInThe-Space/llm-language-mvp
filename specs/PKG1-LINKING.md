# pkg1 — Linking und unabhängige Bindungsprüfung

Issues #14/#15. Normative Ergänzung zu PKG1-SPEC.md.

1. Parser dekodiert Manifest/Lock und P0-Dateien mit strikter Form und Budgets.
2. Resolver liest alle Dateien einmal, prüft Lock-Hashes, Dependency-Closure,
   exakte Versionen, Sichtbarkeit und DAG. Ergebnis ist ein unveränderlicher Snapshot.
3. Linker besucht Module in deterministischer Topologie: startend bei sortierten
   `(package,module)`-Schlüsseln, Tiefensuche über sortierte Import-Provider.
   Vorgänger kommen zuerst; jedes Modul genau einmal. Funktionen behalten ihre
   lokale Reihenfolge. Unbenutzte deklarierte Funktionen werden mitgeprüft.
4. Lokale Importplätze werden auf exportierte globale Slots abgebildet, lokale
   Calls auf bereits eingefügte Vorgänger. Parameter und Binder bleiben unverändert.
   Der vollständige Core wird mit P0 validate geprüft.

## Bindungsmanifest

`BoundProgram` enthält spec/candidate sowie ein Manifest als JSON-Objekt:
format=`pkg1-bound`, checker=`pkg1-bind-v1`, snapshot_hash, baseline_hash,
candidate_hash, functions. Je Funktion in Core-Reihenfolge:

- package, version, package_hash, module, name, exported (Bool);
- local_index, core_slot;
- contract (kanonische Einzel-P0-spec), body (kanonische Einzel-P0-candidate);
- call_slots (Importslots gefolgt von allen lokalen Slots);
- parameters (Typen in Deklarationsreihenfolge), binder_indices (n-1 bis 0).

bound_hash = SHA256(`UTF8("pkg1:bound\0") || canonical_manifest_without_bound_hash`).
Manifest-Slots, Provideridentität und Quellkörper sind keine ungeprüften Behauptungen.

## Unabhängiger Prüfer

Der Linkcheck erhält autorisierten Snapshot und angebotenen BoundProgram. Er darf
weder link() noch dessen Umschreibungshelfer verwenden. Er rekonstruiert
Exports/Provider, deterministische Modulreihenfolge und jeden erwarteten Callslot.
Er vergleicht alle Quellverträge, Körperbäume, Parameter- und Binderzuordnungen
strukturell gegen den Core und rekonstruiert das vollständige Bindungsmanifest.
Jede fehlende/zusätzliche/abweichende Bindung führt zu Ablehnung. Ein Paketdigest
oder korrekter Core-Beweis alleine reicht nicht.

Ein Paketbeleg enthält format=`pkg1-proof`, snapshot_hash, bound_hash und
core_certificate. Akzeptanz verlangt zuerst Linkcheck und exakte Hashbindung,
danach den bestehenden unabhängigen P0-Zertifikatschecker. Solver wird beim
Prüfen vorhandener Belege nicht aufgerufen. Proof-Suche bleibt optional und
untrusted. Kein eigener `proved`-Pfad umgeht diese Reihenfolge.

TCB: P0-TCB plus pkg1-Parser, Snapshotautorisation und unabhängiger Linkcheck.
Der Linker ist Vorschlagsgenerator. Der Python-Linkcheck ist getestet, nicht
selbst formal bewiesen. Diese Erweiterung behauptet kein A3/A4 und keine
modulare Beweiswiederverwendung.
