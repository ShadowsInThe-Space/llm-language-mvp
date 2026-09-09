"""Independent adversarial checks of trust boundaries and observable semantics."""

from dataclasses import replace

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from llmlang.core import evaluate, validate
from llmlang.model import Candidate, Expr, LanguageError, Limits, Specification
from llmlang.parser import parse_candidate, parse_spec
from llmlang.proof import check_certificate, verify
from llmlang.transport import decode_inputs, decode_value


def _identity() -> tuple[Specification, Candidate]:
    return (
        parse_spec(
            "(spec p0 (fn (params Int) (result Int) (requires true)"
            " (ensures (int.eq result (var 0)))))"
        ),
        parse_candidate("(candidate p0 (body (var 0)))"),
    )


@pytest.mark.parametrize(
    "source",
    [
        '[{"type":"Int","type":"Bool","value":true}]',
        '[{"type":"Int","value":"1","value":"2"}]',
        '[{"type":"Int","value":9007199254740993}]',
        '[{"type":"Int","value":true}]',
        '[{"type":"Bool","value":1}]',
        '[{"type":"Int","value":"-0"}]',
        '[{"type":"Int","value":"+1"}]',
        '[{"type":"Int","value":"01"}]',
        '[{"type":"Int","value":"1", "trusted":true}]',
        '[{"type":"Int","value":NaN}]',
    ],
)
def test_ambiguous_or_coerced_inputs_are_rejected(source: str) -> None:
    with pytest.raises(LanguageError):
        decode_inputs(source)


def test_large_integer_roundtrips_without_javascript_number_coercion() -> None:
    assert decode_inputs('[{"type":"Int","value":"9007199254740993"}]') == (
        9007199254740993,
    )


def test_excessively_nested_inputs_are_a_controlled_input_error() -> None:
    with pytest.raises(LanguageError):
        decode_inputs("[" * 2000 + "0" + "]" * 2000)


@pytest.mark.parametrize(
    "expression",
    [
        Expr("var", value=False),
        Expr("var", value=-1),
        Expr("int", value=False),
        Expr("bool", value=0),
        Expr("int.add", (Expr("int", value=1), Expr("int", value=2)), value=7),
        Expr("result", (Expr("int", value=1),)),
        Expr("int", value=1 << 8192),
    ],
)
def test_direct_ast_cannot_smuggle_payload_or_wrong_exact_type(expression: Expr) -> None:
    spec, _ = _identity()
    with pytest.raises(LanguageError):
        validate(spec, Candidate((expression,)))


def test_direct_ast_cannot_smuggle_mutable_containers() -> None:
    spec, candidate = _identity()
    # Runtime APIs also accept Python callers; hints alone do not freeze their containers.
    mutable = Candidate(list(candidate.bodies))  # type: ignore[arg-type]
    with pytest.raises(LanguageError):
        validate(spec, mutable)
    mutable_spec = replace(spec, functions=list(spec.functions))  # type: ignore[arg-type]
    with pytest.raises(LanguageError):
        validate(mutable_spec, candidate)


def test_cyclic_direct_ast_stops_at_structure_budget() -> None:
    spec, _ = _identity()
    cycle = Expr("int.add")
    # Deliberate host-level corruption should not hang even before type rejection.
    object.__setattr__(cycle, "args", (cycle, Expr("int", value=1)))
    with pytest.raises(LanguageError):
        validate(spec, Candidate((cycle,)))


def test_unselected_branch_does_not_overflow_but_strict_operand_does() -> None:
    spec, _ = _identity()
    lazy = parse_candidate("(candidate p0 (body (if true 7 (int.mul 128 128))))")
    strict = parse_candidate(
        "(candidate p0 (body (if (and false (int.eq (int.mul 128 128) 0)) 1 7)))"
    )
    limits = Limits(max_bits=8)
    assert evaluate(validate(spec, lazy, limits), (0,), limits=limits) == 7
    with pytest.raises(LanguageError) as exc:
        evaluate(validate(spec, strict, limits), (0,), limits=limits)
    assert exc.value.code == "E_LIMIT"


def test_debruijn_shadowing_keeps_original_parameters_and_result_separate() -> None:
    spec = parse_spec(
        "(spec p0 (fn (params Int Int) (result Int) (requires true)"
        " (ensures (int.eq result (int.sub (var 1) (var 0))))))"
    )
    candidate = parse_candidate(
        "(candidate p0 (body (let (var 1) (let (var 1) (int.sub (var 1) (var 0))))))"
    )
    program = validate(spec, candidate)
    assert evaluate(program, (14, 5)) == 9
    assert evaluate(program, (-2, 5)) == -7


def test_validation_budget_exhaustion_does_not_claim_semantic_invalidity() -> None:
    spec, candidate = _identity()
    report = verify(spec, candidate, Limits(max_nodes=1))
    assert report.status == "unverified"
    assert report.certificate is None


def test_checker_does_not_depend_on_solver_search(monkeypatch: pytest.MonkeyPatch) -> None:
    from llmlang import solver

    spec, candidate = _identity()
    report = verify(spec, candidate)
    assert report.certificate is not None

    def unavailable(*args: object, **kwargs: object) -> None:
        raise AssertionError("The independent checker must not invoke search")

    monkeypatch.setattr(solver, "find_weights", unavailable)
    monkeypatch.setattr(solver, "find_integers", unavailable)
    assert check_certificate(spec, candidate, report.certificate)


