"""Canonical A1 IR parsing and structural validation."""

from __future__ import annotations

import hashlib
import json
from typing import Any


class A1IRError(ValueError):
    """Stable fail-closed IR diagnostic."""

    def __init__(self, code: str, message: str, location: str = "module") -> None:
        self.code = code
        self.location = location
        super().__init__(message)

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": str(self), "location": self.location}


def canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise A1IRError("E_A1_CANONICAL", "IR is not canonical-JSON encodable") from exc


def module_hash(module: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(module)).hexdigest()


_OPS = {
    "const",
    "record_make",
    "record_get",
    "variant_make",
    "match_value",
    "list_empty",
    "list_append",
    "list_index",
    "bounded_map",
    "bounded_fold",
    "text_utf8_bytes",
    "text_codepoint_count",
    "text_prefix_codepoints",
    "text_concat",
    "refine_nat",
    "add",
    "call",
}


def _require(condition: bool, code: str, message: str, location: str) -> None:
    if not condition:
        raise A1IRError(code, message, location)


def validate_module(module: object) -> dict[str, Any]:
    _require(isinstance(module, dict), "E_A1_MODULE", "module must be an object", "module")
    assert isinstance(module, dict)
    _require(module.get("format") == "a1-ir-v1", "E_A1_FORMAT", "unsupported format", "format")
    types = module.get("types", [])
    functions = module.get("functions")
    entries = module.get("entries", [])
    _require(isinstance(types, list), "E_A1_TYPES", "types must be a list", "types")
    _require(isinstance(functions, list), "E_A1_FUNCTIONS", "functions must be a list", "functions")
    _require(isinstance(entries, list), "E_A1_ENTRIES", "entries must be a list", "entries")
    assert isinstance(types, list) and isinstance(functions, list) and isinstance(entries, list)

    type_names: set[str] = set()
    variants: dict[str, set[str]] = {}
    records: dict[str, tuple[str, ...]] = {}
    for index, declaration in enumerate(types):
        location = f"types[{index}]"
        _require(isinstance(declaration, dict), "E_A1_TYPE", "type must be object", location)
        assert isinstance(declaration, dict)
        name = declaration.get("name")
        _require(bool(isinstance(name, str) and name), "E_A1_TYPE", "type name required", location)
        assert isinstance(name, str) and name
        _require(name not in type_names, "E_A1_TYPE", "duplicate nominal type", location)
        type_names.add(name)
        kind = declaration.get("kind")
        if kind == "record":
            fields = declaration.get("fields")
            _require(
                bool(isinstance(fields, list) and fields),
                "E_A1_RECORD",
                "fields required",
                location,
            )
            assert isinstance(fields, list) and fields
            field_names = tuple(field.get("name") for field in fields if isinstance(field, dict))
            _require(
                len(field_names) == len(fields) and all(isinstance(x, str) for x in field_names),
                "E_A1_RECORD",
                "invalid record fields",
                location,
            )
            _require(
                len(set(field_names)) == len(field_names),
                "E_A1_RECORD",
                "duplicate field",
                location,
            )
            records[name] = tuple(str(item) for item in field_names)
        elif kind == "variant":
            cases = declaration.get("cases")
            _require(
                bool(isinstance(cases, list) and cases),
                "E_A1_VARIANT",
                "cases required",
                location,
            )
            assert isinstance(cases, list) and cases
            tags = {case.get("tag") for case in cases if isinstance(case, dict)}
            _require(
                len(tags) == len(cases) and all(isinstance(x, str) for x in tags),
                "E_A1_VARIANT",
                "invalid cases",
                location,
            )
            variants[name] = {str(item) for item in tags}
        else:
            raise A1IRError("E_A1_TYPE", "type kind must be record or variant", location)

    names: set[str] = set()
    for f_index, function in enumerate(functions):
        location = f"functions[{f_index}]"
        _require(isinstance(function, dict), "E_A1_FUNCTION", "function must be object", location)
        assert isinstance(function, dict)
        name = function.get("name")
        _require(
            isinstance(name, str) and name not in names,
            "E_A1_FUNCTION",
            "unique name required",
            location,
        )
        assert isinstance(name, str)
        names.add(name)
        params = function.get("params", [])
        body = function.get("body")
        _require(
            isinstance(params, list) and isinstance(body, list),
            "E_A1_FUNCTION",
            "params/body must be lists",
            location,
        )
        assert isinstance(params, list) and isinstance(body, list)
        values = {param.get("name") for param in params if isinstance(param, dict)}
        _require(
            len(values) == len(params) and all(isinstance(x, str) for x in values),
            "E_A1_PARAM",
            "invalid params",
            location,
        )
        for i_index, instruction in enumerate(body):
            iloc = f"{location}.body[{i_index}]"
            _require(
                isinstance(instruction, dict),
                "E_A1_INSTRUCTION",
                "instruction must be object",
                iloc,
            )
            assert isinstance(instruction, dict)
            op = instruction.get("op")
            dest = instruction.get("dest")
            _require(op in _OPS, "E_A1_OP", "unknown operation", iloc)
            _require(
                isinstance(dest, str) and dest not in values,
                "E_A1_SSA",
                "unique destination required",
                iloc,
            )
            assert isinstance(dest, str)
            values.add(dest)
            if op == "record_make":
                type_name = instruction.get("record")
                supplied = instruction.get("fields", {})
                _require(
                    type_name in records and isinstance(supplied, dict),
                    "E_A1_RECORD",
                    "unknown record",
                    iloc,
                )
                assert isinstance(type_name, str) and isinstance(supplied, dict)
                _require(
                    tuple(supplied) == records[type_name],
                    "E_A1_RECORD_FIELDS",
                    "record fields differ",
                    iloc,
                )
            if op == "variant_make":
                type_name, tag = instruction.get("variant"), instruction.get("tag")
                _require(
                    isinstance(type_name, str)
                    and type_name in variants
                    and tag in variants[type_name],
                    "E_A1_VARIANT_TAG",
                    "unknown variant tag",
                    iloc,
                )
            if op == "match_value":
                type_name, arms = instruction.get("variant"), instruction.get("arms")
                _require(
                    isinstance(type_name, str) and type_name in variants and isinstance(arms, dict),
                    "E_A1_MATCH",
                    "invalid match",
                    iloc,
                )
                assert isinstance(type_name, str) and isinstance(arms, dict)
                _require(
                    set(arms) == variants[type_name],
                    "E_A1_MATCH_EXHAUSTIVE",
                    "match must be exhaustive",
                    iloc,
                )
        result = function.get("return")
        _require(result in values, "E_A1_RETURN", "return references unknown value", location)
    _require(all(entry in names for entry in entries), "E_A1_ENTRY", "unknown entry", "entries")
    function_table = {function["name"]: function for function in functions}
    graph: dict[str, set[str]] = {name: set() for name in function_table}
    for function in functions:
        for index, instruction in enumerate(function["body"]):
            location = f"functions.{function['name']}.body[{index}]"
            op = instruction["op"]
            if op == "call":
                callee = instruction.get("callee")
                _require(callee in function_table, "E_A1_CALL", "unknown callee", location)
                assert isinstance(callee, str)
                graph[function["name"]].add(callee)
                arguments = instruction.get("args", [])
                _require(
                    isinstance(arguments, list)
                    and len(arguments) == len(function_table[callee].get("params", [])),
                    "E_A1_CALL",
                    "call argument arity differs",
                    location,
                )
            if op in {"bounded_map", "bounded_fold"}:
                callback = instruction.get("callback")
                _require(
                    callback in function_table,
                    "E_A1_CALLBACK_TYPE",
                    "callback must be a static function",
                    location,
                )
                assert isinstance(callback, str)
                graph[function["name"]].add(callback)
                expected = 1 if op == "bounded_map" else 2
                _require(
                    len(function_table[callback].get("params", [])) == expected,
                    "E_A1_CALLBACK_TYPE",
                    "callback arity differs",
                    location,
                )
            if op == "refine_nat":
                _require(
                    instruction.get("evidence") == {"predicate": ">=0", "rule": "A1-C004"},
                    "E_A1_REFINEMENT",
                    "Nat refinement evidence is missing",
                    location,
                )

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(name: str) -> None:
        if name in visiting:
            raise A1IRError("E_A1_CALL_CYCLE", "call graph must be acyclic", name)
        if name in visited:
            return
        visiting.add(name)
        for child in sorted(graph[name]):
            visit(child)
        visiting.remove(name)
        visited.add(name)

    for name in sorted(graph):
        visit(name)
    return module
