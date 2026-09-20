"""TDD contract tests for the A1 nominal type core (issue #17)."""

from dataclasses import FrozenInstanceError

import pytest

from llmlang.a1.model import (
    BOOL,
    INT,
    NAT,
    UNIT,
    A1Error,
    ConstructorDef,
    FieldDef,
    RecordDef,
    TypedValue,
    TypeEnv,
    TypeRef,
    VariantDef,
    option_type,
    result_type,
)
from llmlang.a1.types import (
    get_field,
    make_record,
    make_variant,
    match_variant,
    option_none,
    option_some,
    result_err,
    result_ok,
    validate_value,
)


def tv(value: object, type_ref: TypeRef) -> TypedValue:
    return TypedValue(value=value, type_ref=type_ref)


@pytest.fixture
def env() -> TypeEnv:
    symbols = TypeEnv()
    symbols.add_record(
        RecordDef(
            "Customer",
            (
                FieldDef("id", TypeRef("CustomerId")),
                FieldDef("name", TypeRef("Text")),
            ),
        )
    )
    symbols.add_record(RecordDef("Booking", (FieldDef("id", TypeRef("BookingId")),)))
    symbols.add_variant(
        VariantDef(
            "BookingError",
            (
                ConstructorDef("invalid", UNIT),
                ConstructorDef("sold_out", UNIT),
                ConstructorDef("retry", TypeRef("Int")),
            ),
        )
    )
    return symbols


def test_records_are_closed_nominal_and_immutable(env: TypeEnv) -> None:
    customer = make_record(
        env,
        "Customer",
        {
            "name": tv("Ada", TypeRef("Text")),
            "id": tv(7, TypeRef("CustomerId")),
        },
    )

    assert customer.type_ref == TypeRef("Customer")
    assert get_field(env, customer, "id") == tv(7, TypeRef("CustomerId"))
    assert tuple(name for name, _ in customer.fields) == ("id", "name")
    with pytest.raises(FrozenInstanceError):
        customer.type_ref = TypeRef("Booking")  # type: ignore[misc]
    with pytest.raises(TypeError):
        customer.fields[0] = ("id", tv(8, TypeRef("CustomerId")))  # type: ignore[index]


@pytest.mark.parametrize(
    ("fields", "code"),
    [
        ({"id": tv(1, TypeRef("CustomerId"))}, "E_A1_FIELD"),
        (
            {
                "id": tv(1, TypeRef("CustomerId")),
                "name": tv("Ada", TypeRef("Text")),
                "extra": tv(True, BOOL),
            },
            "E_A1_FIELD",
        ),
        (
            {
                "id": tv(1, INT),
                "name": tv("Ada", TypeRef("Text")),
            },
            "E_A1_TYPE",
        ),
    ],
)
def test_record_fields_are_exact_and_typed(
    env: TypeEnv, fields: dict[str, TypedValue], code: str
) -> None:
    with pytest.raises(A1Error) as error:
        make_record(env, "Customer", fields)
    assert error.value.code == code


def test_nominal_records_do_not_interchange(env: TypeEnv) -> None:
    booking = make_record(env, "Booking", {"id": tv(7, TypeRef("BookingId"))})
    with pytest.raises(A1Error) as error:
        get_field(env, booking, "id", expected_record="Customer")
    assert error.value.code == "E_A1_TYPE"


def test_variants_validate_nominal_constructor_and_payload(env: TypeEnv) -> None:
    retry = make_variant(env, "BookingError", "retry", tv(3, INT))
    assert retry.constructor == "retry"
    assert retry.payload == tv(3, INT)

    with pytest.raises(A1Error) as error:
        make_variant(env, "BookingError", "retry", tv(True, BOOL))
    assert error.value.code == "E_A1_TYPE"

    with pytest.raises(A1Error) as error:
        make_variant(env, "BookingError", "missing")
    assert error.value.code == "E_A1_VARIANT"

    with pytest.raises(A1Error) as error:
        make_variant(env, "BookingError", "invalid", tv(1, INT))
    assert error.value.code == "E_A1_VARIANT"


def test_variant_match_requires_each_constructor_once(env: TypeEnv) -> None:
    value = make_variant(env, "BookingError", "retry", tv(3, INT))
    branches = {
        "invalid": lambda: "invalid",
        "sold_out": lambda: "sold",
        "retry": lambda payload: payload.value,
    }
    assert match_variant(env, value, branches) == 3

    with pytest.raises(A1Error) as error:
        match_variant(env, value, {"invalid": lambda: "invalid"})
    assert error.value.code == "E_A1_MATCH"

    with pytest.raises(A1Error) as error:
        match_variant(env, value, {**branches, "default": lambda: "bad"})
    assert error.value.code == "E_A1_MATCH"


def test_option_and_result_use_the_same_closed_variant_rules() -> None:
    maybe_id = option_some(TypeRef("CustomerId"), tv(9, TypeRef("CustomerId")))
    assert maybe_id.type_ref == option_type(TypeRef("CustomerId"))
    assert (
        match_variant(
            None,
            maybe_id,
            {"none": lambda: "none", "some": lambda payload: payload.value},
        )
        == 9
    )

    failure = result_err(
        TypeRef("Customer"), TypeRef("BookingError"), tv("sold", TypeRef("BookingError"))
    )
    success = result_ok(
        TypeRef("Customer"), TypeRef("BookingError"), tv("Ada", TypeRef("Customer"))
    )
    assert failure.type_ref == result_type(TypeRef("Customer"), TypeRef("BookingError"))
    assert success.type_ref == result_type(TypeRef("Customer"), TypeRef("BookingError"))
    assert option_none(INT).payload is None
    with pytest.raises(A1Error) as error:
        option_some(INT, tv("no", TypeRef("Text")))
    assert error.value.code == "E_A1_TYPE"


def test_nat_is_a_checked_refinement_not_an_int_cast() -> None:
    assert validate_value(tv(0, NAT), NAT) == tv(0, NAT)
    assert validate_value(tv(4, NAT), NAT) == tv(4, NAT)
    with pytest.raises(A1Error) as error:
        validate_value(tv(-1, NAT), NAT)
    assert error.value.code == "E_A1_NAT"
    with pytest.raises(A1Error) as error:
        validate_value(tv(2, INT), NAT)
    assert error.value.code == "E_A1_NAT"


def test_duplicate_symbols_are_stable_diagnostics() -> None:
    with pytest.raises(A1Error) as error:
        RecordDef("Bad", (FieldDef("x", INT), FieldDef("x", BOOL)))
    assert error.value.code == "E_A1_NAME"

    with pytest.raises(A1Error) as error:
        VariantDef("Bad", (ConstructorDef("x", UNIT), ConstructorDef("x", UNIT)))
    assert error.value.code == "E_A1_NAME"
