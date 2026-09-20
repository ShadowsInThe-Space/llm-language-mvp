"""Deterministic PKG1 linker.

The linker is deliberately a proposal generator: package validation is delegated to
the resolver and the resulting program is always checked by the unchanged P0 checker.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from typing import cast

from llmlang.core import validate
from llmlang.model import Candidate, Expr, FunctionSpec, Limits, Specification
from llmlang.parser import canonical_candidate, canonical_spec
from llmlang.proof import baseline_hash, candidate_hash

from .model import BoundProgram, Module, Package, PkgError, PkgLimits, Snapshot
from .parser import package_hash, snapshot_hash
from .resolver import validate_snapshot


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _bound_digest(manifest: dict[str, object]) -> str:
    body = {key: value for key, value in manifest.items() if key != "bound_hash"}
    return hashlib.sha256(b"pkg1:bound\0" + _json(body).encode("utf-8")).hexdigest()


def canonical_bound(bound: BoundProgram) -> str:
    """Return the canonical JSON representation of a bound manifest."""
    return _json(bound.manifest)


def _error(exc: Exception, code: str = "P_TYPE") -> PkgError:
    if hasattr(exc, "code"):
        source = cast(object, exc)
        original = getattr(source, "code", "")
        code = {
            "E_CALL": "P_CALL",
            "E_BINDING": "P_BINDING",
            "E_TYPE": "P_TYPE",
            "E_LIMIT": "P_LIMIT",
        }.get(str(original), code)
    return PkgError(code, str(exc), phase="link")


def _rewrite(expr: Expr, imports: tuple[int, ...], local_start: int, local_index: int) -> Expr:
    if expr.op == "call":
        if type(expr.value) is not int or expr.value < 0:
            raise PkgError("P_CALL", "Invalid call index", phase="link")
        index = expr.value
        if index < len(imports):
            target = imports[index]
        else:
            local = index - len(imports)
            if local >= local_index:
                raise PkgError("P_CALL", "Forward or self local call", phase="link")
            target = local_start + local
        rewritten = tuple(
            _rewrite(a, imports, local_start, local_index) for a in expr.args
        )
        return replace(expr, value=target, args=rewritten)
    if not expr.args:
        return expr
    rewritten = tuple(_rewrite(a, imports, local_start, local_index) for a in expr.args)
    return replace(expr, args=rewritten)


def _module_map(snapshot: Snapshot) -> dict[tuple[str, str], tuple[Package, Module]]:
    result: dict[tuple[str, str], tuple[Package, Module]] = {}
    for package in snapshot.packages:
        for module in package.modules:
            key = (package.name, module.name)
            if key in result:
                raise PkgError("P_DUPLICATE", "Duplicate package/module", phase="link")
            result[key] = (package, module)
    return result


def link(
    snapshot: Snapshot,
    limits: PkgLimits = PkgLimits(),  # noqa: B008
    core_limits: Limits = Limits(),  # noqa: B008
) -> BoundProgram:
    """Resolve a validated snapshot into one deterministic, closed P0 program."""
    try:
        validate_snapshot(snapshot, limits=limits)
    except PkgError:
        raise
    except Exception as exc:
        raise _error(exc, "P_PARSE") from None

    modules = _module_map(snapshot)
    packages = {package.name: package for package in snapshot.packages}
    visiting: set[tuple[str, str]] = set()
    visited: set[tuple[str, str]] = set()
    order: list[tuple[str, str]] = []

    def providers(key: tuple[str, str], module: Module) -> list[tuple[str, str]]:
        package = packages[key[0]]
        found: list[tuple[str, str]] = []
        for item in module.imports:
            target = (item.package, item.module)
            if item.package != package.name and item.package not in dict(package.dependencies):
                raise PkgError(
                    "P_DEPENDENCY",
                    "Import is not a direct dependency",
                    phase="link",
                    symbol=item.alias,
                )
            if target not in modules:
                raise PkgError(
                    "P_UNBOUND", "Import provider does not exist", phase="link", symbol=item.alias
                )
            found.append(target)
        return sorted(set(found))

    def visit(key: tuple[str, str]) -> None:
        if key in visited:
            return
        if key in visiting:
            raise PkgError(
                "P_CYCLE", "Package/module import cycle", phase="link", symbol=f"{key[0]}.{key[1]}"
            )
        visiting.add(key)
        package, module = modules[key]
        for provider in providers(key, module):
            visit(provider)
        visiting.remove(key)
        visited.add(key)
        order.append(key)

    for key in sorted(modules):
        visit(key)

    starts: dict[tuple[str, str], int] = {}
    cursor = 0
    for key in order:
        starts[key] = cursor
        cursor += len(modules[key][1].names)

    specs: list[FunctionSpec] = []
    bodies: list[Expr] = []
    rows: list[dict[str, object]] = []
    for key in order:
        package, module = modules[key]
        exports = set(module.exports)
        import_slots: list[int] = []
        for item in module.imports:
            provider_key = (item.package, item.module)
            _, provider = modules[provider_key]
            if item.export not in provider.exports or item.export not in provider.names:
                raise PkgError(
                    "P_PRIVATE",
                    "Import targets a private or unknown export",
                    phase="link",
                    symbol=item.alias,
                )
            provider_index = provider.names.index(item.export)
            import_slots.append(starts[provider_key] + provider_index)
        phash = package_hash(package)
        entries = zip(module.names, module.spec.functions, module.candidate.bodies, strict=True)
        for index, (name, function, body) in enumerate(entries):
            rewritten = _rewrite(body, tuple(import_slots), starts[key], index)
            specs.append(function)
            bodies.append(rewritten)
            rows.append(
                {
                    "package": package.name,
                    "version": package.version,
                    "package_hash": phash,
                    "module": module.name,
                    "name": name,
                    "exported": name in exports,
                    "local_index": index,
                    "core_slot": starts[key] + index,
                    "contract": canonical_spec(Specification((function,))),
                    "body": canonical_candidate(Candidate((body,))),
                    "call_slots": import_slots
                    + [starts[key] + local for local in range(len(module.names))],
                    "parameters": list(function.params),
                    "binder_indices": list(range(len(function.params) - 1, -1, -1)),
                }
            )

    linked_spec = Specification(tuple(specs))
    linked_candidate = Candidate(tuple(bodies))
    try:
        validate(linked_spec, linked_candidate, core_limits)
    except Exception as exc:
        raise _error(exc) from None

    manifest: dict[str, object] = {
        "format": "pkg1-bound",
        "checker": "pkg1-bind-v1",
        "snapshot_hash": snapshot_hash(snapshot),
        "baseline_hash": baseline_hash(linked_spec),
        "candidate_hash": candidate_hash(linked_candidate),
        "functions": rows,
    }
    manifest["bound_hash"] = _bound_digest(manifest)
    return BoundProgram(linked_spec, linked_candidate, manifest)
