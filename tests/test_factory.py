"""Synthesis accepts independent evidence, never provider status or changed contracts."""

from dataclasses import replace
from typing import Any

import pytest

from llmlang import factory
from llmlang.adapters import FileCandidates
from llmlang.core import evaluate, validate
from llmlang.model import LanguageError, Limits
from llmlang.parser import canonical_spec, parse_spec

SPEC_SOURCE = (
    "(spec p0 (fn (params Int Int) (result Int) "
    "(requires (and (int.le 0 (var 1)) (int.le 0 (var 0)))) "
    "(ensures (int.eq result (if (int.le (var 1) (var 0)) (var 1) (var 0))))))"
)
WRONG = "(candidate p0 (body (var 1)))"
CORRECT = "(candidate p0 (body (if (int.le (var 1) (var 0)) (var 1) (var 0))))"


def test_factory_repairs_wrong_candidate_with_validated_feedback() -> None:
    requests: list[dict[str, object]] = []
    sources = iter([WRONG, CORRECT])

    class Provider:
        def generate(self, request: dict[str, object]) -> str:
            requests.append(request)
            return next(sources)

    spec = parse_spec(SPEC_SOURCE)
    result = factory.run_factory(spec, Provider())
    assert result.status == "proved"
    assert result.candidate is not None
    assert evaluate(validate(spec, result.candidate), (12, 4)) == 4
    assert len(result.attempts) == 2
    assert result.attempts[0].status == "counterexample"
    assert requests[0]["specification"] == requests[1]["specification"] == canonical_spec(spec)
    assert requests[0]["baseline_hash"] == requests[1]["baseline_hash"]
    feedback = requests[1]["feedback"]
    assert isinstance(feedback, dict) and feedback["status"] == "counterexample"
    assert feedback["counterexample"] is not None
    assert requests[1]["previous_candidate"] == WRONG
    assert result.to_dict()["status"] == "proved"


@pytest.mark.parametrize("source", [SPEC_SOURCE, '{"status":"proved"}', CORRECT + SPEC_SOURCE])
def test_factory_does_not_accept_candidate_contract_replacements(source: str) -> None:
    result = factory.run_factory(parse_spec(SPEC_SOURCE), FileCandidates([source]))
    assert result.status != "proved"
    assert result.attempts[0].status == "invalid"


def test_factory_cannot_skip_independent_certificate_check(monkeypatch: pytest.MonkeyPatch) -> None:
    checks: list[object] = []

    def reject(*args: Any, **kwargs: Any) -> bool:
        checks.append(args)
        return False

    monkeypatch.setattr(factory, "check_certificate", reject)
    result = factory.run_factory(
        parse_spec(SPEC_SOURCE), FileCandidates([CORRECT]), Limits(max_attempts=1)
    )
    assert checks
    assert result.status != "proved"
    assert result.attempts[0].feedback["code"] == "E_CERTIFICATE"


def test_factory_provider_cannot_mutate_the_frozen_request_or_audit() -> None:
    requests: list[dict[str, object]] = []

    class TamperingProvider:
        def generate(self, request: dict[str, object]) -> str:
            requests.append(dict(request))
            request["specification"] = "(spec p0)"
            request["baseline_hash"] = "fake"
            feedback = request["feedback"]
            if isinstance(feedback, dict):
                feedback["status"] = "proved"
            return WRONG if len(requests) == 1 else CORRECT

    result = factory.run_factory(parse_spec(SPEC_SOURCE), TamperingProvider())
    assert result.status == "proved"
    assert (
        requests[0]["specification"]
        == requests[1]["specification"]
        == canonical_spec(parse_spec(SPEC_SOURCE))
    )
    assert result.attempts[0].feedback["status"] == "counterexample"
    assert result.baseline_hash != "fake"


def test_factory_attempt_budget_is_at_most_three() -> None:
    count = 0

    class NeverValid:
        def generate(self, request: dict[str, object]) -> str:
            nonlocal count
            count += 1
            return "malformed"

    result = factory.run_factory(parse_spec(SPEC_SOURCE), NeverValid(), Limits(max_attempts=200))
    assert count == 3
    assert len(result.attempts) == 3
    assert result.status == "exhausted"


def test_factory_time_budget_cannot_accept_a_late_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = [0.0]
    monkeypatch.setattr(factory.time, "monotonic", lambda: now[0])

    class TooLate:
        def generate(self, request: dict[str, object]) -> str:
            now[0] = 1.0
            return CORRECT

    result = factory.run_factory(
        parse_spec(SPEC_SOURCE), TooLate(), replace(Limits(), factory_timeout_ms=10)
    )
    assert result.status == "exhausted"
    assert result.verification is None
    assert result.attempts[0].feedback["code"] == "E_FACTORY_TIMEOUT"


@pytest.mark.parametrize(
    "exception",
    [
        RuntimeError("API-KEY-SECRET"),
        LanguageError("E_PROVIDER_TIMEOUT", "API-KEY-SECRET"),
    ],
)
def test_factory_sanitizes_arbitrary_provider_exceptions(exception: Exception) -> None:
    class BrokenProvider:
        def generate(self, request: dict[str, object]) -> str:
            raise exception

    result = factory.run_factory(parse_spec(SPEC_SOURCE), BrokenProvider(), Limits(max_attempts=1))
    assert result.status != "proved"
    assert "API-KEY-SECRET" not in str(result.to_dict())
    assert result.attempts[0].feedback["code"] == "E_PROVIDER"


def test_factory_rejects_nontext_model_output() -> None:
    class InvalidProvider:
        def generate(self, request: dict[str, object]) -> Any:
            return {"status": "proved", "candidate": CORRECT}

    result = factory.run_factory(parse_spec(SPEC_SOURCE), InvalidProvider(), Limits(max_attempts=1))
    assert result.status != "proved"
    assert result.attempts[0].feedback["code"] == "E_PROVIDER_RESPONSE"
