# ruff: noqa: E501
"""Additive portable pure A1 runtime; the historical Node target is unchanged."""

from __future__ import annotations

import json
from typing import Any

from llmlang.a1.ir import canonical_bytes, validate_module
from llmlang.a1.target import _reject_unsafe_integers
from llmlang.a1.typecheck import Type, _declarations, _runtime, _type

RUNTIME_VERSION = "a1-pure-runtime-v1"
MAX_RUNTIME_STEPS = 100_000
MAX_RUNTIME_COLLECTION = 10_000
MAX_RUNTIME_CALL_DEPTH = 64
MAX_RUNTIME_VALUE_NODES = 100_000
MAX_RUNTIME_TEXT_BYTES = 1_048_576
MAX_RUNTIME_TEXT_WORK = 4_194_304
MAX_RUNTIME_MODULE_BYTES = 131_072
MAX_RUNTIME_FUNCTIONS = 64


class A1RuntimeError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _program(module: dict[str, Any], entries: tuple[str, ...]) -> dict[str, Any]:
    """Infer checked SSA result types for the runtime's independent value monitor."""
    records, variants = _declarations(module)
    names_r, names_v = set(records), set(variants)

    def resolve(raw: Any) -> Type:
        return _type(raw, names_r, names_v)

    results = {f["name"]: resolve(f["result"]) for f in module["functions"]}
    parameter_types = {f["name"]: [resolve(p["type"]) for p in f["params"]] for f in module["functions"]}

    def literal(value: Any, expected: Type, *, allow_ref: bool = True) -> None:
        if allow_ref and isinstance(value, dict) and set(value) == {"ref"}:
            return
        try:
            _runtime(value, expected, records, variants, "literal")

            def strict(item: Any, type_: Type, depth: int = 0) -> None:
                if depth > 64:
                    raise ValueError("literal depth")
                kind = type_[0]
                if kind == "list":
                    if type(item["capacity"]) is not int:
                        raise ValueError("exact list capacity")
                    for child in item["list"]:
                        strict(child, type_[1], depth + 1)
                elif kind == "record":
                    for field, field_type in records[type_[1]].items():
                        strict(item["fields"][field], field_type, depth + 1)
                elif kind == "variant":
                    payload = variants[type_[1]][item["tag"]]
                    if payload is not None:
                        strict(item["value"], payload, depth + 1)
                elif kind == "option" and item["tag"] == "Some":
                    strict(item["value"], type_[1], depth + 1)
                elif kind == "result":
                    strict(item["value"], type_[1] if item["tag"] == "Ok" else type_[2], depth + 1)

            strict(value, expected)
        except (ValueError, KeyError, TypeError, RecursionError) as error:
            raise A1RuntimeError("E_A1_VALUE_LITERAL", "Malformed typed literal") from error

    functions = []
    for function in module["functions"]:
        env = {p["name"]: resolve(p["type"]) for p in function["params"]}

        def operand(value: Any, bound_env: dict[str, Type] = env) -> Type:
            if isinstance(value, dict) and set(value) == {"ref"}:
                return bound_env[value["ref"]]
            if type(value) is int:
                return ("int",)
            if type(value) is bool:
                return ("bool",)
            return ("unknown",)

        body = []
        for instruction in function["body"]:
            op = instruction["op"]
            if "type" in instruction:
                result = resolve(instruction["type"])
            elif op == "record_make":
                result = ("record", instruction["record"])
            elif op == "record_get":
                result = records[instruction["record"]][instruction["field"]]
            elif op == "variant_make":
                result = ("variant", instruction["variant"])
            elif op == "list_append":
                result = ("result", operand(instruction["list"]), ("variant", "CapacityError"))
            elif op == "list_index":
                result = ("option", operand(instruction["list"])[1])
            elif op == "bounded_map":
                result = ("list", results[instruction["callback"]], operand(instruction["list"])[2])
            elif op in {"bounded_fold", "call"}:
                result = results[instruction["callback"] if op == "bounded_fold" else instruction["callee"]]
            elif op in {"text_utf8_bytes", "text_codepoint_count", "refine_nat"}:
                result = ("nat",)
            elif op == "text_prefix_codepoints":
                result = operand(instruction["value"])
            elif op == "text_concat":
                result = ("text", instruction.get("capacity", operand(instruction["left"])[1] + operand(instruction["right"])[1]))
            elif op == "add":
                result = ("nat",) if operand(instruction["left"]) == ("nat",) else ("int",)
            else:
                raise A1RuntimeError("E_A1_OP", "Unsupported pure runtime operation")
            if op == "const":
                literal(instruction.get("value"), result, allow_ref=False)
            elif op == "record_make":
                for field, raw in instruction["fields"].items():
                    literal(raw, records[instruction["record"]][field])
            elif op in {"record_get", "match_value"}:
                literal(instruction["value"], ("record", instruction["record"]) if op == "record_get" else ("variant", instruction["variant"]))
                if op == "match_value":
                    for arm in instruction["arms"].values():
                        literal(arm, result)
            elif op == "variant_make":
                payload = variants[instruction["variant"]][instruction["tag"]]
                if payload is not None:
                    literal(instruction["value"], payload)
            elif op == "list_append":
                literal(instruction["value"], operand(instruction["list"])[1])
            elif op == "list_index":
                literal(instruction["index"], ("nat",))
            elif op == "bounded_fold":
                literal(instruction["initial"], result)
            elif op == "text_prefix_codepoints":
                literal(instruction["count"], ("nat",))
            elif op == "refine_nat":
                literal(instruction["value"], ("int",))
            elif op == "add":
                literal(instruction["left"], result)
                literal(instruction["right"], result)
            elif op == "call":
                for raw, expected in zip(instruction.get("args", []), parameter_types[instruction["callee"]], strict=True):
                    literal(raw, expected)
            env[instruction["dest"]] = result
            item = dict(instruction)
            item["value_type"] = result
            if op == "const":
                item["value"] = instruction.get("value")
            if op == "call":
                item["args"] = instruction.get("args", [])
            if op == "text_concat":
                item["capacity"] = result[1]
            body.append(item)
        functions.append({
            "name": function["name"],
            "params": [{"name": p["name"], "value_type": resolve(p["type"])} for p in function["params"]],
            "result": results[function["name"]], "body": body, "return": function["return"],
        })
    return {
        "version": RUNTIME_VERSION, "entries": entries, "limits": module["limits"],
        "functions": functions, "records": list(records.items()),
        "variants": list(variants.items()),
    }


