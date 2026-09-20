"""A1 construction, validation and exhaustive-match operations."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from .model import (
    BOOL,
    INT,
    NAT,
    UNIT,
    A1Error,
    ConstructorDef,
    RecordValue,
    TypedValue,
    TypeEnv,
    TypeRef,
    VariantDef,
    VariantValue,
    option_type,
    result_type,
)


def validate_value(
    value: TypedValue, expected: TypeRef, *, path: tuple[str, ...] = ()
) -> TypedValue:
    """Validate exact nominal identity and return ``value`` unchanged."""

    if expected == NAT:
        if value.type_ref != NAT:
            raise A1Error("E_A1_NAT", "Nat requires a checked Nat value", path=path)
        if not isinstance(value.value, int) or isinstance(value.value, bool) or value.value < 0:
            raise A1Error("E_A1_NAT", "Nat value is negative or not an exact integer", path=path)
        return value
    if value.type_ref != expected:
        raise A1Error(
            "E_A1_TYPE",
            f"Expected {expected.qualified_name}, got {value.type_ref.qualified_name}",
            path=path,
        )
    if expected == INT and (not isinstance(value.value, int) or isinstance(value.value, bool)):
        raise A1Error("E_A1_TYPE", "Int value must be an exact integer", path=path)
    if expected == BOOL and not isinstance(value.value, bool):
        raise A1Error("E_A1_TYPE", "Bool value must be a boolean", path=path)
    return value


def make_record(env: TypeEnv, record: str, fields: Mapping[str, TypedValue]) -> RecordValue:
    """Construct a closed record after exact field-set and type checks."""

    definition = env.record(record)
    expected = definition.field_map
    if set(fields) != set(expected):
        missing = sorted(set(expected) - set(fields))
        extra = sorted(set(fields) - set(expected))
        detail = f"missing={missing}, extra={extra}"
        raise A1Error("E_A1_FIELD", f"Record {record} has the wrong fields: {detail}")
    for name, field in expected.items():
        validate_value(fields[name], field.type_ref, path=("field", name))
    return RecordValue(
        TypeRef(record),
        tuple((name, fields[name]) for name in sorted(fields)),
    )


def get_field(
    env: TypeEnv,
    value: RecordValue,
    field: str,
    *,
    expected_record: str | None = None,
) -> TypedValue:
    """Read a field only through its nominal record declaration."""

    record_name = expected_record or value.type_ref.name
    if value.type_ref != TypeRef(record_name):
        raise A1Error("E_A1_TYPE", "Record value is not nominally compatible")
    definition = env.record(record_name)
    if field not in definition.field_map:
        raise A1Error("E_A1_FIELD", f"Unknown field {field}", symbol=field)
    return value.get(field)


def _variant_definition(env: TypeEnv | None, type_ref: TypeRef) -> VariantDef:
    if type_ref.name == "Option" and len(type_ref.args) == 1:
        return VariantDef(
            "Option", (ConstructorDef("none", UNIT), ConstructorDef("some", type_ref.args[0]))
        )
    if type_ref.name == "Result" and len(type_ref.args) == 2:
        return VariantDef(
            "Result",
            (ConstructorDef("ok", type_ref.args[0]), ConstructorDef("err", type_ref.args[1])),
        )
    if env is None:
        raise A1Error("E_A1_VARIANT", f"Unknown variant {type_ref.qualified_name}")
    return env.variant(type_ref.name)


def make_variant(
    env: TypeEnv,
    variant: str,
    constructor: str,
    payload: TypedValue | None = None,
) -> VariantValue:
    """Construct a closed variant with a nominally correct constructor payload."""

    definition = env.variant(variant)
    try:
        constructor_def = definition.constructor_map[constructor]
    except KeyError as error:
        raise A1Error(
            "E_A1_VARIANT", f"Unknown constructor {constructor}", symbol=constructor
        ) from error
    if not constructor_def.has_payload:
        if payload is not None:
            raise A1Error("E_A1_VARIANT", f"Constructor {constructor} has no payload")
    elif payload is None:
        raise A1Error("E_A1_VARIANT", f"Constructor {constructor} requires a payload")
    else:
        validate_value(payload, constructor_def.payload or UNIT, path=("constructor", constructor))
    return VariantValue(
        TypeRef(variant), constructor, payload if constructor_def.has_payload else None
    )


def match_variant(
    env: TypeEnv | None,
    value: VariantValue,
    branches: Mapping[str, Callable[..., object]],
) -> object:
    """Evaluate an exhaustive match; wildcard/default branches are forbidden."""

    if "default" in branches or "_" in branches:
        raise A1Error("E_A1_MATCH", "A1 matches do not support wildcard/default branches")
    definition = _variant_definition(env, value.type_ref)
    expected = {constructor.name for constructor in definition.constructors}
    actual = set(branches)
    if expected != actual:
        raise A1Error(
            "E_A1_MATCH",
            f"Match must cover exactly {sorted(expected)}; got {sorted(actual)}",
        )
    constructor = definition.constructor_map.get(value.constructor)
    if constructor is None:
        raise A1Error("E_A1_VARIANT", f"Unknown constructor {value.constructor}")
    branch = branches[value.constructor]
    if constructor.has_payload:
        if value.payload is None:
            raise A1Error("E_A1_VARIANT", "Variant payload is missing")
        return branch(value.payload)
    return branch()


def option_none(value_type: TypeRef) -> VariantValue:
    return VariantValue(option_type(value_type), "none")


def option_some(value_type: TypeRef, value: TypedValue) -> VariantValue:
    validate_value(value, value_type, path=("constructor", "some"))
    return VariantValue(option_type(value_type), "some", value)


def result_ok(ok_type: TypeRef, error_type: TypeRef, value: TypedValue) -> VariantValue:
    validate_value(value, ok_type, path=("constructor", "ok"))
    return VariantValue(result_type(ok_type, error_type), "ok", value)


def result_err(ok_type: TypeRef, error_type: TypeRef, value: TypedValue) -> VariantValue:
    validate_value(value, error_type, path=("constructor", "err"))
    return VariantValue(result_type(ok_type, error_type), "err", value)
