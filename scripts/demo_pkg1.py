"""Run the PKG1 Issue #16 acceptance scenario in an isolated workspace.

The demonstration deliberately copies the checked-in example before doing any
work.  Consequently locks, bound artifacts, certificates, and source edits
cannot alter tracked inputs.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "pkg1"
PYTHON = Path(sys.executable)


def _command(workspace: Path, *args: str, expect: int = 0) -> dict[str, Any]:
    environment = os.environ.copy()
    process = subprocess.run(
        [str(PYTHON), "-m", "llmlang", *args],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    if process.returncode != expect:
        raise RuntimeError(
            f"command failed ({process.returncode}, expected {expect}): {args}\n"
            f"stdout={process.stdout}\nstderr={process.stderr}"
        )
    try:
        return json.loads(process.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"command did not return JSON: {process.stdout!r}") from error


def _selection(workspace: Path, root: str) -> list[str]:
    manifests: dict[str, tuple[str, dict[str, Any]]] = {}
    for package_dir in sorted(workspace.iterdir()):
        if (package_dir / "package.llpkg").is_file():
            manifest = json.loads((package_dir / "package.llpkg").read_text(encoding="utf-8"))
            manifests[manifest["name"]] = (package_dir.name, manifest)
    if "remaining" not in manifests:
        raise RuntimeError("Issue #16 fixture examples/pkg1/remaining is missing")
    reachable: set[str] = set()
    pending = [root]
    while pending:
        name = pending.pop()
        if name in reachable:
            continue
        if name not in manifests:
            raise RuntimeError(f"package {name!r} is missing")
        reachable.add(name)
        pending.extend(manifests[name][1].get("dependencies", {}))
    return [f"{name}={manifests[name][0]}" for name in sorted(reachable)]


def _freeze_link_check(workspace: Path, root: str, output: Path) -> dict[str, Any]:
    selection = _selection(workspace, root)
    lock = output / f"{root}.lock.json"
    bound = output / f"{root}.bound.json"
    proof = output / f"{root}.proof.json"
    common = ("--workspace", str(workspace))
    package_args = [part for item in selection for part in ("--package", item)]
    _command(
        workspace,
        "lock-pkg",
        *common,
        "--root",
        root,
        *package_args,
        "--out",
        str(lock),
    )
    linked = _command(workspace, "link-pkg", *common, "--lock", str(lock), "--out", str(bound))
    checked = _command(
        workspace,
        "check-pkg",
        *common,
        "--lock",
        str(lock),
        "--bound",
        str(bound),
        "--write-certificate",
        str(proof),
    )
    return {"lock": lock, "bound": bound, "proof": proof, "linked": linked, "checked": checked}


def _run(workspace: Path, files: dict[str, Any], entry: str) -> dict[str, Any]:
    return _command(
        workspace,
        "run-pkg",
        "--workspace",
        str(workspace),
        "--lock",
        str(files["lock"]),
        "--bound",
        str(files["bound"]),
        "--certificate",
        str(files["proof"]),
        "--entry",
        entry,
        "--inputs",
        '[{"type":"Int","value":"7"},{"type":"Int","value":"3"}]',
    )


def main() -> int:
    try:
        with tempfile.TemporaryDirectory(prefix="llmlang-pkg1-demo-") as temporary:
            root = Path(temporary)
            first = root / "first"
            shutil.copytree(EXAMPLE, first)
            output = root / "artifacts"
            output.mkdir()

            app = _freeze_link_check(first, "app", output)
            remaining = _freeze_link_check(first, "remaining", output)
            app_run = _run(first, app, "main.run")
            remaining_run = _run(first, remaining, "main.run")

            app_lock = json.loads(app["lock"].read_text(encoding="utf-8"))
            remaining_lock = json.loads(remaining["lock"].read_text(encoding="utf-8"))
            app_packages = {item["name"]: item for item in app_lock["packages"]}
            remaining_packages = {item["name"]: item for item in remaining_lock["packages"]}
            shared_base_hash = app_packages["base"]["sha256"]
            if remaining_packages["base"]["sha256"] != shared_base_hash:
                raise RuntimeError("consumers do not share the same authorized base hash")

            # Change only the copied base body.  This is semantically equivalent,
            # but source identity must still invalidate old locks and proofs.
            base_source = first / "base" / "math.llmod"
            base_source.write_text(
                "(candidate p0 (body (int.add (if (int.le (var 1) (var 0)) (var 1) (var 0)) 0)))\n",
                encoding="utf-8",
            )
            stale_link = _command(
                first,
                "link-pkg",
                "--workspace",
                str(first),
                "--lock",
                str(app["lock"]),
                "--out",
                str(output / "stale.bound.json"),
                expect=1,
            )
            if stale_link.get("diagnostics", [{}])[0].get("code") != "P_HASH":
                raise RuntimeError(f"stale lock was not rejected: {stale_link}")
            stale_remaining_link = _command(
                first,
                "link-pkg",
                "--workspace",
                str(first),
                "--lock",
                str(remaining["lock"]),
                "--out",
                str(output / "stale-remaining.bound.json"),
                expect=1,
            )
            if stale_remaining_link.get("diagnostics", [{}])[0].get("code") != "P_HASH":
                raise RuntimeError(f"stale remaining lock was not rejected: {stale_remaining_link}")

            # Use a new artifact directory: PKG1 outputs are intentionally
            # exclusive-create and must never be silently overwritten.
            fresh = _freeze_link_check(first, "app", output / "fresh")
            stale_proof = _command(
                first,
                "run-pkg",
                "--workspace",
                str(first),
                "--lock",
                str(fresh["lock"]),
                "--bound",
                str(fresh["bound"]),
                "--certificate",
                str(app["proof"]),
                "--entry",
                "main.run",
                "--inputs",
                '[{"type":"Int","value":"7"},{"type":"Int","value":"3"}]',
                expect=1,
            )
            if stale_proof.get("diagnostics", [{}])[0].get("code") != "P_BINDING":
                raise RuntimeError(f"stale proof was not rejected: {stale_proof}")
            fresh_run = _run(first, fresh, "main.run")
            fresh_remaining = _freeze_link_check(first, "remaining", output / "fresh-remaining")
            stale_remaining_proof = _command(
                first,
                "run-pkg",
                "--workspace",
                str(first),
                "--lock",
                str(fresh_remaining["lock"]),
                "--bound",
                str(fresh_remaining["bound"]),
                "--certificate",
                str(remaining["proof"]),
                "--entry",
                "main.run",
                "--inputs",
                '[{"type":"Int","value":"7"},{"type":"Int","value":"3"}]',
                expect=1,
            )
            if stale_remaining_proof.get("diagnostics", [{}])[0].get("code") != "P_BINDING":
                raise RuntimeError(
                    f"stale remaining proof was not rejected: {stale_remaining_proof}"
                )
            fresh_remaining_run = _run(first, fresh_remaining, "main.run")

            relocated = root / "relocated"
            shutil.copytree(first, relocated)
            relocated_files = _freeze_link_check(relocated, "app", output / "relocated")
            relocation_deterministic = (
                fresh["linked"]["bound_hash"] == relocated_files["linked"]["bound_hash"]
            )

            summary = {
                "status": "passed",
                "app": {"result": app_run["result"], "run_status": app_run["run_status"]},
                "remaining": {
                    "result": remaining_run["result"],
                    "run_status": remaining_run["run_status"],
                },
                "shared_base_hash": shared_base_hash,
                "transitive_dependency": set(app_packages) >= {"app", "rules", "base"},
                "stale_lock_rejected": True,
                "stale_lock_rejected_by_consumer": {"app": True, "remaining": True},
                "stale_proof_rejected": True,
                "stale_proof_rejected_by_consumer": {"app": True, "remaining": True},
                "fresh_proof_valid": fresh_run["status"] == "proved",
                "fresh_proof_valid_by_consumer": {
                    "app": fresh_run["status"] == "proved",
                    "remaining": fresh_remaining_run["status"] == "proved",
                },
                "relocation_deterministic": relocation_deterministic,
            }
            acceptance = (
                summary["app"]["result"] == {"type": "Int", "value": "3"}
                and summary["remaining"]["result"] == {"type": "Int", "value": "0"}
                and summary["transitive_dependency"]
                and summary["fresh_proof_valid"]
                and relocation_deterministic
            )
            if not acceptance:
                raise RuntimeError(f"acceptance assertion failed: {summary}")
            print(json.dumps(summary, sort_keys=True))
            return 0
    except (OSError, RuntimeError, KeyError, ValueError) as error:
        print(json.dumps({"status": "failed", "error": str(error)}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