def test_missing_boolean_input_case_cannot_reuse_valid_branch_certificate() -> None:
    spec = parse_spec(
        "(spec p0 (fn (params Bool) (result Int) (requires true)"
        " (ensures (int.eq result 7))))"
    )
    safe = parse_candidate("(candidate p0 (body (if (var 0) 7 7)))")
    unsafe = parse_candidate("(candidate p0 (body (if (var 0) 7 9)))")
    report = verify(spec, safe)
    assert report.certificate is not None
    assert not check_certificate(spec, unsafe, report.certificate)
    rejected = verify(spec, unsafe)
    assert rejected.status == "counterexample"
    assert rejected.counterexample is not None
    assert rejected.counterexample["inputs"] == [{"type": "Bool", "value": False}]


_integer_expressions = st.recursive(
    st.one_of(
        st.integers(-3, 3).map(lambda value: Expr("int", value=value)),
        st.integers(0, 1).map(lambda index: Expr("var", value=index)),
    ),
    lambda children: st.one_of(
        st.tuples(st.sampled_from(["int.add", "int.sub", "let"]), children, children).map(
            lambda triple: Expr(triple[0], (triple[1], triple[2]))
        ),
        st.tuples(children, children, children, children).map(
            lambda values: Expr(
                "if", (Expr("int.lt", (values[0], values[1])), values[2], values[3])
            )
        ),
    ),
    max_leaves=8,
)


@given(_integer_expressions, _integer_expressions, st.booleans())
@settings(max_examples=60, deadline=None, derandomize=True)
def test_generated_proofs_and_counterexamples_agree_with_concrete_execution(
    left: Expr, right: Expr, equal: bool
) -> None:
    """Exercise composed branch/let programs beyond manually selected golden cases."""
    spec = parse_spec(
        "(spec p0 (fn (params Int Int) (result Int) (requires true)"
        " (ensures (int.eq result 0))))"
    )
    candidate = Candidate((Expr("int.sub", (left, left if equal else right)),))
    program = validate(spec, candidate)
    report = verify(spec, candidate)
    if report.status == "proved":
        assert report.certificate is not None
        assert check_certificate(spec, candidate, report.certificate)
        for x in (-3, 0, 7):
            for y in (-2, 0, 8):
                assert evaluate(program, (x, y)) == 0
    elif report.status == "counterexample":
        assert report.counterexample is not None
        encoded = report.counterexample["inputs"]
        assert isinstance(encoded, list)
        inputs = tuple(decode_value(item) for item in encoded)
        assert evaluate(program, inputs) != 0
    else:
        assert report.status == "unverified"


@pytest.mark.parametrize(
    "params,requires",
    [
        ("Int", "(and (int.le (var 0) 0) (int.le (int.mul -1 (var 0)) 0))"),
        ("Int", "(int.eq (int.mul 2 (var 0)) 2)"),
        (
            "Int Int",
            "(and (int.le (int.add (var 1) (var 0)) 0)"
            " (int.le (int.sub (int.mul -1 (var 1)) (int.mul 2 (var 0))) -1))",
        ),
    ],
)
def test_pruning_preserves_feasible_boundaries_and_distinct_coefficient_vectors(
    params: str, requires: str
) -> None:
    spec = parse_spec(
        f"(spec p0 (fn (params {params}) (result Int) (requires {requires}) (ensures false)))"
    )
    report = verify(spec, parse_candidate("(candidate p0 (body 0))"))
    assert report.status == "counterexample"
    assert report.domains[0].status == "domain_nonempty"


def test_pruning_does_not_add_an_integrality_cut() -> None:
    spec = parse_spec(
        "(spec p0 (fn (params Int) (result Int)"
        " (requires (int.eq (int.mul 2 (var 0)) 1)) (ensures false)))"
    )
    report = verify(spec, parse_candidate("(candidate p0 (body 0))"))
    assert report.status == "unverified"
    assert report.domains[0].status == "domain_unknown"


def test_an_actually_contradictory_opposite_pair_is_safe_to_prune() -> None:
    spec = parse_spec(
        "(spec p0 (fn (params Int Int) (result Int)"
        " (requires (and (int.le (int.add (var 1) (var 0)) 0)"
        " (int.le (int.sub (int.mul -1 (var 1)) (var 0)) -1))) (ensures false)))"
    )
    candidate = parse_candidate("(candidate p0 (body 0))")
    report = verify(spec, candidate)
    assert report.status == "proved"
    assert report.domains[0].status == "contract_empty"
    assert report.certificate is not None
    assert check_certificate(spec, candidate, report.certificate)


def test_excessive_parameter_dimensions_stop_before_symbolic_allocation() -> None:
    spec = parse_spec(
        "(spec p0 (fn (params " + " ".join(["Int"] * 33)
        + ") (result Int) (requires true) (ensures true)))"
    )
    candidate = parse_candidate("(candidate p0 (body 0))")
    with pytest.raises(LanguageError) as exc:
        validate(spec, candidate)
    assert exc.value.code == "E_LIMIT"
    report = verify(spec, candidate)
    assert report.status == "unverified"
    assert report.certificate is None
