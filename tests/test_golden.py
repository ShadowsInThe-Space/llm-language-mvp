"""End-to-end acceptance and rejection for the ten frozen P0 tasks."""

import json
from pathlib import Path

import pytest

from llmlang.core import evaluate, evaluate_contract, validate
from llmlang.model import Candidate, Expr, Value
from llmlang.parser import parse_candidate, parse_spec
from llmlang.proof import check_certificate, verify

GOLDEN = Path(__file__).resolve().parents[1] / "examples" / "golden"
TASKS = (
    "identity",
    "minimum",
    "maximum",
    "abs",
    "clamp",
    "nonnegative_difference",
    "overlap_length",
    "grant",
    "tiered_fee",
    "access_rule",
)


def decode(value: dict[str, object]) -> Value:
    """Fixtures transport integers exactly, without binary64 JSON numbers."""
    if value["type"] == "Int":
        assert isinstance(value["value"], str)
        return int(value["value"])
    assert value["type"] == "Bool"
    assert type(value["value"]) is bool
    return value["value"]


@pytest.mark.parametrize("task", TASKS)
def test_golden_program_proved_and_independently_executed(task: str) -> None:
    spec = parse_spec((GOLDEN / f"{task}.llspec").read_text())
    candidate = parse_candidate((GOLDEN / f"{task}.ll").read_text())
    fixture = json.loads((GOLDEN / f"{task}.json").read_text())
    entry = fixture["entry"]
    report = verify(spec, candidate)

    assert report.status == "proved", report.to_dict()
    assert report.certificate is not None
    assert check_certificate(spec, candidate, report.certificate)
    assert all(domain.status == "domain_nonempty" for domain in report.domains)
    witness = tuple(decode(value) for value in fixture["witness"])
    assert evaluate_contract(spec.functions[entry].requires, witness) is True

    program = validate(spec, candidate)
    for sample in fixture["samples"]:
        inputs = tuple(decode(value) for value in sample["inputs"])
        expected = decode(sample["expected"])
        actual = evaluate(program, inputs, entry=entry)
        assert type(actual) is type(expected)
        assert actual == expected


@pytest.mark.parametrize("task", ("identity", "minimum", "grant", "access_rule"))
def test_golden_contract_rejects_wrong_body_with_replayable_counterexample(task: str) -> None:
    spec = parse_spec((GOLDEN / f"{task}.llspec").read_text())
    good = parse_candidate((GOLDEN / f"{task}.ll").read_text())
    entry = len(spec.functions) - 1
    literal = Expr("bool", value=False) if task == "access_rule" else Expr("int", value=-1)
    bad = Candidate(good.bodies[:entry] + (literal,))

    report = verify(spec, bad)

    assert report.status == "counterexample", report.to_dict()
    assert report.certificate is None
    assert report.counterexample is not None
    counterexample = report.counterexample
    assert counterexample["entry"] == entry
    assert counterexample["kind"] == "postcondition"
    inputs = tuple(decode(value) for value in counterexample["inputs"])
    function = spec.functions[entry]
    assert evaluate_contract(function.requires, inputs) is True
    actual = evaluate(validate(spec, bad), inputs, entry=entry)
    assert evaluate_contract(function.ensures, inputs, result=actual) is False


def test_golden_corpus_has_ten_named_tasks() -> None:
    assert {path.stem for path in GOLDEN.glob("*.llspec")} == set(TASKS)
    assert {path.stem for path in GOLDEN.glob("*.ll")} == set(TASKS)
    assert {path.stem for path in GOLDEN.glob("*.json")} == set(TASKS)
