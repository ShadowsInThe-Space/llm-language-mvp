"""Independent structural certificate producer and checker for A1."""

from __future__ import annotations

from typing import Any

from llmlang.a1.certificate import make_certificate
from llmlang.a1.ir import A1IRError, validate_module


def verify(module: dict[str, Any]) -> dict[str, Any]:
    try:
        validated = validate_module(module)
    except A1IRError as exc:
        return {"status": "invalid", "diagnostics": [exc.to_dict()]}
    return {
        "status": "proved",
        "proof_scope": "a1-structural-and-local-contracts",
        "certificate": make_certificate(validated),
    }


def check_certificate(module: dict[str, Any], certificate: object) -> bool:
    from llmlang.a1.certificate import check_certificate as independent_check

    return independent_check(module, certificate)
