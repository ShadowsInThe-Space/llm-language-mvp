"""Closed A1 generics: explicit calls, acyclic reachability and monomorphization.

This module deliberately has no dependency on the P0 model.  A1 instances are
immutable values and are materialized only when reachable from an entrypoint.
The small API is also useful to the IR checker: all validation errors carry a
stable diagnostic code rather than host exception text.
"""

from __future__ import annotations

import builtins
import hashlib
import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, cast

from ..diagnostics import diagnostic


class GenericError(Exception):
    """A fail-closed A1 generic diagnostic."""

    def __init__(self, code: str, message: str, path: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.path = path

    def to_dict(self) -> dict[str, object]:
        return diagnostic({"code": self.code, "message": self.message, "path": list(self.path)})


@dataclass(frozen=True, slots=True)
class Type:
    """A closed nominal type or an explicit generic type variable."""

    kind: str
    name: str | None = None
    args: tuple[Type, ...] = ()
    capacity: int | str | None = None

    @classmethod
    def int(cls) -> Type:
        return cls("Int")

    @classmethod
    def nat(cls) -> Type:
        return cls("Nat")

    @classmethod
    def bool(cls) -> Type:
        return cls("Bool")

    @classmethod
    def unit(cls) -> Type:
        return cls("Unit")

    @classmethod
    def var(cls, name: str) -> Type:
        return cls("type_var", name=name)

    @classmethod
    def capacity_var(cls, name: str) -> Type:
        return cls("capacity_var", name=name)

    @classmethod
    def record(cls, name: str, *args: Type) -> Type:
        return cls("record", name=name, args=tuple(args))

    @classmethod
    def list_of(cls, item: Type, capacity: builtins.int | str) -> Type:
        return cls("list", args=(item,), capacity=capacity)

    def substitute(self, types: Mapping[str, Type], capacities: Mapping[str, builtins.int]) -> Type:
        if self.kind == "type_var":
            return types.get(self.name or "", self)
        if self.kind == "capacity_var":
            value = capacities.get(self.name or "")
            return Type("capacity", name=str(value)) if value is not None else self
        capacity = self.capacity
        if isinstance(capacity, str):
            capacity = capacities.get(capacity, capacity)
        return Type(
            self.kind,
            self.name,
            tuple(arg.substitute(types, capacities) for arg in self.args),
            capacity,
        )

    def is_closed(self) -> builtins.bool:
        return (
            self.kind not in {"type_var", "capacity_var"}
            and all(arg.is_closed() for arg in self.args)
            and not isinstance(self.capacity, builtins.str)
        )

    def canonical(self) -> str:
        if self.kind == "type_var":
            return f"$t:{self.name}"
        if self.kind == "capacity_var":
            return f"$n:{self.name}"
        suffix = "".join(f"[{arg.canonical()}]" for arg in self.args)
        cap = f"@{self.capacity}" if self.capacity is not None else ""
        return f"{self.kind}:{self.name or ''}{suffix}{cap}"


@dataclass(frozen=True, slots=True)
class Call:
    callee: str
    type_args: tuple[Type, ...] = ()
    capacity_args: tuple[int | str, ...] = ()
    callback: str | None = None

    def __init__(
        self,
        callee: str,
        type_args: Iterable[Type] = (),
        capacity_args: Iterable[int | str] = (),
        callback: str | None = None,
    ) -> None:
        object.__setattr__(self, "callee", callee)
        object.__setattr__(self, "type_args", tuple(type_args))
        object.__setattr__(self, "capacity_args", tuple(capacity_args))
        object.__setattr__(self, "callback", callback)


@dataclass(frozen=True, slots=True)
class Function:
    name: str
    type_params: tuple[str, ...] = ()
    capacity_params: tuple[str, ...] = ()
    params: tuple[Type, ...] = ()
    result: Type = field(default_factory=Type.unit)
    calls: tuple[Call, ...] = ()

    def __init__(
        self,
        name: str,
        type_params: Iterable[str] = (),
        capacity_params: Iterable[str] = (),
        params: Iterable[Type] = (),
        result: Type | None = None,
        calls: Iterable[Call] = (),
    ) -> None:
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "type_params", tuple(type_params))
        object.__setattr__(self, "capacity_params", tuple(capacity_params))
        object.__setattr__(self, "params", tuple(params))
        object.__setattr__(self, "result", result or Type.unit())
        object.__setattr__(self, "calls", tuple(calls))

    def with_name(self, name: str) -> Function:
        return Function(
            name,
            self.type_params,
            self.capacity_params,
            self.params,
            self.result,
            self.calls,
        )


