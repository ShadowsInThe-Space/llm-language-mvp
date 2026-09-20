"""Issue #16: two consumers reuse the same transitive implementation safely."""

import json
import shutil
from pathlib import Path

import pytest

from llmlang.cli import main
from llmlang.pkg.model import PkgError
from llmlang.pkg.resolver import freeze, resolve

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "pkg1"


@pytest.mark.parametrize("root,expected", [("app", "3"), ("remaining", "4")])
def test_complete_reused_bundles_execute_distinct_outputs(tmp_path, capsys, root, expected):
    workspace = tmp_path / "workspace"
    shutil.copytree(EXAMPLE, workspace)
    common = ["--workspace", str(workspace)]
    lock = workspace / f"{root}.ll.lock.json"
    assert (
        main(
            [
                "lock-pkg",
                *common,
                "--root",
                root,
                "--package",
                f"{root}={root}",
                "--package",
                "rules=rules",
                "--package",
                "base=base",
                "--out",
                str(lock),
            ]
        )
        == 0
    )
    artifact = tmp_path / f"{root}.bound.json"
    certificate = tmp_path / f"{root}.proof.json"
    assert main(["link-pkg", *common, "--lock", str(lock), "--out", str(artifact)]) == 0
    assert (
        main(
            [
                "check-pkg",
                *common,
                "--lock",
                str(lock),
                "--bound",
                str(artifact),
                "--write-certificate",
                str(certificate),
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert (
        main(
            [
                "run-pkg",
                *common,
                "--lock",
                str(lock),
                "--bound",
                str(artifact),
                "--certificate",
                str(certificate),
                "--entry",
                "main.run",
                "--inputs",
                '[{"type":"Int","value":"3"},{"type":"Int","value":"7"}]',
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["result"] == {"type": "Int", "value": expected}


@pytest.mark.parametrize("root", ["app", "remaining"])
def test_shared_change_rejects_stale_lock_then_fresh_bundle_is_accepted(tmp_path, root):
    workspace = tmp_path / root
    shutil.copytree(EXAMPLE, workspace)
    selection = {root: root, "rules": "rules", "base": "base"}
    old_lock = freeze(workspace, root, selection)
    old_path = workspace / "old.ll.lock.json"
    old_path.write_text(json.dumps(old_lock), encoding="utf-8")
    resolve(workspace, old_path)

    source = workspace / "base" / "math.llmod"
    source.write_text(
        "(candidate p0 (body (int.add 0 (if (int.le (var 1) (var 0)) "
        "(var 1) (var 0)))))",
        encoding="utf-8",
    )
    with pytest.raises(PkgError) as stale:
        resolve(workspace, old_path)
    assert stale.value.code == "P_HASH"

    fresh_lock = freeze(workspace, root, selection)
    fresh_path = workspace / "fresh.ll.lock.json"
    fresh_path.write_text(json.dumps(fresh_lock), encoding="utf-8")
    snapshot = resolve(workspace, fresh_path)
    assert snapshot.root == root
