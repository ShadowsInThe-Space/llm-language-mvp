"""Fail-closed tests for the JavaScript target's host/value boundary."""

import json
import shutil
import subprocess

import pytest

from llmlang.a1.ir import A1IRError
from llmlang.a1.target import A1TargetError, emit_javascript
from llmlang.a1.typecheck import A1TypeError

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="Node target unavailable")


def const_module(value: object, *, value_type: dict[str, object]) -> dict[str, object]:
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
        "types": [],
        "entrypoints": ["main"],
        "functions": [
            {
                "name": "main",
                "params": [],
                "result": value_type,
                "body": [{"op": "const", "dest": "%0", "type": value_type, "value": value}],
                "return": "%0",
            }
        ],
    }


def run_target(module: dict[str, object]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["node", "-e", emit_javascript(module, "main", [])],
        check=False,
        capture_output=True,
        text=True,
    )


def test_text_const_rejects_utf8_capacity_before_target_value_escapes() -> None:
    with pytest.raises(A1IRError) as error:
        emit_javascript(const_module("é", value_type={"kind": "text", "capacity": 1}), "main", [])
    assert error.value.code == "E_A1_TEXT_CAPACITY"


def test_text_const_rejects_nul_and_unpaired_surrogate() -> None:
    with pytest.raises(A1IRError) as nul:
        emit_javascript(
            const_module("a\x00b", value_type={"kind": "text", "capacity": 3}), "main", []
        )
    assert nul.value.code == "E_A1_TEXT_ENCODING"

    with pytest.raises(A1IRError) as surrogate:
        emit_javascript(
            const_module("\ud800", value_type={"kind": "text", "capacity": 3}), "main", []
        )
    assert surrogate.value.code == "E_A1_TEXT_ENCODING"


def test_target_fails_closed_before_emitting_unsafe_integer_json() -> None:
    unsafe = 9_007_199_254_740_993
    with pytest.raises(A1TargetError) as error:
        emit_javascript(const_module(unsafe, value_type={"kind": "int"}), "main", [])
    assert error.value.code == "E_A1_UNSAFE_INTEGER"

    safe = 9_007_199_254_740_991
    completed = run_target(const_module(safe, value_type={"kind": "int"}))
    assert completed.returncode == 0
    assert json.loads(completed.stdout) == safe


def test_addition_that_would_leave_safe_integer_range_is_rejected() -> None:
    module = const_module(0, value_type={"kind": "int"})
    module["functions"][0]["body"] = [
        {"op": "const", "dest": "%0", "type": {"kind": "int"}, "value": 9_007_199_254_740_991},
        {"op": "const", "dest": "%1", "type": {"kind": "int"}, "value": 1},
        {"op": "add", "dest": "%2", "left": {"ref": "%0"}, "right": {"ref": "%1"}},
    ]
    module["functions"][0]["return"] = "%2"
    completed = run_target(module)
    assert completed.returncode != 0
    assert "E_A1_UNSAFE_INTEGER" in completed.stderr


def test_concat_uses_scalar_validation_and_exact_utf8_capacity() -> None:
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
                "name": "main",
                "params": [],
                "result": {"kind": "text", "capacity": 4},
                "body": [
                    {
                        "op": "const",
                        "dest": "%0",
                        "type": {"kind": "text", "capacity": 2},
                        "value": "é",
                    },
                    {
                        "op": "const",
                        "dest": "%1",
                        "type": {"kind": "text", "capacity": 2},
                        "value": "é",
                    },
                    {
                        "op": "text_concat",
                        "dest": "%2",
                        "left": {"ref": "%0"},
                        "right": {"ref": "%1"},
                        "capacity": 4,
                    },
                ],
                "return": "%2",
            }
        ],
    }
    completed = run_target(module)
    assert completed.returncode == 0
    assert json.loads(completed.stdout) == "éé"


def test_target_rejects_invalid_external_arguments_before_emission() -> None:
    module = const_module("ok", value_type={"kind": "text", "capacity": 2})
    module["functions"][0]["params"] = [{"name": "input", "type": {"kind": "text", "capacity": 1}}]
    with pytest.raises(A1TypeError) as error:
        emit_javascript(module, "main", ["é"])
    assert getattr(error.value, "code", None) == "E_A1_TEXT_CAPACITY"
