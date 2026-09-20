import pytest

from llmlang.a1.typecheck import A1TypeError, validate_module, validate_runtime_arguments


def module(body, *, params=(), result="Int", types=()):
    return {
        "format": "a1-ir-v1",
        "types": list(types),
        "entries": ["main"],
        "functions": [
            {
                "name": "main",
                "params": list(params),
                "body": body,
                "return": "out",
                "result": result,
            }
        ],
    }


def test_rejects_wrong_const_and_unbound_reference():
    bad_const = module([{"op": "const", "dest": "out", "type": "Bool", "value": "no"}])
    with pytest.raises(A1TypeError) as error:
        validate_module(bad_const)
    assert error.value.code == "E_A1_TYPE"

    bad_ref = module([{"op": "add", "dest": "out", "left": {"ref": "missing"}, "right": 1}])
    with pytest.raises(A1TypeError) as error:
        validate_module(bad_ref)
    assert error.value.code == "E_A1_BINDING"


def test_records_and_variants_are_nominal_and_payload_typed():
    types = (
        {"kind": "record", "name": "Customer", "fields": [{"name": "id", "type": "Int"}]},
        {"kind": "record", "name": "Order", "fields": [{"name": "id", "type": "Int"}]},
        {
            "kind": "variant",
            "name": "Choice",
            "cases": [{"tag": "None"}, {"tag": "Some", "type": "Customer"}],
        },
    )
    record = module(
        [
            {"op": "const", "dest": "x", "type": "Int", "value": 1},
            {
                "op": "record_make",
                "dest": "r",
                "record": "Customer",
                "fields": {"id": {"ref": "x"}},
            },
            {
                "op": "variant_make",
                "dest": "out",
                "variant": "Choice",
                "tag": "Some",
                "value": {"ref": "r"},
            },
        ],
        result="Choice",
        types=types,
    )
    validate_module(record)
    wrong = dict(record)
    wrong["functions"] = [dict(record["functions"][0])]
    wrong["functions"][0]["body"] = [
        {"op": "const", "dest": "x", "type": "Int", "value": 1},
        {"op": "record_make", "dest": "r", "record": "Order", "fields": {"id": {"ref": "x"}}},
        {
            "op": "variant_make",
            "dest": "out",
            "variant": "Choice",
            "tag": "Some",
            "value": {"ref": "r"},
        },
    ]
    with pytest.raises(A1TypeError) as error:
        validate_module(wrong)
    assert error.value.code == "E_A1_TYPE"


def test_text_list_nat_and_callbacks_are_checked():
    bad_text = module(
        [{"op": "const", "dest": "out", "type": {"kind": "text", "capacity": 1}, "value": "é"}],
        result={"kind": "text", "capacity": 1},
    )
    with pytest.raises(A1TypeError) as error:
        validate_module(bad_text)
    assert error.value.code == "E_A1_TEXT_CAPACITY"

    bad_nat = module(
        [
            {
                "op": "refine_nat",
                "dest": "out",
                "value": -1,
                "evidence": {"predicate": ">=0", "rule": "A1-C004"},
            }
        ],
        result="Nat",
    )
    with pytest.raises(A1TypeError) as error:
        validate_module(bad_nat)
    assert error.value.code == "E_A1_NAT"


def test_runtime_boundary_rejects_nominal_and_capacity_drift():
    types = ({"kind": "record", "name": "R", "fields": [{"name": "x", "type": "Int"}]},)
    m = module(
        [],
        params=(
            {"name": "r", "type": "R"},
            {"name": "xs", "type": {"kind": "list", "elem": "Int", "capacity": 2}},
        ),
        types=types,
    )
    with pytest.raises(A1TypeError) as error:
        validate_runtime_arguments(
            m, "main", [{"record": "Other", "fields": {"x": 1}}, {"list": [1], "capacity": 2}]
        )
    assert error.value.code == "E_A1_TYPE"
    with pytest.raises(A1TypeError) as error:
        validate_runtime_arguments(
            m, "main", [{"record": "R", "fields": {"x": 1}}, {"list": [1, 2, 3], "capacity": 2}]
        )
    assert error.value.code == "E_A1_LIST_BOUNDS"
