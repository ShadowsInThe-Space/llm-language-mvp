"""Strict pkg1 manifest parser and canonical identity helpers."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from typing import Any

from llmlang.parser import canonical_candidate, canonical_spec, parse_candidate, parse_spec

from .model import Import, Module, Package, PkgError, PkgLimits, Snapshot

_NAME = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")
_VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\Z")
DEFAULT_LIMITS = PkgLimits()


def _err(code: str, message: str, phase: str = "parse", symbol: str | None = None) -> PkgError:
    return PkgError(code, message, phase, symbol)


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise _err("P_DUPLICATE", "Duplicate JSON key")
        out[key] = value
    return out


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant: {value}")


def _json(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text, object_pairs_hook=_pairs, parse_constant=_reject_constant)
    except PkgError:
        raise
    except (json.JSONDecodeError, UnicodeError, TypeError, ValueError, RecursionError) as exc:
        raise _err("P_PARSE", "Invalid JSON") from exc
    if type(value) is not dict:
        raise _err("P_PARSE", "Manifest must be a JSON object")
    return value


def _object(value: Any, fields: set[str]) -> dict[str, Any]:
    if type(value) is not dict or set(value) != fields:
        raise _err("P_PARSE", "Object has unexpected fields")
    return value


def _name(value: Any) -> str:
    if type(value) is not str or _NAME.fullmatch(value) is None:
        raise _err("P_NAME", "Invalid identifier")
    return value


def _version(value: Any) -> str:
    if type(value) is not str or _VERSION.fullmatch(value) is None:
        raise _err("P_VERSION", "Invalid exact version")
    return value


def _path(value: Any) -> str:
    if type(value) is not str or not value or "\\" in value or "\x00" in value:
        raise _err("P_PATH", "Invalid relative path")
    parts = value.split("/")
    if any(not part or part in (".", "..") for part in parts) or value.startswith("/"):
        raise _err("P_PATH", "Invalid relative path")
    return value


def _limits(limits: PkgLimits) -> None:
    if type(limits) is not PkgLimits:
        raise _err("P_LIMIT", "Invalid package budget object")
    values = (
        limits.max_packages,
        limits.max_modules,
        limits.max_functions,
        limits.max_imports,
        limits.max_total_bytes,
        limits.max_file_bytes,
    )
    defaults = (
        DEFAULT_LIMITS.max_packages,
        DEFAULT_LIMITS.max_modules,
        DEFAULT_LIMITS.max_functions,
        DEFAULT_LIMITS.max_imports,
        DEFAULT_LIMITS.max_total_bytes,
        DEFAULT_LIMITS.max_file_bytes,
    )
    for value, maximum in zip(values, defaults, strict=True):
        if type(value) is not int or value <= 0 or value > maximum:
            raise _err("P_LIMIT", "Invalid package budget")


def parse_package(
    manifest_text: str, read_file: Callable[[str], str], limits: PkgLimits = DEFAULT_LIMITS
) -> Package:
    _limits(limits)
    try:
        if (
            type(manifest_text) is not str
            or len(manifest_text.encode("utf-8")) > limits.max_file_bytes
        ):
            raise _err("P_LIMIT", "Manifest size limit exceeded")
    except UnicodeEncodeError as exc:
        raise _err("P_PARSE", "Manifest is not valid UTF-8") from exc
    data = _json(manifest_text)
    _object(data, {"format", "name", "version", "dependencies", "modules"})
    if data["format"] != "pkg1":
        raise _err("P_PARSE", "Expected pkg1 manifest")
    name, version = _name(data["name"]), _version(data["version"])
    deps_value = data["dependencies"]
    if type(deps_value) is not dict:
        raise _err("P_PARSE", "Dependencies must be an object")
    dependencies: list[tuple[str, str]] = []
    for dep, dep_version in deps_value.items():
        dependencies.append((_name(dep), _version(dep_version)))
    modules_value = data["modules"]
    if type(modules_value) is not list or not modules_value:
        raise _err("P_PARSE", "Package must contain modules")
    modules: list[Module] = []
    seen_modules: set[str] = set()
    total = len(manifest_text.encode("utf-8"))
    for raw in modules_value:
        item = _object(raw, {"name", "names", "imports", "exports", "spec", "source"})
        module_name = _name(item["name"])
        if module_name in seen_modules:
            raise _err("P_DUPLICATE", "Duplicate module name", symbol=module_name)
        seen_modules.add(module_name)
        names = item["names"]
        if type(names) is not list or not names:
            raise _err("P_PARSE", "Module must contain functions")
        fn_names = tuple(_name(v) for v in names)
        if len(set(fn_names)) != len(fn_names):
            raise _err("P_DUPLICATE", "Duplicate function name", symbol=module_name)
        imports_raw = item["imports"]
        if type(imports_raw) is not list:
            raise _err("P_PARSE", "Imports must be an array")
        imports: list[Import] = []
        aliases: set[str] = set()
        for raw_import in imports_raw:
            imp = _object(raw_import, {"alias", "package", "module", "export"})
            alias = _name(imp["alias"])
            if alias in aliases or alias in fn_names:
                raise _err("P_DUPLICATE", "Import alias collides with local name", symbol=alias)
            aliases.add(alias)
            imports.append(
                Import(alias, _name(imp["package"]), _name(imp["module"]), _name(imp["export"]))
            )
        exports_raw = item["exports"]
        if type(exports_raw) is not list:
            raise _err("P_PARSE", "Exports must be an array")
        exports = tuple(_name(v) for v in exports_raw)
        if len(set(exports)) != len(exports):
            raise _err("P_DUPLICATE", "Duplicate export name", symbol=module_name)
        if any(v not in fn_names for v in exports):
            raise _err("P_PRIVATE", "Export is not a local function", symbol=module_name)
        spec_path, source_path = _path(item["spec"]), _path(item["source"])
        try:
            spec_text, source_text = read_file(spec_path), read_file(source_path)
        except PkgError:
            raise
        except Exception as exc:
            raise _err("P_IO", "Unable to read package source") from exc
        if type(spec_text) is not str or type(source_text) is not str:
            raise _err("P_IO", "Unable to read package source")
        total += len(spec_text.encode("utf-8")) + len(source_text.encode("utf-8"))
        if (
            max(len(spec_text.encode("utf-8")), len(source_text.encode("utf-8")))
            > limits.max_file_bytes
        ):
            raise _err("P_LIMIT", "Source file size limit exceeded", symbol=module_name)
        if total > limits.max_total_bytes:
            raise _err("P_LIMIT", "Package source budget exceeded")
        try:
            spec, candidate = parse_spec(spec_text), parse_candidate(source_text)
        except Exception as exc:
            if isinstance(exc, PkgError):
                raise
            code = getattr(exc, "code", "P_TYPE")
            raise _err(
                "P_TYPE" if code.startswith("E_") else str(code),
                "Invalid P0 module",
                symbol=module_name,
            ) from exc
        if len(spec.functions) != len(fn_names) or len(candidate.bodies) != len(fn_names):
            raise _err(
                "P_PARSE", "Function declaration count does not match names", symbol=module_name
            )
        modules.append(
            Module(module_name, fn_names, tuple(imports), tuple(sorted(exports)), spec, candidate)
        )
    if len(modules) > limits.max_modules:
        raise _err("P_LIMIT", "Module budget exceeded")
    if sum(len(m.names) for m in modules) > limits.max_functions:
        raise _err("P_LIMIT", "Function budget exceeded")
    if sum(len(m.imports) for m in modules) > limits.max_imports:
        raise _err("P_LIMIT", "Import budget exceeded")
    return Package(name, version, tuple(sorted(dependencies)), tuple(modules))


def _package_obj(pkg: Package) -> dict[str, object]:
    return {
        "dependencies": {k: v for k, v in sorted(pkg.dependencies)},
        "format": "pkg1",
        "name": pkg.name,
        "version": pkg.version,
        "modules": [
            {
                "exports": list(sorted(m.exports)),
                "imports": [
                    {"alias": i.alias, "export": i.export, "module": i.module, "package": i.package}
                    for i in m.imports
                ],
                "name": m.name,
                "names": list(m.names),
                "source": canonical_candidate(m.candidate),
                "spec": canonical_spec(m.spec),
            }
            for m in sorted(pkg.modules, key=lambda x: x.name)
        ],
    }


def canonical_package(pkg: Package) -> str:
    return json.dumps(_package_obj(pkg), ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def canonical_snapshot(snapshot: Snapshot) -> str:
    packages = sorted(snapshot.packages, key=lambda x: x.name)
    obj = {
        "format": "pkg1-snapshot",
        "packages": [_package_obj(p) for p in packages],
        "root": snapshot.root,
    }
    return json.dumps(obj, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def package_hash(pkg: Package) -> str:
    return hashlib.sha256(b"pkg1:package\0" + canonical_package(pkg).encode("utf-8")).hexdigest()


def snapshot_hash(snapshot: Snapshot) -> str:
    return hashlib.sha256(
        b"pkg1:snapshot\0" + canonical_snapshot(snapshot).encode("utf-8")
    ).hexdigest()
