# Independent workflow review — 2026-09-20

Scope: milestone-sized delivery tooling on `milestone/m2`, not M2 language
completion. This is an independent AI review; no academic endorsement claimed.
**Verdict: no open blockers for pushing the work branch. Not a release approval.**

## Findings resolved with failing regressions first

1. A published-release-by-tag lookup cannot find interrupted unpublished drafts.
   The publisher now falls back to the authenticated paginated release list.
2. Upload success did not prove the complete asset set before public publication.
   Exact assets, SHA256 digests and commit target are now checked while still
   draft and again after publication. Extra/partial assets block publication.
3. An approval substring could accept a negated/example review marker. Approval
   now requires an exact line; ordinary Markdown version headers remain valid.
4. Initial main protection was absent. Live protection now requires PRs and
   all three GitHub-Actions checks, including for admins, without force/deletion.

## Independent evidence

- 33 focused tests passed at the review snapshot; script/test Ruff checks passed.
- Realistic offline interrupted-upload simulation: by-tag 404, draft discovered
  via paginated list, retry reuses it; only one draft is created.
- Live read-only candidate check correctly rejected six open M2 issues,
  readiness=false, missing final release documents and unchanged version.
- Live main protection read back: strict checks, Actions app binding, PR-required,
  admin enforcement, no force push, no branch deletion.
- No skipped-success route for the required milestone check. Publish permissions
  are granted only to the job after the gate and full validation matrix.

The GitHub publisher was deliberately not run against the live repository.
The future M2 milestone review and real release execution remain required.
The current branch does not authorize or imply a v0.6.0 release.
