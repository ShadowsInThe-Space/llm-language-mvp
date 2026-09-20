# Changelog

Notable delivered changes are grouped by milestone release. Unreleased entries
describe work accepted on the milestone branch, not features available on main.
Release policy: [one package, one merge, one release](docs/RELEASE-WORKFLOW.md).

## [Unreleased]

### Changed

- M2 work branch prepares milestone-sized delivery, a live issue-completion gate,
  reviewed release documents and an automatic draft/publish/verify lifecycle
  ([#30](https://github.com/ShadowsInThe-Space/llm-language-mvp/issues/30)).
  This workflow is not yet activated on main; M2 remains incomplete.

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

[Unreleased]: https://github.com/ShadowsInThe-Space/llm-language-mvp/compare/v0.5.0...milestone/m2
[0.5.0]: https://github.com/ShadowsInThe-Space/llm-language-mvp/releases/tag/v0.5.0
