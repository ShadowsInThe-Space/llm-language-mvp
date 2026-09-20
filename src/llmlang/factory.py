"""Bounded synthesis against an immutable contract and independent acceptance gate."""

import hashlib
import time
from copy import deepcopy
from dataclasses import dataclass, field

from .adapters import CandidateProvider, ProviderError
from .core import validate
from .diagnostics import diagnostic, diagnostic_document
from .model import CHECKER_VERSION, Candidate, Expr, LanguageError, Limits, Specification
from .parser import canonical_candidate, canonical_spec, parse_candidate, parse_spec
from .proof import VerificationReport, baseline_hash, check_certificate, verify

DEFAULT_LIMITS = Limits()


@dataclass(frozen=True, slots=True)
class FactoryAttempt:
    attempt: int
    status: str
    source_hash: str | None
    elapsed_ms: int
    feedback: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "attempt": self.attempt,
            "status": self.status,
            "source_hash": self.source_hash,
            "elapsed_ms": self.elapsed_ms,
            "feedback": diagnostic_document(deepcopy(self.feedback)),
        }


@dataclass(frozen=True, slots=True)
class FactoryResult:
    status: str
    baseline_hash: str | None
    candidate: Candidate | None = None
    verification: VerificationReport | None = None
    attempts: tuple[FactoryAttempt, ...] = ()
    reason: dict[str, object] | None = field(default=None)

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "baseline_hash": self.baseline_hash,
            "checker": CHECKER_VERSION,
            "candidate_source": canonical_candidate(self.candidate) if self.candidate else None,
            "verification": self.verification.to_dict() if self.verification else None,
            "attempts": [attempt.to_dict() for attempt in self.attempts],
            "reason": diagnostic_document(deepcopy(self.reason)),
        }


def _error(code: str, message: str, *, status: str = "unverified") -> dict[str, object]:
    return diagnostic({"status": status, "code": code, "message": message})


def _report_feedback(report: VerificationReport) -> dict[str, object]:
    # Certificates are acceptance artifacts, not instructions for the candidate generator.
    return {key: value for key, value in report.to_dict().items() if key != "certificate"}


def _generate(provider: CandidateProvider, request: dict[str, object]) -> str:
    try:
        return provider.generate(request)
    except ProviderError:
        raise
    except Exception:
        # A provider must not impersonate a trusted parser/checker LanguageError.
        raise ProviderError("E_PROVIDER", "Candidate provider failed") from None


def _freeze_spec(spec: Specification, limits: Limits) -> tuple[Specification, str, str]:
    if type(spec) is not Specification or type(spec.functions) is not tuple:
        raise LanguageError("E_TYPE", "Expected immutable specification")
    dummy = Candidate(
        tuple(
            Expr("bool", value=False) if fn.returns == "Bool" else Expr("int", value=0)
            for fn in spec.functions
        )
    )
    validate(spec, dummy, limits)
    source = canonical_spec(spec)
    frozen = parse_spec(source, limits)
    return frozen, source, baseline_hash(frozen)


