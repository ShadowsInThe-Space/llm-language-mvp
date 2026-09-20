# Milestone delivery: one work package, one merge, one release

Effective policy: 2026-09-20. Current published release: v0.5.0.
This workflow is initially prepared on `milestone/m2`; it becomes part of `main`
with the complete M2 delivery, not through a separate process-only merge.

## Fixed rules

1. One active release scope at a time, with a shared `milestone/<id>` branch.
2. All implementation and intermediate commits stay on that branch. Push it
   regularly for backup and CI. Do not push incomplete packages to `main`.
3. No per-issue PRs to `main`. Open one final PR after the entire package is ready.
4. Close an issue as **completed** only after its acceptance criteria pass on the
   work branch. Add the exact commit, commands/results and remaining limitations
   in a GitHub comment. Closed means implemented/accepted; the milestone release
   indicates availability on `main`. Reopen if acceptance regresses.
5. Every scoped issue must be completed before the final merge. Do not rely on
   automatic `Closes #...` at merge time; that would be circular with the gate.
6. Full tests, code/type checks, independent review, release notes, README and
   CHANGELOG belong to the same final package. No post-release README direct push.
7. A green final PR is squash-merged once. Main is revalidated before publication.
8. Every completed package publishes one version. Milestone closes only after
   the GitHub release and its exact commit/assets are verified.

## Roadmap and release boundaries

| Package | Issues | Target |
| --- | --- | --- |
| M0/M1 (complete) | #12–#16 | Included in published v0.5.0; no retroactive extra release |
| M2 | #17 #18 #19 #20 #30 #31 | v0.6.0 Developer Preview |
| M3 | #21 #22 #32 | v0.7.0 Web Preview |
| M4 | #23 #24 #33 #34 | v0.8.0 Beta |
| M5 | #25 #35 | 1.0 candidate only after demonstrated readiness |
| M6 | #26 | Conditional; first freeze a concrete measured extension scope |
| F1 | #1 #2 #7 #36 | Bounded live agent orchestration |
| F2 | #4 #8 #9 #37 | Evidence, memory and measured resource reporting |
| F3 | #3 #5 | Candidate knowledge consolidation and retrieval |
| F4 | #6 | Conditional measured routing optimization |

