"""Independent cert-v0 proof checking and conservative verification orchestration.

The checker never imports or calls a solver. It reconstructs all obligations from
trusted frozen inputs, accepts exact nonnegative Farkas combinations only, and
requires complete leaf coverage. The Python implementation is part of the TCB.
"""

import json
import re
from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
from math import gcd
from typing import Literal

from .core import evaluate, evaluate_contract, validate
from .model import (
    CHECKER_VERSION,
    PROFILE,
    Candidate,
    LanguageError,
    Limits,
    Program,
    Specification,
    Value,
    encode_value,
)
from .parser import canonical_candidate, canonical_spec
from .symbolic import Leaf, instantiate, reconstruct

VerificationStatus = Literal["invalid", "unverified", "counterexample", "proved"]
DomainStatus = Literal["domain_nonempty", "contract_empty", "domain_unknown"]
DEFAULT_LIMITS = Limits()


@dataclass(frozen=True, slots=True)
class DomainResult:
    status: DomainStatus
    witness: tuple[Value, ...] | None = None
    certificate: dict[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "witness": None if self.witness is None else [encode_value(v) for v in self.witness],
            "certificate": self.certificate,
        }


@dataclass(frozen=True, slots=True)
class VerificationReport:
    status: VerificationStatus
    domains: tuple[DomainResult, ...]
    certificate: dict[str, object] | None = None
    counterexample: dict[str, object] | None = None
    diagnostics: tuple[dict[str, object], ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "domains": [d.to_dict() for d in self.domains],
            "certificate": self.certificate,
            "counterexample": self.counterexample,
            "diagnostics": list(self.diagnostics),
        }


def _digest(domain: str, payload: str) -> str:
    digest = sha256()
    for field in (domain, PROFILE, CHECKER_VERSION, payload):
        data = field.encode("utf-8")
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def baseline_hash(spec: Specification) -> str:
    return _digest("llmlang:baseline", canonical_spec(spec))


def candidate_hash(candidate: Candidate) -> str:
    return _digest("llmlang:candidate", canonical_candidate(candidate))


def _header(spec: Specification, candidate: Candidate) -> dict[str, object]:
    return {
        "checker": CHECKER_VERSION,
        "baseline_hash": baseline_hash(spec),
        "candidate_hash": candidate_hash(candidate),
    }


class _CertificateBudget:
    def __init__(self, limits: Limits) -> None:
        self.limits = limits
        self.steps = 0
        self.bytes = 0

    def tick(self, steps: int = 1, size: int = 0) -> None:
        self.steps += steps
        self.bytes += size
        if self.steps > self.limits.max_steps or self.bytes > self.limits.max_certificate_bytes:
            raise LanguageError("E_RESOURCE", "Certificate work/size budget exhausted")

    def bounded(self, value: Fraction) -> Fraction:
        if (
            abs(value.numerator).bit_length() > self.limits.max_coefficient_bits
            or value.denominator.bit_length() > self.limits.max_coefficient_bits
        ):
            raise LanguageError("E_RESOURCE", "Certificate arithmetic budget exhausted")
        return value

    def rational(self, item: object) -> Fraction:
        self.tick()
        if type(item) is not list or len(item) != 2:
            raise ValueError("Expected a canonical rational pair")
        numerator, denominator = item
        if type(numerator) is not str or type(denominator) is not str:
            raise ValueError("Certificate coefficients must be integer strings")
        self.tick(size=len(numerator) + len(denominator) + 7)
        if (
            len(numerator) > self.limits.max_int_digits
            or len(denominator) > self.limits.max_int_digits
        ):
            raise ValueError("Certificate integer digit limit")
        if not re.fullmatch(r"0|[1-9][0-9]*", numerator):
            raise ValueError("Nonnegative canonical numerator required")
        if not re.fullmatch(r"[1-9][0-9]*", denominator):
            raise ValueError("Positive canonical denominator required")
        n, d = int(numerator), int(denominator)
        if gcd(n, d) != 1:
            raise ValueError("Unreduced certificate fraction")
        return self.bounded(Fraction(n, d))


