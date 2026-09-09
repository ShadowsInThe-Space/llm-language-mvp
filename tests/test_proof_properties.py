"""Independent concrete evaluations challenge symbolic acceptance on generated programs."""

from hypothesis import given, settings
from hypothesis import strategies as st

from llmlang.core import evaluate, evaluate_contract, validate
from llmlang.model import Candidate, Expr, FunctionSpec, Specification
from llmlang.proof import check_certificate, verify


def integer(value):
    return Expr("int", value=value)


def expression(name, *args):
    return Expr(name, args)


@given(st.integers(-10, 10), st.integers(-10, 10), st.integers(-10, 10))
@settings(max_examples=35, deadline=None)
def test_affine_branch_programs_match_independent_concrete_checks(a, b, cut):
    x = Expr("var", value=0)
    affine = expression("int.add", expression("int.mul", integer(a), x), integer(b))
    body = expression("if", expression("int.le", x, integer(cut)), affine, x)
    # This deliberately mixes true and false conjectures; search cannot pick the contract.
    ensures = expression("int.le", Expr("result"), x)
    spec = Specification((FunctionSpec(("Int",), "Int", Expr("bool", value=True), ensures),))
    candidate = Candidate((body,))
    program = validate(spec, candidate)
    report = verify(spec, candidate)
    if report.status == "proved":
        assert check_certificate(spec, candidate, report.certificate)
        for value in range(-15, 16):
            returned = evaluate(program, (value,))
            assert evaluate_contract(ensures, (value,), result=returned) is True
    elif report.status == "counterexample":
        value = int(report.counterexample["inputs"][0]["value"])
        returned = evaluate(program, (value,))
        assert evaluate_contract(ensures, (value,), result=returned) is False
    else:
        assert report.status == "unverified"


@given(st.integers(-100, 100), st.booleans())
@settings(max_examples=20, deadline=None)
def test_nested_boolean_inputs_and_let_round_trip_are_proved(offset, flag):
    x, condition = Expr("var", value=0), Expr("var", value=1)
    term = expression("if", condition, expression("int.add", x, integer(offset)), x)
    body = expression(
        "let",
        Expr("bool", value=flag),
        expression(
            "if",
            Expr("var", value=0),
            expression(
                "if",
                Expr("var", value=2),
                expression("int.add", Expr("var", value=1), integer(offset)),
                Expr("var", value=1),
            ),
            expression(
                "if",
                Expr("var", value=2),
                expression("int.add", Expr("var", value=1), integer(offset)),
                Expr("var", value=1),
            ),
        ),
    )
    spec = Specification(
        (
            FunctionSpec(
                ("Bool", "Int"),
                "Int",
                Expr("bool", value=True),
                expression("int.eq", Expr("result"), term),
            ),
        )
    )
    candidate = Candidate((body,))
    report = verify(spec, candidate)
    assert report.status == "proved"
    assert check_certificate(spec, candidate, report.certificate)


@given(st.integers(-25, 25), st.integers(-25, 25), st.integers(1, 5))
@settings(max_examples=40, deadline=None)
def test_early_opposite_row_pruning_preserves_integer_witnesses(lower, upper, coefficient):
    x = Expr("var", value=0)
    scaled = expression("int.mul", integer(coefficient), x)
    # Feasible interval scaled lower <= coefficient*x <= scaled upper.
    requires = expression(
        "and",
        expression("int.le", integer(coefficient * lower), scaled),
        expression("int.le", scaled, integer(coefficient * upper)),
    )
    spec = Specification((FunctionSpec(("Int",), "Int", requires, Expr("bool", value=False)),))
    candidate = Candidate((x,))
    report = verify(spec, candidate)
    if lower <= upper:
        assert report.status == "counterexample"
        value = int(report.counterexample["inputs"][0]["value"])
        assert lower <= value <= upper
        assert report.domains[0].status == "domain_nonempty"
    else:
        assert report.status == "proved"
        assert report.domains[0].status == "contract_empty"
        assert check_certificate(spec, candidate, report.certificate)
