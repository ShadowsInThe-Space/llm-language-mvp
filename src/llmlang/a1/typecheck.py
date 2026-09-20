"""Fail-closed static and host-boundary checking for the A1 JSON IR.

This module intentionally depends only on the IR-shaped dictionaries.  It is
kept separate from the validator so the producer and certificate checker can
use it without importing the interpreter.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, NoReturn


class A1TypeError(ValueError):
    def __init__(self, code: str, message: str, location: str = "module") -> None:
        self.code = code
        self.location = location
        super().__init__(message)

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": str(self), "location": self.location}


Type = tuple[Any, ...]
UNKNOWN: Type = ("unknown",)
UNIT: Type = ("unit",)
BOOL: Type = ("bool",)
INT: Type = ("int",)
NAT: Type = ("nat",)


def _fail(code: str, message: str, location: str) -> NoReturn:
    raise A1TypeError(code, message, location)


def _type(raw: Any, records: set[str], variants: set[str]) -> Type:
    if isinstance(raw, str):
        aliases = {"Unit": UNIT, "Bool": BOOL, "Int": INT, "Nat": NAT}
        if raw in aliases:
            return aliases[raw]
        if raw in records:
            return ("record", raw)
        if raw in variants:
            return ("variant", raw)
        _fail("E_A1_TYPE", f"unknown type {raw}", "type")
    if not isinstance(raw, Mapping):
        _fail("E_A1_TYPE", "type must be a string or object", "type")
    kind = raw.get("kind")
    primitive = {"unit": UNIT, "bool": BOOL, "int": INT, "nat": NAT}
    if kind in primitive:
        return primitive[kind]
    if kind == "text":
        cap = raw.get("capacity", raw.get("max_bytes"))
        if type(cap) is not int or cap < 0:
            _fail("E_A1_TYPE_CAPACITY", "text capacity must be a non-negative integer", "type")
        return ("text", cap)
    if kind == "list":
        cap = raw.get("capacity")
        if type(cap) is not int or cap < 0:
            _fail("E_A1_TYPE_CAPACITY", "list capacity must be a non-negative integer", "type")
        if "elem" not in raw:
            _fail("E_A1_TYPE", "list element type is required", "type")
        return ("list", _type(raw["elem"], records, variants), cap)
    if kind == "option":
        return ("option", _type(raw.get("elem"), records, variants))
    if kind == "result":
        return (
            "result",
            _type(raw.get("ok"), records, variants),
            _type(raw.get("error"), records, variants),
        )
    if kind == "record" and isinstance(raw.get("id"), str):
        if raw["id"] not in records:
            _fail("E_A1_TYPE", "unknown nominal record type", "type")
        return ("record", raw["id"])
    if kind == "variant" and isinstance(raw.get("id"), str):
        if raw["id"] not in variants:
            _fail("E_A1_TYPE", "unknown nominal variant type", "type")
        return ("variant", raw["id"])
    _fail("E_A1_TYPE", "unsupported type expression", "type")


def _declarations(
    module: Mapping[str, Any],
) -> tuple[dict[str, dict[str, Type]], dict[str, dict[str, Type | None]]]:
    records: dict[str, dict[str, Type]] = {}
    variants: dict[str, dict[str, Type | None]] = {}
    declarations = module.get("types", [])
    if not isinstance(declarations, list):
        _fail("E_A1_TYPE", "types must be a list", "types")
    raw_names = {item.get("name") for item in declarations if isinstance(item, Mapping)}
    if any(not isinstance(name, str) for name in raw_names):
        _fail("E_A1_TYPE", "every declaration needs a name", "types")
    record_names = {
        str(item.get("name"))
        for item in declarations
        if isinstance(item, Mapping) and item.get("kind") == "record"
    }
    variant_names = {
        str(item.get("name"))
        for item in declarations
        if isinstance(item, Mapping) and item.get("kind") == "variant"
    }
    for index, declaration in enumerate(declarations):
        if not isinstance(declaration, Mapping):
            _fail("E_A1_TYPE", "declaration must be an object", f"types[{index}]")
        name = declaration.get("name")
        if declaration.get("kind") == "record":
            fields = declaration.get("fields")
            if not isinstance(name, str) or not isinstance(fields, list):
                _fail("E_A1_FIELD", "record fields are required", f"types[{index}]")
            field_names = [field.get("name") for field in fields if isinstance(field, Mapping)]
            if len(field_names) != len(fields) or len(set(field_names)) != len(field_names):
                _fail("E_A1_NAME", "record fields must be unique", f"types[{index}]")
            if any("type" not in field for field in fields):
                _fail("E_A1_TYPE", "record field type is required", f"types[{index}]")
            records[name] = {
                field["name"]: _type(field["type"], record_names, variant_names) for field in fields
            }
        elif declaration.get("kind") == "variant":
            cases = declaration.get("cases")
            if not isinstance(name, str) or not isinstance(cases, list):
                _fail("E_A1_VARIANT", "variant cases are required", f"types[{index}]")
            tags = [case.get("tag") for case in cases if isinstance(case, Mapping)]
            if len(tags) != len(cases) or len(set(tags)) != len(tags):
                _fail("E_A1_NAME", "variant tags must be unique", f"types[{index}]")
            variants[name] = {
                case["tag"]: (
                    _type(case["type"], record_names, variant_names) if "type" in case else None
                )
                for case in cases
            }
    return records, variants


def _lookup(operand: Any, env: Mapping[str, Type], expected: Type | None, location: str) -> Type:
    if isinstance(operand, Mapping) and set(operand) == {"ref"}:
        name = operand.get("ref")
        if not isinstance(name, str) or name not in env:
            _fail("E_A1_BINDING", "reference is not defined", location)
        actual = env[name]
    elif expected is not None:
        _check_literal(operand, expected, location)
        actual = expected
    else:
        actual = INT if type(operand) is int else BOOL if isinstance(operand, bool) else UNKNOWN
    if expected is not None and actual != expected and actual != UNKNOWN:
        _fail("E_A1_TYPE", "operand type differs", location)
    return actual


def _check_literal(value: Any, expected: Type, location: str) -> None:
    kind = expected[0]
    if kind == "int" and type(value) is not int:
        _fail("E_A1_TYPE", "Int literal required", location)
    if kind == "nat" and (type(value) is not int or value < 0):
        _fail("E_A1_NAT", "Nat literal must be non-negative", location)
    if kind == "bool" and type(value) is not bool:
        _fail("E_A1_TYPE", "Bool literal required", location)
    if kind == "unit" and value is not None:
        _fail("E_A1_TYPE", "Unit literal required", location)
    if kind == "text":
        if not isinstance(value, str) or "\x00" in value:
            _fail("E_A1_TEXT_ENCODING", "valid text scalar required", location)
        try:
            size = len(value.encode("utf-8"))
        except UnicodeEncodeError:
            _fail("E_A1_TEXT_ENCODING", "valid UTF-8 text required", location)
        if size > expected[1]:
            _fail("E_A1_TEXT_CAPACITY", "text capacity exceeded", location)


def _same(left: Type, right: Type, location: str) -> None:
    if left != right and left != UNKNOWN and right != UNKNOWN:
        _fail("E_A1_TYPE", "incompatible nominal types", location)


def _function_types(
    module: Mapping[str, Any],
    records: dict[str, dict[str, Type]],
    variants: dict[str, dict[str, Type | None]],
) -> dict[str, Type]:
    functions = module.get("functions")
    if not isinstance(functions, list):
        _fail("E_A1_FUNCTION", "functions must be a list", "functions")
    names = set(records) | set(variants)
    result: dict[str, Type] = {}
    for function in functions:
        name = function.get("name")
        if not isinstance(name, str):
            _fail("E_A1_FUNCTION", "function needs a name", "functions")
        if "result" not in function:
            _fail("E_A1_TYPE", "function result type is required", f"functions[{name}]")
        result[name] = _type(function["result"], names - set(variants), set(variants))
    return result


def validate_module(module: Mapping[str, Any]) -> None:
    records, variants = _declarations(module)
    functions = module.get("functions")
    if not isinstance(functions, list):
        _fail("E_A1_FUNCTION", "functions must be a list", "functions")
    function_results = _function_types(module, records, variants)
    function_map = {function.get("name"): function for function in functions}
    for function in functions:
        name = function.get("name")
        if not isinstance(name, str):
            _fail("E_A1_FUNCTION", "function needs a name", "functions")
        env: dict[str, Type] = {}
        for index, parameter in enumerate(function.get("params", [])):
            if not isinstance(parameter, Mapping) or not isinstance(parameter.get("name"), str):
                _fail("E_A1_BINDING", "invalid parameter", f"functions[{name}].params[{index}]")
            if "type" not in parameter:
                _fail(
                    "E_A1_TYPE", "parameter type is required", f"functions[{name}].params[{index}]"
                )
            parameter_type = _type(parameter["type"], set(records), set(variants))
            if parameter["name"] in env:
                _fail("E_A1_BINDING", "duplicate parameter", f"functions[{name}]")
            env[parameter["name"]] = parameter_type
        for index, instruction in enumerate(function.get("body", [])):
            if not isinstance(instruction, Mapping):
                _fail(
                    "E_A1_INSTRUCTION",
                    "instruction must be an object",
                    f"functions[{name}].body[{index}]",
                )
            location = f"functions[{name}].body[{index}]"
            dest = instruction.get("dest")
            if not isinstance(dest, str) or dest in env:
                _fail("E_A1_SSA", "destination must be unique", location)
            op = instruction.get("op")
            if op == "const":
                if "type" not in instruction:
                    _fail("E_A1_TYPE", "const type is required", location)
                result_type = _type(instruction["type"], set(records), set(variants))
                _check_literal(instruction.get("value"), result_type, location)
            elif op == "record_make":
                record_name = instruction.get("record")
                if not isinstance(record_name, str) or record_name not in records:
                    _fail("E_A1_FIELD", "unknown record", location)
                supplied = instruction.get("fields")
                if not isinstance(supplied, Mapping) or set(supplied) != set(records[record_name]):
                    _fail("E_A1_FIELD", "record fields are not exact", location)
                for field, expected in records[record_name].items():
                    _lookup(supplied[field], env, expected, f"{location}.{field}")
                result_type = ("record", record_name)
            elif op == "record_get":
                record_name = instruction.get("record")
                if record_name not in records:
                    _fail("E_A1_FIELD", "unknown record", location)
                _lookup(instruction.get("value"), env, ("record", record_name), location)
                projected_field = instruction.get("field")
                if projected_field not in records[record_name]:
                    _fail("E_A1_FIELD", "unknown field", location)
                assert isinstance(projected_field, str)
                result_type = records[record_name][projected_field]
            elif op == "variant_make":
                variant_name, tag = instruction.get("variant"), instruction.get("tag")
                if variant_name not in variants or tag not in variants[variant_name]:
                    _fail("E_A1_VARIANT", "unknown constructor", location)
                payload_type = variants[variant_name][tag]
                has_value = "value" in instruction
                if payload_type is None and has_value:
                    _fail("E_A1_VARIANT", "unit constructor cannot have payload", location)
                if payload_type is not None:
                    if not has_value:
                        _fail("E_A1_VARIANT", "payload is required", location)
                    _lookup(instruction["value"], env, payload_type, location)
                result_type = ("variant", variant_name)
            elif op == "match_value":
                variant_name = instruction.get("variant")
                _lookup(instruction.get("value"), env, ("variant", variant_name), location)
                arms = instruction.get("arms")
                if (
                    variant_name not in variants
                    or not isinstance(arms, Mapping)
                    or set(arms) != set(variants[variant_name])
                ):
                    _fail("E_A1_MATCH", "match must be exhaustive", location)
                if "type" not in instruction:
                    _fail("E_A1_TYPE", "match requires an explicit result type", location)
                result_type = _type(instruction["type"], set(records), set(variants))
                for arm in arms.values():
                    _lookup(arm, env, result_type, location)
            elif op == "add":
                left = _lookup(instruction.get("left"), env, None, location)
                right = _lookup(instruction.get("right"), env, left, location)
                if left[0] not in {"int", "nat"} or right[0] not in {"int", "nat"}:
                    _fail("E_A1_TYPE", "add requires Int or Nat", location)
                result_type = NAT if left == NAT and right == NAT else INT
            elif op == "refine_nat":
                candidate = _lookup(instruction.get("value"), env, INT, location)
                if instruction.get("evidence") != {"predicate": ">=0", "rule": "A1-C004"}:
                    _fail("E_A1_NAT", "Nat evidence is missing", location)
                if not isinstance(instruction.get("value"), Mapping) and (
                    type(instruction.get("value")) is not int or instruction["value"] < 0
                ):
                    _fail("E_A1_NAT", "Nat literal must be non-negative", location)
                del candidate
                result_type = NAT
            elif op in {"text_utf8_bytes", "text_codepoint_count"}:
                operand = _lookup(instruction.get("value"), env, None, location)
                if operand[0] != "text":
                    _fail("E_A1_TYPE", "text operation requires Text", location)
                result_type = NAT
            elif op == "text_prefix_codepoints":
                text = _lookup(instruction.get("value"), env, None, location)
                _lookup(instruction.get("count"), env, NAT, location)
                if text[0] != "text":
                    _fail("E_A1_TYPE", "text operation requires Text", location)
                result_type = text
            elif op == "text_concat":
                left = _lookup(instruction.get("left"), env, None, location)
                right = _lookup(instruction.get("right"), env, None, location)
                if left[0] != "text" or right[0] != "text":
                    _fail("E_A1_TYPE", "text concat requires Text", location)
                capacity = instruction.get("capacity", left[1] + right[1])
                if type(capacity) is not int or capacity < 0:
                    _fail("E_A1_TYPE_CAPACITY", "invalid text capacity", location)
                result_type = ("text", capacity)
            elif op == "list_empty":
                capacity = instruction.get("capacity")
                if type(capacity) is not int or capacity < 0:
                    _fail("E_A1_TYPE_CAPACITY", "invalid list capacity", location)
                result_type = ("list", UNKNOWN, capacity)
            elif op == "list_index":
                source = _lookup(instruction.get("list"), env, None, location)
                _lookup(instruction.get("index"), env, NAT, location)
                if source[0] != "list":
                    _fail("E_A1_TYPE", "index requires List", location)
                result_type = ("option", source[1])
            elif op == "list_append":
                source = _lookup(instruction.get("list"), env, None, location)
                if source[0] != "list":
                    _fail("E_A1_TYPE", "append requires List", location)
                _lookup(
                    instruction.get("value"),
                    env,
                    source[1] if source[1] != UNKNOWN else None,
                    location,
                )
                result_type = ("result", source, ("variant", "CapacityError"))
            elif op in {"bounded_map", "bounded_fold"}:
                source = _lookup(instruction.get("list"), env, None, location)
                callback = function_map.get(instruction.get("callback"))
                if source[0] != "list" or not isinstance(callback, Mapping):
                    _fail("E_A1_CALLBACK", "invalid bounded callback", location)
                callback_name = callback.get("name")
                if not isinstance(callback_name, str):
                    _fail("E_A1_CALLBACK", "callback needs a name", location)
                callback_params = callback.get("params", [])
                wanted = 1 if op == "bounded_map" else 2
                if len(callback_params) != wanted:
                    _fail("E_A1_CALLBACK", "callback arity differs", location)
                callback_result = function_results.get(callback_name, UNKNOWN)
                first_type = _type(callback_params[0].get("type"), set(records), set(variants))
                if op == "bounded_map":
                    _same(source[1], first_type, location)
                    result_type = ("list", callback_result, source[2])
                else:
                    second_type = _type(callback_params[1].get("type"), set(records), set(variants))
                    _same(source[1], second_type, location)
                    _same(first_type, callback_result, location)
                    _lookup(
                        instruction.get("initial"),
                        env,
                        first_type,
                        location,
                    )
                    result_type = callback_result
            elif op == "call":
                callee = function_map.get(instruction.get("callee"))
                if not isinstance(callee, Mapping):
                    _fail("E_A1_CALL", "unknown callee", location)
                callee_name = callee.get("name")
                if not isinstance(callee_name, str):
                    _fail("E_A1_CALL", "callee needs a name", location)
                args = instruction.get("args", [])
                params = callee.get("params", [])
                if not isinstance(args, list) or len(args) != len(params):
                    _fail("E_A1_CALL", "call arity differs", location)
                for arg, param in zip(args, params, strict=True):
                    _lookup(
                        arg, env, _type(param.get("type"), set(records), set(variants)), location
                    )
                result_type = function_results.get(callee_name, UNIT)
            else:
                _fail("E_A1_OP", "unsupported operation", location)
            if "type" in instruction:
                declared = _type(instruction["type"], set(records), set(variants))
                _same(declared, result_type, f"{location}.type")
            env[dest] = result_type
        return_type = function_results[name]
        if function.get("return") not in env:
            _fail("E_A1_BINDING", "return reference is not defined", f"functions[{name}]")
        _same(env[function["return"]], return_type, f"functions[{name}].return")


def _runtime(
    value: Any,
    expected: Type,
    records: dict[str, dict[str, Type]],
    variants: dict[str, dict[str, Type | None]],
    location: str,
) -> None:
    kind = expected[0]
    if kind == "int" and type(value) is not int:
        _fail("E_A1_TYPE", "exact Int required", location)
    elif kind == "unit" and value is not None:
        _fail("E_A1_TYPE", "Unit requires null", location)
    elif kind == "nat" and (type(value) is not int or value < 0):
        _fail("E_A1_NAT", "non-negative Nat required", location)
    elif kind == "bool" and type(value) is not bool:
        _fail("E_A1_TYPE", "Bool required", location)
    elif kind == "text":
        _check_literal(value, expected, location)
    elif kind == "record":
        if (
            not isinstance(value, Mapping)
            or set(value) != {"record", "fields"}
            or value.get("record") != expected[1]
            or set(value.get("fields", {})) != set(records[expected[1]])
        ):
            _fail("E_A1_TYPE", "nominal record mismatch", location)
        for field, field_type in records[expected[1]].items():
            _runtime(value["fields"][field], field_type, records, variants, f"{location}.{field}")
    elif kind == "variant":
        if (
            not isinstance(value, Mapping)
            or value.get("variant") != expected[1]
            or value.get("tag") not in variants[expected[1]]
        ):
            _fail("E_A1_TYPE", "nominal variant mismatch", location)
        payload = variants[expected[1]][value["tag"]]
        if payload is None:
            if set(value) - {"variant", "tag", "value"} or value.get("value") is not None:
                _fail("E_A1_TYPE", "unit variant has invalid representation", location)
        else:
            if set(value) != {"variant", "tag", "value"}:
                _fail("E_A1_TYPE", "variant payload is required", location)
            _runtime(value.get("value"), payload, records, variants, location)
    elif kind == "list":
        if (
            not isinstance(value, Mapping)
            or set(value) != {"capacity", "list"}
            or value.get("capacity") != expected[2]
            or not isinstance(value.get("list"), list)
        ):
            _fail("E_A1_TYPE", "list representation mismatch", location)
        if len(value["list"]) > expected[2]:
            _fail("E_A1_LIST_BOUNDS", "list exceeds capacity", location)
        if expected[1] != UNKNOWN:
            for item in value["list"]:
                _runtime(item, expected[1], records, variants, location)
    elif kind == "option":
        if not isinstance(value, Mapping) or value.get("tag") not in {"None", "Some"}:
            _fail("E_A1_TYPE", "Option tagged value required", location)
        if value["tag"] == "None":
            if set(value) - {"tag", "value"} or value.get("value") is not None:
                _fail("E_A1_TYPE", "None cannot carry a payload", location)
        else:
            if set(value) != {"tag", "value"}:
                _fail("E_A1_TYPE", "Some payload is required", location)
            _runtime(value["value"], expected[1], records, variants, location)
    elif kind == "result":
        if not isinstance(value, Mapping) or value.get("tag") not in {"Ok", "Err"}:
            _fail("E_A1_TYPE", "Result tagged value required", location)
        if set(value) != {"tag", "value"}:
            _fail("E_A1_TYPE", "Result has an invalid closed representation", location)
        payload_type = expected[1] if value["tag"] == "Ok" else expected[2]
        _runtime(value["value"], payload_type, records, variants, location)


def validate_runtime_arguments(
    module: Mapping[str, Any], entry: str, arguments: Sequence[Any]
) -> None:
    records, variants = _declarations(module)
    functions = {function.get("name"): function for function in module.get("functions", [])}
    function = functions.get(entry)
    if not isinstance(function, Mapping):
        _fail("E_A1_CALL", "unknown entry", "entry")
    params = function.get("params", [])
    if len(arguments) != len(params):
        _fail("E_A1_CALL", "argument arity differs", "entry")
    for index, (argument, parameter) in enumerate(zip(arguments, params, strict=True)):
        expected = _type(parameter.get("type"), set(records), set(variants))
        _runtime(argument, expected, records, variants, f"entry.args[{index}]")
