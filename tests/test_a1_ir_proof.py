from copy import deepcopy

import pytest

from llmlang.a1 import A1Limits, check_certificate, interpret, module_hash, verify
from llmlang.a1.ir import A1IRError, validate_module


def sample_module():
    return {
        "format": "a1-ir-v1",
        "profile": "a1",
        "checker": "a1-check-v1",
        "specializations": [],
        "limits": {
            "max_steps": 10000,
            "max_collection_expansion": 1000,
            "max_call_depth": 64,
        },
        "types": [
            {
                "kind": "record",
                "name": "Customer",
                "fields": [{"name": "name", "type": {"kind": "text", "capacity": 16}}],
            },
            {
                "kind": "variant",
                "name": "Choice",
                "cases": [{"tag": "Some", "type": "Customer"}, {"tag": "None"}],
            },
        ],
        "entrypoints": ["main"],
        "functions": [
            {
                "name": "main",
                "params": [],
                "result": "Nat",
                "body": [
                    {
                        "op": "const",
                        "dest": "%0",
                        "type": {"kind": "text", "capacity": 16},
                        "value": "Grüße",
                    },
                    {
                        "op": "record_make",
                        "dest": "%1",
                        "record": "Customer",
                        "fields": {"name": {"ref": "%0"}},
                    },
                    {
                        "op": "variant_make",
                        "dest": "%2",
                        "variant": "Choice",
                        "tag": "Some",
                        "value": {"ref": "%1"},
                    },
                    {
                        "op": "match_value",
                        "dest": "%3",
                        "type": {"kind": "text", "capacity": 16},
                        "variant": "Choice",
                        "value": {"ref": "%2"},
                        "arms": {"Some": {"ref": "%0"}, "None": "none"},
                    },
                    {"op": "text_utf8_bytes", "dest": "%4", "value": {"ref": "%3"}},
                ],
                "return": "%4",
            }
        ],
    }


def test_ir_is_canonical_executable_and_certified():
    module = sample_module()
    assert len(module_hash(module)) == 64
    report = verify(module)
    assert report["status"] == "proved"
    assert check_certificate(module, report["certificate"])
    assert interpret(module, "main", []) == 7


@pytest.mark.parametrize("field", ["ir_hash", "rule_set", "obligations", "checker", "limits"])
def test_mutated_or_incomplete_evidence_is_rejected(field):
    module = sample_module()
    certificate = deepcopy(verify(module)["certificate"])
    certificate[field] = [] if isinstance(certificate[field], list) else "mutated"
    assert not check_certificate(module, certificate)


def test_non_exhaustive_match_fails_closed():
    module = sample_module()
    module["functions"][0]["body"][3]["arms"].pop("None")
    with pytest.raises(A1IRError, match="exhaustive"):
        validate_module(module)
    assert verify(module)["status"] == "invalid"


def test_collection_budget_is_separate_from_proof():
    module = {
        "format": "a1-ir-v1",
        "profile": "a1",
        "checker": "a1-check-v1",
        "specializations": [],
        "limits": {
            "max_steps": 10000,
            "max_collection_expansion": 1000,
            "max_call_depth": 64,
        },
        "types": [],
        "entrypoints": ["main"],
        "functions": [
            {
                "name": "identity",
                "params": [{"name": "x", "type": "Int"}],
                "result": "Int",
                "body": [],
                "return": "x",
            },
            {
                "name": "main",
                "params": [{"name": "items", "type": {"kind": "list", "capacity": 3}}],
                "body": [
                    {
                        "op": "bounded_map",
                        "dest": "%0",
                        "list": {"ref": "items"},
                        "callback": "identity",
                    }
                ],
                "result": {"kind": "list", "elem": "Int", "capacity": 3},
                "return": "%0",
            },
        ],
    }
    assert verify(module)["status"] == "proved"
    with pytest.raises(A1IRError, match="budget"):
        interpret(
            module,
            "main",
            [{"list": [1, 2, 3], "capacity": 3}],
            A1Limits(max_collection_expansion=2),
        )


def test_unknown_callback_and_recursive_call_fail_closed():
    module = sample_module()
    module["functions"][0]["body"].append(
        {"op": "call", "dest": "%5", "callee": "main", "args": []}
    )
    module["functions"][0]["return"] = "%5"
    assert verify(module)["diagnostics"][0]["code"] == "E_A1_CALL_CYCLE"

    module = sample_module()
    module["functions"][0]["body"].append(
        {"op": "bounded_map", "dest": "%5", "list": [], "callback": "missing"}
    )
    module["functions"][0]["return"] = "%5"
    assert verify(module)["diagnostics"][0]["code"] == "E_A1_CALLBACK_TYPE"


def test_nat_refinement_requires_explicit_checker_evidence():
    module = sample_module()
    module["functions"][0]["body"].append({"op": "refine_nat", "dest": "%5", "value": 1})
    module["functions"][0]["return"] = "%5"
    assert verify(module)["diagnostics"][0]["code"] == "E_A1_REFINEMENT"
    module["functions"][0]["body"][-1]["evidence"] = {
        "predicate": ">=0",
        "rule": "A1-C004",
    }
    assert verify(module)["status"] == "proved"


def test_proof_path_rejects_wrong_literal_field_and_unbound_operand_types():
    module = sample_module()
    module["functions"][0]["body"][0] = {
        "op": "const",
        "dest": "%0",
        "type": "Bool",
        "value": "not-a-bool",
    }
    assert verify(module)["diagnostics"][0]["code"] == "E_A1_TYPE"

    module = sample_module()
    module["functions"][0]["body"][1]["fields"]["name"] = {"ref": "%missing"}
    assert verify(module)["diagnostics"][0]["code"] == "E_A1_BINDING"

    module = sample_module()
    module["functions"][0]["body"].append(
        {"op": "add", "dest": "%5", "left": {"ref": "%missing"}, "right": 1}
    )
    module["functions"][0]["return"] = "%5"
    module["functions"][0]["result"] = "Int"
    assert verify(module)["diagnostics"][0]["code"] == "E_A1_BINDING"
