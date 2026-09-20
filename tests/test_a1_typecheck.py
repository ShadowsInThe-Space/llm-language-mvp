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


@pytest.mark.parametrize(
    ("parameter_type", "bad_value"),
    [
        ({"kind": "option", "elem": "Int"}, "not-option"),
        ({"kind": "option", "elem": "Int"}, {"tag": "Nope"}),
        ({"kind": "option", "elem": "Int"}, {"tag": "Some", "value": "bad"}),
        ({"kind": "result", "ok": "Int", "error": "Unit"}, {"tag": "Ok", "value": "bad"}),
    ],
)
def test_runtime_boundary_rejects_invalid_option_and_result(parameter_type, bad_value):
    checked = module([], params=({"name": "value", "type": parameter_type},))
    with pytest.raises(A1TypeError):
        validate_runtime_arguments(checked, "main", [bad_value])


def test_unknown_nominal_ids_and_missing_explicit_types_fail_closed():
    unknown = module(
        [],
        params=({"name": "value", "type": {"kind": "record", "id": "Missing"}},),
        result={"kind": "record", "id": "Missing"},
    )
    with pytest.raises(A1TypeError, match="unknown nominal"):
        validate_module(unknown)

    missing_param = module([], params=({"name": "value"},))
    with pytest.raises(A1TypeError, match="parameter type"):
        validate_module(missing_param)

    missing_const = module([{"op": "const", "dest": "out", "value": None}], result="Unit")
    with pytest.raises(A1TypeError, match="const type"):
        validate_module(missing_const)


def test_variant_fields_and_callback_element_types_are_checked():
    declarations = (
        {
            "kind": "variant",
            "name": "Choice",
            "cases": [{"tag": "None"}, {"tag": "Some", "type": "Int"}],
        },
        {"kind": "record", "name": "Box", "fields": [{"name": "choice", "type": "Choice"}]},
    )
    nested = module(
        [
            {"op": "variant_make", "dest": "choice", "variant": "Choice", "tag": "None"},
            {
                "op": "record_make",
                "dest": "out",
                "record": "Box",
                "fields": {"choice": {"ref": "choice"}},
            },
        ],
        result="Box",
        types=declarations,
    )
    validate_module(nested)

    bad_map = {
        "format": "a1-ir-v1",
        "types": [],
        "entries": ["main"],
        "functions": [
            {
                "name": "callback",
                "params": [{"name": "value", "type": "Bool"}],
                "result": "Int",
                "body": [{"op": "const", "dest": "out", "type": "Int", "value": 1}],
                "return": "out",
            },
            {
                "name": "main",
                "params": [
                    {
                        "name": "items",
                        "type": {"kind": "list", "elem": "Int", "capacity": 2},
                    }
                ],
                "result": {"kind": "list", "elem": "Int", "capacity": 2},
                "body": [
                    {
                        "op": "bounded_map",
                        "dest": "out",
                        "list": {"ref": "items"},
                        "callback": "callback",
                    }
                ],
                "return": "out",
            },
        ],
    }
    with pytest.raises(A1TypeError, match="incompatible"):
        validate_module(bad_map)


def test_result_host_values_reject_extra_fields():
    checked = module(
        [],
        params=({"name": "value", "type": {"kind": "result", "ok": "Int", "error": "Bool"}},),
    )
    with pytest.raises(A1TypeError, match="closed representation"):
        validate_runtime_arguments(
            checked,
            "main",
            [{"tag": "Ok", "value": 1, "error": "unexpected"}],
        )


def test_list_empty_requires_explicit_element_type():
    missing = module(
        [{"op": "list_empty", "dest": "out", "capacity": 2}],
        result={"kind": "list", "elem": "Int", "capacity": 2},
    )
    with pytest.raises(A1TypeError, match="explicit list type"):
        validate_module(missing)

    valid = module(
        [
            {
                "op": "list_empty",
                "dest": "out",
                "capacity": 2,
                "type": {"kind": "list", "elem": "Int", "capacity": 2},
            }
        ],
        result={"kind": "list", "elem": "Int", "capacity": 2},
    )
    validate_module(valid)
