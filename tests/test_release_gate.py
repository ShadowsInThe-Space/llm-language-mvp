import json
from pathlib import Path

import pytest

from scripts import release_gate as gate


def write_valid(root: Path, **overrides):
    plan = {
        "format": 1,
        "milestone_number": 2,
        "title": "M2",
        "branch": "milestone/m2",
        "version": "0.6.0",
        "prerelease": True,
        "ready": True,
        "required_issues": [10, 11],
        "review_file": "docs/reviews/M2-REVIEW.md",
        "notes_file": "docs/releases/v0.6.0.md",
    }
    plan.update(overrides)
    (root / "release-plan.json").write_text(json.dumps(plan), encoding="utf-8")
    (root / "pyproject.toml").write_text('[project]\nversion = "0.6.0"\n', encoding="utf-8")
    (root / "README.md").write_text(
        "*Current version: 0.6.0 — Developer Preview · experimental*\n", encoding="utf-8"
    )
    (root / "CHANGELOG.md").write_text("## [0.6.0] - 2026-09-20\n", encoding="utf-8")
    (root / "docs/reviews").mkdir(parents=True)
    (root / "docs/releases").mkdir(parents=True)
    (root / "docs/reviews/M2-REVIEW.md").write_text("Release-Review: approved\n", encoding="utf-8")
    (root / "docs/releases/v0.6.0.md").write_text("Release 0.6.0\n", encoding="utf-8")
    return gate.load_plan(root / "release-plan.json")


def live_issues():
    return [
        {"number": 10, "state": "closed", "state_reason": "completed", "milestone": {"number": 2}},
        {"number": 11, "state": "closed", "state_reason": "completed", "milestone": {"number": 2}},
        {"number": 99, "state": "open", "milestone": {"number": 2}, "pull_request": {"url": "x"}},
    ]


def test_normal_markdown_release_header_is_accepted(tmp_path):
    plan = write_valid(tmp_path)
    (tmp_path / plan.notes_file).write_text(
        "# v0.6.0 — Structured language\n\nDelivered features and limitations.\n",
        encoding="utf-8",
    )
    assert gate.validate_documents(tmp_path, plan) == []


@pytest.mark.parametrize(
    "changes,expected",
    [
        ({"ready": False}, "plan is not ready"),
    ],
)
def test_document_gate_rejects_plan_state(tmp_path, changes, expected):
    plan = write_valid(tmp_path, **changes)
    assert expected in gate.validate_documents(tmp_path, plan)


@pytest.mark.parametrize(
    "issues,expected",
    [
        (
            lambda: [{**live_issues()[0], "state": "open"}, live_issues()[1]],
            "issue 10 is not closed",
        ),
        (
            lambda: [{**live_issues()[0], "state_reason": "reopened"}, live_issues()[1]],
            "issue 10 is not completed",
        ),
        (
            lambda: [{**live_issues()[0], "state_reason": "not_planned"}, live_issues()[1]],
            "issue 10 is not completed",
        ),
        (lambda: live_issues()[:1], "required issue set mismatch"),
        (
            lambda: (
                live_issues()[:2]
                + [
                    {
                        "number": 12,
                        "state": "closed",
                        "state_reason": "completed",
                        "milestone": {"number": 2},
                    }
                ]
            ),
            "required issue set mismatch",
        ),
        (lambda: [], "milestone has no issues"),
    ],
)
def test_live_issue_gate_is_fail_closed(issues, expected):
    plan = gate.Plan(1, 2, "M2", "milestone/m2", "0.6.0", True, True, (10, 11), "review", "notes")
    assert expected in gate.validate_live(plan, {"number": 2, "title": "M2"}, issues())


def test_pull_requests_are_excluded_and_milestone_must_match():
    plan = gate.Plan(1, 2, "M2", "milestone/m2", "0.6.0", True, True, (10, 11), "review", "notes")
    assert gate.validate_live(plan, {"number": 2, "title": "M2"}, live_issues()) == []
    assert "live milestone mismatch" in gate.validate_live(
        plan, {"number": 2, "title": "other"}, live_issues()
    )


def test_documents_reject_version_and_review_mismatch(tmp_path):
    plan = write_valid(tmp_path)
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "0.5.0"\n', encoding="utf-8")
    (tmp_path / plan.review_file).write_text("Release-Review: pending\n", encoding="utf-8")
    errors = gate.validate_documents(tmp_path, plan)
    assert "pyproject version mismatch" in errors
    assert f"{plan.review_file} content invalid" in errors


def test_markers_are_exact_and_current_version_is_bounded(tmp_path):
    plan = write_valid(tmp_path)
    (tmp_path / "README.md").write_text("Roadmap mentions 0.6.00\n", encoding="utf-8")
    (tmp_path / plan.review_file).write_text(
        "This says Release-Review: approved inline\n", encoding="utf-8"
    )
    errors = gate.validate_documents(tmp_path, plan)
    assert "README version missing" in errors
    assert f"{plan.review_file} content invalid" in errors


