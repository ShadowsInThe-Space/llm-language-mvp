"""Independent structural link check; no linker or solver in acceptance paths."""

import hashlib
import json

from llmlang.core import validate
from llmlang.model import Candidate, Expr, LanguageError, Limits, Specification
from llmlang.parser import canonical_candidate, canonical_spec
from llmlang.proof import baseline_hash, candidate_hash, check_certificate, verify

from .model import BoundProgram, Module, Package, PkgError, PkgLimits, Snapshot
from .parser import package_hash, snapshot_hash
from .resolver import validate_snapshot

DEFAULT_LIMITS = PkgLimits()
DEFAULT_CORE_LIMITS = Limits()


def _order(modules: dict[tuple[str, str], Module]) -> list[tuple[str, str]]:
    """Explicit stack replay of the normative sorted depth-first ordering."""
    result: list[tuple[str, str]] = []
    state: dict[tuple[str, str], int] = {}
    for root in sorted(modules):
        stack = [(root, False)]
        while stack:
            key, exit_node = stack.pop()
            if exit_node:
                state[key] = 2
                result.append(key)
                continue
            if state.get(key) == 2:
                continue
            if state.get(key) == 1:
                raise PkgError("P_CYCLE", "Cyclic module binding", "bind")
            state[key] = 1
            stack.append((key, True))
            providers = sorted({(imp.package, imp.module) for imp in modules[key].imports})
            stack.extend((provider, False) for provider in reversed(providers))
    return result


def _same_body(source: Expr, target: Expr, slots: list[int], available: int) -> bool:
    """Bisimulation on trees, with exactly one allowed change: call relocation."""
    pending = [(source, target)]
    while pending:
        left, right = pending.pop()
        if left.op != right.op or len(left.args) != len(right.args):
            return False
        if left.op == "call":
            index = left.value
            if type(index) is not int or not 0 <= index < available:
                return False
            if right.value != slots[index]:
                return False
        elif left.value != right.value or type(left.value) is not type(right.value):
            return False
        pending.extend(zip(left.args, right.args, strict=True))
    return True


def _expected_manifest(
    snapshot: Snapshot, bound: BoundProgram, limits: PkgLimits, core_limits: Limits
) -> dict[str, object] | None:
    validate_snapshot(snapshot, limits)
    validate(bound.spec, bound.candidate, core_limits)
    packages: dict[str, Package] = {p.name: p for p in snapshot.packages}
    modules = {(p.name, m.name): m for p in snapshot.packages for m in p.modules}
    order = _order(modules)
    offsets: dict[tuple[str, str], int] = {}
    size = 0
    for key in order:
        offsets[key] = size
        size += len(modules[key].names)
    if size != len(bound.spec.functions) or size != len(bound.candidate.bodies):
        return None
    rows: list[dict[str, object]] = []
    for key in order:
        package, module = packages[key[0]], modules[key]
        slots: list[int] = []
        for imp in module.imports:
            # Reconstruct visibility and exact exported identity, not linker metadata.
            if imp.package != package.name and imp.package not in dict(package.dependencies):
                return None
            provider = modules[(imp.package, imp.module)]
            if imp.export not in provider.exports or imp.export not in provider.names:
                return None
            slots.append(offsets[(imp.package, imp.module)] + provider.names.index(imp.export))
        slots.extend(range(offsets[key], offsets[key] + len(module.names)))
        for index, name in enumerate(module.names):
            slot = offsets[key] + index
            contract = module.spec.functions[index]
            body = module.candidate.bodies[index]
            if bound.spec.functions[slot] != contract:
                return None
            if not _same_body(
                body, bound.candidate.bodies[slot], slots, len(module.imports) + index
            ):
                return None
            rows.append(
                {
                    "package": package.name,
                    "version": package.version,
                    "package_hash": package_hash(package),
                    "module": module.name,
                    "name": name,
                    "exported": name in module.exports,
                    "local_index": index,
                    "core_slot": slot,
                    "contract": canonical_spec(Specification((contract,))),
                    "body": canonical_candidate(Candidate((body,))),
                    "call_slots": slots,
                    "parameters": list(contract.params),
                    "binder_indices": list(reversed(range(len(contract.params)))),
                }
            )
    manifest: dict[str, object] = {
        "format": "pkg1-bound",
        "checker": "pkg1-bind-v1",
        "snapshot_hash": snapshot_hash(snapshot),
        "baseline_hash": baseline_hash(bound.spec),
        "candidate_hash": candidate_hash(bound.candidate),
        "functions": rows,
    }
    encoded = json.dumps(manifest, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    manifest["bound_hash"] = hashlib.sha256(b"pkg1:bound\0" + encoded.encode()).hexdigest()
    return manifest


def check_binding(
    snapshot: Snapshot,
    bound: BoundProgram,
    limits: PkgLimits = DEFAULT_LIMITS,
    core_limits: Limits = DEFAULT_CORE_LIMITS,
) -> bool:
    """Reconstruct every binding from separately authorized inputs; fail closed."""
    try:
        if type(bound) is not BoundProgram or type(bound.manifest) is not dict:
            return False
        expected = _expected_manifest(snapshot, bound, limits, core_limits)
        # Serialized equality prevents Python's True == 1 from accepting malformed evidence.
        return expected is not None and json.dumps(
            expected, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False
        ) == json.dumps(
            bound.manifest,
            sort_keys=True,
            ensure_ascii=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (
        PkgError,
        LanguageError,
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        AttributeError,
        RecursionError,
        OverflowError,
    ):
        return False


def check_package_certificate(
    snapshot: Snapshot,
    bound: BoundProgram,
    evidence: object,
    limits: PkgLimits = DEFAULT_LIMITS,
    core_limits: Limits = DEFAULT_CORE_LIMITS,
) -> bool:
    if not check_binding(snapshot, bound, limits, core_limits):
        return False
    if type(evidence) is not dict or set(evidence) != {
        "format",
        "snapshot_hash",
        "bound_hash",
        "core_certificate",
    }:
        return False
    if (
        evidence["format"] != "pkg1-proof"
        or evidence["snapshot_hash"] != snapshot_hash(snapshot)
        or evidence["bound_hash"] != bound.manifest["bound_hash"]
        or type(evidence["core_certificate"]) is not dict
    ):
        return False
    return check_certificate(bound.spec, bound.candidate, evidence["core_certificate"], core_limits)


def verify_package(
    snapshot: Snapshot,
    bound: BoundProgram,
    limits: PkgLimits = DEFAULT_LIMITS,
    core_limits: Limits = DEFAULT_CORE_LIMITS,
) -> dict[str, object]:
    if not check_binding(snapshot, bound, limits, core_limits):
        return {
            "status": "invalid",
            "certificate": None,
            "diagnostics": [
                PkgError("P_BINDING", "Source-to-Core binding rejected", "bind").to_dict()
            ],
        }
    report = verify(bound.spec, bound.candidate, core_limits)
    evidence = {
        "format": "pkg1-proof",
        "snapshot_hash": snapshot_hash(snapshot),
        "bound_hash": bound.manifest["bound_hash"],
        "core_certificate": report.certificate,
    }
    if report.status == "proved" and check_package_certificate(
        snapshot, bound, evidence, limits, core_limits
    ):
        return {"status": "proved", "certificate": evidence, "core": report.to_dict()}
    return {
        "status": report.status if report.status != "proved" else "unverified",
        "certificate": None,
        "core": report.to_dict(),
    }