@dataclass(frozen=True, slots=True)
class Program:
    functions: tuple[Function, ...]
    entrypoints: tuple[str, ...]

    def __init__(
        self,
        functions: Iterable[Function] | Mapping[str, Function],
        entrypoints: Iterable[str],
    ) -> None:
        if isinstance(functions, Mapping):
            values = tuple(cast(Mapping[str, Function], functions).values())
        else:
            values = tuple(functions)
        object.__setattr__(self, "functions", values)
        object.__setattr__(self, "entrypoints", tuple(entrypoints))

    def index(self) -> dict[str, Function]:
        result: dict[str, Function] = {}
        for function in self.functions:
            if function.name in result:
                raise GenericError("E_A1_CALL", f"duplicate function: {function.name}")
            result[function.name] = function
        return result


@dataclass(frozen=True, slots=True)
class Limits:
    max_instances: int = 512
    max_nodes: int = 100_000
    max_call_depth: int = 256
    max_bounded_iterations: int = 100_000
    max_capacity: int = 256


@dataclass(frozen=True, slots=True)
class Instance:
    instance_id: str
    generic: str
    type_args: tuple[Type, ...]
    capacity_args: tuple[int, ...]
    body_hash: str
    calls: tuple[Call, ...] = ()

    @property
    def specialization_key(self) -> str:
        return self.instance_id


def _validate_cycles(functions: Mapping[str, Function]) -> None:
    state: dict[str, int] = {}

    def visit(name: str, stack: tuple[str, ...]) -> None:
        mark = state.get(name, 0)
        if mark == 1:
            raise GenericError("E_A1_CALL_CYCLE", "cyclic call graph", stack + (name,))
        if mark == 2:
            return
        function = functions.get(name)
        if function is None:
            raise GenericError("E_A1_CALL", f"unknown callee: {name}", stack + (name,))
        state[name] = 1
        for call in function.calls:
            visit(call.callee, stack + (name,))
        state[name] = 2

    for name in sorted(functions):
        visit(name, ())


def _instance_id(name: str, types: Sequence[Type], capacities: Sequence[int]) -> str:
    type_part = ",".join(item.canonical() for item in types) or "-"
    cap_part = ",".join(str(item) for item in capacities) or "-"
    return f"{name}#{type_part}#{cap_part}"


