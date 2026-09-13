# v0.4.0 — From a language blueprint to a small web app

Release notes prepared for an experimental pre-release. A GitHub Release and tag
have not been published by this document. Install from the repository using the
[quickstart](../QUICKSTART.md).

## Included

- Python compiler for the w1 and w2 web profiles.
- React/TypeScript page and server generation, plus database schema generation.
- w2 saved-text history, entry selection, display-only clearing and read receipts.
- w1 compatibility and a migration script for preserving the earlier saved value.
- The existing P0 calculation core with independent certificate checking and
  a bounded generate/check/repair loop.
- Examples, specifications, tests, browser evidence and an English quickstart.

## Try it

Follow [QUICKSTART.md](../QUICKSTART.md), compile `examples/web/hello-history.llapp`,
and run `python scripts/demo.py`. The examples need no model account or API key.

## Scope and limitations

This is an experimental compiler, not a general-purpose app builder.
The generated web source requires a Vinext/React/D1 host. Compilation alone
neither starts the server nor provisions the database. A standalone host starter,
authentication, multi-tenant applications, general libraries, CRM and booking
workflows are not delivered by this release.

P0 certificates cover stated rules within the documented model. The web output
is statically checked and tested, not formally proven end to end.
Saved agent responses make the included proof demo repeatable; it is not live synthesis.

## Validation

The September 13, 2026 compiler synchronization reran 309 tests and Ruff successfully.
The launch preparation additionally ran compilation, generated-file integrity checking
and the proof/repair demo. Existing browser evidence is from September 9;
this launch preparation did not repeat the deployed browser acceptance test.

## Historical artifacts

Root `RELEASE.json` and `history/llm-language-mvp.bundle` describe the original
v0.2.0 archive. They are not manifests for this source revision.
