"""Behavioral regression tests for the independently checked P0 proof boundary."""

import copy
from dataclasses import replace

from llmlang.model import Candidate, Expr, FunctionSpec, Limits, Specification
from llmlang.proof import check_certificate, verify


def lit(value):
    return Expr("bool" if type(value) is bool else "int", value=value)


def op(name, *args):
    return Expr(name, args)


def var(index):
    return Expr("var", value=index)


def fixture(body, ensures, requires=None, params=("Int",), returns="Int"):
    return Specification(
        (FunctionSpec(params, returns, requires or lit(True), ensures),)
    ), Candidate((body,))


def certificate_fixture():
    requires = op("and", op("int.le", var(2), var(1)), op("int.le", var(1), var(0)))
    return fixture(
        var(2), op("int.le", Expr("result"), var(0)), requires, params=("Int", "Int", "Int")
    )


def test_minimum_proved_and_nonempty():
    body = op("if", op("int.le", var(1), var(0)), var(1), var(0))
    spec, candidate = fixture(body, op("int.eq", Expr("result"), body), params=("Int", "Int"))
    report = verify(spec, candidate)
    assert report.status == "proved"
    assert report.domains[0].status == "domain_nonempty"
    assert check_certificate(spec, candidate, report.certificate)


def test_counterexample_replayed_for_wrong_identity():
    spec, candidate = fixture(lit(0), op("int.eq", Expr("result"), var(0)))
    report = verify(spec, candidate)
    assert report.status == "counterexample"
    assert report.counterexample["inputs"][0]["value"] != "0"


def test_empty_domain_needs_certificate_and_integrality_gap_stays_unknown():
    spec, candidate = fixture(lit(0), lit(True), op("int.lt", var(0), var(0)))
    report = verify(spec, candidate)
    assert report.status == "proved"
    assert report.domains[0].status == "contract_empty"
    assert report.domains[0].certificate is not None
    spec2, candidate2 = fixture(
        lit(0), lit(True), op("int.eq", op("int.mul", lit(2), var(0)), lit(1))
    )
    report2 = verify(spec2, candidate2)
    assert report2.domains[0].status == "domain_unknown"


def test_mutated_binding_missing_leaf_and_negative_weights_rejected():
    spec, candidate = certificate_fixture()
    cert = verify(spec, candidate).certificate
    assert check_certificate(spec, candidate, cert)
    changed = Candidate((op("int.add", var(0), lit(1)),))
    assert not check_certificate(spec, changed, cert)
    other_spec = Specification((replace(spec.functions[0], ensures=lit(False)),))
    assert not check_certificate(other_spec, candidate, cert)
    for edit in ("missing", "negative", "extra", "unreduced"):
        bad = copy.deepcopy(cert)
        key = next(iter(bad["obligations"]))
        if edit == "missing":
            del bad["obligations"][key]
        elif edit == "negative":
            bad["obligations"][key][0] = ["-1", "1"]
        elif edit == "extra":
            bad["premises"] = []
        else:
            bad["obligations"][key][0] = ["2", "2"]
        assert not check_certificate(spec, candidate, bad)


def test_false_second_strict_boolean_operand_does_not_hide_call_failure():
    callee = FunctionSpec(("Int",), "Bool", op("int.lt", lit(0), var(0)), lit(True))
    caller = FunctionSpec((), "Bool", lit(True), op("bool.eq", Expr("result"), lit(False)))
    spec = Specification((callee, caller))
    candidate = Candidate((lit(True), op("and", lit(False), Expr("call", (lit(0),), 0))))
    report = verify(spec, candidate)
    assert report.status == "counterexample"
    assert report.counterexample["kind"] == "call_precondition"
    assert report.counterexample["entry"] == 1


def test_unselected_if_call_is_not_required():
    callee = FunctionSpec(("Int",), "Int", op("int.lt", lit(0), var(0)), lit(True))
    caller = FunctionSpec((), "Int", lit(True), op("int.eq", Expr("result"), lit(7)))
    spec = Specification((callee, caller))
    candidate = Candidate((var(0), op("if", lit(True), lit(7), Expr("call", (lit(0),), 0))))
    assert verify(spec, candidate).status == "proved"


def test_capture_avoiding_let_and_call_substitution():
    identity = FunctionSpec(("Int",), "Int", lit(True), op("int.eq", Expr("result"), var(0)))
    caller = FunctionSpec(
        ("Int",), "Int", lit(True), op("int.eq", Expr("result"), op("int.add", var(0), lit(3)))
    )
    spec = Specification((identity, caller))
    candidate = Candidate(
        (var(0), op("let", lit(3), Expr("call", (op("int.add", var(0), var(1)),), 0)))
    )
    assert verify(spec, candidate).status == "proved"


