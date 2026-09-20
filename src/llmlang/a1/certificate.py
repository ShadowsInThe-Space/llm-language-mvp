"""Independent A1 certificate construction and fail-closed checking.

The checker in this module intentionally does not call :mod:`llmlang.a1.proof`.
It validates the IR, reconstructs its own obligation list, and binds every
accepted certificate to a framed A1 hash.  This is a separate trust boundary,
not a wrapper around a producer's claimed status.
"""

from __future__ import annotations

import json
from typing import Any

from llmlang.a1.ir import A1IRError, module_hash, validate_module

CHECKER = "a1-check-v1"
RULE_SET = "a1-rules-v1"
SCHEMA = "a1-evidence-v1"
IR_FORMAT = "a1-ir-v1"
PROFILE = "a1"


def canonical_json(value: object) -> bytes:
    """Encode the A1 canonical payload without host-dependent formatting."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def framed_module_hash(
    module: dict[str, Any],
    *,
    format: str = IR_FORMAT,
    profile: str = PROFILE,
    checker: str = CHECKER,
) -> str:
    """Hash format/profile/checker and canonical payload under one domain."""
    if (
        module.get("format") != format
        or module.get("profile") != profile
        or module.get("checker") != checker
    ):
        raise ValueError("module versions do not match hash frame")
    return module_hash(module)


def _obligation(rule: str, subject: str, *, kind: str = "structural") -> dict[str, Any]:
    return {"kind": kind, "proof": {"rule": rule, "subject": subject}}


def _expected_obligations(module: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Reconstruct all obligations from the validated IR, never from evidence."""
    obligations: dict[str, dict[str, Any]] = {
        "O-S001-document": _obligation("A1-S001", "document"),
    }
    for index, declaration in enumerate(module["types"]):
        name = str(declaration["name"])
        rule = "A1-S006" if declaration["kind"] == "record" else "A1-S007"
        obligations[f"O-S002-type-{index}-{name}"] = _obligation(rule, f"types[{index}]")
    functions = sorted(module["functions"], key=lambda item: str(item["name"]))
    for function in functions:
        name = str(function["name"])
        obligations[f"O-S003-function-{name}"] = _obligation("A1-S003", f"function:{name}")
        for index, instruction in enumerate(function["body"]):
            op = str(instruction["op"])
            rule = {
                "call": "A1-S009",
                "bounded_map": "A1-S012",
                "bounded_fold": "A1-S012",
                "refine_nat": "A1-S011",
            }.get(op, "A1-S005")
            subject = f"function:{name}:body[{index}]:{op}"
            obligations[f"O-S004-{name}-{index}"] = _obligation(rule, subject)
        obligations[f"O-S005-return-{name}"] = _obligation("A1-S004", f"function:{name}:return")
    for index, entry in enumerate(sorted(module["entrypoints"])):
        obligations[f"O-S006-entry-{index}"] = _obligation("A1-S009", f"entry:{entry}")
    return obligations


def make_certificate(module: dict[str, Any]) -> dict[str, Any]:
    """Create a certificate using the same independently reconstructible shape."""
    validated = validate_module(module)
    return {
        "schema": SCHEMA,
        "ir_hash": framed_module_hash(validated),
        "checker": CHECKER,
        "rule_set": RULE_SET,
        "limits": dict(validated["limits"]),
        "obligations": _expected_obligations(validated),
        "summaries": {},
        "counterexamples": [],
    }


certificate_for = make_certificate


def check_certificate(module: dict[str, Any], certificate: object) -> bool:
    """Independently validate an A1 evidence document; reject every mutation."""
    try:
        validated = validate_module(module)
        if not isinstance(certificate, dict):
            return False
        required = {
            "schema",
            "ir_hash",
            "checker",
            "rule_set",
            "limits",
            "obligations",
            "summaries",
            "counterexamples",
        }
        if set(certificate) != required:
            return False
        if certificate["schema"] != SCHEMA or certificate["checker"] != CHECKER:
            return False
        if certificate["rule_set"] != RULE_SET:
            return False
        if certificate["ir_hash"] != framed_module_hash(validated):
            return False
        if certificate["limits"] != validated["limits"]:
            return False
        if certificate["obligations"] != _expected_obligations(validated):
            return False
        if certificate["summaries"] != {} or certificate["counterexamples"] != []:
            return False
        canonical_json(certificate)
        return True
    except (A1IRError, TypeError, ValueError, OverflowError):
        return False


__all__ = [
    "CHECKER",
    "IR_FORMAT",
    "PROFILE",
    "RULE_SET",
    "SCHEMA",
    "canonical_json",
    "certificate_for",
    "check_certificate",
    "framed_module_hash",
    "make_certificate",
]
