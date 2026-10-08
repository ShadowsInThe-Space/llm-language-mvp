"""Bounded S-expression source lowering to the unchanged pure A1 IR contract.

Source parsing is independent of an offered IR or certificate. Every successful
parse runs the existing IR checker and validates structured constant values.
"""

from __future__ import annotations

import json
import re
from bisect import bisect_right
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, NoReturn

from llmlang.a1.ir import A1IRError, canonical_bytes, module_hash, validate_module
from llmlang.a1.typecheck import A1TypeError, validate_runtime_arguments


@dataclass(frozen=True, slots=True)
class SourceSpan:
    """Zero-based character offset and one-based line/column of a source node."""

    offset: int
    line: int
    column: int


class A1SourceError(ValueError):
    """Stable source diagnostic; all rejected input stays in this namespace."""

    def __init__(
        self, code: str, message: str, location: str = "module", span: SourceSpan | None = None
    ) -> None:
        self.code = code
        self.location = location
        self.span = span
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": str(self),
            "location": self.location,
            "line": self.span.line if self.span else None,
            "column": self.span.column if self.span else None,
        }


@dataclass(frozen=True, slots=True)
class SourceLimits:
    """Producer resource limits, separate from execution budgets in the module."""

    max_bytes: int = 262144
    max_depth: int = 64
    max_nodes: int = 50000
    max_integer_digits: int = 1024

    def __post_init__(self) -> None:
        for name, ceiling in (
            ("max_bytes", 1048576),
            ("max_depth", 128),
            ("max_nodes", 200000),
            ("max_integer_digits", 1024),
        ):
            value = getattr(self, name)
            if type(value) is not int or not 0 < value <= ceiling:
                raise A1SourceError("E_A1_SOURCE_LIMIT", f"invalid {name}")


@dataclass(frozen=True, slots=True)
class ParsedSource:
    _module_bytes: bytes
    canonical_source: str
    semantic_hash: str
    source_map: Mapping[str, SourceSpan]

    @property
    def module(self) -> dict[str, Any]:
        """A defensive copy; callers cannot invalidate this result's binding."""
        decoded: dict[str, Any] = json.loads(self._module_bytes)
        return decoded


@dataclass(frozen=True, slots=True)
class _Node:
    kind: str
    value: Any
    span: SourceSpan


_ID = re.compile(r"[A-Za-z_%][A-Za-z0-9_.:%-]*\Z")
_INTEGER = re.compile(r"-?(?:0|[1-9][0-9]*)\Z")
_RESERVED = {"true", "false", "unit"}
_PRIMITIVES = {"Unit", "Bool", "Int", "Nat"}


def _fail(message: str, node: _Node, location: str = "module", code: str = "SYNTAX") -> NoReturn:
    raise A1SourceError(f"E_A1_SOURCE_{code}", message, location, node.span)