def _prepare(module: dict[str, Any], entries: tuple[str, ...]) -> dict[str, Any]:
    pending = [(module, 0)]
    count = 0
    while pending:
        value, depth = pending.pop()
        count += 1
        if depth > 128 or count > 20000:
            raise A1RuntimeError("E_A1_RUNTIME_LIMIT", "Pure module structure budget exceeded")
        if isinstance(value, dict):
            if count + len(pending) + len(value) > 20000:
                raise A1RuntimeError("E_A1_RUNTIME_LIMIT", "Pure module structure budget exceeded")
            pending.extend((child, depth + 1) for child in value.values())
        elif isinstance(value, (list, tuple)):
            if count + len(pending) + len(value) > 20000:
                raise A1RuntimeError("E_A1_RUNTIME_LIMIT", "Pure module structure budget exceeded")
            pending.extend((child, depth + 1) for child in value)
    try:
        encoded = canonical_bytes(module)
    except (RecursionError, ValueError) as error:
        raise A1RuntimeError("E_A1_RUNTIME_LIMIT", "Pure module cannot be serialized safely") from error
    if len(encoded) > MAX_RUNTIME_MODULE_BYTES:
        raise A1RuntimeError("E_A1_RUNTIME_LIMIT", "Pure module byte budget exceeded")
    validated = validate_module(module)
    if len(validated["functions"]) > MAX_RUNTIME_FUNCTIONS:
        raise A1RuntimeError("E_A1_RUNTIME_LIMIT", "Pure module function budget exceeded")
    ceilings = {
        "max_steps": MAX_RUNTIME_STEPS,
        "max_collection_expansion": MAX_RUNTIME_COLLECTION,
        "max_call_depth": MAX_RUNTIME_CALL_DEPTH,
    }
    if any(validated["limits"][key] > maximum for key, maximum in ceilings.items()):
        raise A1RuntimeError("E_A1_RUNTIME_LIMIT", "Declared runtime limit exceeds portable ceiling")
    if type(entries) is not tuple or any(type(name) is not str for name in entries):
        raise A1RuntimeError("E_A1_ENTRY", "Explicit entry tuple required")
    if len(set(entries)) != len(entries) or any(name not in validated["entrypoints"] for name in entries):
        raise A1RuntimeError("E_A1_ENTRY", "Pure runtime whitelist differs from declared entries")
    _reject_unsafe_integers(validated)
    return _program(validated, entries)


