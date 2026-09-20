from copy import deepcopy

import pytest

from llmlang.a1.certificate import (
    CHECKER,
    RULE_SET,
    certificate_for,
    check_certificate,
    framed_module_hash,
)


def module() -> dict[str, object]:
    return {
        "format": "a1-ir-v1",
        "types": [],
        "profile": "a1",
        "checker": "a1-check-v1",
        "entrypoints": ["main"],
        "specializations": [],
        "limits": {
            "max_call_depth": 256,
            "max_collection_expansion": 100_000,
            "max_steps": 1_000_000,
        },
        "functions": [
            {
                "name": "main",
                "params": [],
                "result": "Int",
                "body": [{"op": "const", "dest": "%0", "type": "Int", "value": 3}],
                "return": "%0",
            }
        ],
    }


def test_certificate_roundtrip_uses_framed_hash_and_exact_versions():
    ir = module()
    certificate = certificate_for(ir)
    assert check_certificate(ir, certificate)
    assert certificate["checker"] == CHECKER
    assert certificate["rule_set"] == RULE_SET
    assert certificate["ir_hash"] == framed_module_hash(ir)


@pytest.mark.parametrize(
    "field", ["schema", "checker", "rule_set", "ir_hash", "limits", "obligations"]
)
def test_mutating_version_hash_or_evidence_fails_closed(field: str):
    ir = module()
    certificate = deepcopy(certificate_for(ir))
    if field == "limits":
        certificate[field] = {"max_steps": 1}
    elif field == "obligations":
        certificate[field] = {}
    else:
        certificate[field] = "mutated"
    assert not check_certificate(ir, certificate)


def test_module_mutation_invalidates_old_hash():
    ir = module()
    certificate = certificate_for(ir)
    changed = deepcopy(ir)
    changed["functions"][0]["body"][0]["value"] = 4  # type: ignore[index]
    assert not check_certificate(changed, certificate)


def test_checker_does_not_call_proof_verify(monkeypatch: pytest.MonkeyPatch):
    import llmlang.a1.proof as proof

    ir = module()
    certificate = certificate_for(ir)

    def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError("independent checker called proof.verify")

    monkeypatch.setattr(proof, "verify", forbidden)
    assert check_certificate(ir, certificate)