def run_factory(
    spec: Specification, provider: CandidateProvider, limits: Limits = DEFAULT_LIMITS
) -> FactoryResult:
    """Generate, validate, verify and independently recheck at most three candidates.

    The deadline is checked before/after every synchronous stage. Arbitrary Python
    providers belong to the trusted host and cannot be forcibly interrupted here;
    the network adapter separately bounds its socket operations and response size.
    """
    if (
        type(limits.max_attempts) is not int
        or limits.max_attempts <= 0
        or type(limits.factory_timeout_ms) is not int
        or limits.factory_timeout_ms <= 0
    ):
        return FactoryResult("invalid", None, reason=_error("E_LIMIT", "Invalid factory budget"))
    started = time.monotonic()
    deadline = started + limits.factory_timeout_ms / 1000
    try:
        frozen, spec_source, bound_hash = _freeze_spec(spec, limits)
    except LanguageError as exc:
        return FactoryResult("invalid", None, reason=exc.to_dict())
    except Exception:
        return FactoryResult("invalid", None, reason=_error("E_SPEC", "Malformed specification"))

    attempts: list[FactoryAttempt] = []
    last_candidate: Candidate | None = None
    last_report: VerificationReport | None = None
    previous_source: str | None = None
    feedback: dict[str, object] | None = None
    reason = _error("E_FACTORY_ATTEMPTS", "Candidate attempt budget exhausted")

    for index in range(1, min(limits.max_attempts, 3) + 1):
        if time.monotonic() >= deadline:
            reason = _error("E_FACTORY_TIMEOUT", "Factory time budget exhausted")
            break
        attempt_started = time.monotonic()
        source_hash: str | None = None
        accepted = False
        terminate = False
        request: dict[str, object] = {
            "profile": frozen.profile,
            "checker": CHECKER_VERSION,
            "specification": spec_source,
            "baseline_hash": bound_hash,
            "attempt": index,
            "max_attempts": min(limits.max_attempts, 3),
            "previous_candidate": previous_source,
            "feedback": deepcopy(feedback),
        }
        try:
            source = _generate(provider, request)
            if time.monotonic() >= deadline:
                raise LanguageError("E_FACTORY_TIMEOUT", "Factory time budget exhausted")
            if type(source) is not str:
                raise LanguageError("E_PROVIDER_RESPONSE", "Candidate response must be source text")
            if (
                len(source) > limits.max_source_bytes
                or len(source.encode("utf-8")) > limits.max_source_bytes
            ):
                raise LanguageError("E_PROVIDER_SIZE", "Candidate source exceeds byte limit")
            previous_source = source
            source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
            candidate = parse_candidate(source, limits)
            validate(frozen, candidate, limits)
            last_candidate = candidate
            if time.monotonic() >= deadline:
                raise LanguageError("E_FACTORY_TIMEOUT", "Factory time budget exhausted")
            report = verify(frozen, candidate, limits)
            last_report = report
            feedback = _report_feedback(report)
            if time.monotonic() >= deadline:
                last_report = None
                raise LanguageError("E_FACTORY_TIMEOUT", "Factory time budget exhausted")
            if report.status == "proved":
                if report.certificate is None or not check_certificate(
                    frozen, candidate, report.certificate, limits
                ):
                    last_report = None
                    feedback = _error(
                        "E_CERTIFICATE", "Independent certificate check rejected acceptance"
                    )
                elif time.monotonic() >= deadline:
                    last_report = None
                    raise LanguageError("E_FACTORY_TIMEOUT", "Factory time budget exhausted")
                else:
                    accepted = True
        except ProviderError as exc:
            # Even a provider subclass can construct an exception containing secrets.
            allowed_codes = {
                "E_PROVIDER_EXHAUSTED",
                "E_PROVIDER_SIZE",
                "E_PROVIDER_RESPONSE",
                "E_PROVIDER_READ",
                "E_PROVIDER_CONFIG",
                "E_PROVIDER_REQUEST",
                "E_PROVIDER_TIMEOUT",
                "E_PROVIDER_HTTP",
                "E_PROVIDER_NETWORK",
            }
            code = exc.code if exc.code in allowed_codes else "E_PROVIDER"
            feedback = _error(code, "Candidate provider did not return a usable response")
            terminate = code == "E_PROVIDER_EXHAUSTED"
            if terminate:
                reason = feedback
        except LanguageError as exc:
            status = "unverified" if exc.code == "E_FACTORY_TIMEOUT" else "invalid"
            feedback = {"status": status, **exc.to_dict()}
            terminate = exc.code == "E_FACTORY_TIMEOUT"
            if terminate:
                reason = feedback
        except Exception:
            feedback = _error("E_PROVIDER", "Candidate generation or verification failed")
            last_report = None

        assert feedback is not None
        attempts.append(
            FactoryAttempt(
                attempt=index,
                status=str(feedback["status"]),
                source_hash=source_hash,
                elapsed_ms=max(0, int((time.monotonic() - attempt_started) * 1000)),
                feedback=deepcopy(feedback),
            )
        )
        if accepted:
            return FactoryResult("proved", bound_hash, last_candidate, last_report, tuple(attempts))
        if terminate:
            break

    return FactoryResult(
        "exhausted", bound_hash, last_candidate, last_report, tuple(attempts), reason
    )
