"""Behavioral tests for P0 typing, binding, and bounded evaluation."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from llmlang.core import evaluate, evaluate_contract, validate
from llmlang.model import Candidate, Expr, LanguageError, Limits
from llmlang.parser import parse_candidate, parse_spec


def program(body: str, params: str = "Int", returns: str = "Int", requires: str = "true"):
    return validate(
        parse_spec(
            f"(spec p0 (fn (params {params}) (result {returns})"
            f" (requires {requires}) (ensures true)))"
        ),
        parse_candidate(f"(candidate p0 (body {body}))"),
    )


@given(st.integers(min_value=-(10**80), max_value=10**80), st.integers(-10000, 10000))
def test_arithmetic_and_let_binding(x: int, y: int) -> None:
    p = program("(let (int.add (var 1) (var 0)) (int.sub (var 0) (var 2)))", "Int Int")
    assert evaluate(p, (x, y)) == y


@pytest.mark.parametrize(
    "body",
    [
        "(var 1)",
        "result",
        "(int.add true 1)",
        "(if 0 1 2)",
        "(if true 0 false)",
        "(int.mul (var 0) (var 0))",
        "(call 0 (var 0))",
        "(bool.eq 0 0)",
        "(not 0)",
    ],
)
def test_reject_ill_typed_or_out_of_scope_program(body: str) -> None:
    with pytest.raises(LanguageError):
        program(body)


def test_boolean_is_not_integer() -> None:
    with pytest.raises(LanguageError):
        evaluate(program("(var 0)"), (True,))
    with pytest.raises(LanguageError):
        evaluate(program("(var 0)", "Bool", "Bool"), (1,))
    with pytest.raises(LanguageError):
        evaluate(program("(var 0)"), (1.0,))


def test_exact_entry_arity_and_precondition() -> None:
    p = program("(var 0)", requires="(int.le 0 (var 0))")
    for inputs in [(), (0, 1), (-1,)]:
        with pytest.raises(LanguageError):
            evaluate(p, inputs)
    assert evaluate(p, (0,)) == 0


def test_backward_calls_check_actual_precondition_and_lazy_if() -> None:
    spec = parse_spec(
        "(spec p0 "
        "(fn (params Int) (result Bool) (requires (int.le 0 (var 0))) (ensures true)) "
        "(fn (params Int) (result Bool) (requires true) (ensures true)))"
    )
    safe = validate(
        spec,
        parse_candidate(
            "(candidate p0 (body true) (body (if (int.le 0 (var 0)) (call 0 (var 0)) false)))"
        ),
    )
    assert evaluate(safe, (-1,)) is False
    assert evaluate(safe, (1,)) is True
    strict = validate(
        spec, parse_candidate("(candidate p0 (body true) (body (and false (call 0 (var 0)))))")
    )
    with pytest.raises(LanguageError) as error:
        evaluate(strict, (-1,))
    assert error.value.code == "E_PRECONDITION"


def test_call_arity_and_types() -> None:
    spec = parse_spec(
        "(spec p0 (fn (params Int) (result Int) (requires true) (ensures true))"
        " (fn (params) (result Int) (requires true) (ensures true)))"
    )
    for body in ["(call 0)", "(call 0 1 2)", "(call 0 true)", "(call 2 0)"]:
        with pytest.raises(LanguageError):
            validate(spec, parse_candidate(f"(candidate p0 (body (var 0)) (body {body}))"))


def test_result_has_separate_slot_and_contract_forbids_calls() -> None:
    expr = (
        parse_spec(
            "(spec p0 (fn (params Int) (result Int) (requires true)"
            " (ensures (int.eq result (var 0)))))"
        )
        .functions[0]
        .ensures
    )
    assert evaluate_contract(expr, (42,), 42) is True
    assert evaluate_contract(expr, (42,), 43) is False
    with pytest.raises(LanguageError):
        evaluate_contract(Expr("call", (Expr("int", value=0),), 0), ())


def test_direct_ast_is_validated_too() -> None:
    spec = program("0").spec
    for expr in [
        Expr("int", value=True),
        Expr("int.add", (Expr("int", value=0),)),
        Expr("int", (Expr("bool", value=False),), 1),
        Expr("var", value=True),
        Expr("unknown"),
        Expr("bool", value=1),
    ]:
        with pytest.raises(LanguageError):
            validate(spec, Candidate((expr,)))


def test_execution_resource_limits() -> None:
    p = program("(int.mul 1024 (var 0))")
    with pytest.raises(LanguageError):
        evaluate(p, (1024,), limits=Limits(max_bits=16))
    with pytest.raises(LanguageError):
        evaluate(p, (1,), limits=Limits(max_steps=1))
    with pytest.raises(LanguageError):
        evaluate(p, (1 << 9000,))


def test_backward_call_parameter_order_and_let() -> None:
    spec = parse_spec(
        "(spec p0"
        " (fn (params Int Int) (result Int) (requires true) (ensures true))"
        " (fn (params Int Int) (result Int) (requires true) (ensures true)))"
    )
    p = validate(
        spec,
        parse_candidate(
            "(candidate p0 (body (int.sub (var 1) (var 0)))"
            " (body (let (var 0) (call 0 (var 2) (var 0)))))"
        ),
    )
    assert evaluate(p, (10, 3)) == 7


def test_postcondition_does_not_forge_runtime_verification() -> None:
    spec = parse_spec("(spec p0 (fn (params) (result Int) (requires true) (ensures false)))")
    p = validate(spec, parse_candidate("(candidate p0 (body 3))"))
    assert evaluate(p, ()) == 3


@pytest.mark.parametrize(
    "requires,ensures",
    [
        ("result", "true"),
        ("0", "true"),
        ("true", "0"),
        ("(call 0)", "true"),
        ("true", "(call 0)"),
        ("true", "(int.eq result (var 1))"),
    ],
)
def test_every_contract_is_type_and_scope_checked(requires: str, ensures: str) -> None:
    spec = parse_spec(
        f"(spec p0 (fn (params Int) (result Int) (requires {requires}) (ensures {ensures})))"
    )
    with pytest.raises(LanguageError):
        validate(spec, parse_candidate("(candidate p0 (body 0))"))


@pytest.mark.parametrize("entry", [-1, 1, True])
def test_public_entry_index_is_checked(entry: int) -> None:
    with pytest.raises(LanguageError):
        evaluate(program("0"), (1,), entry)


@pytest.mark.parametrize(
    "body,path",
    [
        ("(let 0 (int.add (var 0) true))", (1, 0, 1, 1)),
        ("(if true 1 (var 7))", (1, 0, 2)),
        ("(if 0 1 2)", (1, 0, 0)),
        ("true", (1, 0)),
    ],
)
def test_type_failures_pinpoint_candidate_ast(body: str, path: tuple[int, ...]) -> None:
    with pytest.raises(LanguageError) as error:
        program(body)
    assert error.value.path == path


def test_contract_failure_pinpoints_spec_ast() -> None:
    spec = parse_spec(
        "(spec p0 (fn (params Int) (result Int) (requires true) (ensures (int.eq result (var 2)))))"
    )
    with pytest.raises(LanguageError) as error:
        validate(spec, parse_candidate("(candidate p0 (body 0))"))
    assert error.value.path == (0, 0, 3, 1)


def test_runtime_failures_pinpoint_input_and_expression() -> None:
    p = program("(int.add (var 0) 1)")
    with pytest.raises(LanguageError) as error:
        evaluate(p, (True,))
    assert error.value.path == (2, 0, 0)
    with pytest.raises(LanguageError) as error:
        evaluate(p, (255,), limits=Limits(max_bits=8))
    assert error.value.path == (1, 0)
    p = program("(var 0)", requires="(int.le 0 (var 0))")
    with pytest.raises(LanguageError) as error:
        evaluate(p, (-1,))
    assert error.value.path == (0, 0, 2)
