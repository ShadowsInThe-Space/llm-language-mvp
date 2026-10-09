"""Compile explicit source and local library files without model or network calls."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from .build import compile_source, write_build
from .source import WebSourceError

_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}\Z")
_MAX_BYTES = 262144


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("source", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--library", action="append", default=[], metavar="NAME=FILE")
    parser.add_argument("--pure-library", action="append", default=[], metavar="NAME=FILE")


def _read(path: Path) -> str:
    with path.open("rb") as stream:
        data = stream.read(_MAX_BYTES + 1)
    if len(data) > _MAX_BYTES:
        raise ValueError("Source file exceeds byte limit")
    return data.decode("utf-8")


def _libraries(arguments: list[str]) -> dict[str, str]:
    if len(arguments) > 64:
        raise ValueError("Too many explicit libraries")
    result: dict[str, str] = {}
    total = 0
    for argument in arguments:
        name, separator, path = argument.partition("=")
        if not separator or not path or _NAME.fullmatch(name) is None or name in result:
            raise ValueError("Libraries require distinct NAME=FILE bindings")
        text = _read(Path(path))
        total += len(text.encode("utf-8"))
        if total > _MAX_BYTES:
            raise ValueError("Library snapshot exceeds byte limit")
        result[name] = text
    return result


def execute(args: argparse.Namespace) -> int:
    try:
        build = compile_source(_read(args.source), library_sources=_libraries(args.library),
                               pure_sources=_libraries(args.pure_library))
        output = write_build(build, args.out)
        print(json.dumps({"status": "compiled", "output": str(output), **build.manifest},
                         ensure_ascii=True, sort_keys=True))
        return 0
    except WebSourceError as error:
        details: dict[str, object] = error.to_dict()
    except (OSError, UnicodeError, ValueError):
        details = {"code": "W_GENERAL_INPUT", "message": "Invalid input or unavailable output"}
    print(json.dumps({"status": "invalid", "diagnostics": [details]}, sort_keys=True))
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compile the additive general web source profile")
    add_arguments(parser)
    return execute(parser.parse_args(argv))
