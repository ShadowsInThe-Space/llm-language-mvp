"""Deterministic compilation and an explicit, non-destructive output boundary."""

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .emit import emit_app
from .model import ActionButton, ClearButton, TextInput, TextOutput, WebApp, WebError
from .parser import canonical_app, parse_app

COMPILER_VERSION = "web.0.4.0"
TARGET = "vinext-d1"
MANIFEST_PATH = "llmlang/manifest.json"
SOURCE_PATH = "llmlang/source.llapp"


@dataclass(frozen=True, slots=True)
class WebBuild:
    app: WebApp
    files: dict[str, str]
    manifest: dict[str, object]


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n"


def _ir(app: WebApp) -> dict[str, object]:
    widgets: list[dict[str, object]] = []
    for widget in app.page.widgets:
        item: dict[str, object] = {"name": widget.name, "label": widget.label}
        if isinstance(widget, TextInput):
            item.update(kind="input", store=widget.store, initial=widget.initial)
        elif isinstance(widget, ActionButton):
            item.update(
                kind="button", action=widget.action, input=widget.input, output=widget.output
            )
        elif isinstance(widget, TextOutput):
            item.update(kind="output")
        elif isinstance(widget, ClearButton):
            item.update(kind="clear", output=widget.output)
        widgets.append(item)
    return {
        "profile": app.profile,
        "app": app.name,
        "stores": [{"name": store.name, "max_bytes": store.max_bytes} for store in app.stores],
        "actions": [
            {"name": action.name, "effect": action.effect, "store": action.store}
            for action in app.actions
        ],
        "page": {"path": app.page.path, "title": app.page.title, "widgets": widgets},
    }


def compile_source(source: str) -> WebBuild:
    app = parse_app(source)
    canonical = canonical_app(app)
    files = emit_app(app)
    files[SOURCE_PATH] = canonical + "\n"
    files["llmlang/ir.json"] = _json(_ir(app))
    manifest: dict[str, object] = {
        "status": "compiled",
        "profile": app.profile,
        "compiler_version": COMPILER_VERSION,
        "target": TARGET,
        "schema_version": 2 if app.profile == "w2" else 1,
        "source_sha256": hashlib.sha256(
            f"llapp-{app.profile}\0".encode() + canonical.encode("utf-8")
        ).hexdigest(),
        "assurance": "statically-checked; compiler-and-runtime-tested; no-A3-or-A4-proof",
        "files": {
            path: {
                "bytes": len(content.encode("utf-8")),
                "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            }
            for path, content in sorted(files.items())
        },
    }
    files[MANIFEST_PATH] = _json(manifest)
    return WebBuild(app, files, manifest)


def _check_paths(files: dict[str, str]) -> None:
    for name, content in files.items():
        if type(name) is not str or type(content) is not str:
            raise WebError("W_TARGET", "Unsafe generated artifact path or content")
        path = PurePosixPath(name)
        if (
            path.is_absolute()
            or path.as_posix() != name
            or any(part in {".", ".."} for part in path.parts)
            or "\\" in name
            or "\0" in name
            or not path.parts
        ):
            raise WebError("W_TARGET", "Unsafe generated artifact path or content")


def write_build(build: WebBuild, directory: str | Path) -> Path:
    """Install one complete build only into a new or empty, non-symlink directory."""
    _check_paths(build.files)
    destination = Path(directory).absolute()
    if any(path.is_symlink() for path in (destination, *destination.parents)):
        raise WebError("W_TARGET", "Output path must not traverse symlinks")
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise WebError("W_TARGET", "Output directory must be new or empty")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".llmlang-build-", dir=destination.parent))
    try:
        for relative, content in sorted(build.files.items()):
            path = staging / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="")
        os.replace(staging, destination)
    except OSError as exc:
        raise WebError("W_TARGET", "Unable to write a complete compiler output") from exc
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return destination


def verify_build(directory: str | Path) -> bool:
    """Recompile source and compare all bytes; integrity checking is not a proof."""
    root = Path(directory)
    try:
        if root.is_symlink() or not root.is_dir():
            return False
        with (root / SOURCE_PATH).open("rb") as source:
            data = source.read(131073)
        expected = compile_source(data.decode("utf-8"))
        paths = list(root.rglob("*"))
        if any(path.is_symlink() for path in paths):
            return False
        actual_names = {path.relative_to(root).as_posix() for path in paths if path.is_file()}
        if actual_names != set(expected.files):
            return False
        return all(
            (root / name).read_bytes() == content.encode("utf-8")
            for name, content in expected.files.items()
        )
    except (OSError, UnicodeError, WebError):
        return False
