"""Bounded parser for the closed P0 transport grammar and canonical serialization.

Lexical errors carry path=(offset,), a zero-based Unicode character offset in the
original source (EOF is len(source)). Their messages explicitly label this offset.
Grammar decoding does not preserve a full source map.
"""

import re
from typing import cast

from .model import Candidate, Expr, FunctionSpec, LanguageError, Limits, Specification, Type

type SExpr = str | tuple[SExpr, ...]
DEFAULT_LIMITS = Limits()
DECIMAL = re.compile(r"(?:0|-[1-9][0-9]*|[1-9][0-9]*)\Z")
ATOM = re.compile(r"[A-Za-z][A-Za-z0-9.]*\Z")
ARITIES = {
    "let": 2,
    "if": 3,
    "int.add": 2,
    "int.sub": 2,
    "int.mul": 2,
    "int.le": 2,
    "int.lt": 2,
    "int.eq": 2,
    "not": 1,
    "and": 2,
    "or": 2,
    "bool.eq": 2,
}


def _error(message: str) -> LanguageError:
    return LanguageError("E_PARSE", message)


def _lexical(message: str, offset: int, code: str = "E_PARSE") -> LanguageError:
    return LanguageError(code, f"{message} at character offset {offset}", (offset,))


def _read(source: str, limits: Limits) -> SExpr:
    if type(source) is not str:
        raise _lexical("Source must be a string", 0)
    try:
        encoded = source.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise _lexical("Source is not valid UTF-8", exc.start) from exc
    if len(encoded) > limits.max_source_bytes:
        offset = len(encoded[: limits.max_source_bytes].decode("utf-8", errors="ignore"))
        raise _lexical("Source byte limit exceeded", offset, "E_LIMIT")
    # Incremental scanning counts every atom and list before constructing it.
    stack: list[list[SExpr]] = []
    root: list[SExpr] = []
    count = 0
    offset = 0
    while offset < len(source):
        char = source[offset]
        if char.isspace():
            offset += 1
            continue
        if char == ")":
            if not stack:
                raise _lexical("Unmatched closing parenthesis", offset)
            node = tuple(stack.pop())
            (stack[-1] if stack else root).append(node)
            offset += 1
            continue
        if root and not stack:
            raise _lexical("Unexpected input after complete source form", offset)
        count += 1
        if count > limits.max_nodes:
            raise _lexical("Syntax node limit exceeded", offset, "E_LIMIT")
        if char == "(":
            # A hard ceiling protects recursive grammar decoding on the Python host.
            if len(stack) + 1 > min(limits.max_depth, 256):
                raise _lexical("Syntax depth limit exceeded", offset, "E_LIMIT")
            stack.append([])
            offset += 1
            continue
        end = offset + 1
        while end < len(source) and not source[end].isspace() and source[end] not in "()":
            end += 1
        atom = source[offset:end]
        if atom[:1] in "-+0123456789":
            try:
                _integer(atom, limits)
            except LanguageError as exc:
                raise _lexical(exc.message, offset, exc.code) from exc
        elif ATOM.fullmatch(atom) is None:
            raise _lexical("Invalid token", offset)
        (stack[-1] if stack else root).append(atom)
        offset = end
    if stack:
        raise _lexical("Unclosed parenthesis", len(source))
    if len(root) != 1:
        raise _lexical("Expected exactly one complete source form", len(source))
    return root[0]


def _form(node: SExpr, head: str, size: int | None = None) -> tuple[SExpr, ...]:
    if not isinstance(node, tuple) or not node or node[0] != head:
        raise _error(f"Expected {head} form")
    if size is not None and len(node) != size:
        raise _error(f"Wrong field count in {head}")
    return node


