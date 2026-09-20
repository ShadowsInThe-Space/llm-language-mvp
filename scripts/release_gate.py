#!/usr/bin/env python3
"""Read-only release gate for a milestone release."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

SEMVER = re.compile(r"\A(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\Z")
DATE_HEADING = re.compile(r"^## \[(?P<v>[^\]]+)\] - \d{4}-\d{2}-\d{2}$", re.MULTILINE)
PLAN_KEYS = {
    "format",
    "milestone_number",
    "title",
    "branch",
    "version",
    "prerelease",
    "ready",
    "required_issues",
    "review_file",
    "notes_file",
}


@dataclass(frozen=True)
class Plan:
    format: int
    milestone_number: int
    title: str
    branch: str
    version: str
    prerelease: bool
    ready: bool
    required_issues: tuple[int, ...]
    review_file: str
    notes_file: str


class GateError(Exception):
    pass


class NotFoundError(GateError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise GateError("release plan contains duplicate keys")
        result[key] = value
    return result


def _path_ok(value: Any) -> bool:
    return (
        type(value) is str
        and value != ""
        and not value.startswith(("/", "\\"))
        and "\\" not in value
        and ".." not in Path(value).parts
    )


def _safe_path(root: Path, value: str) -> Path:
    if not _path_ok(value):
        raise GateError("release plan contains unsafe path")
    resolved_root = root.resolve()
    resolved = root.joinpath(value).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise GateError("release plan path escapes repository") from exc
    return resolved


def load_plan(path: Path) -> Plan:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except (OSError, ValueError) as exc:
        raise GateError("invalid release-plan.json") from exc
    if type(raw) is not dict or set(raw) != PLAN_KEYS:
        raise GateError("release plan schema mismatch")
    expected = {
        "format": int,
        "milestone_number": int,
        "title": str,
        "branch": str,
        "version": str,
        "prerelease": bool,
        "ready": bool,
        "required_issues": list,
        "review_file": str,
        "notes_file": str,
    }
    if any(type(raw[k]) is not typ for k, typ in expected.items()):
        raise GateError("release plan contains invalid types")
    if raw["format"] != 1 or raw["milestone_number"] <= 0 or not raw["title"] or not raw["branch"]:
        raise GateError("release plan contains invalid values")
    if not re.fullmatch(r"milestone/[A-Za-z0-9._/-]+", raw["branch"]):
        raise GateError("release plan branch is invalid")
    if not SEMVER.fullmatch(raw["version"]):
        raise GateError("version must be numeric semver")
    issues = raw["required_issues"]
    if (
        not issues
        or any(type(i) is not int or i <= 0 for i in issues)
        or len(issues) != len(set(issues))
        or issues != sorted(issues)
    ):
        raise GateError("required_issues must be a sorted nonempty list")
    if not _path_ok(raw["review_file"]) or not _path_ok(raw["notes_file"]):
        raise GateError("release plan contains unsafe path")
    return Plan(
        raw["format"],
        raw["milestone_number"],
        raw["title"],
        raw["branch"],
        raw["version"],
        raw["prerelease"],
        raw["ready"],
        tuple(issues),
        raw["review_file"],
        raw["notes_file"],
    )


def validate_documents(root: Path, plan: Plan) -> list[str]:
    errors: list[str] = []
    if not plan.ready:
        errors.append("plan is not ready")
    try:
        with root.joinpath("pyproject.toml").open("rb") as stream:
            project = tomllib.load(stream).get("project", {})
    except (OSError, UnicodeError, tomllib.TOMLDecodeError, AttributeError):
        errors.append("pyproject.toml missing")
    else:
        if (
            type(project) is not dict
            or type(project.get("version")) is not str
            or project["version"] != plan.version
        ):
            errors.append("pyproject version mismatch")
    try:
        readme = root.joinpath("README.md").read_text(encoding="utf-8")
    except OSError:
        errors.append("README.md missing")
    else:
        version_line = re.compile(
            rf"^\*Current version:\s*{re.escape(plan.version)}(?:\s+[^*]*)?\*$"
        )
        if not any(version_line.fullmatch(line) for line in readme.splitlines()):
            errors.append("README version missing")
    try:
        changelog = root.joinpath("CHANGELOG.md").read_text(encoding="utf-8")
    except OSError:
        errors.append("CHANGELOG.md missing")
    else:
        valid_heading = False
        for match in DATE_HEADING.finditer(changelog):
            try:
                date.fromisoformat(match.group(0).rsplit(" - ", 1)[1])
            except ValueError:
                continue
            valid_heading |= match.group("v") == plan.version
        if not valid_heading:
            errors.append("dated changelog heading missing")
    for name, marker in (
        (plan.notes_file, plan.version),
        (plan.review_file, "Release-Review: approved"),
    ):
        try:
            content = _safe_path(root, name).read_text(encoding="utf-8")
        except (OSError, UnicodeError, GateError):
            errors.append(f"{name} missing")
        else:
            marker_found = (
                marker in content.splitlines()
                if name == plan.review_file
                else re.search(r"(?<![0-9.])" + re.escape(marker) + r"(?![0-9.])", content)
            )
            if not content.strip() or not marker_found:
                errors.append(f"{name} content invalid")
    return errors


def validate_live(plan: Plan, milestone: dict[str, Any], issues: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    if type(milestone) is not dict:
        return ["live milestone response malformed"]
    if milestone.get("number") != plan.milestone_number or milestone.get("title") != plan.title:
        errors.append("live milestone mismatch")
    if type(issues) is not list or any(type(i) is not dict for i in issues):
        return errors + ["live issue response malformed"]
    scoped = []
    for issue in issues:
        if "pull_request" in issue:
            continue
        issue_milestone = issue.get("milestone")
        if type(issue_milestone) is dict and issue_milestone.get("number") == plan.milestone_number:
            scoped.append(issue)
    numbers = {i.get("number") for i in scoped}
    if numbers != set(plan.required_issues):
        errors.append("required issue set mismatch")
    if not scoped:
        errors.append("milestone has no issues")
    for issue in scoped:
        if issue.get("state") != "closed":
            errors.append(f"issue {issue.get('number')} is not closed")
        elif issue.get("state_reason") != "completed":
            errors.append(f"issue {issue.get('number')} is not completed")
    return errors


def gh_json(repo: str, endpoint: str) -> Any:
    cmd = [
        "gh",
        "api",
        endpoint,
        "--paginate",
        "--slurp",
        "-H",
        "Accept: application/vnd.github+json",
    ]
    try:
        proc = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=30)
        value = json.loads(proc.stdout or "[]")
        if type(value) not in (dict, list):
            raise GateError("GitHub API response malformed")
        if isinstance(value, list) and value and all(isinstance(page, list) for page in value):
            return [item for page in value for item in page]
        return value
    except subprocess.CalledProcessError as exc:
        if re.search(r"\(HTTP 404\)", exc.stderr or ""):
            raise NotFoundError("GitHub resource not found") from exc
        raise GateError("GitHub API request failed") from exc
    except subprocess.TimeoutExpired as exc:
        raise GateError("GitHub API request timed out") from exc
    except (OSError, ValueError) as exc:
        raise GateError("GitHub API request failed") from exc


def _git(args: list[str]) -> str:
    try:
        return subprocess.run(
            ["git", *args], check=True, capture_output=True, text=True, timeout=30
        ).stdout.strip()
    except subprocess.TimeoutExpired as exc:
        raise GateError("git state unavailable") from exc
    except (OSError, subprocess.CalledProcessError) as exc:
        raise GateError("git state unavailable") from exc


def validate_branch(plan: Plan, mode: str, repo: str) -> list[str]:
    errors: list[str] = []
    if mode == "candidate":
        branch = os.environ.get("GITHUB_HEAD_REF") or _git(["branch", "--show-current"])
        if branch != plan.branch:
            errors.append("candidate branch mismatch")
    else:
        if os.environ.get("GITHUB_REF") != "refs/heads/main":
            errors.append("release requires main ref")
        remote = gh_json(repo, f"repos/{repo}/commits/main")
        if isinstance(remote, list):
            remote = remote[0] if remote else {}
        if _git(["rev-parse", "HEAD"]) != remote.get("sha"):
            errors.append("local HEAD is not origin main")
    return errors


def validate_candidate_state(plan: Plan, milestone: dict[str, Any], repo: str) -> list[str]:
    """A published work package cannot authorize another main merge."""
    errors = []
    if milestone.get("state") != "open":
        errors.append("candidate milestone must be open")
    for endpoint in (
        f"repos/{repo}/releases/tags/v{plan.version}",
        f"repos/{repo}/git/ref/tags/v{plan.version}",
    ):
        try:
            gh_json(repo, endpoint)
        except NotFoundError:
            continue
        errors.append("candidate version already exists")
    return errors


def render_notes(
    root: Path, plan: Plan, repo: str, milestone: dict[str, Any], issues: list[dict[str, Any]]
) -> str:
    base = _safe_path(root, plan.notes_file).read_text(encoding="utf-8").rstrip()
    lines = [base, "", f"Milestone: https://github.com/{repo}/milestone/{plan.milestone_number}"]
    for number in sorted(
        i["number"]
        for i in issues
        if "pull_request" not in i
        and isinstance(i.get("milestone"), dict)
        and i["milestone"].get("number") == plan.milestone_number
    ):
        lines.append(f"Issue: https://github.com/{repo}/issues/{number}")
    lines.append(f"Changelog: https://github.com/{repo}/blob/v{plan.version}/CHANGELOG.md")
    return "\n".join(lines) + "\n"


def write_notes(path: Path, content: str) -> None:
    try:
        with path.open("x", encoding="utf-8") as stream:
            stream.write(content)
    except FileExistsError as exc:
        raise GateError("notes output already exists") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--mode", choices=("candidate", "release"), required=True)
    parser.add_argument("--notes-output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repository):
        print(
            json.dumps(
                {"ok": False, "errors": ["repository must be OWNER/REPO"], "mode": args.mode},
                sort_keys=True,
            )
        )
        return 1
    root = Path.cwd()
    try:
        plan = load_plan(root / "release-plan.json")
        errors = validate_documents(root, plan)
        milestone = gh_json(
            args.repository, f"repos/{args.repository}/milestones/{plan.milestone_number}"
        )
        if isinstance(milestone, list):
            milestone = milestone[0] if milestone else {}
        issues = gh_json(args.repository, f"repos/{args.repository}/issues?state=all&per_page=100")
        errors += validate_live(plan, milestone, issues)
        errors += validate_branch(plan, args.mode, args.repository)
        if args.mode == "candidate":
            errors += validate_candidate_state(plan, milestone, args.repository)
        if not errors and args.notes_output:
            write_notes(
                Path(args.notes_output),
                render_notes(root, plan, args.repository, milestone, issues),
            )
    except (GateError, OSError, UnicodeError, TypeError, AttributeError) as exc:
        errors = [str(exc)]
    result = {"ok": not errors, "errors": sorted(set(errors)), "mode": args.mode}
    print(json.dumps(result, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
