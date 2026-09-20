"""Dependency authorization and whole-program expansion boundaries."""

from dataclasses import replace

import pytest

from llmlang.model import Candidate, Expr, FunctionSpec, Specification
from llmlang.pkg.model import Import, Module, Package, PkgError, PkgLimits, Snapshot
from llmlang.pkg.resolver import validate_snapshot


def graph():
    fn = FunctionSpec((), "Int", Expr("bool", value=True), Expr("bool", value=True))
    leaf = Module(
        "main", ("run",), (), ("run",), Specification((fn,)), Candidate((Expr("int", value=1),))
    )
    middle = replace(
        leaf,
        imports=(Import("base", "base", "main", "run"),),
        candidate=Candidate((Expr("call", value=0),)),
    )
    root = replace(middle, imports=(Import("middle", "middle", "main", "run"),))
    return Snapshot(
        "app",
        (
            Package("app", "1.0.0", (("middle", "1.0.0"),), (root,)),
            Package("middle", "1.0.0", (("base", "1.0.0"),), (middle,)),
            Package("base", "1.0.0", (), (leaf,)),
        ),
    )


@pytest.mark.parametrize(
    "case,code",
    [
        ("version", "P_DEPENDENCY"),
        ("missing", "P_DEPENDENCY"),
        ("transitive", "P_PRIVATE"),
        ("private", "P_PRIVATE"),
        ("unknown", "P_UNBOUND"),
        ("imports", "P_LIMIT"),
    ],
)
def test_graph_rejections(case, code):
    snapshot = graph()
    app, middle, base = snapshot.packages
    limits = PkgLimits()
    if case == "version":
        base = replace(base, version="2.0.0")
    elif case == "private":
        base = replace(base, modules=(replace(base.modules[0], exports=()),))
    elif case in {"transitive", "unknown"}:
        imp = Import(
            "external",
            "base" if case == "transitive" else "middle",
            "main",
            "run" if case == "transitive" else "absent",
        )
        app = replace(app, modules=(replace(app.modules[0], imports=(imp,)),))
    elif case == "imports":
        limits = replace(limits, max_imports=1)
    snapshot = replace(
        snapshot, packages=(app, middle) if case == "missing" else (app, middle, base)
    )
    with pytest.raises(PkgError) as error:
        validate_snapshot(snapshot, limits)
    assert error.value.code == code


def test_ast_budget_is_global_not_per_module():
    expr = Expr("int", value=0)
    for _ in range(10):
        expr = Expr("int.add", (expr, expr))
    fn = FunctionSpec((), "Int", Expr("bool", value=True), Expr("bool", value=True))
    modules = tuple(
        Module(f"m{i}", ("run",), (), ("run",), Specification((fn,)), Candidate((expr,)))
        for i in range(6)
    )
    with pytest.raises(PkgError) as error:
        validate_snapshot(Snapshot("app", (Package("app", "1.0.0", (), modules),)))
    assert error.value.code == "P_LIMIT"