See [GitHub milestones](https://github.com/ShadowsInThe-Space/llm-language-mvp/milestones).
Epics #10/#11 span releases and intentionally have no milestone. They must not
create circular completion gates. F1–F4 are a coordinated Factory track, not
permission to implement everything at once. Fix their version and exact scope
before starting. There are no fabricated release dates.

## Starting a package

- Begin from the last released `main` in a clean worktree.
- Create `milestone/<id>`, keep individual commits small and linked to issues.
- Assign all relevant GitHub issues to one milestone.
- Set `release-plan.json`: exact milestone number/title, work branch, version,
  sorted issue IDs, review path, notes path, preview flag; keep `ready: false`.
- Do not bump the published version/README until the release candidate is ready.
- Any scope change must be recorded in an issue comment and `Log.md`, reviewed,
  and reflected in both the plan and milestone. Never move unfinished issues
  away just to make the gate green. Exact-set checks detect unilateral drift,
  not dishonest simultaneous edits; human/independent review remains essential.

Commit subjects use `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `ci:` or `chore:`
(optional scope). Reference the issue in the message. Release notes describe
user-visible outcomes, fixes, compatibility and limitations rather than copying
every commit message. Breaking changes must be explicit, including in 0.x.

## Acceptance and preparing the final PR

- TDD: failing behavioral test first, minimal implementation, then refactoring.
- Each issue: update acceptance checklist, attach evidence, close as completed.
- Entire package: regression suite, Ruff, strict Mypy, installed-wheel smoke test
  and package-specific end-to-end acceptance (including browser/DB where relevant).
- Independent specialist review with no unresolved blockers. Record scope,
  findings/fixes and evidence in `docs/reviews/<PACKAGE>-REVIEW.md`; include the
  exact line `Release-Review: approved` only after that review. A marker is not
  proof that a review happened; maintainers must verify its provenance.
- Update `pyproject.toml`, README current-version line, delivered features,
  examples, setup and limitations. Prepare `docs/releases/v<VERSION>.md`.
- Move accepted entries from `CHANGELOG.md`'s Unreleased section into a dated
  `## [VERSION] - YYYY-MM-DD` section; link issues and compatibility changes.
  Keep planned features out of released sections. Use Added/Changed/Fixed/
  Security/Deprecated/Removed headings when relevant.
- Set `ready: true` only after the preceding evidence exists. Run:

```sh
python scripts/release_gate.py --repository ShadowsInThe-Space/llm-language-mvp --mode candidate
```

Commit the final package and open the single PR. Required checks:
`baseline (3.12)`, `baseline (3.13)`, `milestone-complete`.
The gate runs on every relevant PR update without a skip-success path.
It also rejects already-closed milestones and already-tagged/released versions,
so a completed package cannot authorize another main merge. Publication retries
use the separate main release mode and do not need a second PR.
If only an issue state changed, rerun the PR gate; issue events do not magically
refresh a previous result. Recheck live issue state immediately before merging.

Main protection requires an up-to-date PR and these checks, including for admins;
force pushes and branch deletion are disallowed. The specialist review can be
performed by a separate AI reviewer and recorded, without pretending to be a
real academic endorsement or requiring the sole owner to self-approve a PR.

## Automatic release after the one merge

`Milestone release` runs on a push to `main`:

1. Check the live milestone again, the exact issue set, completed state, readiness,
   current main SHA and required release documents.
2. Run the full compatibility matrix on Python 3.12/3.13 and Node.js 24.
3. Build the wheel with locked build tooling and commit-derived SOURCE_DATE_EPOCH.
4. Install the wheel into a separate environment; run package and web smoke checks.
5. Recheck the live gate immediately before writing to GitHub.
6. Create a draft against the exact checked commit, upload wheel and SHA256SUMS,
   publish it and verify tag target/asset digests.
7. Close the milestone. No bot version bump, source commit or direct main push.

Release notes are rendered from the reviewed committed notes and augmented with
the complete issue list and immutable tagged CHANGELOG link. Source archives are
provided by GitHub. Numeric tags `vMAJOR.MINOR.PATCH` are supported; preview status
is explicit GitHub prerelease metadata. This workflow does not upload to PyPI.

README is therefore current **at** publication, already in the release commit.
GitHub's release is the authoritative publication status. Before publication the
same source revision is only a candidate, even if the version is already bumped.

## Failure and retry

- Red gate/tests/review: stay on the work branch; no merge or release.
- Main check/build/upload fails: do not close the milestone or announce release.
  Inspect the failed run; rerun the same workflow at the same main commit after
  resolving an external failure. `workflow_dispatch` supports a manual retry
  once the workflow exists on main; non-main refs fail the release gate.
- Partial draft: a retry may replace draft assets; never published assets.
- Existing published release: only an exact matching tag, preview status and
  asset checksums permits a no-op/recovery of milestone closure. Conflicts fail
  closed and require investigation, not force-moved tags or overwritten releases.
- A real code fix after a merge follows a new explicitly scoped repair package;
  never silently patch main or pretend a failed release was successful.
- Do not start the next package's main merge before the prior release is verified.

GitHub issue state and publication are separate APIs, not an atomic transaction.
The gates check before merge and immediately before publication; they do not
prevent a human from reopening an issue immediately afterwards. Preserve the
release evidence and treat such regression as a new issue/repair package.

## Progress and resource reports

GitHub milestones show issue progress; issue comments carry commit/test evidence;
the work branch carries Unreleased changes; main/tagged CHANGELOG and GitHub
Releases carry completed packages. No unfinished source is merged merely to
update a progress counter. `Log.md` retains architectural reasoning.

At task/package completion report token usage, average tokens per second and
elapsed duration when measured. Aggregate agents without double counting;
average uses total wall time including tools/waits. Missing measurements are
explicitly unavailable, never inferred. Product instrumentation is tracked in #37.

## Automation trust boundary

Workflow code, release-plan edits, independent-review attestations and maintainers
are trusted. Branch protection is not a defense against an administrator who
deliberately edits protection rules or rewrites the gate. API failures fail closed.
The publisher has contents/issues write access only after the main test gates;
PR jobs have read-only tokens. No `pull_request_target` execution of untrusted code.
