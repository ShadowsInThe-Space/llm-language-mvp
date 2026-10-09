# Changelog

Notable changes are grouped by milestone release. A section explicitly marked
candidate describes the work branch, not a published package. Unreleased entries
are likewise unavailable on main until accepted and released.
Release policy: [one package, one merge, one release](docs/RELEASE-WORKFLOW.md).

## [Unreleased]

## [0.7.0] - 2026-10-09

**Web Preview candidate; acceptance and publication pending.** This date records
candidate preparation. v0.6.0 remains the latest published package.

### Added

- Explicit shared/client/server locations, a closed host-operation registry,
  transitive effect/capability checks and stable boundary diagnostics
  ([#21](https://github.com/ShadowsInThe-Space/llm-language-mvp/issues/21)).
- General typed web sources and reusable UI components compile saved-text history
  and task applications through the same codec/query/server/client pipeline
  ([#22](https://github.com/ShadowsInThe-Space/llm-language-mvp/issues/22)).
- Typed server-side parameter transforms call a shared A1 library through a
  bounded portable runtime; generated runtime and source snapshots are bound by
  the reproducible build manifest.
- Exact nominal wire codecs, positional SQL bindings, unique/list reads,
  lexicographic keyset cursors and single-statement revision-conditional updates.
- Textarea inputs preserve accepted multiline Unicode and empty text up to
  4096 UTF-8 bytes. Pagination reaches older entries; local confirmation counters
  make repeated successful loads observable. Clear changes only local UI state.
- A pinned Vinext/local D1 acceptance host, built-client/source-map inspection,
  process-restart checks and Chromium/Firefox/WebKit tests
  ([#32](https://github.com/ShadowsInThe-Space/llm-language-mvp/issues/32)).

### Security and bounds

- DB bindings, authorization policy and executable Pure libraries remain server
  inputs. Protected actions deny access without a trusted host authorization
  adapter. Both examples are public shared-data demonstrations.
- Int/Nat use canonical decimal strings within the exact safe-integer range;
  requests/results enforce 32768-byte and 4096-node bounds. Queries admit at most
  100 bindings and 100000 UTF-8 SQL bytes.
- Previous-page navigation retains at most 32 cursors and 256 KiB per list;
  older pages remain reachable through Next. Confirmation counters use no clock.
- Controls remain disabled until React hydration is ready; failures preserve
  confirmed values and stale responses cannot replace current state.

### Compatibility and candidate validation

- P0, w1, w2, pkg1 and frozen A1 contracts remain unchanged. This additive profile
  does not clone the W2 HTTP/idempotency protocol or migrate its stored data.
- Baseline checkpoint: 703 tests plus 260 subtests passed on Python 3.12/3.13,
  with Ruff, strict Mypy, generated TypeScript, React and installed-wheel checks.
- Pinned Vinext build, inspection of ten client JavaScript files and seven source
  maps, local D1 conditional-write/concurrency and process restart passed.
- Browser checkpoint: 32 of 33 Playwright tests passed; one HTTP 503 remains
  unresolved. Full browser acceptance, final independent review and the exact
  milestone gate are still required. No cloud deployment or whole-website proof
  is claimed.

Checkpoint: `3c740ebb8a231255aa6afb0cb4b8931e0980a09e`,
[Actions run 37977221372](https://github.com/ShadowsInThe-Space/llm-language-mvp/actions/runs/37977221372).

See [candidate notes](docs/releases/v0.7.0.md) and
[the implementation guide](docs/GENERAL-WEB-PREVIEW.md). The candidate status and
checkpoint results must be updated only after the final evidence passes.

## [0.6.0] - 2026-09-20

### Added

- Nominal immutable records, closed variants, exhaustive matching and general
  `Option<T>`/`Result<T,E>` ([#17](https://github.com/ShadowsInThe-Space/llm-language-mvp/issues/17)).
- Acyclic named functions, explicit `Nat` refinements and deterministic,
  budgeted used-only generic specialization ([#18](https://github.com/ShadowsInThe-Space/llm-language-mvp/issues/18)).
- Canonical typed A1 IR, deterministic reference interpreter, versioned checker
  rules and independently reconstructed certificates ([#19](https://github.com/ShadowsInThe-Space/llm-language-mvp/issues/19)).
- Bounded `List<T,N>`, precise UTF-8 `Text<N>` and generated JavaScript target
  differential tests ([#20](https://github.com/ShadowsInThe-Space/llm-language-mvp/issues/20)).

### Changed

- Milestone-sized delivery now requires all frozen issues, evidence, review and
  release material before its single completion merge ([#30](https://github.com/ShadowsInThe-Space/llm-language-mvp/issues/30),
  [#31](https://github.com/ShadowsInThe-Space/llm-language-mvp/issues/31)).

### Validation and scope

- 530 tests expected at final acceptance; Python 3.12/3.13 CI, Ruff, strict
  Mypy, installed-wheel and independent AI PL review remain release gates.
- Developer Preview. A1 proves structural well-formedness and supported local
  contracts; target equivalence is differential-tested, not formally proved.

## [0.5.0] - 2026-09-20

### Added

- Frozen P0/w1/w2 compatibility baseline
  ([#12](https://github.com/ShadowsInThe-Space/llm-language-mvp/issues/12)).
- Explicit local pkg1 packages, exports/imports, exact locks and deterministic DAG
  linking ([#13](https://github.com/ShadowsInThe-Space/llm-language-mvp/issues/13),
  [#14](https://github.com/ShadowsInThe-Space/llm-language-mvp/issues/14)).
- Independent Source-to-Core binding before accepting whole-program certificates
  ([#15](https://github.com/ShadowsInThe-Space/llm-language-mvp/issues/15)).
- Two distinct programs sharing one transitive pure library, with stale-lock and
  stale-proof rejection after changes
  ([#16](https://github.com/ShadowsInThe-Space/llm-language-mvp/issues/16)).

### Validation and scope

- 419 tests passed; Ruff/Mypy clean; CI on Python 3.12/3.13; installed-wheel smoke
  checks; independent AI PL review with no open blockers.
- Developer Preview, Linux package commands. P0 Int/Bool only; no general web
  libraries or autonomous factory. Historical web generator stays `web.0.4.0`.
- [Release](https://github.com/ShadowsInThe-Space/llm-language-mvp/releases/tag/v0.5.0)
  · [review](docs/reviews/M1-REVIEW.md)
  · [proof boundaries](docs/PKG1-ASSURANCE.md)

Earlier implementation versions are documented in historical `Log.md` and
`RELEASE.json`; this changelog does not invent retroactive GitHub releases.

[Unreleased]: https://github.com/ShadowsInThe-Space/llm-language-mvp/compare/v0.6.0...HEAD
[0.7.0]: https://github.com/ShadowsInThe-Space/llm-language-mvp/tree/milestone/m3
[0.6.0]: https://github.com/ShadowsInThe-Space/llm-language-mvp/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/ShadowsInThe-Space/llm-language-mvp/releases/tag/v0.5.0