def _check_leaf(leaf: Leaf, encoded: object, budget: _CertificateBudget) -> bool:
    if type(encoded) is not list or len(encoded) != len(leaf.rows):
        return False
    dimensions = len(leaf.rows[0].coefficients) if leaf.rows else 0
    total = [Fraction(0) for _ in range(dimensions)]
    bound = Fraction(0)
    for row, pair in zip(leaf.rows, encoded, strict=True):
        weight = budget.rational(pair)
        for column, coefficient in enumerate(row.coefficients):
            budget.tick()
            total[column] = budget.bounded(total[column] + budget.bounded(weight * coefficient))
        bound = budget.bounded(bound + budget.bounded(weight * row.bound))
    return not any(total) and bound < 0


def _check_leaves(leaves: tuple[Leaf, ...], evidence: object, budget: _CertificateBudget) -> bool:
    if type(evidence) is not dict or set(evidence) != {leaf.identifier for leaf in leaves}:
        return False
    for leaf in leaves:
        budget.tick(size=len(leaf.identifier) + 4)
        if not _check_leaf(leaf, evidence[leaf.identifier], budget):
            return False
    return True


def check_certificate(
    spec: Specification,
    candidate: Candidate,
    certificate: dict[str, object],
    limits: Limits = DEFAULT_LIMITS,
) -> bool:
    """Return True only for a complete, bound, independently reconstructed proof."""
    try:
        program = validate(spec, candidate, limits)
        if type(certificate) is not dict or set(certificate) != {
            "checker",
            "baseline_hash",
            "candidate_hash",
            "obligations",
            "domains",
        }:
            return False
        if any(certificate[key] != value for key, value in _header(spec, candidate).items()):
            return False
        obligations = reconstruct(program, limits)
        budget = _CertificateBudget(limits)
        budget.tick(size=300)
        if not _check_leaves(obligations.leaves, certificate["obligations"], budget):
            return False
        domains = certificate["domains"]
        if type(domains) is not dict:
            return False
        if not set(domains).issubset({str(i) for i in range(len(spec.functions))}):
            return False
        for index, proofs in domains.items():
            if not _check_leaves(obligations.domains[int(index)], proofs, budget):
                return False
        # Exact serialized-size check after bounded structural/scalar validation.
        return len(json.dumps(certificate, separators=(",", ":")).encode()) <= (
            limits.max_certificate_bytes
        )
    except (
        LanguageError,
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        OverflowError,
        RecursionError,
    ):
        return False


def _encode_weights(weights: tuple[Fraction, ...]) -> list[list[str]]:
    return [[str(value.numerator), str(value.denominator)] for value in weights]


def _valid_witness(program: Program, entry: int, values: tuple[Value, ...], limits: Limits) -> bool:
    spec = program.spec.functions[entry]
    if len(values) != len(spec.params):
        return False
    if any(
        type(value) is not (int if typ == "Int" else bool)
        for value, typ in zip(values, spec.params, strict=True)
    ):
        return False
    try:
        return evaluate_contract(spec.requires, values, limits=limits) is True
    except LanguageError:
        return False


def _counterexample(
    program: Program, leaf: Leaf, values: tuple[Value, ...], limits: Limits
) -> dict[str, object] | None:
    if not _valid_witness(program, leaf.entry, values, limits):
        return None
    base: dict[str, object] = {
        "entry": leaf.entry,
        "obligation_id": leaf.identifier,
        "baseline_hash": baseline_hash(program.spec),
        "candidate_hash": candidate_hash(program.candidate),
        "inputs": [encode_value(v) for v in values],
    }
    try:
        result = evaluate(program, values, entry=leaf.entry, limits=limits)
    except LanguageError as error:
        if error.code == "E_PRECONDITION":
            return {**base, "kind": "call_precondition", "diagnostic": error.to_dict()}
        return None
    try:
        ensures = program.spec.functions[leaf.entry].ensures
        if evaluate_contract(ensures, values, result=result, limits=limits) is False:
            return {**base, "kind": "postcondition", "result": encode_value(result)}
    except LanguageError:
        return None
    return None


