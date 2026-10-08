"""Additive, bounded structural effect checking for M3; not A1 proof evidence."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, NoReturn

from llmlang.a1.model import A1Error

Location = Literal["shared", "client", "server"]


class EffectError(A1Error):
    """Stable diagnostic-v1 structural effect error."""


def _fail(code: str, message: str, path: tuple[str, ...]) -> NoReturn:
    raise EffectError(code, message, path=path, phase="validate")


@dataclass(frozen=True, slots=True)
class HostOperation:
    effect: str
    capability: str
    locations: frozenset[str]


FORMAT = "a1-effects-v1"
CHECKER = "a1-effects-check-v1"
REGISTRY_VERSION = "a1-host-effects-v1"
HOST_OPERATIONS = MappingProxyType({
    "db.read": HostOperation("db.read", "db.read", frozenset({"server"})),
    "db.write": HostOperation("db.write", "db.write", frozenset({"server"})),
    "network.call": HostOperation("network.call", "network.call", frozenset({"client", "server"})),
    "clock.read": HostOperation("clock.read", "clock.read", frozenset({"client", "server"})),
})
_EFFECTS = frozenset(HOST_OPERATIONS)
_CAPABILITIES = _EFFECTS | {"identity.authenticated", "identity.admin"}
_SERVER_ONLY = frozenset({"db.read", "db.write", "identity.authenticated", "identity.admin"})


@dataclass(frozen=True, slots=True)
class EffectFunction:
    name: str
    location: Location
    effects: frozenset[str] = frozenset()
    capabilities: frozenset[str] = frozenset()
    calls: tuple[str, ...] = ()
    host_calls: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EffectLimits:
    max_functions: int = 1000
    max_edges: int = 10000
    max_call_depth: int = 64


DEFAULT_LIMITS = EffectLimits()


@dataclass(frozen=True, slots=True)
class EffectSummary:
    name: str
    transitive_effects: frozenset[str]
    transitive_capabilities: frozenset[str]


@dataclass(frozen=True, slots=True)
class EffectCheckResult:
    summaries: tuple[EffectSummary, ...]
    client_reachable: frozenset[str]
    server_reachable: frozenset[str]
    semantic_hash: str

    def summary(self, name: str) -> EffectSummary:
        for item in self.summaries:
            if item.name == name:
                return item
        raise KeyError(name)

    def to_dict(self) -> dict[str, object]:
        return {
            "format": FORMAT,
            "checker": CHECKER,
            "registry": REGISTRY_VERSION,
            "status": "checked",
            "semantic_hash": self.semantic_hash,
            "summaries": [
                {"name": item.name, "effects": sorted(item.transitive_effects),
                 "capabilities": sorted(item.transitive_capabilities)}
                for item in self.summaries
            ],
            "client_reachable": sorted(self.client_reachable),
            "server_reachable": sorted(self.server_reachable),
        }


def _symbols(value: object, allowed: frozenset[str], code: str,
             path: tuple[str, ...]) -> None:
    if not isinstance(value, frozenset) or any(not isinstance(item, str) for item in value):
        _fail(code, "immutable string set required", path)
    unknown = sorted(value - allowed)
    if unknown:
        _fail(code, f"unknown symbol {unknown[0]}", path)


def _references(value: object, path: tuple[str, ...]) -> None:
    if not isinstance(value, tuple) or any(not isinstance(item, str) or not item for item in value):
        _fail("E_A1_BINDING", "immutable reference tuple required", path)


def _reachability(entries: tuple[str, ...], table: dict[str, EffectFunction]) -> frozenset[str]:
    reached: set[str] = set()
    pending = list(entries)
    while pending:
        name = pending.pop()
        if name not in reached:
            reached.add(name)
            pending.extend(table[name].calls)
    return frozenset(reached)


def check_effect_graph(
    functions: Sequence[EffectFunction],
    *,
    client_entries: Sequence[str] = (),
    server_entries: Sequence[str] = (),
    limits: EffectLimits = DEFAULT_LIMITS,
) -> EffectCheckResult:
    """Check an adapter-derived graph, never authority or producer proof claims.

    Input declaration/edge order determines diagnostics. Sets are sorted for
    messages and hashing. Callbacks must be represented as ordinary call edges.
    """
    if not isinstance(limits, EffectLimits) or any(
        type(value) is not int or value < 0
        for value in (limits.max_functions, limits.max_edges, limits.max_call_depth)
    ) or limits.max_call_depth == 0:
        _fail("E_A1_LIMIT", "non-negative bounds and positive call depth required", ("limits",))
    if not isinstance(functions, Sequence) or isinstance(functions, (str, bytes)):
        _fail("E_A1_BINDING", "function sequence required", ("functions",))
    if len(functions) > limits.max_functions:
        _fail("E_A1_LIMIT", "function budget exceeded", ("functions",))
    snapshot = tuple(functions)
    table: dict[str, EffectFunction] = {}
    edges = 0
    for item in snapshot:
        if not isinstance(item, EffectFunction) or not isinstance(item.name, str) or not item.name:
            _fail("E_A1_BINDING", "named EffectFunction required", ("functions",))
        path = ("functions", item.name)
        if item.name in table:
            _fail("E_A1_BINDING", "duplicate function", (*path, "name"))
        table[item.name] = item
        if item.location not in ("shared", "client", "server"):
            _fail("E_A1_LOCATION", "unknown execution location", (*path, "location"))
        _symbols(item.effects, _EFFECTS, "E_A1_EFFECT", (*path, "effects"))
        _symbols(item.capabilities, _CAPABILITIES, "E_A1_CAPABILITY", (*path, "capabilities"))
        _references(item.calls, (*path, "calls"))
        _references(item.host_calls, (*path, "host_calls"))
        edges += len(item.calls) + len(item.host_calls)
        if edges > limits.max_edges:
            _fail("E_A1_LIMIT", "edge budget exceeded", ("functions",))
        if item.location == "shared" and (item.effects or item.capabilities):
            _fail("E_A1_LOCATION", "shared functions must be pure and capability-free",
                  (*path, "location"))
        for index, name in enumerate(item.host_calls):
            edge_path = (*path, "host_calls", str(index))
            operation = HOST_OPERATIONS.get(name)
            if operation is None:
                _fail("E_A1_EFFECT", f"unknown host operation {name}", edge_path)
            if item.location not in operation.locations:
                _fail("E_A1_LOCATION", "host operation forbidden at this location", edge_path)
            if operation.effect not in item.effects:
                _fail("E_A1_EFFECT", "host effect absent from function contract", edge_path)
            if operation.capability not in item.capabilities:
                _fail("E_A1_CAPABILITY", "host capability absent from function contract", edge_path)
        if item.location == "client":
            if item.capabilities & _SERVER_ONLY:
                _fail("E_A1_CAPABILITY", "server authority forbidden in client graph",
                      (*path, "capabilities"))
            if item.effects & _SERVER_ONLY:
                _fail("E_A1_LOCATION", "server effects forbidden in client graph",
                      (*path, "effects"))

    for item in snapshot:
        for index, name in enumerate(item.calls):
            path = ("functions", item.name, "calls", str(index))
            if name not in table:
                _fail("E_A1_BINDING", "unknown static callee", path)
            callee = table[name]
            if callee.location != "shared" and callee.location != item.location:
                _fail("E_A1_LOCATION", "ordinary call crosses execution boundary", path)

    entry_sets: list[tuple[str, ...]] = []
    for label, entries, location in (
        ("client_entries", client_entries, "client"),
        ("server_entries", server_entries, "server"),
    ):
        if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
            _fail("E_A1_BINDING", "entry sequence required", (label,))
        if len(entries) > limits.max_functions:
            _fail("E_A1_LIMIT", "entry budget exceeded", (label,))
        seen: set[str] = set()
        copied = tuple(entries)
        for index, name in enumerate(copied):
            path = (label, str(index))
            if not isinstance(name, str) or name not in table or name in seen:
                _fail("E_A1_BINDING", "unknown or duplicate entry", path)
            seen.add(name)
            if table[name].location not in (location, "shared"):
                _fail("E_A1_LOCATION", "entry has wrong location", path)
        entry_sets.append(copied)

    # Iterative dependency elimination avoids Python recursion even on hostile graphs.
    parents: dict[str, list[str]] = {name: [] for name in table}
    remaining = {item.name: len(set(item.calls)) for item in snapshot}
    for item in snapshot:
        for name in dict.fromkeys(item.calls):
            parents[name].append(item.name)
    ready = [item.name for item in snapshot if not remaining[item.name]]
    summaries: dict[str, EffectSummary] = {}
    depths: dict[str, int] = {}
    for name in ready:
        item = table[name]
        effects = set(item.effects)
        capabilities = set(item.capabilities)
        depth = 1
        for callee in item.calls:
            effects.update(summaries[callee].transitive_effects)
            capabilities.update(summaries[callee].transitive_capabilities)
            depth = max(depth, depths[callee] + 1)
        summaries[name] = EffectSummary(name, frozenset(effects), frozenset(capabilities))
        depths[name] = depth
        for parent in parents[name]:
            remaining[parent] -= 1
            if remaining[parent] == 0:
                ready.append(parent)
    for item in snapshot:
        if item.name not in summaries:
            _fail("E_A1_CONTROL", "cyclic call graph", ("functions", item.name, "calls"))
        if depths[item.name] > limits.max_call_depth:
            _fail("E_A1_LIMIT", "call-depth budget exceeded", ("functions", item.name, "calls"))
        for index, name in enumerate(item.calls):
            path = ("functions", item.name, "calls", str(index))
            if not summaries[name].transitive_effects <= item.effects:
                _fail("E_A1_EFFECT", "transitive callee effects exceed caller contract", path)
            if not summaries[name].transitive_capabilities <= item.capabilities:
                _fail("E_A1_CAPABILITY", "transitive callee capabilities exceed caller contract",
                      path)

    payload = {
        "format": FORMAT, "checker": CHECKER, "registry": REGISTRY_VERSION,
        "functions": [
            {"name": item.name, "location": item.location, "effects": sorted(item.effects),
             "capabilities": sorted(item.capabilities), "calls": list(item.calls),
             "host_calls": list(item.host_calls)}
            for item in snapshot
        ],
        "client_entries": list(entry_sets[0]), "server_entries": list(entry_sets[1]),
        "limits": {"max_functions": limits.max_functions, "max_edges": limits.max_edges,
                   "max_call_depth": limits.max_call_depth},
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True, allow_nan=False,
                           separators=(",", ":")).encode("ascii")
    parts = (b"llmlang:a1-effects", FORMAT.encode(), CHECKER.encode(),
             REGISTRY_VERSION.encode(), canonical)
    framed = b"".join(len(part).to_bytes(8, "big") + part for part in parts)
    return EffectCheckResult(
        tuple(summaries[item.name] for item in snapshot),
        _reachability(entry_sets[0], table), _reachability(entry_sets[1], table),
        hashlib.sha256(framed).hexdigest(),
    )
