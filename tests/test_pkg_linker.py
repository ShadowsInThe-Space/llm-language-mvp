import pytest

from llmlang.model import Candidate, Expr, FunctionSpec, Limits, Specification
from llmlang.pkg.linker import canonical_bound, link
from llmlang.pkg.model import Import, Module, Package, Snapshot


def _fn(body: Expr, params: tuple[str, ...] = ()) -> tuple[Specification, Candidate]:
    signature = FunctionSpec(params, "Int", Expr("bool", value=True), Expr("bool", value=True))
    return Specification((signature,)), Candidate((body,))


def _module(name: str, body: Expr, *, imports=(), exports=("run",), names=("run",)) -> Module:
    spec, candidate = _fn(body)
    return Module(name, tuple(names), tuple(imports), tuple(exports), spec, candidate)


def _typed_module(name: str, returns: str, body: Expr, *, imports=(), exports=("run",)) -> Module:
    signature = FunctionSpec((), returns, Expr("bool", value=True), Expr("bool", value=True))
    return Module(
        name,
        ("run",),
        tuple(imports),
        tuple(exports),
        Specification((signature,)),
        Candidate((body,)),
    )


def test_link_rewrites_import_and_is_deterministic() -> None:
    provider = Package("math", "1.0.0", (), (_module("math", Expr("int", value=7)),))
    consumer = Package(
        "app",
        "1.0.0",
        (("math", "1.0.0"),),
        (
            _module(
                "main", Expr("call", value=0),
                imports=(Import("minimum", "math", "math", "run"),),
            ),
        ),
    )
    snapshot = Snapshot("app", (consumer, provider))
    first = link(snapshot)
    second = link(Snapshot("app", (provider, consumer)))
    assert first.candidate.bodies[-1].value == 0
    assert first.manifest == second.manifest
    assert canonical_bound(first) == canonical_bound(second)
    assert first.manifest["functions"][-1]["call_slots"] == [0, 1]


def test_link_rejects_forward_and_self_calls() -> None:
    signature = FunctionSpec((), "Int", Expr("bool", value=True), Expr("bool", value=True))
    module = Module(
        "main",
        ("first", "second"),
        (),
        ("first",),
        Specification((signature, signature)),
        Candidate((Expr("call", value=1), Expr("int", value=1))),
    )
    snapshot = Snapshot("app", (Package("app", "1.0.0", (), (module,)),))
    try:
        link(snapshot)
    except Exception as exc:
        assert getattr(exc, "code", None) == "P_CALL"
    else:
        raise AssertionError("forward local call unexpectedly linked")


def test_diamond_and_multiple_modules_are_deduplicated() -> None:
    leaf = Package("leaf", "1.0.0", (), (_module("api", Expr("int", value=1)),))
    left = Package(
        "left", "1.0.0", (("leaf", "1.0.0"),),
        (_module("api", Expr("call", value=0), imports=(Import("value", "leaf", "api", "run"),)),),
    )
    right = Package(
        "right", "1.0.0", (("leaf", "1.0.0"),),
        (_module("api", Expr("call", value=0), imports=(Import("value", "leaf", "api", "run"),)),),
    )
    app = Package(
        "app", "1.0.0", (("left", "1.0.0"), ("right", "1.0.0")),
        (_module("main", Expr("call", value=0), imports=(Import("left", "left", "api", "run"),)),
         _module(
             "second", Expr("call", value=0),
             imports=(Import("right", "right", "api", "run"),),
         )),
    )
    bound = link(Snapshot("app", (app, right, leaf, left)))
    assert len(bound.spec.functions) == 5
    assert [row["package"] for row in bound.manifest["functions"]].count("leaf") == 1


def test_module_and_package_declaration_permutations_have_same_manifest() -> None:
    first = Package(
        "app", "1.0.0", (),
        (_module("z", Expr("int", value=2)), _module("a", Expr("int", value=1))),
    )
    second = Package(
        "app", "1.0.0", (),
        (_module("a", Expr("int", value=1)), _module("z", Expr("int", value=2))),
    )
    assert link(Snapshot("app", (first,))).manifest == link(Snapshot("app", (second,))).manifest


def test_parameter_and_let_binding_is_preserved() -> None:
    signature = FunctionSpec(
        ("Int", "Int"), "Int", Expr("bool", value=True), Expr("bool", value=True)
    )
    body = Expr(
        "let",
        (Expr("int", value=3), Expr("int.add", (Expr("var", value=0), Expr("var", value=1)))),
    )
    module = Module("main", ("run",), (), ("run",), Specification((signature,)), Candidate((body,)))
    bound = link(Snapshot("app", (Package("app", "1.0.0", (), (module,)),)))
    row = bound.manifest["functions"][0]
    assert row["parameters"] == ["Int", "Int"]
    assert row["binder_indices"] == [1, 0]
    assert bound.candidate.bodies[0] == body


def test_import_result_type_is_checked_by_final_core() -> None:
    provider = Package(
        "lib", "1.0.0", (), (_typed_module("api", "Bool", Expr("bool", value=True)),)
    )
    consumer = Package(
        "app", "1.0.0", (("lib", "1.0.0"),),
        (
            _typed_module(
                "main", "Int", Expr("call", value=0),
                imports=(Import("flag", "lib", "api", "run"),),
            ),
        ),
    )
    with pytest.raises(Exception) as caught:
        link(Snapshot("app", (consumer, provider)), core_limits=Limits())
    assert getattr(caught.value, "code", None) == "P_TYPE"
