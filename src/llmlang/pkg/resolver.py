"""Filesystem resolver, lock validation, and pkg1 snapshot checks."""

from __future__ import annotations

import os
import stat as statmod
from pathlib import Path
from typing import Any

from llmlang.core import validate
from llmlang.model import Candidate, Expr, FunctionSpec, Limits, Specification

from .model import Import, Module, Package, PkgError, PkgLimits, Snapshot
from .parser import (
    _NAME,
    _VERSION,
    DEFAULT_LIMITS,
    _json,
    _limits,
    _path,
    package_hash,
    parse_package,
)


def _err(code: str, message: str, symbol: str | None = None) -> PkgError:
    return PkgError(code, message, "resolve", symbol)


def _safe_read(path: Path, *, base: Path | None = None, max_bytes: int = 131072) -> str:
    try:
        if base is not None:
            rel = path.as_posix()
            if path.is_absolute() or any(part in ("", ".", "..") for part in rel.split("/")):
                raise _err("P_PATH", "Invalid relative path")
            fd = os.open(str(base), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                parts = rel.split("/")
                for part in parts:
                    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
                    nxt = os.open(part, flags, dir_fd=fd)
                    os.close(fd)
                    fd = nxt
                file_stat = os.fstat(fd)
                if not statmod.S_ISREG(file_stat.st_mode):
                    raise _err("P_IO", "File is not regular")
                chunks: list[bytes] = []
                total = 0
                while True:
                    chunk = os.read(fd, max_bytes + 1)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        raise _err("P_LIMIT", "File size limit exceeded")
                    chunks.append(chunk)
            finally:
                os.close(fd)
            return b"".join(chunks).decode("utf-8")
        # Traverse an external lock path component-by-component as well;
        # O_NOFOLLOW on only the final component would leave a symlink race.
        absolute = path if path.is_absolute() else Path.cwd() / path
        parts = list(absolute.parts)
        fd = os.open(parts.pop(0) or os.sep, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for part in parts:
                nxt = os.open(part, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
                os.close(fd)
                fd = nxt
            if not statmod.S_ISREG(os.fstat(fd).st_mode):
                raise _err("P_IO", "Lock is not regular")
            data = os.read(fd, max_bytes + 1)
        finally:
            os.close(fd)
        if len(data) > max_bytes:
            raise _err("P_LIMIT", "Lock size limit exceeded")
        return data.decode("utf-8")
    except PkgError:
        raise
    except (OSError, UnicodeError) as exc:
        raise _err("P_IO", "Unable to read authorized package file") from exc


class _Reader:
    """One immutable read per path with a shared whole-workspace byte budget."""

    def __init__(self, limits: PkgLimits) -> None:
        self.limits = limits
        self.total = 0
        self.cache: dict[str, str] = {}

    def read(self, path: Path, *, base: Path | None = None) -> str:
        key = str((base / path if base is not None else path).absolute())
        if key not in self.cache:
            value = _safe_read(path, base=base, max_bytes=self.limits.max_file_bytes)
            self.total += len(value.encode("utf-8"))
            if self.total > self.limits.max_total_bytes:
                raise _err("P_LIMIT", "Whole workspace source byte budget exceeded")
            self.cache[key] = value
        return self.cache[key]


def _manifest(workspace: Path, rel: str, limits: PkgLimits, reader: _Reader) -> Package:
    package_prefix = Path(rel)
    text = reader.read(package_prefix / "package.llpkg", base=workspace)
    return parse_package(text, lambda p: reader.read(package_prefix / p, base=workspace), limits)


def _check_limits(limits: PkgLimits) -> None:
    _limits(limits)


def validate_snapshot(snapshot: Snapshot, limits: PkgLimits = DEFAULT_LIMITS) -> None:
    _check_limits(limits)
    if type(snapshot) is not Snapshot or type(snapshot.root) is not str:
        raise _err("P_PARSE", "Malformed snapshot")
    packages = snapshot.packages
    if type(packages) is not tuple or not packages or len(packages) > limits.max_packages:
        raise _err("P_LIMIT", "Package budget exceeded")
    by_name: dict[str, Package] = {}
    total_modules = total_functions = total_imports = total_nodes = 0
    core_limits = Limits()
    for pkg in packages:
        if (
            type(pkg) is not Package
            or type(pkg.name) is not str
            or type(pkg.version) is not str
            or type(pkg.dependencies) is not tuple
            or type(pkg.modules) is not tuple
            or pkg.name in by_name
        ):
            raise _err("P_DUPLICATE", "Duplicate package identity")
        by_name[pkg.name] = pkg
        if not pkg.modules:
            raise _err("P_PARSE", "Package requires a module")
        for dep_item in pkg.dependencies:
            if (
                type(dep_item) is not tuple
                or len(dep_item) != 2
                or type(dep_item[0]) is not str
                or type(dep_item[1]) is not str
            ):
                raise _err("P_PARSE", "Malformed dependency", pkg.name)
        if len({dep[0] for dep in pkg.dependencies}) != len(pkg.dependencies):
            raise _err("P_DUPLICATE", "Duplicate dependency", pkg.name)
        module_names: set[str] = set()
        for module in pkg.modules:
            if (
                type(module) is not Module
                or type(module.name) is not str
                or type(module.names) is not tuple
                or type(module.imports) is not tuple
                or type(module.exports) is not tuple
            ):
                raise _err("P_PARSE", "Malformed module", pkg.name)
            if _NAME.fullmatch(module.name) is None or module.name in module_names:
                raise _err("P_NAME", "Invalid or duplicate module name", module.name)
            module_names.add(module.name)
            if (
                type(module.spec) is not Specification
                or type(module.candidate) is not Candidate
                or type(module.spec.functions) is not tuple
                or type(module.candidate.bodies) is not tuple
                or not module.names
            ):
                raise _err("P_PARSE", "Malformed P0 module container", module.name)
            for fn in module.spec.functions:
                if type(fn) is not FunctionSpec or type(fn.params) is not tuple:
                    raise _err("P_TYPE", "Malformed function contract", module.name)
            trees = [body for body in module.candidate.bodies]
            trees.extend(expr for fn in module.spec.functions for expr in (fn.requires, fn.ensures))
            pending = [(expr, 1) for expr in trees]
            while pending:
                expr, depth = pending.pop()
                total_nodes += 1
                if total_nodes > core_limits.max_nodes or depth > core_limits.max_depth:
                    raise _err("P_LIMIT", "Whole Core AST budget exceeded")
                if type(expr) is not Expr or type(expr.args) is not tuple:
                    raise _err("P_TYPE", "Malformed expression", module.name)
                pending.extend((arg, depth + 1) for arg in expr.args)
            if any(type(name) is not str or _NAME.fullmatch(name) is None for name in module.names):
                raise _err("P_NAME", "Invalid function name", module.name)
            if any(
                type(name) is not str or _NAME.fullmatch(name) is None for name in module.exports
            ):
                raise _err("P_NAME", "Invalid export name", module.name)
            for imp in module.imports:
                if type(imp) is not Import or any(
                    type(value) is not str or _NAME.fullmatch(value) is None
                    for value in (imp.alias, imp.package, imp.module, imp.export)
                ):
                    raise _err("P_PARSE", "Malformed import", module.name)
            if len(module.names) != len(module.spec.functions) or len(module.names) != len(
                module.candidate.bodies
            ):
                raise _err("P_PARSE", "Module declaration count mismatch", module.name)
            names = set(module.names)
            if len(names) != len(module.names) or len(set(module.exports)) != len(module.exports):
                raise _err("P_DUPLICATE", "Duplicate module symbol", module.name)
            if any(name not in names for name in module.exports):
                raise _err("P_PRIVATE", "Export is not local", module.name)
            aliases = [i.alias for i in module.imports]
            if len(set(aliases)) != len(aliases) or names.intersection(aliases):
                raise _err("P_DUPLICATE", "Import alias collision", module.name)
        total_modules += len(pkg.modules)
        total_functions += sum(len(m.names) for m in pkg.modules)
        total_imports += sum(len(m.imports) for m in pkg.modules)
        if _NAME.fullmatch(pkg.name) is None:
            raise _err("P_NAME", "Invalid package name", pkg.name)
        if _VERSION.fullmatch(pkg.version) is None:
            raise _err("P_VERSION", "Invalid package version", pkg.name)
    if (
        total_modules > limits.max_modules
        or total_functions > limits.max_functions
        or total_imports > limits.max_imports
    ):
        raise _err("P_LIMIT", "Aggregate package budget exceeded")
    if snapshot.root not in by_name:
        raise _err("P_DEPENDENCY", "Root package is absent", snapshot.root)
    # Exact dependency identities and visibility.
    for pkg in packages:
        deps = dict(pkg.dependencies)
        for dep, version in pkg.dependencies:
            target = by_name.get(dep)
            if target is None or target.version != version:
                raise _err("P_DEPENDENCY", "Dependency is not pinned in snapshot", dep)
        for module in pkg.modules:
            for imp in module.imports:
                if imp.package != pkg.name and imp.package not in deps:
                    raise _err("P_PRIVATE", "Transitive dependency is not visible", imp.package)
                target_pkg = by_name.get(imp.package)
                if target_pkg is None:
                    raise _err("P_UNBOUND", "Import package is absent", imp.package)
                target_module = next((m for m in target_pkg.modules if m.name == imp.module), None)
                if target_module is None or imp.export not in target_module.names:
                    raise _err("P_UNBOUND", "Import export target is unavailable", imp.export)
                if imp.export not in target_module.exports:
                    raise _err("P_PRIVATE", "Import target is private", imp.export)
                if imp.package == pkg.name and imp.module == module.name:
                    raise _err("P_CYCLE", "Module cannot import itself", module.name)
    # P0 call indices in a module are relative to imports followed by locals.
    # Validate against an ephemeral signature/body prefix for those imports;
    # the immutable source module and its function order are not changed.
    for pkg in packages:
        for module in pkg.modules:
            imported: list[FunctionSpec] = []
            for imp in module.imports:
                target_pkg = by_name[imp.package]
                target_module = next(m for m in target_pkg.modules if m.name == imp.module)
                imported.append(target_module.spec.functions[target_module.names.index(imp.export)])
            if imported:
                augmented = Specification(
                    tuple(imported) + module.spec.functions, module.spec.profile
                )
                placeholders = tuple(
                    Expr("int", value=0) if fn.returns == "Int" else Expr("bool", value=False)
                    for fn in imported
                )
                candidate = Candidate(
                    placeholders + module.candidate.bodies, module.candidate.profile
                )
            else:
                augmented, candidate = module.spec, module.candidate
            try:
                validate(augmented, candidate)
            except Exception as exc:
                source_code = getattr(exc, "code", "")
                code = {
                    "E_CALL": "P_CALL",
                    "E_BINDING": "P_BINDING",
                    "E_LIMIT": "P_LIMIT",
                    "E_TYPE": "P_TYPE",
                }.get(str(source_code), "P_TYPE")
                raise _err(code, "Invalid P0 module", module.name) from exc
    # Package DAG (self edges and cycles).
    state: dict[str, int] = {}

    def visit(name: str) -> None:
        if state.get(name) == 1:
            raise _err("P_CYCLE", "Package dependency cycle", name)
        if state.get(name) == 2:
            return
        state[name] = 1
        for dep, _ in sorted(by_name[name].dependencies):
            if dep not in by_name:
                raise _err("P_DEPENDENCY", "Missing dependency", dep)
            visit(dep)
        state[name] = 2

    for name in sorted(by_name):
        visit(name)
    reachable: set[str] = set()

    def collect(name: str) -> None:
        if name in reachable:
            return
        reachable.add(name)
        for dep, _ in by_name[name].dependencies:
            collect(dep)

    collect(snapshot.root)
    if reachable != set(by_name):
        raise _err("P_DEPENDENCY", "Snapshot contains packages outside root closure")
    module_state: dict[tuple[str, str], int] = {}

    def visit_module(key: tuple[str, str]) -> None:
        current = module_state.get(key, 0)
        if current == 1:
            raise _err("P_CYCLE", "Module import cycle", f"{key[0]}.{key[1]}")
        if current == 2:
            return
        module_state[key] = 1
        pkg = by_name[key[0]]
        module = next(m for m in pkg.modules if m.name == key[1])
        for imp in sorted(module.imports, key=lambda item: (item.package, item.module, item.alias)):
            if imp.package == pkg.name:
                visit_module((imp.package, imp.module))
        module_state[key] = 2

    for key in sorted((pkg.name, module.name) for pkg in packages for module in pkg.modules):
        visit_module(key)


def _lock(lock_text: str) -> dict[str, Any]:
    obj = _json(lock_text)
    if set(obj) != {"format", "root", "packages"} or obj["format"] != "pkg1-lock":
        raise _err("P_PARSE", "Invalid lock format")
    if type(obj["root"]) is not str or type(obj["packages"]) is not list:
        raise _err("P_PARSE", "Malformed lock")
    return obj


def resolve(workspace: Path, lock_path: Path, limits: PkgLimits = DEFAULT_LIMITS) -> Snapshot:
    _check_limits(limits)
    try:
        base = workspace.resolve(strict=True)
    except OSError as exc:
        raise _err("P_IO", "Workspace is unavailable") from exc
    reader = _Reader(limits)
    lock = _lock(reader.read(lock_path))
    entries = lock["packages"]
    if len(entries) > limits.max_packages:
        raise _err("P_LIMIT", "Package budget exceeded")
    packages: list[Package] = []
    seen: set[str] = set()
    for raw in entries:
        if type(raw) is not dict or set(raw) != {"name", "version", "path", "sha256"}:
            raise _err("P_PARSE", "Malformed lock package")
        name, version, rel, expected = raw["name"], raw["version"], raw["path"], raw["sha256"]
        rel = _path(rel)
        if (
            type(expected) is not str
            or len(expected) != 64
            or any(c not in "0123456789abcdef" for c in expected)
        ):
            raise _err("P_HASH", "Invalid package hash")
        if type(name) is not str or name in seen:
            raise _err("P_DUPLICATE", "Duplicate lock package")
        pkg = _manifest(base, rel, limits, reader)
        if pkg.name != name or pkg.version != version:
            raise _err("P_DEPENDENCY", "Lock identity does not match manifest", name)
        if package_hash(pkg) != expected:
            raise _err("P_HASH", "Package hash does not match lock", name)
        seen.add(name)
        packages.append(pkg)
    snapshot = Snapshot(lock["root"], tuple(sorted(packages, key=lambda p: p.name)))
    validate_snapshot(snapshot, limits)
    # Ensure lock is exact closure from root.
    by_name = {p.name: p for p in snapshot.packages}
    reachable: set[str] = set()

    def walk(name: str) -> None:
        if name in reachable:
            return
        reachable.add(name)
        for dep, _ in by_name[name].dependencies:
            walk(dep)

    walk(snapshot.root)
    if reachable != set(by_name):
        raise _err("P_DEPENDENCY", "Lock is not exact dependency closure")
    return snapshot


def freeze(
    workspace: Path, root: str, selection: dict[str, str], limits: PkgLimits = DEFAULT_LIMITS
) -> dict[str, object]:
    _check_limits(limits)
    try:
        base = workspace.resolve(strict=True)
    except OSError as exc:
        raise _err("P_IO", "Workspace is unavailable") from exc
    reader = _Reader(limits)
    if type(selection) is not dict or root not in selection:
        raise _err("P_DEPENDENCY", "Root is absent from explicit selection", root)
    loaded: dict[str, Package] = {}
    paths: dict[str, str] = {}
    pending = [root]
    while pending:
        name = pending.pop()
        if name in loaded:
            continue
        rel = selection.get(name)
        if type(rel) is not str:
            raise _err("P_PATH", "Selection path is invalid", name)
        rel = _path(rel)
        pkg = _manifest(base, rel, limits, reader)
        if pkg.name != name:
            raise _err("P_DEPENDENCY", "Selection name mismatches manifest", name)
        loaded[name], paths[name] = pkg, rel
        pending.extend(dep for dep, _ in pkg.dependencies)
        if len(loaded) > limits.max_packages:
            raise _err("P_LIMIT", "Package budget exceeded")
    if set(selection) != set(loaded):
        raise _err("P_DEPENDENCY", "Selection contains packages outside closure")
    snapshot = Snapshot(root, tuple(sorted(loaded.values(), key=lambda p: p.name)))
    validate_snapshot(snapshot, limits)
    return {
        "format": "pkg1-lock",
        "root": root,
        "packages": [
            {"name": p.name, "version": p.version, "path": paths[p.name], "sha256": package_hash(p)}
            for p in snapshot.packages
        ],
    }
