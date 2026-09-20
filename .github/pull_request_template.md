## Milestone completion — one PR for the complete work package

Milestone:
Work branch:
Release version:

- [ ] Every issue in release-plan.json is closed as completed with commit/test evidence.
- [ ] The live milestone issue set exactly matches the frozen scope.
- [ ] Full regression, Ruff, strict Mypy and installed-package smoke tests pass.
- [ ] Independent review completed; no open release blockers.
- [ ] README describes the delivered scope and limits, not future promises.
- [ ] CHANGELOG has the dated release entry with issue links and breaking changes.
- [ ] Version, release notes and review record match release-plan.json; ready=true.
- [ ] This is the sole final PR for the work package, not a partial issue merge.

## Acceptance evidence

Commands/results and independent review:

## Compatibility, migration and known limitations

## Release

After merge: the main release workflow repeats validation, publishes the exact
merge commit, verifies assets and closes the milestone. No follow-up direct
main push for README/version changes. Issues must be completed before merge;
do not rely on `Closes #...` to satisfy the pre-merge gate.