def _syntax_tree(source: str, limits: SourceLimits) -> _Node:
    if not isinstance(source, str):
        raise A1SourceError("E_A1_SOURCE_ENCODING", "source must be Unicode text")
    try:
        size = len(source.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise A1SourceError("E_A1_SOURCE_ENCODING", "source contains a non-scalar") from exc
    if size > limits.max_bytes:
        raise A1SourceError("E_A1_SOURCE_LIMIT", "source byte budget exceeded")
    if "\x00" in source:
        raise A1SourceError("E_A1_SOURCE_ENCODING", "source contains NUL")
    starts = [0] + [i + 1 for i, char in enumerate(source) if char == "\n"]

    def span(offset: int) -> SourceSpan:
        line = bisect_right(starts, offset)
        return SourceSpan(offset, line, offset - starts[line - 1] + 1)

    stack: list[tuple[SourceSpan, list[_Node]]] = []
    roots: list[_Node] = []
    count = 0
    offset = 0
    while offset < len(source):
        char = source[offset]
        if char in " \t\r\n":
            offset += 1
            continue
        at = span(offset)
        if char == ")":
            if not stack:
                raise A1SourceError("E_A1_SOURCE_SYNTAX", "unexpected closing parenthesis", span=at)
            opened, children = stack.pop()
            node = _Node("list", tuple(children), opened)
            (stack[-1][1] if stack else roots).append(node)
            offset += 1
            continue
        count += 1
        if count > limits.max_nodes:
            raise A1SourceError("E_A1_SOURCE_LIMIT", "source node budget exceeded", span=at)
        if char == "(":
            if len(stack) >= limits.max_depth:
                raise A1SourceError("E_A1_SOURCE_LIMIT", "source depth budget exceeded", span=at)
            stack.append((at, []))
            offset += 1
            continue
        begin = offset
        if char == '"':
            offset += 1
            escaped = False
            while offset < len(source):
                current = source[offset]
                offset += 1
                if current == '"' and not escaped:
                    break
                if current == "\\" and not escaped:
                    escaped = True
                else:
                    escaped = False
            else:
                raise A1SourceError("E_A1_SOURCE_SYNTAX", "unterminated string", span=at)
            try:
                value = json.loads(source[begin:offset])
                value.encode("utf-8")
            except (ValueError, UnicodeEncodeError) as exc:
                raise A1SourceError(
                    "E_A1_SOURCE_ENCODING", "invalid string escape/scalar", span=at
                ) from exc
            if "\x00" in value:
                raise A1SourceError("E_A1_SOURCE_ENCODING", "string contains NUL", span=at)
            node = _Node("string", value, at)
        else:
            while offset < len(source) and source[offset] not in "() \t\r\n\"":
                offset += 1
            token = source[begin:offset]
            if _INTEGER.fullmatch(token):
                if len(token.lstrip("-")) > limits.max_integer_digits:
                    raise A1SourceError(
                        "E_A1_SOURCE_LIMIT", "integer digit budget exceeded", span=at
                    )
                node = _Node("integer", int(token), at)
            elif _ID.fullmatch(token) or token == ">=0":
                node = _Node("symbol", token, at)
            else:
                raise A1SourceError("E_A1_SOURCE_SYNTAX", "invalid atom", span=at)
        (stack[-1][1] if stack else roots).append(node)
    if stack:
        raise A1SourceError("E_A1_SOURCE_SYNTAX", "unclosed parenthesis", span=stack[-1][0])
    if len(roots) != 1:
        raise A1SourceError("E_A1_SOURCE_SYNTAX", "exactly one source module required")
    return roots[0]


def _items(node: _Node, minimum: int = 0, maximum: int | None = None) -> tuple[_Node, ...]:
    if node.kind != "list" or len(node.value) < minimum:
        _fail("invalid form or missing argument", node)
    if maximum is not None and len(node.value) > maximum:
        _fail("unexpected argument", node)
    result: tuple[_Node, ...] = node.value
    return result


def _symbol(node: _Node) -> str:
    if node.kind != "symbol" or not _ID.fullmatch(node.value) or node.value in _RESERVED:
        _fail("identifier required", node)
    return str(node.value)


def _number(node: _Node, *, positive: bool = False) -> int:
    if node.kind != "integer" or node.value < (1 if positive else 0):
        _fail("positive integer required" if positive else "capacity must be non-negative", node)
    return int(node.value)


def _type(node: _Node) -> Any:
    if node.kind == "symbol":
        return _symbol(node)
    items = _items(node, 2)
    name = _symbol(items[0])
    arity = {"Text": 2, "List": 3, "Option": 2, "Result": 3}.get(name)
    if arity is None or len(items) != arity:
        _fail("unsupported type expression", node)
    if name == "Text":
        return {"kind": "text", "capacity": _number(items[1])}
    if name == "List":
        return {"kind": "list", "elem": _type(items[1]), "capacity": _number(items[2])}
    if name == "Option":
        return {"kind": "option", "elem": _type(items[1])}
    return {"kind": "result", "ok": _type(items[1]), "error": _type(items[2])}


def _pairs(nodes: tuple[_Node, ...], *, literal: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for node in nodes:
        key, value = _items(node, 2, 2)
        name = _symbol(key)
        if name in result:
            _fail("duplicate field or arm", node, code="NAME")
        result[name] = _literal(value) if literal else _operand(value)
    return result


def _literal(node: _Node) -> Any:
    if node.kind in {"string", "integer"}:
        return node.value
    if node.kind == "symbol" and node.value in _RESERVED:
        return {"true": True, "false": False, "unit": None}[node.value]
    items = _items(node, 1)
    kind = _symbol(items[0])
    if kind == "list":
        _items(node, 2)
        return {"capacity": _number(items[1]), "list": [_literal(x) for x in items[2:]]}
    if kind == "record":
        _items(node, 2)
        return {"record": _symbol(items[1]), "fields": _pairs(items[2:], literal=True)}
    if kind == "variant":
        _items(node, 3, 4)
        result = {"variant": _symbol(items[1]), "tag": _symbol(items[2])}
        if len(items) == 4:
            result["value"] = _literal(items[3])
        return result
    if kind == "none":
        _items(node, 1, 1)
        return {"tag": "None"}
    if kind in {"some", "ok", "err"}:
        _items(node, 2, 2)
        return {
            "tag": {"some": "Some", "ok": "Ok", "err": "Err"}[kind],
            "value": _literal(items[1]),
        }
    _fail("literal required; identifiers cannot appear in constants", node)


def _operand(node: _Node) -> Any:
    if node.kind == "list":
        _fail("structured operands require a typed const and binder reference", node)
    if node.kind == "symbol" and node.value not in _RESERVED:
        return {"ref": _symbol(node)}
    return _literal(node)


# Operand schemas deliberately exclude static identifiers and capacities.
_OPERANDS = {
    "add": ("left", "right"),
    "list_append": ("list", "value"),
    "list_index": ("list", "index"),
    "text_utf8_bytes": ("value",),
    "text_codepoint_count": ("value",),
    "text_prefix_codepoints": ("value", "count"),
}


def _operation(node: _Node, result_type: Any) -> dict[str, Any]:
    items = _items(node, 1)
    op = _symbol(items[0])
    args = items[1:]
    result: dict[str, Any] = {"op": op}
    if op in _OPERANDS:
        fields = _OPERANDS[op]
        _items(node, len(fields) + 1, len(fields) + 1)
        result.update({field: _operand(arg) for field, arg in zip(fields, args, strict=True)})
    elif op == "const":
        _items(node, 2, 2)
        result["value"] = _literal(args[0])
    elif op == "record_make":
        _items(node, 2)
        result.update(record=_symbol(args[0]), fields=_pairs(args[1:]))
    elif op == "record_get":
        _items(node, 4, 4)
        result.update(record=_symbol(args[0]), value=_operand(args[1]), field=_symbol(args[2]))
    elif op == "variant_make":
        _items(node, 3, 4)
        result.update(variant=_symbol(args[0]), tag=_symbol(args[1]))
        if len(args) == 3:
            result["value"] = _operand(args[2])
    elif op == "match_value":
        _items(node, 4)
        result.update(variant=_symbol(args[0]), value=_operand(args[1]), arms=_pairs(args[2:]))
    elif op == "call":
        _items(node, 2)
        result.update(callee=_symbol(args[0]), args=[_operand(arg) for arg in args[1:]])
    elif op in {"bounded_map", "bounded_fold"}:
        _items(node, 3 if op == "bounded_map" else 4, 3 if op == "bounded_map" else 4)
        result.update(list=_operand(args[0]), callback=_symbol(args[-1]))
        if op == "bounded_fold":
            result["initial"] = _operand(args[1])
    elif op == "list_empty":
        _items(node, 1, 1)
        if not isinstance(result_type, dict) or result_type.get("kind") != "list":
            _fail("list_empty requires a List result type", node, code="TYPE")
        result["capacity"] = result_type["capacity"]
    elif op == "text_concat":
        _items(node, 4, 4)
        result.update(left=_operand(args[0]), right=_operand(args[1]), capacity=_number(args[2]))
    elif op == "refine_nat":
        _items(node, 3, 3)
        evidence = _items(args[1], 3, 3)
        if [item.value for item in evidence] != ["evidence", ">=0", "A1-C004"] or any(
            item.kind != "symbol" for item in evidence
        ):
            _fail("exact A1-C004 evidence required", args[1], code="EVIDENCE")
        result.update(value=_operand(args[0]), evidence={"predicate": ">=0", "rule": "A1-C004"})
    else:
        _fail("unsupported pure operation", node, code="OP")
    return result


def _declaration(node: _Node) -> dict[str, Any]:
    items = _items(node, 3)
    kind, name = _symbol(items[0]), _symbol(items[1])
    if name in _PRIMITIVES | {"Text", "List", "Option", "Result"}:
        _fail("nominal name shadows a built-in type", items[1], code="NAME")
    declarations: list[dict[str, Any]] = []
    names: set[str] = set()
    for item in items[2:]:
        parts = _items(item, 2 if kind == "record" else 1, 2)
        member = _symbol(parts[0])
        if member in names:
            _fail("duplicate field or case", item, code="NAME")
        names.add(member)
        entry = {"name" if kind == "record" else "tag": member}
        if len(parts) == 2:
            entry["type"] = _type(parts[1])
        declarations.append(entry)
    return {"kind": kind, "name": name, "fields" if kind == "record" else "cases": declarations}


def _function(node: _Node, path: str, source_map: dict[str, SourceSpan]) -> dict[str, Any]:
    items = _items(node, 5)
    name = _symbol(items[1])
    params: list[dict[str, Any]] = []
    source_map[path] = node.span
    for index, param in enumerate(_items(items[2])):
        p_name, p_type = _items(param, 2, 2)
        params.append({"name": _symbol(p_name), "type": _type(p_type)})
        source_map[f"{path}.params[{index}]"] = param.span
    result_type = _type(items[3])
    body: list[dict[str, Any]] = []
    for index, instruction in enumerate(items[4:-1]):
        parts = _items(instruction, 4, 4)
        if _symbol(parts[0]) != "let":
            _fail("function body requires typed let forms", instruction, path)
        asserted = _type(parts[2])
        body.append({**_operation(parts[3], asserted), "dest": _symbol(parts[1]), "type": asserted})
        source_map[f"{path}.body[{index}]"] = instruction.span
    returned = _items(items[-1], 2, 2)
    if _symbol(returned[0]) != "return":
        _fail("function requires a final return", items[-1], path)
    source_map[f"{path}.return"] = items[-1].span
    return {
        "name": name, "params": params, "result": result_type,
        "body": body, "return": _symbol(returned[1]),
    }


def _lower(root: _Node) -> tuple[dict[str, Any], dict[str, SourceSpan]]:
    items = _items(root, 2)
    if _symbol(items[0]) != "a1src1":
        _fail("unsupported source version", root, code="VERSION")
    budgets = _items(items[1], 4, 4)
    if _symbol(budgets[0]) != "limits":
        _fail("explicit limits must be the first module form", items[1])
    module: dict[str, Any] = {
        "format": "a1-ir-v1", "profile": "a1", "checker": "a1-check-v1",
        "types": [], "functions": [], "specializations": [], "entrypoints": [],
        "limits": dict(zip(
            ("max_steps", "max_collection_expansion", "max_call_depth"),
            (_number(item, positive=True) for item in budgets[1:]), strict=True,
        )),
    }
    source_map = {"module": root.span, "limits": items[1].span}
    for node in items[2:]:
        parts = _items(node, 1)
        kind = _symbol(parts[0])
        if kind in {"record", "variant"}:
            path = f"types[{len(module['types'])}]"
            source_map[path] = node.span
            module["types"].append(_declaration(node))
        elif kind == "fn":
            path = f"functions[{len(module['functions'])}]"
            module["functions"].append(_function(node, path, source_map))
        elif kind == "entry":
            _items(node, 2, 2)
            source_map[f"entrypoints[{len(module['entrypoints'])}]"] = node.span
            name = _symbol(parts[1])
            if name in module["entrypoints"]:
                _fail("duplicate entrypoint", node, code="NAME")
            module["entrypoints"].append(name)
        else:
            _fail("unsupported module form", node)
    return module, source_map


def _render(node: _Node) -> str:
    if node.kind == "list":
        return "(" + " ".join(_render(item) for item in node.value) + ")"
    if node.kind == "string":
        return json.dumps(node.value, ensure_ascii=False)
    return str(node.value)


def _validate_literal(
    module: dict[str, Any], value: Any, expected: Any,
    location: str, source_map: dict[str, SourceSpan],
) -> None:
    if isinstance(value, dict) and set(value) == {"ref"}:
        return  # Binding and exact type equality are checked by the IR checker.
    boundary = {
        "types": module["types"],
        "functions": [{
            "name": "literal",
            "params": [{"name": "value", "type": expected}],
        }],
    }
    try:
        validate_runtime_arguments(boundary, "literal", [value])
    except A1TypeError as exc:
        raise A1SourceError(
            "E_A1_SOURCE_TYPE", str(exc), location, source_map[location]
        ) from exc


def _validate_literals(module: dict[str, Any], source_map: dict[str, SourceSpan]) -> None:
    """Close the core checker's shallow literal boundary without new inference."""
    declarations = {item["name"]: item for item in module["types"]}
    functions = {item["name"]: item for item in module["functions"]}
    for f_index, function in enumerate(module["functions"]):
        env = {param["name"]: param["type"] for param in function["params"]}
        for i_index, instruction in enumerate(function["body"]):
            location = f"functions[{f_index}].body[{i_index}]"
            op = instruction["op"]
            candidates: list[tuple[Any, Any]] = []
            if op == "const":
                candidates.append((instruction["value"], instruction["type"]))
            elif op == "call":
                parameters = functions[instruction["callee"]]["params"]
                candidates.extend(
                    (value, param["type"])
                    for value, param in zip(instruction["args"], parameters, strict=True)
                )
            elif op == "record_make":
                fields = declarations[instruction["record"]]["fields"]
                candidates.extend(
                    (instruction["fields"][field["name"]], field["type"]) for field in fields
                )
            elif op == "record_get":
                candidates.append((instruction["value"], instruction["record"]))
            elif op == "variant_make" and "value" in instruction:
                cases = declarations[instruction["variant"]]["cases"]
                payload = next(case["type"] for case in cases if case["tag"] == instruction["tag"])
                candidates.append((instruction["value"], payload))
            elif op == "match_value":
                candidates.append((instruction["value"], instruction["variant"]))
                candidates.extend(
                    (value, instruction["type"]) for value in instruction["arms"].values()
                )
            elif op == "bounded_fold":
                accumulator = functions[instruction["callback"]]["params"][0]["type"]
                candidates.append((instruction["initial"], accumulator))
            elif op == "list_append":
                element = env[instruction["list"]["ref"]]["elem"]
                candidates.append((instruction["value"], element))
            for value, expected in candidates:
                _validate_literal(module, value, expected, location, source_map)
            env[instruction["dest"]] = instruction["type"]


def _checked(module: dict[str, Any], source_map: dict[str, SourceSpan]) -> None:
    try:
        validate_module(module)
        _validate_literals(module, source_map)
    except A1IRError as exc:
        location = exc.location
        for index, function in enumerate(module["functions"]):
            location = location.replace(f"functions[{function['name']}]", f"functions[{index}]")
            location = location.replace(f"functions.{function['name']}.", f"functions[{index}].")
        matches = [path for path in source_map if location.startswith(path)]
        nearest = max(matches, key=len) if matches else "module"
        raise A1SourceError("E_A1_SOURCE_TYPE", str(exc), location, source_map[nearest]) from exc
    except RecursionError as exc:
        raise A1SourceError("E_A1_SOURCE_LIMIT", "checker traversal budget exceeded") from exc


def parse_source(source: str, *, limits: SourceLimits | None = None) -> ParsedSource:
    """Parse, lower and check a pure a1src1 module with explicit SSA binders."""
    configured = limits or SourceLimits()
    root = _syntax_tree(source, configured)
    canonical_source = _render(root)
    if len(canonical_source.encode("utf-8")) > configured.max_bytes:
        raise A1SourceError("E_A1_SOURCE_LIMIT", "canonical source byte budget exceeded")
    module, source_map = _lower(root)
    _checked(module, source_map)
    return ParsedSource(
        canonical_bytes(module), canonical_source, module_hash(module),
        MappingProxyType(dict(source_map)),
    )


def lower_source(source: str, *, limits: SourceLimits | None = None) -> dict[str, Any]:
    """Return freshly reconstructed, statically checked a1-ir-v1."""
    return parse_source(source, limits=limits).module


def canonicalize_source(source: str, *, limits: SourceLimits | None = None) -> str:
    """Canonical whitespace/escape spelling; binders and declaration order persist."""
    return parse_source(source, limits=limits).canonical_source


def check_source_binding(
    source: str, offered_ir: object, *, limits: SourceLimits | None = None
) -> bool:
    """Independently recompute lowering and compare complete canonical IR bytes."""
    try:
        expected = lower_source(source, limits=limits)
        return canonical_bytes(expected) == canonical_bytes(offered_ir)
    except (A1SourceError, A1IRError, TypeError, ValueError, RecursionError):
        return False
