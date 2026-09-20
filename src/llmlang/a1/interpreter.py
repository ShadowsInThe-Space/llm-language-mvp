"""Deterministic reference interpreter for canonical A1 IR."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from llmlang.a1.ir import A1IRError, validate_module
from llmlang.a1.typecheck import A1TypeError, validate_runtime_arguments


@dataclass(frozen=True)
class A1Limits:
    max_steps: int = 10_000
    max_collection_expansion: int = 1_000
    max_call_depth: int = 64


def _lookup(env: dict[str, Any], value: Any) -> Any:
    if isinstance(value, dict) and set(value) == {"ref"}:
        name = value["ref"]
        if name not in env:
            raise A1IRError("E_A1_REFERENCE", "unknown value reference")
        return env[name]
    return value


def _text(value: Any, capacity: int) -> str:
    if not isinstance(value, str) or "\x00" in value:
        raise A1IRError("E_A1_TEXT_SCALAR", "invalid text scalar")
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise A1IRError("E_A1_TEXT_SCALAR", "invalid text scalar") from exc
    if len(encoded) > capacity:
        raise A1IRError("E_A1_TEXT_CAPACITY", "text capacity exceeded")
    return value


def interpret(
    module: dict[str, Any], entry: str, arguments: list[Any], limits: A1Limits | None = None
) -> Any:
    validated = validate_module(module)
    try:
        validate_runtime_arguments(validated, entry, arguments)
    except A1TypeError as exc:
        raise A1IRError(exc.code, str(exc), exc.location) from exc
    functions = {function["name"]: function for function in validated["functions"]}
    budget = {"steps": 0, "collection": 0}
    declared = A1Limits(
        max_steps=validated["limits"]["max_steps"],
        max_collection_expansion=validated["limits"]["max_collection_expansion"],
        max_call_depth=validated["limits"]["max_call_depth"],
    )
    configured = (
        declared
        if limits is None
        else A1Limits(
            max_steps=min(declared.max_steps, limits.max_steps),
            max_collection_expansion=min(
                declared.max_collection_expansion, limits.max_collection_expansion
            ),
            max_call_depth=min(declared.max_call_depth, limits.max_call_depth),
        )
    )

    def call(name: str, args: list[Any], depth: int) -> Any:
        if depth > configured.max_call_depth:
            raise A1IRError("E_A1_CALL_DEPTH", "call depth exhausted")
        if name not in functions:
            raise A1IRError("E_A1_CALL", "unknown callee")
        function = functions[name]
        params = function.get("params", [])
        if len(params) != len(args):
            raise A1IRError("E_A1_CALL", "argument arity differs")
        env = {param["name"]: arg for param, arg in zip(params, args, strict=True)}
        for instruction in function["body"]:
            budget["steps"] += 1
            if budget["steps"] > configured.max_steps:
                raise A1IRError("E_A1_STEP_LIMIT", "step budget exhausted")
            op = instruction["op"]
            value: Any
            if op == "const":
                value = instruction.get("value")
                if instruction.get("type", {}).get("kind") == "text":
                    value = _text(value, instruction["type"]["capacity"])
            elif op == "record_make":
                value = {
                    "record": instruction["record"],
                    "fields": {
                        key: _lookup(env, item) for key, item in instruction["fields"].items()
                    },
                }
            elif op == "record_get":
                record = _lookup(env, instruction["value"])
                if not isinstance(record, dict) or record.get("record") != instruction["record"]:
                    raise A1IRError("E_A1_NOMINAL", "record type differs")
                value = record["fields"][instruction["field"]]
            elif op == "variant_make":
                value = {
                    "variant": instruction["variant"],
                    "tag": instruction["tag"],
                    "value": _lookup(env, instruction.get("value")),
                }
            elif op == "match_value":
                variant = _lookup(env, instruction["value"])
                value = _lookup(env, instruction["arms"][variant["tag"]])
            elif op == "list_empty":
                value = {"list": [], "capacity": instruction["capacity"]}
            elif op == "list_append":
                source, item = _lookup(env, instruction["list"]), _lookup(env, instruction["value"])
                if len(source["list"]) >= source["capacity"]:
                    value = {"tag": "Err", "value": {"tag": "CapacityError"}}
                else:
                    value = {
                        "tag": "Ok",
                        "value": {"list": [*source["list"], item], "capacity": source["capacity"]},
                    }
            elif op == "list_index":
                source, index = (
                    _lookup(env, instruction["list"]),
                    _lookup(env, instruction["index"]),
                )
                value = (
                    {"tag": "Some", "value": source["list"][index]}
                    if isinstance(index, int) and 0 <= index < len(source["list"])
                    else {"tag": "None", "value": None}
                )
            elif op in {"bounded_map", "bounded_fold"}:
                source = _lookup(env, instruction["list"])
                budget["collection"] += len(source["list"])
                if budget["collection"] > configured.max_collection_expansion:
                    raise A1IRError("E_A1_COLLECTION_LIMIT", "collection budget exhausted")
                if op == "bounded_map":
                    items = [
                        call(instruction["callback"], [item], depth + 1) for item in source["list"]
                    ]
                    value = {"list": items, "capacity": source["capacity"]}
                else:
                    value = _lookup(env, instruction["initial"])
                    for item in source["list"]:
                        value = call(instruction["callback"], [value, item], depth + 1)
            elif op == "text_utf8_bytes":
                value = len(_lookup(env, instruction["value"]).encode("utf-8"))
            elif op == "text_codepoint_count":
                value = len(_lookup(env, instruction["value"]))
            elif op == "text_prefix_codepoints":
                value = _lookup(env, instruction["value"])[: _lookup(env, instruction["count"])]
            elif op == "text_concat":
                value = _text(
                    _lookup(env, instruction["left"]) + _lookup(env, instruction["right"]),
                    instruction["capacity"],
                )
            elif op == "refine_nat":
                candidate = _lookup(env, instruction["value"])
                if not isinstance(candidate, int) or isinstance(candidate, bool) or candidate < 0:
                    raise A1IRError("E_A1_REFINEMENT", "Nat requires non-negative Int")
                value = candidate
            elif op == "add":
                value = _lookup(env, instruction["left"]) + _lookup(env, instruction["right"])
            elif op == "call":
                value = call(
                    instruction["callee"],
                    [_lookup(env, arg) for arg in instruction.get("args", [])],
                    depth + 1,
                )
            else:  # pragma: no cover - validator rejects this
                raise A1IRError("E_A1_OP", "unknown operation")
            env[instruction["dest"]] = value
        return env[function["return"]]

    return call(entry, arguments, 0)