def _integer(atom: SExpr, limits: Limits, *, index: bool = False) -> int:
    if not isinstance(atom, str) or DECIMAL.fullmatch(atom) is None:
        raise _error("Expected a canonical decimal integer")
    digits = atom.removeprefix("-")
    if len(digits) > limits.max_int_digits:
        raise LanguageError("E_LIMIT", "Integer digit limit exceeded")
    value = 0
    # Bounded chunks avoid Python's process-global decimal conversion setting.
    for offset in range(0, len(digits), 9):
        chunk = digits[offset : offset + 9]
        value = value * 10 ** len(chunk) + int(chunk)
        if value.bit_length() > limits.max_bits:
            raise LanguageError("E_LIMIT", "Integer bit limit exceeded")
    if atom.startswith("-"):
        value = -value
    if index and (value < 0 or value > limits.max_nodes):
        raise _error("Index outside the bounded nonnegative index range")
    return value


def _expr(node: SExpr, limits: Limits) -> Expr:
    if isinstance(node, str):
        if node in ("true", "false"):
            return Expr("bool", value=node == "true")
        if node == "result":
            return Expr("result")
        return Expr("int", value=_integer(node, limits))
    if not node or not isinstance(node[0], str):
        raise _error("Expected an expression operator")
    op = node[0]
    if op == "var":
        _form(node, "var", 2)
        return Expr("var", value=_integer(node[1], limits, index=True))
    if op == "call":
        if len(node) < 2:
            raise _error("Call requires a function index")
        index = _integer(node[1], limits, index=True)
        return Expr("call", tuple(_expr(arg, limits) for arg in node[2:]), index)
    if op not in ARITIES or len(node) != ARITIES[op] + 1:
        raise _error(f"Unknown operator or incorrect arity: {op}")
    return Expr(op, tuple(_expr(arg, limits) for arg in node[1:]))


def _type(node: SExpr) -> Type:
    if node not in ("Int", "Bool"):
        raise _error("Expected Int or Bool type")
    return cast(Type, node)


def parse_spec(source: str, limits: Limits = DEFAULT_LIMITS) -> Specification:
    top = _form(_read(source, limits), "spec")
    if len(top) < 3 or top[1] != "p0":
        raise _error("Expected p0 specification with at least one function")
    functions: list[FunctionSpec] = []
    for node in top[2:]:
        fn = _form(node, "fn", 5)
        params = _form(fn[1], "params")
        result = _form(fn[2], "result", 2)
        requires = _form(fn[3], "requires", 2)
        ensures = _form(fn[4], "ensures", 2)
        functions.append(
            FunctionSpec(
                tuple(_type(p) for p in params[1:]),
                _type(result[1]),
                _expr(requires[1], limits),
                _expr(ensures[1], limits),
            )
        )
    return Specification(tuple(functions))


def parse_candidate(source: str, limits: Limits = DEFAULT_LIMITS) -> Candidate:
    top = _form(_read(source, limits), "candidate")
    if len(top) < 3 or top[1] != "p0":
        raise _error("Expected p0 candidate with at least one body")
    return Candidate(tuple(_expr(_form(node, "body", 2)[1], limits) for node in top[2:]))


def canonical_expr(expr: Expr) -> str:
    if expr.op == "int":
        return str(expr.value)
    if expr.op == "bool":
        return "true" if expr.value else "false"
    if expr.op == "result":
        return "result"
    children = [expr.op]
    if expr.op in ("var", "call"):
        children.append(str(expr.value))
    children.extend(canonical_expr(arg) for arg in expr.args)
    return "(" + " ".join(children) + ")"


def canonical_spec(spec: Specification) -> str:
    functions = []
    for fn in spec.functions:
        params = "(params" + (" " + " ".join(fn.params) if fn.params else "") + ")"
        functions.append(
            f"(fn {params} (result {fn.returns})"
            f" (requires {canonical_expr(fn.requires)})"
            f" (ensures {canonical_expr(fn.ensures)}))"
        )
    return "(spec " + spec.profile + " " + " ".join(functions) + ")"


def canonical_candidate(candidate: Candidate) -> str:
    bodies = " ".join(f"(body {canonical_expr(expr)})" for expr in candidate.bodies)
    return f"(candidate {candidate.profile} {bodies})"
