"""Reproducible source-bound general web artifacts; no target-proof claim."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any

from llmlang.a1.runtime import RUNTIME_VERSION
from llmlang.a1.runtime import emit_typescript_runtime as emit_pure_runtime
from llmlang.a1.source import parse_source as parse_pure_source

from .client import emit_client
from .codecs import CODEC_VERSION, emit_typescript_runtime
from .queries import schema_sql
from .server import emit_server
from .source import parse_component_library, parse_web_source

COMPILER_VERSION = "general-web.0.3.0"


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True, indent=2) + "\n"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class GeneralBuild:
    files: Mapping[str, str]
    _manifest_json: str

    @property
    def manifest(self) -> dict[str, Any]:
        return dict(json.loads(self._manifest_json))


def compile_source(
    source: str, *, library_sources: Mapping[str, str] | None = None,
    pure_sources: Mapping[str, str] | None = None,
) -> GeneralBuild:
    """Compile only a freshly reconstructed source and explicit library snapshot."""
    libraries = dict(library_sources or {})
    pure = dict(pure_sources or {})
    parsed = parse_web_source(source, library_sources=libraries, pure_sources=pure)
    files = {
        "App.tsx": emit_client(parsed.program),
        "server.ts": emit_server(parsed.program),
        "codecs.ts": emit_typescript_runtime(),
        "schema.sql": ";\n".join(schema_sql(parsed.program.schema)) + ";\n",
        "program.json": parsed.checked.canonical_bytes.decode("ascii") + "\n",
        "source.webapp": parsed.canonical_source + "\n",
        "source-map.json": _json({name: {"offset": span.offset, "line": span.line,
                                        "column": span.column}
                                  for name, span in parsed.source_map.items()}),
    }
    entries = tuple(sorted({transform.function for action in parsed.checked.actions
                            for transform in action.transforms}))
    if entries:
        assert parsed.program.pure_library is not None
        files["a1-pure.ts"] = emit_pure_runtime(json.loads(parsed.program.pure_library), entries)
    for name, text in libraries.items():
        files[f"libraries/{name}.webuilib"] = parse_component_library(text).canonical_source + "\n"
    for name, text in pure.items():
        files[f"libraries/{name}.a1src"] = parse_pure_source(text).canonical_source + "\n"
    manifest = {
        "format": "general-web-build-v1",
        "compiler": COMPILER_VERSION,
        "codec": CODEC_VERSION,
        "pure_runtime": RUNTIME_VERSION if entries else None,
        "source_hash": parsed.source_hash,
        "program_hash": parsed.semantic_hash,
        "effects_hash": parsed.checked.effects.semantic_hash,
        "target": "react-typescript-d1",
        "assurance": {
            "status": "structurally-checked",
            "formal_target_proof": False,
            "host_acceptance": "required-separately",
            "limitations": ["No full website proof", "No host authentication proof",
                            "No D1 or browser execution implied by compilation"],
        },
        "files": {name: _hash(text) for name, text in sorted(files.items())},
    }
    manifest_json = _json(manifest)
    files["manifest.json"] = manifest_json
    return GeneralBuild(MappingProxyType(dict(sorted(files.items()))), manifest_json)


def check_build(
    source: str, offered_files: Mapping[str, str], *,
    library_sources: Mapping[str, str] | None = None,
    pure_sources: Mapping[str, str] | None = None,
) -> bool:
    """Compare complete reconstructed artifacts, not an offered producer hash."""
    expected = compile_source(source, library_sources=library_sources, pure_sources=pure_sources)
    return dict(offered_files) == dict(expected.files)


def write_build(build: GeneralBuild, output: Path) -> Path:
    """Publish a complete new artifact directory for a single writer.

    Existing outputs are refused. The parent directory is a trusted host-selected
    location; this is not a concurrent multi-user filesystem sandbox.
    """
    target = output.absolute()
    if target.exists() or target.is_symlink():
        raise FileExistsError(target)
    snapshot = dict(build.files)
    for name, text in snapshot.items():
        relative_path = PurePosixPath(name)
        if (not name or relative_path.is_absolute() or str(relative_path) != name
                or any(part in {".", ".."} for part in relative_path.parts) or "\\" in name
                or not isinstance(text, str)):
            raise ValueError("Invalid artifact path or content")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".general-web-", dir=target.parent))
    try:
        for name, text in snapshot.items():
            path = temporary / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
        if target.exists() or target.is_symlink():
            raise FileExistsError(target)
        os.rename(temporary, target)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return target.resolve()