def _body_hash(function: Function, types: Sequence[Type], capacities: Sequence[int]) -> str:
    payload = {
        "name": function.name,
        "types": [item.canonical() for item in types],
        "caps": list(capacities),
        "calls": [
            [call.callee, [item.canonical() for item in call.type_args], list(call.capacity_args)]
            for call in function.calls
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _resolve_call(
    caller: Function,
    call: Call,
    functions: Mapping[str, Function],
    types: Mapping[str, Type],
    capacities: Mapping[str, int],
    limits: Limits,
) -> tuple[Function, tuple[Type, ...], tuple[int, ...], Call]:
    callee = functions.get(call.callee)
    if callee is None:
        raise GenericError("E_A1_CALL", f"unknown callee: {call.callee}", (caller.name,))
    concrete_types = tuple(item.substitute(types, capacities) for item in call.type_args)
    concrete_caps: list[int] = []
    for item in call.capacity_args:
        value: Any = capacities.get(item, item) if isinstance(item, str) else item
        if type(value) is not int or value < 0 or value > limits.max_capacity:
            raise GenericError(
                "E_A1_CAPACITY_ARGUMENT",
                "capacity must be bounded and non-negative",
                (caller.name, call.callee),
            )
        concrete_caps.append(value)
    if len(concrete_types) != len(callee.type_params):
        raise GenericError(
            "E_A1_TYPE_ARGUMENT",
            "explicit type argument arity mismatch",
            (caller.name, call.callee),
        )
    if len(concrete_caps) != len(callee.capacity_params):
        raise GenericError(
            "E_A1_CAPACITY_ARGUMENT",
            "explicit capacity argument arity mismatch",
            (caller.name, call.callee),
        )
    if any(not item.is_closed() for item in concrete_types):
        raise GenericError(
            "E_A1_TYPE_ARGUMENT",
            "specialization contains an unresolved type",
            (caller.name, call.callee),
        )
    if call.callback is not None:
        callback = functions.get(call.callback)
        if callback is None or len(concrete_types) < 2 or callback.type_params:
            raise GenericError(
                "E_A1_CALLBACK_TYPE",
                "callback must be a static closed function",
                (caller.name, call.callback),
            )
        expected = (concrete_types[0], concrete_types[1])
        if callback.params != (expected[0],) or callback.result != expected[1]:
            raise GenericError(
                "E_A1_CALLBACK_TYPE",
                "callback signature does not match map",
                (caller.name, call.callback),
            )
    resolved = Call(call.callee, concrete_types, tuple(concrete_caps), call.callback)
    return callee, concrete_types, tuple(concrete_caps), resolved


def monomorphize(program: Program, limits: Limits | None = None) -> tuple[Instance, ...]:
    """Return sorted, used-only closed instances or reject the whole expansion."""
    limits = limits or Limits()
    if limits.max_instances < 1 or limits.max_nodes < 1:
        raise GenericError("E_A1_SPECIALIZATION_LIMIT", "invalid specialization budget")
    functions = program.index()
    _validate_cycles(functions)
    roots: list[tuple[str, tuple[Type, ...], tuple[int, ...]]] = []
    for entry in sorted(program.entrypoints):
        function = functions.get(entry)
        if function is None:
            raise GenericError("E_A1_CALL", f"unknown entrypoint: {entry}")
        if function.type_params or function.capacity_params:
            raise GenericError(
                "E_A1_TYPE_ARGUMENT",
                "entrypoints require explicit closed arguments",
                (entry,),
            )
        roots.append((entry, (), ()))
    pending = set(roots)
    seen: dict[str, Instance] = {}
    nodes = 0
    while pending:
        name, type_args, cap_args = min(pending, key=lambda item: _instance_id(*item))
        pending.remove((name, type_args, cap_args))
        instance_id = _instance_id(name, type_args, cap_args)
        if instance_id in seen:
            continue
        if len(seen) >= limits.max_instances:
            raise GenericError("E_A1_SPECIALIZATION_LIMIT", "specialization budget exhausted")
        function = functions[name]
        type_map = dict(zip(function.type_params, type_args, strict=True))
        cap_map = dict(zip(function.capacity_params, cap_args, strict=True))
        resolved_calls: list[Call] = []
        for call in function.calls:
            nodes += 1
            if nodes > limits.max_nodes:
                raise GenericError(
                    "E_A1_SPECIALIZATION_LIMIT",
                    "substituted node budget exhausted",
                    (name,),
                )
            callee, child_types, child_caps, resolved = _resolve_call(
                function, call, functions, type_map, cap_map, limits
            )
            del callee
            resolved_calls.append(resolved)
            pending.add((call.callee, child_types, child_caps))
        seen[instance_id] = Instance(
            instance_id,
            name,
            tuple(type_args),
            tuple(cap_args),
            _body_hash(function, type_args, cap_args),
            tuple(resolved_calls),
        )
    return tuple(seen[key] for key in sorted(seen))


def refine_nat(value: int, *, evidence: bool = False) -> int:
    """Introduce Nat only after checker-reconstructed non-negativity evidence."""
    if type(value) is not int or value < 0 or not evidence:
        raise GenericError("E_A1_REFINEMENT", "Nat introduction lacks reconstructed evidence")
    return value


def map_values(values: Sequence[Any], capacity: int, callback: Callable[[Any], Any]) -> list[Any]:
    """Reference semantics for the bounded generic map: ordered and immutable."""
    if type(capacity) is not int or capacity < 0 or len(values) > capacity:
        raise GenericError("E_A1_CAPACITY_ARGUMENT", "list exceeds its static capacity")
    return [callback(value) for value in values]