def test_proof_budget_exhaustion_never_proves():
    spec, candidate = fixture(var(0), op("int.eq", Expr("result"), var(0)))
    assert verify(spec, candidate, Limits(max_branches=1)).status == "unverified"


def test_invalid_candidate_does_not_raise_or_prove():
    spec, candidate = fixture(lit(True), lit(True))
    assert verify(spec, candidate).status == "invalid"


def test_large_integer_witness_remains_exact():
    big = 9007199254740993
    spec, candidate = fixture(var(0), lit(False), op("int.eq", var(0), lit(big)))
    report = verify(spec, candidate)
    assert report.status == "counterexample"
    assert report.counterexample["inputs"] == [{"type": "Int", "value": str(big)}]


def test_rational_farkas_weights_and_zero_forgery(monkeypatch):
    from llmlang import solver

    requires = op("int.le", op("int.mul", lit(2), var(0)), lit(0))
    ensures = op("int.le", op("int.mul", lit(3), Expr("result")), lit(0))
    spec, candidate = fixture(var(0), ensures, requires)
    report = verify(spec, candidate)
    assert report.status == "proved"
    assert check_certificate(spec, candidate, report.certificate)

    def forbidden_solver(*args, **kwargs):
        raise AssertionError("Certificate checker invoked untrusted search")

    monkeypatch.setattr(solver, "find_weights", forbidden_solver)
    assert check_certificate(spec, candidate, report.certificate)
    forged = copy.deepcopy(report.certificate)
    for key, coefficients in forged["obligations"].items():
        forged["obligations"][key] = [["0", "1"] for _ in coefficients]
    assert not check_certificate(spec, candidate, forged)


def test_solver_output_cannot_add_premises_or_claim_invalid_witness(monkeypatch):
    from fractions import Fraction

    from llmlang import solver

    spec, candidate = fixture(lit(0), lit(False), op("int.lt", lit(10), var(0)))
    monkeypatch.setattr(solver, "find_integers", lambda *args: (0,))
    monkeypatch.setattr(
        solver, "find_weights", lambda leaf, *args: tuple(Fraction(1) for _ in leaf.rows)
    )
    report = verify(spec, candidate)
    assert report.status == "unverified"
    assert report.domains[0].status == "domain_unknown"
    assert report.counterexample is None


def test_false_domain_evidence_and_foreign_leaf_are_rejected():
    spec, candidate = certificate_fixture()
    certificate = verify(spec, candidate).certificate
    forged = copy.deepcopy(certificate)
    forged["domains"] = {"0": {}}
    assert not check_certificate(spec, candidate, forged)
    forged = copy.deepcopy(certificate)
    key = next(iter(forged["obligations"]))
    forged["obligations"]["foreign:0"] = forged["obligations"].pop(key)
    assert not check_certificate(spec, candidate, forged)


def test_proof_integer_and_json_shape_budgets_are_enforced():
    spec, candidate = certificate_fixture()
    certificate = verify(spec, candidate).certificate
    assert not check_certificate(spec, candidate, certificate, Limits(max_certificate_bytes=10))
    for scalar in (1.0, True, "01", "+1", "-0", "NaN", "9" * 1025):
        forged = copy.deepcopy(certificate)
        key = next(iter(forged["obligations"]))
        forged["obligations"][key][0] = [scalar, "1"]
        assert not check_certificate(spec, candidate, forged)


def test_agent_hello_world_proves_with_default_branch_budget():
    from pathlib import Path

    from llmlang.parser import parse_candidate, parse_spec

    root = Path(__file__).resolve().parents[1] / "examples" / "hello"
    spec = parse_spec((root / "hello.llspec").read_text())
    candidate = parse_candidate((root / "hello.ll").read_text())
    report = verify(spec, candidate)
    assert report.status == "proved", report.to_dict()
    assert report.domains[0].status == "domain_nonempty"
    assert check_certificate(spec, candidate, report.certificate)


def test_pruning_does_not_discard_equalities_or_identical_negative_bounds():
    # x<=-1 and x<=-2 share direction and are satisfiable; adding bounds would be unsound.
    requires = op("and", op("int.le", var(0), lit(-1)), op("int.le", var(0), lit(-2)))
    spec, candidate = fixture(var(0), lit(False), requires)
    report = verify(spec, candidate)
    assert report.status == "counterexample"
    assert int(report.counterexample["inputs"][0]["value"]) <= -2
    # Opposite rows with bounds summing to zero define equality, not contradiction.
    requires = op("and", op("int.le", var(0), lit(0)), op("int.le", lit(0), var(0)))
    spec, candidate = fixture(var(0), lit(False), requires)
    report = verify(spec, candidate)
    assert report.status == "counterexample"
    assert report.counterexample["inputs"][0]["value"] == "0"
