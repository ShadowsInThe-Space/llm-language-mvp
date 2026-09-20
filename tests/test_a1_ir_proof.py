from copy import deepcopy

import pytest

from llmlang.a1 import A1Limits, check_certificate, interpret, module_hash, verify
from llmlang.a1.ir import A1IRError, validate_module


def sample_module():
    return {
        "format": "a1-ir-v1",
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
        "entries": ["main"],
        "functions": [
            {
                "name": "main",
                "params": [],
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


@pytest.mark.parametrize(
    "field", ["module_hash", "rule_version", "evidence", "evidence_hash", "required_rules"]
)
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
        "types": [],
        "entries": ["main"],
        "functions": [
            {
                "name": "identity",
                "params": [{"name": "x", "type": "Int"}],
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