def verify(
    spec: Specification, candidate: Candidate, limits: Limits = DEFAULT_LIMITS
) -> VerificationReport:
    """Search is advisory. Failed or missing evidence never becomes `proved`."""
    unknown = tuple(DomainResult("domain_unknown") for _ in spec.functions)
    try:
        program = validate(spec, candidate, limits)
    except LanguageError as error:
        status: VerificationStatus = (
            "unverified" if error.code in ("E_RESOURCE", "E_LIMIT") else "invalid"
        )
        return VerificationReport(status, unknown, diagnostics=(error.to_dict(),))
    try:
        obligations = reconstruct(program, limits)
    except LanguageError as error:
        return VerificationReport("unverified", unknown, diagnostics=(error.to_dict(),))

    # Local import keeps the independent checker's implementation free of solver calls.
    from .solver import SearchBudget, find_integers, find_weights

    search = SearchBudget.start(limits)
    domain_results: list[DomainResult] = []
    domain_proofs: dict[str, object] = {}
    proofs: dict[str, object] = {}
    counterexample: dict[str, object] | None = None
    diagnostic: dict[str, object] | None = None
    try:
        for entry, leaves in enumerate(obligations.domains):
            witness: tuple[Value, ...] | None = None
            empty_proofs: dict[str, object] = {}
            for leaf in leaves:
                integers = find_integers(leaf, limits, search)
                if integers is not None:
                    values = instantiate(leaf, integers)
                    if _valid_witness(program, entry, values, limits):
                        witness = values
                        break
                weights = find_weights(leaf, limits, search)
                if weights is not None:
                    empty_proofs[leaf.identifier] = _encode_weights(weights)
            if witness is not None:
                domain_results.append(DomainResult("domain_nonempty", witness))
            elif _check_leaves(leaves, empty_proofs, _CertificateBudget(limits)):
                domain_proofs[str(entry)] = empty_proofs
                domain_results.append(
                    DomainResult(
                        "contract_empty",
                        certificate={
                            **_header(spec, candidate),
                            "entry": entry,
                            "leaves": empty_proofs,
                        },
                    )
                )
            else:
                domain_results.append(DomainResult("domain_unknown"))
        for leaf in obligations.leaves:
            weights = find_weights(leaf, limits, search)
            if weights is not None:
                encoded = _encode_weights(weights)
                if _check_leaf(leaf, encoded, _CertificateBudget(limits)):
                    proofs[leaf.identifier] = encoded
                    continue
            integers = find_integers(leaf, limits, search)
            if integers is not None:
                values = instantiate(leaf, integers)
                counterexample = _counterexample(program, leaf, values, limits)
                if counterexample is not None:
                    break
    except Exception as error:
        # Solver crashes/malformed output are untrusted failures, never semantic evidence.
        diagnostic = {
            "code": "E_SEARCH",
            "message": f"Proof search unavailable: {type(error).__name__}",
        }
    while len(domain_results) < len(spec.functions):
        domain_results.append(DomainResult("domain_unknown"))
    domains = tuple(domain_results)
    if counterexample is not None:
        return VerificationReport("counterexample", domains, counterexample=counterexample)
    certificate = {**_header(spec, candidate), "obligations": proofs, "domains": domain_proofs}
    if diagnostic is None and check_certificate(spec, candidate, certificate, limits):
        return VerificationReport("proved", domains, certificate=certificate)
    if diagnostic is None:
        diagnostic = {
            "code": "E_UNPROVED",
            "message": "Missing independently checked proof evidence",
        }
    return VerificationReport("unverified", domains, diagnostics=(diagnostic,))
