# LLM-Language delivery rules

Read `docs/RELEASE-WORKFLOW.md` and `release-plan.json` before changing release scope.

- Work on the current `milestone/<id>` branch, never directly on `main`.
- No individual-issue merges. One final PR/merge and one release per complete package.
- All scoped issues must be closed **as completed**, with commit/test evidence,
  before the final merge. A `not_planned` closure or scope removal is not completion.
- Preserve historical M0 fixture hashes, P0 contracts and frozen source/documents.
- Use TDD for compiler, tooling and bug fixes. Run `.venv/bin/python -m pytest -q`,
  `.venv/bin/python -m ruff check src tests scripts`, and
  `.venv/bin/python -m mypy --no-incremental src`.
- Require an independent specialist review before each release. AI review must
  be labelled as such; never claim real academic endorsement or unproved guarantees.
- Prepare README, CHANGELOG, version, release notes and review on the work branch.
  Do not fix these through direct main pushes after publication.
- Release only through the gated workflow against the exact validated main SHA.
  Do not overwrite published assets/tags or publish after incomplete validation.
- Use cheap worker subagents for bounded implementation tasks; verify their results.
- At completion report measured tokens, total-wall-time tokens/s and elapsed duration.
  If counters are unavailable say so; never invent metrics or double-count workers.
- Record architectural decisions and verification evidence in `Log.md`.