def validate_runtime_module(module: dict[str, Any], entries: tuple[str, ...] = ()) -> None:
    """Share emitter admission checks with the application compiler without emitting code."""
    _prepare(module, entries)


def emit_typescript_runtime(module: dict[str, Any], entries: tuple[str, ...]) -> str:
    """Emit a checked pure module with explicit allowed entries and trusted ceilings."""
    program = _prepare(module, entries)
    serialized = canonical_bytes(program).decode("ascii")
    literal = json.dumps(serialized, ensure_ascii=True).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return _RUNTIME.replace("__PROGRAM_LITERAL__", literal)


_RUNTIME = r'''// a1-pure-runtime-v1: checked data, portable web primitives, no dynamic code.
export const RUNTIME_VERSION = "a1-pure-runtime-v1";
type ValueType = readonly unknown[];
type Instruction = {op: string; dest: string; value_type: ValueType; [key: string]: unknown};
type FunctionDef = {name: string; params: {name: string; value_type: ValueType}[]; result: ValueType; body: Instruction[]; return: string};
type Program = {entries: string[]; functions: FunctionDef[]; records: [string, Record<string, ValueType>][]; variants: [string, Record<string, ValueType | null>][]; limits: {max_steps: number; max_collection_expansion: number; max_call_depth: number}};
const program = JSON.parse(__PROGRAM_LITERAL__) as Program;
const functions = new Map(program.functions.map(f => [f.name, f]));
const records = new Map(program.records.map(([name, fields]) => [name, new Map(Object.entries(fields))]));
const variants = new Map(program.variants.map(([name, cases]) => [name, new Map(Object.entries(cases))]));
const entries = new Set(program.entries);
export class PureRuntimeError extends Error {
  readonly code: string;
  constructor(code: string) { super(code); this.code = code; }
}
function fail(code: string): never { throw new PureRuntimeError(code); }
type Budget = {steps: number; collection: number; values: number; text: number};
function integer(value: unknown): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || Object.is(value, -0)) fail("E_A1_UNSAFE_INTEGER");
  return value;
}
function object(value: unknown): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) fail("E_A1_TYPE");
  const prototype = Object.getPrototypeOf(value);
  if (prototype !== null && prototype !== Object.prototype) fail("E_A1_TYPE");
  for (const key of Reflect.ownKeys(value)) {
    if (typeof key !== "string" || !Object.hasOwn(Object.getOwnPropertyDescriptor(value, key)!, "value")) fail("E_A1_TYPE");
  }
  return value as Record<string, unknown>;
}
function exact(value: unknown, keys: readonly string[]): Record<string, unknown> {
  const result = object(value);
  if (Reflect.ownKeys(result).length !== keys.length || !keys.every(key => Object.hasOwn(result, key))) fail("E_A1_TYPE");
  return result;
}
function text(value: unknown, capacity: number, budget: Budget): string {
  if (typeof value !== "string") fail("E_A1_TEXT_ENCODING");
  if (value.length > capacity) fail("E_A1_TEXT_CAPACITY");
  if (value.length > 1048576) fail("E_A1_VALUE_LIMIT");
  budget.text += value.length;
  if (budget.text > 4194304) fail("E_A1_VALUE_LIMIT");
  for (let i = 0; i < value.length; i++) {
    const c = value.charCodeAt(i);
    if (c === 0) fail("E_A1_TEXT_ENCODING");
    if (c >= 0xd800 && c <= 0xdbff) {
      const next = value.charCodeAt(++i);
      if (!(next >= 0xdc00 && next <= 0xdfff)) fail("E_A1_TEXT_ENCODING");
    } else if (c >= 0xdc00 && c <= 0xdfff) fail("E_A1_TEXT_ENCODING");
  }
  const size = new TextEncoder().encode(value).length;
  budget.text += size - value.length;
  if (budget.text > 4194304) fail("E_A1_VALUE_LIMIT");
  if (size > capacity) fail("E_A1_TEXT_CAPACITY");
  if (size > 1048576) fail("E_A1_VALUE_LIMIT");
  return value;
}
function checked(t: ValueType, value: unknown, budget: Budget, depth = 0): unknown {
  if (++budget.values > 100000 || depth > 64) fail("E_A1_VALUE_LIMIT");
  switch (t[0]) {
    case "unit": if (value !== null) fail("E_A1_TYPE"); return null;
    case "bool": if (typeof value !== "boolean") fail("E_A1_TYPE"); return value;
    case "int": return integer(value);
    case "nat": { const n = integer(value); if (n < 0) fail("E_A1_NAT"); return n; }
    case "text": return text(value, t[1] as number, budget);
    case "record": {
      const row = exact(value, ["record", "fields"]), definition = records.get(t[1] as string);
      if (row.record !== t[1] || !definition) fail("E_A1_TYPE");
      const source = exact(row.fields, [...definition.keys()]);
      const fields: Record<string, unknown> = Object.create(null);
      for (const [name, type] of definition) fields[name] = checked(type, source[name], budget, depth + 1);
      return {record: t[1], fields};
    }
    case "variant": {
      const variant = object(value), definition = variants.get(t[1] as string);
      if (!definition) fail("E_A1_TYPE");
      // Frozen append error representation is a single compact builtin tag.
      if (t[1] === "CapacityError" && definition.size === 1 && definition.get("CapacityError") === null
        && Reflect.ownKeys(variant).length === 1 && variant.tag === "CapacityError") return {tag: "CapacityError"};
      if (variant.variant !== t[1] || typeof variant.tag !== "string" || !definition.has(variant.tag)) fail("E_A1_TYPE");
      const payload = definition.get(variant.tag)!;
      if (payload === null) {
        exact(variant, Object.hasOwn(variant, "value") ? ["variant", "tag", "value"] : ["variant", "tag"]);
        if (Object.hasOwn(variant, "value") && variant.value !== null) fail("E_A1_TYPE");
        return Object.hasOwn(variant, "value") ? {variant: t[1], tag: variant.tag, value: null} : {variant: t[1], tag: variant.tag};
      }
      exact(variant, ["variant", "tag", "value"]);
      return {variant: t[1], tag: variant.tag, value: checked(payload, variant.value, budget, depth + 1)};
    }
    case "list": {
      const list = exact(value, ["list", "capacity"]), capacity = t[2] as number;
      if (typeof list.capacity !== "number" || !Number.isSafeInteger(list.capacity) || list.capacity !== capacity || !Array.isArray(list.list)) fail("E_A1_TYPE");
      if (list.list.length > capacity) fail("E_A1_LIST_BOUNDS");
      if (list.list.length > 100000) fail("E_A1_VALUE_LIMIT");
      const items: unknown[] = [];
      for (let i = 0; i < list.list.length; i++) {
        if (!Object.hasOwn(list.list, i)) fail("E_A1_TYPE");
        items.push(checked(t[1] as ValueType, list.list[i], budget, depth + 1));
      }
      return {list: items, capacity};
    }
    case "option": {
      const option = object(value);
      if (option.tag === "None") {
        exact(option, Object.hasOwn(option, "value") ? ["tag", "value"] : ["tag"]);
        if (Object.hasOwn(option, "value") && option.value !== null) fail("E_A1_TYPE");
        return Object.hasOwn(option, "value") ? {tag: "None", value: null} : {tag: "None"};
      }
      exact(option, ["tag", "value"]); if (option.tag !== "Some") fail("E_A1_TYPE");
      return {tag: "Some", value: checked(t[1] as ValueType, option.value, budget, depth + 1)};
    }
    case "result": {
      const result = exact(value, ["tag", "value"]);
      if (result.tag !== "Ok" && result.tag !== "Err") fail("E_A1_TYPE");
      return {tag: result.tag, value: checked(t[result.tag === "Ok" ? 1 : 2] as ValueType, result.value, budget, depth + 1)};
    }
    default: return fail("E_A1_TYPE");
  }
}
function operand(env: Map<string, unknown>, raw: unknown): unknown {
  if (raw !== null && typeof raw === "object" && !Array.isArray(raw)
    && Reflect.ownKeys(raw).length === 1 && Object.hasOwn(raw, "ref")) {
    const name = (raw as {ref: unknown}).ref;
    if (typeof name !== "string" || !env.has(name)) fail("E_A1_REFERENCE");
    return env.get(name);
  }
  return raw;
}
function call(name: string, args: readonly unknown[], budget: Budget, depth: number): unknown {
  if (depth > program.limits.max_call_depth) fail("E_A1_CALL_DEPTH");
  const f = functions.get(name); if (!f || args.length !== f.params.length) fail("E_A1_CALL");
  const env = new Map<string, unknown>();
  for (let i = 0; i < args.length; i++) env.set(f.params[i].name, checked(f.params[i].value_type, args[i], budget));
  for (const i of f.body) {
    if (++budget.steps > program.limits.max_steps) fail("E_A1_STEP_LIMIT");
    const get = (key: string) => operand(env, i[key]);
    let value: unknown;
    switch (i.op) {
      case "const": value = i.value; break;
      case "record_make": {
        const fields: Record<string, unknown> = Object.create(null);
        for (const [name, raw] of Object.entries(i.fields as Record<string, unknown>)) fields[name] = operand(env, raw);
        value = {record: i.record, fields}; break;
      }
      case "record_get": value = object(object(checked(["record", i.record], get("value"), budget)).fields)[i.field as string]; break;
      case "variant_make": value = {variant: i.variant, tag: i.tag, value: Object.hasOwn(i, "value") ? get("value") : null}; break;
      case "match_value": {
        const tag = object(checked(["variant", i.variant], get("value"), budget)).tag;
        const arms = i.arms as Record<string, unknown>;
        if (typeof tag !== "string" || !Object.hasOwn(arms, tag)) fail("E_A1_TYPE");
        value = operand(env, arms[tag]); break;
      }
      case "list_empty": value = {list: [], capacity: i.capacity}; break;
      case "list_append": {
        const list = object(get("list")) as {list: unknown[]; capacity: number};
        value = list.list.length >= list.capacity ? {tag: "Err", value: {tag: "CapacityError"}}
          : {tag: "Ok", value: {list: [...list.list, get("value")], capacity: list.capacity}};
        break;
      }
      case "list_index": {
        const list = object(get("list")) as {list: unknown[]; capacity: number}, n = integer(get("index"));
        value = n >= 0 && n < list.list.length ? {tag: "Some", value: list.list[n]} : {tag: "None", value: null}; break;
      }
      case "bounded_map": case "bounded_fold": {
        const list = object(get("list")) as {list: unknown[]; capacity: number};
        budget.collection += list.list.length;
        if (budget.collection > program.limits.max_collection_expansion) fail("E_A1_COLLECTION_LIMIT");
        if (i.op === "bounded_map") value = {list: list.list.map(item => call(i.callback as string, [item], budget, depth + 1)), capacity: list.capacity};
        else { value = get("initial"); for (const item of list.list) value = call(i.callback as string, [value, item], budget, depth + 1); }
        break;
      }
      case "text_utf8_bytes": value = new TextEncoder().encode(text(get("value"), Number.MAX_SAFE_INTEGER, budget)).length; break;
      case "text_codepoint_count": value = Array.from(text(get("value"), Number.MAX_SAFE_INTEGER, budget)).length; break;
      case "text_prefix_codepoints": value = Array.from(text(get("value"), Number.MAX_SAFE_INTEGER, budget)).slice(0, integer(get("count"))).join(""); break;
      case "text_concat": value = text(text(get("left"), Number.MAX_SAFE_INTEGER, budget) + text(get("right"), Number.MAX_SAFE_INTEGER, budget), i.capacity as number, budget); break;
      case "refine_nat": { const natural = integer(get("value")); if (natural < 0) fail("E_A1_REFINEMENT"); value = natural; break; }
      case "add": value = integer(integer(get("left")) + integer(get("right"))); break;
      case "call": value = call(i.callee as string, (i.args as unknown[]).map(raw => operand(env, raw)), budget, depth + 1); break;
      default: fail("E_A1_OP");
    }
    env.set(i.dest, checked(i.value_type, value, budget));
  }
  if (!env.has(f.return)) fail("E_A1_REFERENCE");
  return checked(f.result, env.get(f.return), budget);
}
export function invokePure(name: string, args: readonly unknown[]): unknown {
  if (typeof name !== "string" || !entries.has(name)) fail("E_A1_ENTRY");
  if (!Array.isArray(args)) fail("E_A1_CALL");
  return call(name, args, {steps: 0, collection: 0, values: 0, text: 0}, 0);
}
'''