def test_duplicate_plan_keys_are_rejected(tmp_path):
    (tmp_path / "release-plan.json").write_text('{"format":1,"format":1}', encoding="utf-8")
    with pytest.raises(gate.GateError, match="duplicate keys"):
        gate.load_plan(tmp_path / "release-plan.json")


@pytest.mark.parametrize("version", ["01.2.3", "1.02.3", "1.2.03"])
def test_plan_rejects_noncanonical_semver(tmp_path, version):
    write_valid(tmp_path)
    plan_json = json.loads((tmp_path / "release-plan.json").read_text(encoding="utf-8"))
    plan_json["version"] = version
    (tmp_path / "release-plan.json").write_text(json.dumps(plan_json), encoding="utf-8")
    with pytest.raises(gate.GateError, match="numeric semver"):
        gate.load_plan(tmp_path / "release-plan.json")


def test_null_and_malformed_api_objects_fail_closed():
    plan = gate.Plan(1, 2, "M2", "milestone/m2", "0.6.0", True, True, (10,), "review", "notes")
    assert "live milestone response malformed" in gate.validate_live(plan, None, [])
    assert "live issue response malformed" in gate.validate_live(
        plan, {"number": 2, "title": "M2"}, None
    )
    assert "live issue response malformed" in gate.validate_live(
        plan, {"number": 2, "title": "M2"}, [None]
    )


def test_symlinked_plan_path_cannot_escape_root(tmp_path):
    outside = tmp_path.parent / "outside-release-notes.md"
    outside.write_text("Release 0.6.0\n", encoding="utf-8")
    root = tmp_path / "repo"
    root.mkdir()
    (root / "docs").mkdir()
    (root / "docs/releases").symlink_to(tmp_path.parent, target_is_directory=True)
    plan = gate.Plan(
        1,
        2,
        "M2",
        "milestone/m2",
        "0.6.0",
        True,
        True,
        (10,),
        "review",
        "docs/releases/outside-release-notes.md",
    )
    assert "docs/releases/outside-release-notes.md missing" in gate.validate_documents(root, plan)


def test_branch_and_release_main_staleness(monkeypatch):
    plan = gate.Plan(1, 2, "M2", "milestone/m2", "0.6.0", True, True, (10,), "review", "notes")
    monkeypatch.setenv("GITHUB_HEAD_REF", "wrong")
    assert "candidate branch mismatch" in gate.validate_branch(plan, "candidate", "o/r")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setattr(gate, "_git", lambda args: "local-sha")
    monkeypatch.setattr(gate, "gh_json", lambda repo, endpoint: {"sha": "remote-sha"})
    assert "local HEAD is not origin main" in gate.validate_branch(plan, "release", "o/r")


def test_gh_network_failure_is_not_treated_as_missing(monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("network down")

    monkeypatch.setattr(gate.subprocess, "run", fail)
    with pytest.raises(gate.GateError):
        gate.gh_json("o/r", "repos/o/r/releases/tags/v0.6.0")


def test_subprocess_timeout_is_stable(monkeypatch):
    def timeout(*args, **kwargs):
        raise gate.subprocess.TimeoutExpired(args[0], 30)

    monkeypatch.setattr(gate.subprocess, "run", timeout)
    with pytest.raises(gate.GateError, match="timed out"):
        gate.gh_json("o/r", "repos/o/r/issues")


def test_notes_output_never_overwrites(tmp_path):
    output = tmp_path / "notes.md"
    output.write_text("keep", encoding="utf-8")
    with pytest.raises(gate.GateError, match="already exists"):
        gate.write_notes(output, "replace")
    assert output.read_text(encoding="utf-8") == "keep"


@pytest.mark.parametrize("state", ["closed", None])
def test_candidate_cannot_remerge_a_completed_milestone(monkeypatch, tmp_path, state):
    plan = write_valid(tmp_path)

    def missing(*args):
        raise gate.NotFoundError("not found")

    monkeypatch.setattr(gate, "gh_json", missing)
    assert "candidate milestone must be open" in gate.validate_candidate_state(
        plan, {"state": state}, "o/r"
    )


def test_candidate_version_must_not_already_be_released_or_tagged(monkeypatch, tmp_path):
    plan = write_valid(tmp_path)
    monkeypatch.setattr(gate, "gh_json", lambda *args: {"present": True})
    assert "candidate version already exists" in gate.validate_candidate_state(
        plan, {"state": "open"}, "o/r"
    )


def test_new_candidate_version_accepts_only_confirmed_absence(monkeypatch, tmp_path):
    plan = write_valid(tmp_path)

    def missing(*args):
        raise gate.NotFoundError("not found")

    monkeypatch.setattr(gate, "gh_json", missing)
    assert gate.validate_candidate_state(plan, {"state": "open"}, "o/r") == []

    def failed(*args):
        raise gate.GateError("network failure")

    monkeypatch.setattr(gate, "gh_json", failed)
    with pytest.raises(gate.GateError):
        gate.validate_candidate_state(plan, {"state": "open"}, "o/r")
