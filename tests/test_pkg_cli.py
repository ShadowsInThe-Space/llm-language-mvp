"""User workflow: freeze explicit inputs, link, certify, run, reject stale inputs."""

import json
import shutil
from pathlib import Path

from llmlang.cli import main


def test_package_workflow_and_transitive_source_drift(tmp_path, capsys):
    workspace = tmp_path / "workspace"
    shutil.copytree(Path(__file__).resolve().parents[1] / "examples/pkg1", workspace)
    common = ["--workspace", str(workspace)]
    lock = workspace / "ll.lock.json"
    assert (
        main(
            [
                "lock-pkg",
                *common,
                "--root",
                "app",
                "--package",
                "app=app",
                "--package",
                "base=base",
                "--package",
                "rules=rules",
                "--out",
                str(lock),
            ]
        )
        == 0
    )
    artifact, certificate = tmp_path / "bound.json", tmp_path / "proof.json"
    assert main(["link-pkg", *common, "--out", str(artifact)]) == 0
    assert (
        main(
            [
                "check-pkg",
                *common,
                "--bound",
                str(artifact),
                "--write-certificate",
                str(certificate),
            ]
        )
        == 0
    )
    capsys.readouterr()
    command = [
        "run-pkg",
        *common,
        "--bound",
        str(artifact),
        "--certificate",
        str(certificate),
        "--entry",
        "main.run",
        "--inputs",
        '[{"type":"Int","value":"7"},{"type":"Int","value":"3"}]',
    ]
    assert main(command) == 0
    assert json.loads(capsys.readouterr().out)["result"] == {"type": "Int", "value": "3"}
    # Existing outputs must not be overwritten silently.
    before = artifact.read_bytes()
    assert main(["link-pkg", *common, "--out", str(artifact)]) == 1
    assert artifact.read_bytes() == before
    source = workspace / "base/math.llmod"
    source.write_text("(candidate p0 (body 0))")
    capsys.readouterr()
    assert main(command) == 1
    assert json.loads(capsys.readouterr().out)["diagnostics"][0]["code"] == "P_HASH"


def test_cli_duplicate_selection_rejected(tmp_path, capsys):
    assert (
        main(
            [
                "lock-pkg",
                "--workspace",
                str(tmp_path),
                "--root",
                "app",
                "--package",
                "app=a",
                "--package",
                "app=b",
                "--out",
                str(tmp_path / "lock.json"),
            ]
        )
        == 1
    )
    assert json.loads(capsys.readouterr().out)["diagnostics"][0]["code"] == "P_DUPLICATE"


def test_linked_artifact_may_exceed_one_source_file_budget(tmp_path):
    from llmlang.model import Candidate, Expr, FunctionSpec, Specification
    from llmlang.parser import canonical_candidate, canonical_spec
    from llmlang.pkg.binding import check_binding
    from llmlang.pkg.cli import _bound
    from llmlang.pkg.linker import link
    from llmlang.pkg.model import Module, Package, Snapshot

    body = Expr("int", value=int("9" * 1000))
    for _ in range(7):
        body = Expr("int.add", (body, body))
    # Each module is below 128 KiB; their combined Core is larger.
    candidate = Candidate((body,))
    assert len(canonical_candidate(candidate)) < 131072
    fn = FunctionSpec((), "Int", Expr("bool", value=True), Expr("bool", value=True))
    modules = tuple(
        Module(name, ("run",), (), ("run",), Specification((fn,)), candidate) for name in ("a", "b")
    )
    snapshot = Snapshot("app", (Package("app", "1.0.0", (), modules),))
    bound = link(snapshot)
    artifact = tmp_path / "large.json"
    artifact.write_text(
        json.dumps(
            {
                "format": "pkg1-artifact",
                "spec": canonical_spec(bound.spec),
                "candidate": canonical_candidate(bound.candidate),
                "manifest": bound.manifest,
            }
        )
    )
    assert check_binding(snapshot, _bound(artifact))
