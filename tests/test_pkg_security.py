import json
import os
from pathlib import Path

import pytest

from llmlang.model import Candidate, Expr, FunctionSpec, Specification
from llmlang.pkg.model import Module, Package, PkgError, PkgLimits, Snapshot
from llmlang.pkg.resolver import _safe_read, freeze, resolve, validate_snapshot

SPEC = "(spec p0 (fn (params) (result Int) (requires true) (ensures true)))"
CANDIDATE = "(candidate p0 (body 0))"


def _package(root: Path, name: str, *, dependency: dict[str, str] | None = None) -> Path:
    package = root / name
    package.mkdir()
    (package / "main.llapi").write_text(SPEC, encoding="utf-8")
    (package / "main.llmod").write_text(CANDIDATE, encoding="utf-8")
    (package / "package.llpkg").write_text(
        json.dumps(
            {
                "format": "pkg1",
                "name": name,
                "version": "1.0.0",
                "dependencies": dependency or {},
                "modules": [
                    {
                        "name": "main",
                        "names": ["run"],
                        "imports": [],
                        "exports": ["run"],
                        "spec": "main.llapi",
                        "source": "main.llmod",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return package


def test_symlink_intermediate_and_file_are_rejected(tmp_path: Path) -> None:
    _package(tmp_path, "app")
    (tmp_path / "alias").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(PkgError) as intermediate:
        freeze(tmp_path, "app", {"app": "alias/app"})
    assert intermediate.value.code in {"P_IO", "P_PATH"}

    outside = tmp_path / "outside.llmod"
    outside.write_text(CANDIDATE, encoding="utf-8")
    (tmp_path / "app" / "main.llmod").unlink()
    (tmp_path / "app" / "main.llmod").symlink_to(outside)
    with pytest.raises(PkgError) as file_link:
        freeze(tmp_path, "app", {"app": "app"})
    assert file_link.value.code in {"P_IO", "P_PATH"}


@pytest.mark.parametrize("selection", ["../app", "/tmp/app"])
def test_path_traversal_and_absolute_selection_are_rejected(tmp_path: Path, selection: str) -> None:
    _package(tmp_path, "app")
    with pytest.raises(PkgError) as error:
        freeze(tmp_path, "app", {"app": selection})
    assert error.value.code == "P_PATH"


def test_fifo_is_rejected_without_blocking(tmp_path: Path) -> None:
    os.mkfifo(tmp_path / "pipe")
    with pytest.raises(PkgError) as error:
        _safe_read(Path("pipe"), base=tmp_path)
    assert error.value.code == "P_IO"


def test_cumulative_package_bytes_and_lock_budget_are_enforced(tmp_path: Path) -> None:
    _package(tmp_path, "app", dependency={"lib": "1.0.0"})
    _package(tmp_path, "lib")
    one = len((tmp_path / "app" / "package.llpkg").read_bytes()) + len(SPEC) + len(CANDIDATE)
    limits = PkgLimits(max_total_bytes=one + 1)
    with pytest.raises(PkgError) as error:
        freeze(tmp_path, "app", {"app": "app", "lib": "lib"}, limits)
    assert error.value.code == "P_LIMIT"

    generous = PkgLimits(max_total_bytes=one * 2 + 1)
    lock = freeze(tmp_path, "app", {"app": "app", "lib": "lib"}, generous)
    lock_path = tmp_path / "ll.lock.json"
    lock_path.write_text(json.dumps(lock), encoding="utf-8")
    with pytest.raises(PkgError) as lock_error:
        resolve(tmp_path, lock_path, generous)
    assert lock_error.value.code == "P_LIMIT"


@pytest.mark.parametrize(
    "limits",
    [PkgLimits(max_packages=True), PkgLimits(max_packages=65), PkgLimits(max_file_bytes=0)],
)
def test_invalid_or_over_default_budgets_are_rejected(limits: PkgLimits) -> None:
    fn = FunctionSpec((), "Int", Expr("bool", value=True), Expr("bool", value=True))
    module = Module(
        "main", ("run",), (), ("run",), Specification((fn,)), Candidate((Expr("int", value=0),))
    )
    snapshot = Snapshot("app", (Package("app", "1.0.0", (), (module,)),))
    with pytest.raises(PkgError) as error:
        validate_snapshot(snapshot, limits)
    assert error.value.code == "P_LIMIT"


def test_duplicate_modules_and_malformed_snapshot_are_rejected() -> None:
    fn = FunctionSpec((), "Int", Expr("bool", value=True), Expr("bool", value=True))
    module = Module(
        "main", ("run",), (), ("run",), Specification((fn,)), Candidate((Expr("int", value=0),))
    )
    duplicate = Snapshot("app", (Package("app", "1.0.0", (), (module, module)),))
    with pytest.raises(PkgError) as duplicate_error:
        validate_snapshot(duplicate)
    assert duplicate_error.value.code in {"P_DUPLICATE", "P_NAME"}
    with pytest.raises(PkgError) as malformed_error:
        validate_snapshot(object())  # type: ignore[arg-type]
    assert malformed_error.value.code == "P_PARSE"


def test_package_cycle_diagnostic_is_deterministic() -> None:
    fn = FunctionSpec((), "Int", Expr("bool", value=True), Expr("bool", value=True))
    module = Module(
        "main", ("run",), (), ("run",), Specification((fn,)), Candidate((Expr("int", value=0),))
    )
    a = Package("a", "1.0.0", (("b", "1.0.0"),), (module,))
    b = Package("b", "1.0.0", (("a", "1.0.0"),), (module,))
    first = second = None
    for _ in range(2):
        with pytest.raises(PkgError) as error:
            validate_snapshot(Snapshot("a", (a, b)))
        if first is None:
            first = error.value.to_dict()
        else:
            second = error.value.to_dict()
    assert first == second
    assert first["code"] == "P_CYCLE"


def test_disjoint_module_cycles_report_same_symbol_after_permutation():
    from llmlang.pkg.model import Import

    fn = FunctionSpec((), "Int", Expr("bool", value=True), Expr("bool", value=True))

    def module(name, other):
        return Module(
            name,
            ("run",),
            (Import("remote", "app", other, "run"),),
            ("run",),
            Specification((fn,)),
            Candidate((Expr("int", value=0),)),
        )

    modules = (module("a", "b"), module("b", "a"), module("c", "d"), module("d", "c"))
    errors = []
    for order in (modules, modules[2:] + modules[:2]):
        with pytest.raises(PkgError) as error:
            validate_snapshot(Snapshot("app", (Package("app", "1.0.0", (), order),)))
        errors.append(error.value.to_dict())
    assert errors[0] == errors[1]
