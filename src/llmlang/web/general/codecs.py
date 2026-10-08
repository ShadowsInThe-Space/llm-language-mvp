# ruff: noqa: E501
"""Closed bounded wire codecs shared by the Python and browser/worker targets.

Integers cross JSON as canonical decimal strings, never lossy JSON numbers.
The target profile deliberately accepts only exact JavaScript-safe integers.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import NoReturn, cast

from llmlang.diagnostics import diagnostic

MAX_SAFE_INTEGER = 9_007_199_254_740_991
CODEC_VERSION = "web-codecs-v1"
MAX_WIRE_BYTES = 32768
MAX_TEXT_BYTES = 32768
MAX_LIST_CAPACITY = 4096
MAX_DEPTH = 32
MAX_NODES = 4096
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_.:-]{0,127}\Z")
_FIELD = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}\Z")
_DECIMAL = re.compile(r"(?:0|-?[1-9][0-9]*)\Z")


class CodecError(ValueError):
    """A stable diagnostic with no external values in its message."""

    def __init__(self, code: str, message: str, path: str = "value") -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.path = path

    def to_dict(self) -> dict[str, object]:
        return diagnostic({"code": self.code, "message": self.message, "path": self.path})


@dataclass(frozen=True, slots=True)
class TextType:
    capacity: int


@dataclass(frozen=True, slots=True)
class IntType:
    pass


@dataclass(frozen=True, slots=True)
class NatType:
    pass


@dataclass(frozen=True, slots=True)
class BoolType:
    pass


@dataclass(frozen=True, slots=True)
class OptionType:
    item: CodecType


@dataclass(frozen=True, slots=True)
class ListType:
    item: CodecType
    capacity: int


@dataclass(frozen=True, slots=True)
class RecordType:
    name: str
    fields: tuple[tuple[str, CodecType], ...]


type ScalarType = TextType | IntType | NatType | BoolType
type CodecType = ScalarType | OptionType | ListType | RecordType


def _fail(code: str, message: str, path: str) -> NoReturn:
    raise CodecError(code, message, path)


class _Budget:
    def __init__(self) -> None:
        self.nodes = 0

    def visit(self, depth: int, path: str) -> None:
        self.nodes += 1
        if depth > MAX_DEPTH or self.nodes > MAX_NODES:
            _fail("W_CODEC_LIMIT", "Codec depth or node budget exceeded", path)


def validate_type(codec: CodecType) -> None:
    """Check the complete immutable descriptor, including unused record fields."""
    budget = _Budget()

    def visit(item: CodecType, depth: int) -> None:
        budget.visit(depth, "type")
        if type(item) in (IntType, NatType, BoolType):
            return
        if type(item) is TextType:
            if type(item.capacity) is not int or not 0 <= item.capacity <= MAX_TEXT_BYTES:
                _fail("W_CODEC_TYPE", "Invalid text capacity", "type")
        elif type(item) is ListType:
            if type(item.capacity) is not int or not 0 <= item.capacity <= MAX_LIST_CAPACITY:
                _fail("W_CODEC_TYPE", "Invalid list capacity", "type")
            visit(item.item, depth + 1)
        elif type(item) is OptionType:
            visit(item.item, depth + 1)
        elif type(item) is RecordType:
            if type(item.name) is not str or _NAME.fullmatch(item.name) is None:
                _fail("W_CODEC_TYPE", "Invalid nominal record name", "type")
            if type(item.fields) is not tuple or not item.fields or len(item.fields) > MAX_NODES:
                _fail("W_CODEC_TYPE", "Invalid record fields", "type")
            names: set[str] = set()
            for field in item.fields:
                if type(field) is not tuple or len(field) != 2:
                    _fail("W_CODEC_TYPE", "Invalid record field", "type")
                name, child = field
                if type(name) is not str or _FIELD.fullmatch(name) is None or name in names:
                    _fail("W_CODEC_TYPE", "Invalid or duplicate record field", "type")
                names.add(name)
                visit(child, depth + 1)
        else:
            _fail("W_CODEC_TYPE", "Unknown codec type", "type")

    visit(codec, 1)


def type_descriptor(codec: CodecType) -> dict[str, object]:
    """Return the closed portable descriptor consumed by the TS runtime."""
    validate_type(codec)

    def describe(item: CodecType) -> dict[str, object]:
        if isinstance(item, TextType):
            return {"kind": "text", "capacity": item.capacity}
        if isinstance(item, IntType):
            return {"kind": "int"}
        if isinstance(item, NatType):
            return {"kind": "nat"}
        if isinstance(item, BoolType):
            return {"kind": "bool"}
        if isinstance(item, OptionType):
            return {"kind": "option", "elem": describe(item.item)}
        if isinstance(item, ListType):
            return {"kind": "list", "elem": describe(item.item), "capacity": item.capacity}
        assert isinstance(item, RecordType)
        return {
            "kind": "record",
            "name": item.name,
            "fields": [{"name": name, "type": describe(child)} for name, child in item.fields],
        }

    return describe(codec)


def max_wire_bytes(codec: CodecType) -> int:
    """Bound canonical ASCII wire bytes, including all structural envelopes.

    Counts use exact bounded-size Python integers and deliberately overapproximate
    values excluded by independent node/depth limits. No value is constructed.
    """
    validate_type(codec)

    def bound(item: CodecType) -> int:
        if isinstance(item, TextType):
            # A valid one-byte control scalar can require six ASCII escape bytes.
            return 2 + 6 * item.capacity
        if isinstance(item, IntType):
            return 19  # quotes, optional minus sign, sixteen safe decimal digits
        if isinstance(item, NatType):
            return 18
        if isinstance(item, BoolType):
            return 5  # false
        if isinstance(item, OptionType):
            return max(27, 23 + bound(item.item))
        if isinstance(item, ListType):
            return 2 + item.capacity * bound(item.item) + max(0, item.capacity - 1)
        assert isinstance(item, RecordType)
        # IDs/field names are checked ASCII identifiers and require no escaping.
        envelope = len('{"fields":{},"record":""}') + len(item.name)
        fields = sum(len(name) + 3 + bound(child) for name, child in item.fields)
        return envelope + fields + len(item.fields) - 1

    return bound(codec)


def _object(value: object, keys: set[str], path: str) -> dict[str, object]:
    if type(value) is not dict or set(value) != keys:
        _fail("W_CODEC_VALUE", "Exact object fields required", path)
    return cast(dict[str, object], value)


def _text(value: object, capacity: int, path: str) -> str:
    if type(value) is not str:
        _fail("W_CODEC_TEXT", "Valid Unicode scalar text required", path)
    if len(value) > capacity:
        _fail("W_CODEC_CAPACITY", "UTF-8 text capacity exceeded", path)
    if "\0" in value:
        _fail("W_CODEC_TEXT", "Valid Unicode scalar text required", path)
    try:
        size = len(value.encode("utf-8"))
    except UnicodeError:
        _fail("W_CODEC_TEXT", "Valid Unicode scalar text required", path)
    if size > capacity:
        _fail("W_CODEC_CAPACITY", "UTF-8 text capacity exceeded", path)
    return value


def _integer(value: object, *, decode: bool, natural: bool, path: str) -> int | str:
    if decode:
        if type(value) is not str or _DECIMAL.fullmatch(value) is None:
            _fail("W_CODEC_INTEGER", "Canonical decimal integer string required", path)
        # Check length before int() to avoid unbounded conversion and Python digit limits.
        digits = value.removeprefix("-")
        if len(digits) > 16 or (len(digits) == 16 and digits > str(MAX_SAFE_INTEGER)):
            _fail("W_CODEC_INTEGER", "Integer exceeds target's exact range", path)
        number = int(value)
    else:
        if type(value) is not int or abs(value) > MAX_SAFE_INTEGER:
            _fail("W_CODEC_INTEGER", "Exact target integer required", path)
        number = value
    if natural and number < 0:
        _fail("W_CODEC_INTEGER", "Nat must be non-negative", path)
    return number if decode else str(number)


def _transform(codec: CodecType, value: object, *, decode: bool) -> object:
    validate_type(codec)
    budget = _Budget()

    def visit(item: CodecType, current: object, depth: int, path: str) -> object:
        budget.visit(depth, path)
        if isinstance(item, TextType):
            return _text(current, item.capacity, path)
        if isinstance(item, (IntType, NatType)):
            return _integer(current, decode=decode, natural=isinstance(item, NatType), path=path)
        if isinstance(item, BoolType):
            if type(current) is not bool:
                _fail("W_CODEC_VALUE", "Bool required", path)
            return current
        if isinstance(item, OptionType):
            option = _object(current, {"tag", "value"}, path)
            if option["tag"] == "None" and option["value"] is None:
                return {"tag": "None", "value": None}
            if option["tag"] != "Some":
                _fail("W_CODEC_VALUE", "Exact Option constructor required", path)
            return {"tag": "Some", "value": visit(item.item, option["value"], depth + 1, path + ".value")}
        if isinstance(item, ListType):
            if decode:
                elements = current
            else:
                container = _object(current, {"list", "capacity"}, path)
                if type(container["capacity"]) is not int or container["capacity"] != item.capacity:
                    _fail("W_CODEC_VALUE", "Declared list capacity required", path)
                elements = container["list"]
            if type(elements) is not list:
                _fail("W_CODEC_VALUE", "Ordered list required", path)
            if len(elements) > item.capacity:
                _fail("W_CODEC_CAPACITY", "List capacity exceeded", path)
            converted = [
                visit(item.item, child, depth + 1, f"{path}[{index}]")
                for index, child in enumerate(elements)
            ]
            return {"list": converted, "capacity": item.capacity} if decode else converted
        assert isinstance(item, RecordType)
        record = _object(current, {"record", "fields"}, path)
        if type(record["record"]) is not str or record["record"] != item.name:
            _fail("W_CODEC_VALUE", "Nominal record identity differs", path)
        fields = _object(record["fields"], {name for name, _ in item.fields}, path + ".fields")
        return {
            "record": item.name,
            "fields": {
                name: visit(child, fields[name], depth + 1, path + ".fields." + name)
                for name, child in item.fields
            },
        }

    return visit(codec, value, 1, "value")


def encode_value(codec: CodecType, value: object) -> object:
    """Validate a runtime value and convert it to wire data without mutation."""
    return _transform(codec, value, decode=False)


def decode_value(codec: CodecType, value: object) -> object:
    """Decode already-parsed wire data; JSON duplicate detection requires decode_json."""
    return _transform(codec, value, decode=True)


def _json_source(source: str | bytes) -> str:
    if type(source) is bytes:
        if len(source) > MAX_WIRE_BYTES:
            _fail("W_CODEC_LIMIT", "Wire byte budget exceeded", "json")
        try:
            source = source.decode("utf-8")
        except UnicodeError:
            _fail("W_CODEC_JSON", "Valid UTF-8 JSON required", "json")
    if type(source) is not str:
        _fail("W_CODEC_JSON", "JSON text or UTF-8 bytes required", "json")
    if len(source) > MAX_WIRE_BYTES:
        _fail("W_CODEC_LIMIT", "Wire byte budget exceeded", "json")
    try:
        size = len(source.encode("utf-8"))
    except UnicodeError:
        _fail("W_CODEC_JSON", "Valid UTF-8 JSON required", "json")
    if size > MAX_WIRE_BYTES:
        _fail("W_CODEC_LIMIT", "Wire byte budget exceeded", "json")
    # Bound json.loads before recursion/allocation. String contents cannot alter depth.
    depth = 0
    budget = _Budget()
    quoted = escaped = token = False
    for char in source:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
            budget.visit(depth + 1, "json")
            token = False
        elif char in "[{":
            depth += 1
            budget.visit(depth, "json")
            token = False
        elif char in "]}":
            depth -= 1
            token = False
        elif char in " \r\n\t,:":
            token = False
        elif not token:
            budget.visit(depth + 1, "json")
            token = True
    return source


def parse_wire_json(source: str | bytes) -> object:
    """Parse the bounded envelope before selecting its declared action codec."""
    text = _json_source(source)

    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                _fail("W_CODEC_JSON", "Duplicate JSON key", "json")
            result[key] = value
        return result

    def number(_: str) -> NoReturn:
        _fail("W_CODEC_INTEGER", "Wire numbers must be canonical decimal strings", "json")

    try:
        value: object = json.loads(
            text, object_pairs_hook=pairs, parse_int=number, parse_float=number,
            parse_constant=lambda _: _fail("W_CODEC_JSON", "Invalid JSON constant", "json"),
        )
    except (ValueError, RecursionError) as error:
        if isinstance(error, CodecError):
            raise
        raise CodecError("W_CODEC_JSON", "Invalid JSON", "json") from error
    return value


def decode_json(codec: CodecType, source: str | bytes) -> object:
    """Decode bounded JSON, rejecting duplicate decoded keys at every depth."""
    validate_type(codec)
    return decode_value(codec, parse_wire_json(source))


def encode_json(codec: CodecType, value: object) -> str:
    """Produce deterministic ASCII JSON, with the same wire budgets as decoding."""
    wire = encode_value(codec, value)
    source = json.dumps(wire, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":"))
    _json_source(source)
    return source


def emit_typescript_runtime() -> str:
    """Emit the versioned standalone runtime; only standard web globals are used."""
    return _TYPESCRIPT_RUNTIME


_TYPESCRIPT_RUNTIME = r'''// llmlang:web-codecs-v1; browser and Worker standard globals only.
export const CODEC_VERSION = "web-codecs-v1";
export type CodecType =
  | {kind: "text"; capacity: number}
  | {kind: "int" | "nat" | "bool"}
  | {kind: "option"; elem: CodecType}
  | {kind: "list"; elem: CodecType; capacity: number}
  | {kind: "record"; name: string; fields: {name: string; type: CodecType}[]};
export class CodecError extends Error {
  readonly code: string; readonly path: string;
  constructor(code: string, message: string, path = "value") {
    super(message); this.code = code; this.path = path;
  }
}
const MAX_SAFE = 9007199254740991;
const MAX_BYTES = 32768, MAX_LIST = 4096, MAX_DEPTH = 32, MAX_NODES = 4096;
function fail(code: string, message: string, path: string): never {
  throw new CodecError(code, message, path);
}
class Budget {
  nodes = 0;
  visit(depth: number, path: string): void {
    if (++this.nodes > MAX_NODES || depth > MAX_DEPTH)
      fail("W_CODEC_LIMIT", "Codec depth or node budget exceeded", path);
  }
}
function object(value: unknown, keys: string[], path: string, code = "W_CODEC_VALUE"): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value))
    fail(code, "Exact object fields required", path);
  const result = value as Record<string, unknown>;
  if (Object.keys(result).length !== keys.length || !keys.every(k => Object.hasOwn(result, k)))
    fail(code, "Exact object fields required", path);
  return result;
}
export function validateType(type: CodecType): void {
  const budget = new Budget();
  function visit(raw: unknown, depth: number): void {
    budget.visit(depth, "type");
    if (raw === null || typeof raw !== "object" || Array.isArray(raw))
      fail("W_CODEC_TYPE", "Unknown codec type", "type");
    const t = raw as Record<string, unknown>;
    switch (t.kind) {
      case "int": case "nat": case "bool": object(t, ["kind"], "type", "W_CODEC_TYPE"); break;
      case "text": case "list": {
        object(t, t.kind === "text" ? ["kind", "capacity"] : ["kind", "elem", "capacity"], "type", "W_CODEC_TYPE");
        const cap = t.capacity;
        if (typeof cap !== "number" || !Number.isSafeInteger(cap) || cap < 0 || cap > (t.kind === "text" ? MAX_BYTES : MAX_LIST))
          fail("W_CODEC_TYPE", "Invalid capacity", "type");
        if (t.kind === "list") visit(t.elem, depth + 1);
        break;
      }
      case "option": object(t, ["kind", "elem"], "type", "W_CODEC_TYPE"); visit(t.elem, depth + 1); break;
      case "record": {
        object(t, ["kind", "name", "fields"], "type", "W_CODEC_TYPE");
        if (typeof t.name !== "string" || !/^[A-Za-z_][A-Za-z0-9_.:-]{0,127}$/.test(t.name)
          || !Array.isArray(t.fields) || t.fields.length === 0 || t.fields.length > MAX_NODES)
          fail("W_CODEC_TYPE", "Invalid record descriptor", "type");
        const names = new Set<string>();
        for (const rawField of t.fields) {
          const field = object(rawField, ["name", "type"], "type", "W_CODEC_TYPE");
          if (typeof field.name !== "string" || !/^[A-Za-z_][A-Za-z0-9_]{0,63}$/.test(field.name) || names.has(field.name))
            fail("W_CODEC_TYPE", "Invalid or duplicate record field", "type");
          names.add(field.name); visit(field.type, depth + 1);
        }
        break;
      }
      default: fail("W_CODEC_TYPE", "Unknown codec type", "type");
    }
  }
  visit(type, 1);
}
export function maxWireBytes(type: CodecType): bigint {
  validateType(type);
  function bound(t: CodecType): bigint {
    switch (t.kind) {
      case "text": return 2n + 6n * BigInt(t.capacity);
      case "int": return 19n;
      case "nat": return 18n;
      case "bool": return 5n;
      case "option": {
        const some = 23n + bound(t.elem); return some > 27n ? some : 27n;
      }
      case "list": return 2n + BigInt(t.capacity) * bound(t.elem) + BigInt(Math.max(0, t.capacity - 1));
      case "record": {
        let count = BigInt('{"fields":{},"record":""}'.length + t.name.length + t.fields.length - 1);
        for (const field of t.fields) count += BigInt(field.name.length + 3) + bound(field.type);
        return count;
      }
    }
  }
  return bound(type);
}
function scalarText(value: unknown, capacity: number, path: string): string {
  if (typeof value !== "string") fail("W_CODEC_TEXT", "Valid Unicode scalar text required", path);
  if (value.length > capacity) fail("W_CODEC_CAPACITY", "UTF-8 text capacity exceeded", path);
  for (let k = 0; k < value.length; k++) {
    const c = value.charCodeAt(k);
    if (c === 0) fail("W_CODEC_TEXT", "Valid Unicode scalar text required", path);
    if (c >= 0xd800 && c <= 0xdbff) {
      const next = value.charCodeAt(++k);
      if (!(next >= 0xdc00 && next <= 0xdfff)) fail("W_CODEC_TEXT", "Valid Unicode scalar text required", path);
    } else if (c >= 0xdc00 && c <= 0xdfff) fail("W_CODEC_TEXT", "Valid Unicode scalar text required", path);
  }
  if (new TextEncoder().encode(value).length > capacity)
    fail("W_CODEC_CAPACITY", "UTF-8 text capacity exceeded", path);
  return value;
}
function integer(value: unknown, decode: boolean, natural: boolean, path: string): number | string {
  let number: number;
  if (decode) {
    if (typeof value !== "string" || !/^(?:0|-?[1-9][0-9]*)$/.test(value))
      fail("W_CODEC_INTEGER", "Canonical decimal integer string required", path);
    const digits = value.startsWith("-") ? value.slice(1) : value;
    if (digits.length > 16 || (digits.length === 16 && digits > String(MAX_SAFE)))
      fail("W_CODEC_INTEGER", "Integer exceeds target's exact range", path);
    number = Number(value);
  } else {
    if (typeof value !== "number" || !Number.isSafeInteger(value) || Object.is(value, -0))
      fail("W_CODEC_INTEGER", "Exact target integer required", path);
    number = value;
  }
  if (natural && number < 0) fail("W_CODEC_INTEGER", "Nat must be non-negative", path);
  return decode ? number : String(number);
}
function transform(type: CodecType, value: unknown, decode: boolean): unknown {
  validateType(type); const budget = new Budget();
  function visit(t: CodecType, current: unknown, depth: number, path: string): unknown {
    budget.visit(depth, path);
    switch (t.kind) {
      case "text": return scalarText(current, t.capacity, path);
      case "int": case "nat": return integer(current, decode, t.kind === "nat", path);
      case "bool": if (typeof current !== "boolean") fail("W_CODEC_VALUE", "Bool required", path); return current;
      case "option": {
        const option = object(current, ["tag", "value"], path);
        if (option.tag === "None" && option.value === null) return {tag: "None", value: null};
        if (option.tag !== "Some") fail("W_CODEC_VALUE", "Exact Option constructor required", path);
        return {tag: "Some", value: visit(t.elem, option.value, depth + 1, path + ".value")};
      }
      case "list": {
        let elements = current;
        if (!decode) {
          const container = object(current, ["list", "capacity"], path);
          if (typeof container.capacity !== "number" || !Number.isSafeInteger(container.capacity) || container.capacity !== t.capacity)
            fail("W_CODEC_VALUE", "Declared list capacity required", path);
          elements = container.list;
        }
        if (!Array.isArray(elements)) fail("W_CODEC_VALUE", "Ordered list required", path);
        if (elements.length > t.capacity) fail("W_CODEC_CAPACITY", "List capacity exceeded", path);
        const converted = [];
        for (let i = 0; i < elements.length; i++) {
          if (!Object.hasOwn(elements, i)) fail("W_CODEC_VALUE", "Dense list required", path);
          converted.push(visit(t.elem, elements[i], depth + 1, path + "[" + i + "]"));
        }
        return decode ? {list: converted, capacity: t.capacity} : converted;
      }
      case "record": {
        const record = object(current, ["record", "fields"], path);
        if (record.record !== t.name) fail("W_CODEC_VALUE", "Nominal record identity differs", path);
        const original = object(record.fields, t.fields.map(f => f.name), path + ".fields");
        const fields: Record<string, unknown> = Object.create(null);
        for (const field of t.fields) fields[field.name] = visit(field.type, original[field.name], depth + 1, path + ".fields." + field.name);
        return {record: t.name, fields};
      }
    }
  }
  return visit(type, value, 1, "value");
}
export function decodeValue(type: CodecType, wire: unknown): unknown { return transform(type, wire, true); }
export function encodeValue(type: CodecType, value: unknown): unknown { return transform(type, value, false); }
function jsonSource(raw: string | Uint8Array): string {
  let source: string;
  if (raw instanceof Uint8Array) {
    if (raw.byteLength > MAX_BYTES) fail("W_CODEC_LIMIT", "Wire byte budget exceeded", "json");
    try { source = new TextDecoder("utf-8", {fatal: true, ignoreBOM: true}).decode(raw); }
    catch { fail("W_CODEC_JSON", "Valid UTF-8 JSON required", "json"); }
  } else {
    if (typeof raw !== "string") fail("W_CODEC_JSON", "JSON text or UTF-8 bytes required", "json");
    source = raw;
  }
  if (source.length > MAX_BYTES) fail("W_CODEC_LIMIT", "Wire byte budget exceeded", "json");
  // Check input scalars without the value-level NUL prohibition: JSON syntax handles NUL.
  for (let i = 0; i < source.length; i++) {
    const c = source.charCodeAt(i);
    if (c >= 0xd800 && c <= 0xdbff) {
      const next = source.charCodeAt(++i);
      if (!(next >= 0xdc00 && next <= 0xdfff)) fail("W_CODEC_JSON", "Valid UTF-8 JSON required", "json");
    } else if (c >= 0xdc00 && c <= 0xdfff) fail("W_CODEC_JSON", "Valid UTF-8 JSON required", "json");
  }
  if (new TextEncoder().encode(source).length > MAX_BYTES) fail("W_CODEC_LIMIT", "Wire byte budget exceeded", "json");
  return source;
}
function parseJson(source: string): unknown {
  let index = 0; const budget = new Budget();
  const whitespace = () => { while (index < source.length && /[ \t\r\n]/.test(source[index])) index++; };
  const invalid = (): never => fail("W_CODEC_JSON", "Invalid JSON", "json");
  function string(): string {
    const start = index++;
    while (index < source.length) {
      const c = source[index++];
      if (c === '"') {
        try { return JSON.parse(source.slice(start, index)) as string; } catch { invalid(); }
      }
      if (c === "\\") index++;
    }
    return invalid();
  }
  function value(depth: number): unknown {
    budget.visit(depth, "json"); whitespace();
    const c = source[index];
    if (c === '"') return string();
    if (c === "{") {
      index++; whitespace(); const result: Record<string, unknown> = Object.create(null);
      if (source[index] === "}") { index++; return result; }
      while (true) {
        whitespace(); budget.visit(depth + 1, "json"); if (source[index] !== '"') invalid();
        const key = string();
        if (Object.hasOwn(result, key)) fail("W_CODEC_JSON", "Duplicate JSON key", "json");
        whitespace(); if (source[index++] !== ":") invalid();
        result[key] = value(depth + 1); whitespace();
        const separator = source[index++]; if (separator === "}") return result;
        if (separator !== ",") invalid();
      }
    }
    if (c === "[") {
      index++; whitespace(); const result: unknown[] = [];
      if (source[index] === "]") { index++; return result; }
      while (true) {
        result.push(value(depth + 1)); whitespace();
        const separator = source[index++]; if (separator === "]") return result;
        if (separator !== ",") invalid();
      }
    }
    for (const [literal, result] of [["true", true], ["false", false], ["null", null]] as const) {
      if (source.startsWith(literal, index)) { index += literal.length; return result; }
    }
    if (c === "-" || (c >= "0" && c <= "9"))
      fail("W_CODEC_INTEGER", "Wire numbers must be canonical decimal strings", "json");
    return invalid();
  }
  const result = value(1); whitespace(); if (index !== source.length) invalid(); return result;
}
export function parseWireJson(raw: string | Uint8Array): unknown {
  return parseJson(jsonSource(raw));
}
export function decodeJson(type: CodecType, raw: string | Uint8Array): unknown {
  validateType(type); return decodeValue(type, parseWireJson(raw));
}
function canonicalJson(value: unknown): string {
  if (typeof value === "string") return JSON.stringify(value).replace(/[\u007f-\uffff]/g, c => "\\u" + c.charCodeAt(0).toString(16).padStart(4, "0"));
  if (value === null || typeof value === "boolean") return JSON.stringify(value);
  if (Array.isArray(value)) return "[" + value.map(canonicalJson).join(",") + "]";
  const object = value as Record<string, unknown>;
  return "{" + Object.keys(object).sort().map(k => canonicalJson(k) + ":" + canonicalJson(object[k])).join(",") + "}";
}
export function encodeJson(type: CodecType, value: unknown): string {
  const source = canonicalJson(encodeValue(type, value));
  parseJson(jsonSource(source)); return source;
}
'''
