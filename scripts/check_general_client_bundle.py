"""Audit actual built client files and source maps for generated server artifacts.

This static artifact check is evidence about the inspected build, not a proof of
browser isolation. Source paths are inspected as data and are never opened.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote

MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_FILES = 10000
_SERVER_NAMES = frozenset({
    "server.ts", "a1-pure.ts", "schema.sql", "program.json", "source.webapp",
})
_SERVER_SUFFIXES = (".a1src", ".webuilib", ".webapp")
_SERVER_MARKERS = frozenset({
    "invokePure", "moduleIR", "db.write", "db.read", "identity.admin",
    "identity.authenticated", "a1-pure-runtime-v1", "web-program-v1",
    "general-web-build-v1", "a1-ir-v1", "(websrc1", "(webapp1", "(webuilib1", "(a1src1",
})


class AuditError(ValueError):
    """Missing audit evidence, malformed artifacts, or a server artifact leak."""


@dataclass(frozen=True)
class AuditResult:
    javascript_files: int
    source_maps: int


def _read(path: Path) -> str:
    if path.stat().st_size > MAX_FILE_BYTES:
        raise AuditError(f"Artifact exceeds file budget: {path}")
    return path.read_text(encoding="utf-8")


def _json(text: str, label: str) -> Any:
    try:
        return json.loads(text)
    except (ValueError, RecursionError) as error:
        raise AuditError(f"Malformed JSON artifact: {label}") from error


def _server_path(name: str) -> bool:
    normalized = unquote(name).replace("\\", "/").split("?", 1)[0].split("#", 1)[0]
    basename = normalized.rsplit("/", 1)[-1]
    return basename in _SERVER_NAMES or basename.endswith(_SERVER_SUFFIXES)


def _markers(program_dir: Path) -> tuple[frozenset[str], frozenset[str]]:
    markers = set(_SERVER_MARKERS)
    sql = set()
    for name in ("history", "tasks"):
        directory = program_dir / name
        program = _json(_read(directory / "program.json"), f"{name}/program.json")
        if not isinstance(program, dict) or program.get("format") != "web-program-v1":
            raise AuditError(f"Missing checked program metadata: {name}")
        actions = program.get("actions")
        if not isinstance(actions, list) or not actions:
            raise AuditError(f"Missing checked actions: {name}")
        for action in actions:
            if not isinstance(action, dict) or not isinstance(action.get("name"), str):
                raise AuditError(f"Malformed checked actions: {name}")
        pure = program.get("pure_library")
        if pure is not None:
            entries = pure.get("entries") if isinstance(pure, dict) else None
            if (not isinstance(entries, list)
                    or any(not isinstance(entry, str) for entry in entries)):
                raise AuditError(f"Malformed pure entry metadata: {name}")
            markers.update(entries)
        server = _read(directory / "server.ts")
        match = re.search(r"const ACTIONS: readonly Action\[\] = ([^\n]+);", server)
        if match is None:
            raise AuditError(f"Missing generated server SQL metadata: {name}")
        metadata = _json(match.group(1), f"{name}/server.ts ACTIONS")
        if not isinstance(metadata, list) or not metadata:
            raise AuditError(f"Missing generated server actions: {name}")
        for action in metadata:
            statement = action.get("sql") if isinstance(action, dict) else None
            if not isinstance(statement, str) or len(statement) < 12:
                raise AuditError(f"Malformed generated server SQL: {name}")
            sql.add(statement)
        schema = directory / "schema.sql"
        if schema.is_file():
            sql.update(statement.strip() for statement in _read(schema).split(";")
                       if statement.strip())
    return frozenset(markers), frozenset(sql)


def _inspect_text(text: str, label: str, markers: frozenset[str], sql: frozenset[str]) -> None:
    if re.search(r"sourceMappingURL\s*=\s*data:", text):
        raise AuditError(f"Uninspected inline source map in client artifact: {label}")
    for marker in sorted(markers):
        if marker in text:
            raise AuditError(f"Server marker {marker!r} in client artifact: {label}")
    for statement in sorted(sql):
        # Bundlers may retain SQL inside either quote style; map content is decoded.
        encoded = json.dumps(statement, ensure_ascii=True)[1:-1]
        if statement in text or encoded in text:
            raise AuditError(f"Generated server SQL in client artifact: {label}")


def _inspect_map(
    value: Any, label: str, markers: frozenset[str], sql: frozenset[str], depth: int = 0
) -> None:
    if depth > 32 or not isinstance(value, dict) or value.get("version") != 3:
        raise AuditError(f"Malformed source map: {label}")
    root = value.get("sourceRoot", "")
    sources, names = value.get("sources", []), value.get("names", [])
    if (not isinstance(root, str) or not isinstance(sources, list)
            or not isinstance(names, list)
            or any(not isinstance(item, str) for item in sources + names)):
        raise AuditError(f"Malformed source map paths/names: {label}")
    for source in sources:
        if _server_path(source) or _server_path(root.rstrip("/") + "/" + source):
            raise AuditError(f"Server source path {source!r} in client source map: {label}")
    for name in names:
        _inspect_text(name, label + " names", markers, sql)
    if "sourcesContent" in value:
        contents = value["sourcesContent"]
        if (not isinstance(contents, list) or len(contents) != len(sources)
                or any(item is not None and not isinstance(item, str) for item in contents)):
            raise AuditError(f"Malformed source map contents: {label}")
        for content in contents:
            if content is not None:
                _inspect_text(content, label + " sourcesContent", markers, sql)
    sections = value.get("sections", [])
    if not isinstance(sections, list):
        raise AuditError(f"Malformed source map sections: {label}")
    for section in sections:
        if not isinstance(section, dict) or "map" not in section or "url" in section:
            raise AuditError(f"Uninspected external source map section: {label}")
        _inspect_map(section["map"], label + " section", markers, sql, depth + 1)


def audit_client_bundle(client_dir: Path, program_dir: Path) -> AuditResult:
    """Fail closed unless real client JS and both generated program snapshots exist."""
    try:
        if not client_dir.is_dir():
            raise AuditError(f"Missing built client directory: {client_dir}")
        markers, sql = _markers(program_dir)
        javascript_files = source_maps = total = count = 0
        for path in sorted(client_dir.rglob("*")):
            if not path.is_file():
                continue
            count += 1
            total += path.stat().st_size
            if count > MAX_FILES or total > MAX_TOTAL_BYTES:
                raise AuditError("Client artifact audit budget exceeded")
            label = str(path.relative_to(client_dir))
            if _server_path(label):
                raise AuditError(f"Server provenance asset published in client directory: {label}")
            if path.suffix in {".js", ".mjs", ".cjs"}:
                javascript_files += 1
                _inspect_text(_read(path), label, markers, sql)
            elif path.suffix == ".map":
                source_maps += 1
                _inspect_map(_json(_read(path), label), label, markers, sql)
            elif path.suffix in {".json", ".html", ".css", ".txt", ".ts", ".tsx"}:
                _inspect_text(_read(path), label, markers, sql)
        if not javascript_files:
            raise AuditError("Missing built client JavaScript files")
        return AuditResult(javascript_files, source_maps)
    except (OSError, UnicodeError) as error:
        raise AuditError(f"Cannot inspect client/program artifacts: {error}") from error


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-dir", required=True, type=Path)
    parser.add_argument("--program-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = audit_client_bundle(args.client_dir, args.program_dir)
    except AuditError as error:
        print(f"Client bundle audit failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    print(f"Client bundle audit passed: {result.javascript_files} JavaScript files, "
          f"{result.source_maps} source maps; no inspected generated server markers")


if __name__ == "__main__":
    main()
