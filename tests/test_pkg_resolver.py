import json
from pathlib import Path

import pytest

from llmlang.pkg.model import PkgError, PkgLimits
from llmlang.pkg.parser import parse_package
from llmlang.pkg.resolver import freeze, resolve

SPEC = "(spec p0 (fn (params) (result Int) (requires true) (ensures true)))"
CANDIDATE = "(candidate p0 (body 1))"


def _package(root: Path, name: str = "app", dependency: dict[str, str] | None = None) -> None:
    package = root / name
    package.mkdir()
    (package / "main.llapi").write_text(SPEC)
    (package / "main.llmod").write_text(CANDIDATE)
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
        )
    )


def test_parser_rejects_duplicate_json_keys() -> None:
    with pytest.raises(PkgError) as error:
        parse_package('{"format":"pkg1","format":"pkg1"}', lambda _: "")
    assert error.value.code == "P_DUPLICATE"


def test_freeze_and_resolve_round_trip(tmp_path: Path) -> None:
    _package(tmp_path)
    lock = freeze(tmp_path, "app", {"app": "app"})
    (tmp_path / "ll.lock.json").write_text(json.dumps(lock))
    snapshot = resolve(tmp_path, tmp_path / "ll.lock.json")
    assert snapshot.root == "app"
    assert snapshot.packages[0].name == "app"


def test_resolve_rejects_changed_source(tmp_path: Path) -> None:
    _package(tmp_path)
    lock = freeze(tmp_path, "app", {"app": "app"})
    (tmp_path / "ll.lock.json").write_text(json.dumps(lock))
    (tmp_path / "app" / "main.llmod").write_text("(candidate p0 (body 2))")
    with pytest.raises(PkgError) as error:
        resolve(tmp_path, tmp_path / "ll.lock.json")
    assert error.value.code == "P_HASH"


def _manifest() -> dict[str, object]:
    return {
        "format": "pkg1",
        "name": "app",
        "version": "1.0.0",
        "dependencies": {},
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


@pytest.mark.parametrize(
    "mutate",
    [
        lambda x: x.update(extra=True),
        lambda x: x.update(format="pkg2"),
        lambda x: x.update(name="_app"),
        lambda x: x.update(version="1.0"),
        lambda x: x.update(dependencies={"Math": "1.0.0"}),
        lambda x: x.update(modules=[]),
        lambda x: x["modules"].append(x["modules"][0].copy()),
        lambda x: x["modules"][0].update(names=["run", "run"]),
        lambda x: x["modules"][0].update(
            imports=[
                {"alias": "x", "package": "dep", "module": "m", "export": "f"},
                {"alias": "x", "package": "dep", "module": "m", "export": "f"},
            ]
        ),
        lambda x: x["modules"][0].update(
            names=["x"], imports=[{"alias": "x", "package": "dep", "module": "m", "export": "f"}]
        ),
        lambda x: x["modules"][0].update(exports=["run", "run"]),
        lambda x: x["modules"][0].update(exports=["private"]),
        lambda x: x["modules"][0].update(spec="/main.llapi"),
        lambda x: x["modules"][0].update(source="../main.llmod"),
        lambda x: x["modules"][0].update(source="main\\main.llmod"),
        lambda x: x["modules"][0].update(unknown=True),
        lambda x: x["modules"][0].update(spec="bad.llapi"),
    ],
    ids=[
        "unknown-root",
        "format",
        "name",
        "version",
        "dependency",
        "empty-modules",
        "duplicate-module",
        "duplicate-function",
        "duplicate-alias",
        "alias-collision",
        "duplicate-export",
        "private-export",
        "absolute-path",
        "traversal",
        "backslash",
        "unknown-module",
        "bad-p0",
    ],
)
def test_parser_rejects_normative_invalid_manifests(mutate) -> None:
    data = _manifest()
    mutate(data)
    files = {"main.llapi": SPEC, "main.llmod": CANDIDATE, "bad.llapi": "(spec nope)"}
    with pytest.raises(PkgError):
        parse_package(json.dumps(data), files.__getitem__)


@pytest.mark.parametrize(
    "limits",
    [
        PkgLimits(max_packages=0),
        PkgLimits(max_modules=257),
        PkgLimits(max_functions=1025),
        PkgLimits(max_imports=4097),
        PkgLimits(max_total_bytes=4194305),
        PkgLimits(max_file_bytes=131073),
    ],
)
def test_parser_rejects_invalid_budget(limits: PkgLimits) -> None:
    with pytest.raises(PkgError) as error:
        parse_package(
            json.dumps(_manifest()),
            {"main.llapi": SPEC, "main.llmod": CANDIDATE}.__getitem__,
            limits,
        )
    assert error.value.code == "P_LIMIT"


def test_parser_allows_import_call_for_resolver_validation() -> None:
    data = _manifest()
    data["modules"][0]["imports"] = [
        {"alias": "f", "package": "dep", "module": "m", "export": "run"}
    ]
    data["modules"][0]["spec"] = "import.llapi"
    data["modules"][0]["source"] = "import.llmod"
    files = {"import.llapi": SPEC, "import.llmod": "(candidate p0 (body (call 0)))"}
    package = parse_package(json.dumps(data), files.__getitem__)
    assert package.modules[0].candidate.bodies[0].value == 0
