import json
import shutil
from pathlib import Path

from llmlang.pkg.binding import check_package_certificate, verify_package
from llmlang.pkg.linker import canonical_bound, link
from llmlang.pkg.resolver import freeze, resolve

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "pkg1"
SELECTION = {"app": "app", "base": "base", "rules": "rules"}


def _prepare(workspace: Path) -> None:
    shutil.copytree(EXAMPLE, workspace)


def _freeze_resolve_link(workspace: Path, root: str):
    selection = {"base": "base", "rules": "rules", root: root}
    lock = freeze(workspace, root, selection)
    lock_path = workspace / f"{root}.ll.lock.json"
    lock_path.write_text(json.dumps(lock), encoding="utf-8")
    snapshot = resolve(workspace, lock_path)
    bound = link(snapshot)
    report = verify_package(snapshot, bound)
    assert report["status"] == "proved"
    return lock, snapshot, bound, report["certificate"]


def test_transitive_source_change_invalidates_both_consumers_and_old_certificates(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    _prepare(workspace)
    old: dict[str, tuple[object, object, object, object]] = {}
    for root in ("app", "remaining"):
        old[root] = _freeze_resolve_link(workspace, root)

    base_source = workspace / "base" / "math.llmod"
    original = base_source.read_text(encoding="utf-8")
    assert original.startswith("(candidate p0")
    base_source.write_text(
        "(candidate p0 (body (int.add 0 (if (int.le (var 1) (var 0)) (var 1) (var 0)))))",
        encoding="utf-8",
    )

    for root in ("app", "remaining"):
        _, changed_snapshot, changed_bound, _ = _freeze_resolve_link(workspace, root)
        _, old_snapshot, old_bound, old_certificate = old[root]
        assert changed_snapshot != old_snapshot
        assert changed_bound.manifest["snapshot_hash"] != old_bound.manifest["snapshot_hash"]
        assert changed_bound.manifest["bound_hash"] != old_bound.manifest["bound_hash"]
        assert not check_package_certificate(changed_snapshot, changed_bound, old_certificate)
        assert not check_package_certificate(old_snapshot, changed_bound, old_certificate)


def test_relocated_workspace_has_identical_canonical_bound_bytes(tmp_path: Path) -> None:
    first = tmp_path / "one"
    second = tmp_path / "two"
    _prepare(first)
    _prepare(second)
    for root in ("app", "remaining"):
        _, _, bound_one, _ = _freeze_resolve_link(first, root)
        _, _, bound_two, _ = _freeze_resolve_link(second, root)
        assert canonical_bound(bound_one) == canonical_bound(bound_two)
