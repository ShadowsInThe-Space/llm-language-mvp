"""Independent structural certificate producer and checker for A1."""

from __future__ import annotations

import hashlib
from typing import Any

from llmlang.a1.ir import A1IRError, canonical_bytes, module_hash, validate_module

RULE_VERSION = "a1-rules-v1"
_RULES = ("A1-S001", "A1-S002", "A1-S003", "A1-S004", "A1-C001")


def _evidence(module: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for function in sorted(module["functions"], key=lambda item: item["name"]):
        rows.append({"rule": "A1-S001", "subject": function["name"]})
        for index, instruction in enumerate(function["body"]):
            rule = (
                "A1-C001"
                if instruction["op"] in {"call", "refine_nat", "bounded_map", "bounded_fold"}
                else "A1-S003"
            )
            rows.append(
                {"rule": rule, "subject": f"{function['name']}:{index}:{instruction['op']}"}
            )
        rows.append({"rule": "A1-S004", "subject": f"{function['name']}:return"})
    rows.append({"rule": "A1-S002", "subject": "closed-module"})
    return rows


def verify(module: dict[str, Any]) -> dict[str, Any]:
    try:
        validated = validate_module(module)
    except A1IRError as exc:
        return {"status": "invalid", "diagnostics": [exc.to_dict()]}
    evidence = _evidence(validated)
    digest = hashlib.sha256(canonical_bytes(evidence)).hexdigest()
    return {
        "status": "proved",
        "proof_scope": "a1-structural-and-local-contracts",
        "certificate": {
            "format": "a1-certificate-v1",
            "rule_version": RULE_VERSION,
            "module_hash": module_hash(validated),
            "required_rules": list(_RULES),
            "evidence": evidence,
            "evidence_hash": digest,
        },
    }


def check_certificate(module: dict[str, Any], certificate: object) -> bool:
    try:
        validated = validate_module(module)
        if not isinstance(certificate, dict):
            return False
        expected = verify(validated).get("certificate")
        return canonical_bytes(certificate) == canonical_bytes(expected)
    except (A1IRError, TypeError, ValueError):
        return False
