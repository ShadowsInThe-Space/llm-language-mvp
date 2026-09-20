"""Independent structural certificate producer and checker for A1."""

from __future__ import annotations

from typing import Any

from llmlang.a1.certificate import CHECKER, RULE_SET, SCHEMA
from llmlang.a1.ir import A1IRError, module_hash, validate_module


def _producer_obligations(module: dict[str, Any]) -> dict[str, dict[str, Any]]:
    obligations: dict[str, dict[str, Any]] = {
        "O-S001-document": {
            "kind": "structural",
            "proof": {"rule": "A1-S001", "subject": "document"},
        }
    }
    for index, declaration in enumerate(module["types"]):
        rule = "A1-S006" if declaration["kind"] == "record" else "A1-S007"
        obligations[f"O-S002-type-{index}-{declaration['name']}"] = {
            "kind": "structural",
            "proof": {"rule": rule, "subject": f"types[{index}]"},
        }
    for function in sorted(module["functions"], key=lambda item: item["name"]):
        name = function["name"]
        obligations[f"O-S003-function-{name}"] = {
            "kind": "structural",
            "proof": {"rule": "A1-S003", "subject": f"function:{name}"},
        }
        for index, instruction in enumerate(function["body"]):
            rule = {
                "call": "A1-S009",
                "bounded_map": "A1-S012",
                "bounded_fold": "A1-S012",
                "refine_nat": "A1-S011",
            }.get(instruction["op"], "A1-S005")
            obligations[f"O-S004-{name}-{index}"] = {
                "kind": "structural",
                "proof": {
                    "rule": rule,
                    "subject": f"function:{name}:body[{index}]:{instruction['op']}",
                },
            }
        obligations[f"O-S005-return-{name}"] = {
            "kind": "structural",
            "proof": {"rule": "A1-S004", "subject": f"function:{name}:return"},
        }
    for index, entry in enumerate(sorted(module["entrypoints"])):
        obligations[f"O-S006-entry-{index}"] = {
            "kind": "structural",
            "proof": {"rule": "A1-S009", "subject": f"entry:{entry}"},
        }
    return obligations


def _produce_certificate(module: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "ir_hash": module_hash(module),
        "checker": CHECKER,
        "rule_set": RULE_SET,
        "limits": dict(module["limits"]),
        "obligations": _producer_obligations(module),
        "summaries": {},
        "counterexamples": [],
    }


def verify(module: dict[str, Any]) -> dict[str, Any]:
    try:
        validated = validate_module(module)
    except A1IRError as exc:
        return {"status": "invalid", "diagnostics": [exc.to_dict()]}
    return {
        "status": "proved",
        "proof_scope": "a1-structural-and-local-contracts",
        "certificate": _produce_certificate(validated),
    }


def check_certificate(module: dict[str, Any], certificate: object) -> bool:
    from llmlang.a1.certificate import check_certificate as independent_check

    return independent_check(module, certificate)
