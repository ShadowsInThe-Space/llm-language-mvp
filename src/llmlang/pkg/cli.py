"""Explicit freeze/link/check/run commands; no implicit updates or overwrites."""

import argparse
import json
from pathlib import Path
from typing import cast

from llmlang.core import evaluate, validate
from llmlang.model import LanguageError, encode_value
from llmlang.parser import canonical_candidate, canonical_spec, parse_candidate, parse_spec
from llmlang.transport import decode_inputs, load_json, read_text

from .binding import check_package_certificate, verify_package
from .linker import link
from .model import BoundProgram, PkgError
from .resolver import freeze, resolve


def _write(path: Path, value: object) -> None:
    text = json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as output:
        output.write(text)


def _load(path: Path) -> object:
    return load_json(read_text(path, 8 * 1024 * 1024), 8 * 1024 * 1024)


def _bound(path: Path) -> BoundProgram:
    value = _load(path)
    if not isinstance(value, dict) or set(value) != {"format", "spec", "candidate", "manifest"}:
        raise PkgError("P_BINDING", "Malformed bound artifact", "bind")
    if (
        value["format"] != "pkg1-artifact"
        or not isinstance(value["spec"], str)
        or not isinstance(value["candidate"], str)
        or not isinstance(value["manifest"], dict)
    ):
        raise PkgError("P_BINDING", "Malformed bound artifact", "bind")
    return BoundProgram(
        parse_spec(value["spec"]), parse_candidate(value["candidate"]), value["manifest"]
    )


def _command(args: argparse.Namespace) -> dict[str, object]:
    if args.command == "lock-pkg":
        selection = {}
        for item in args.package:
            if "=" not in item:
                raise PkgError("P_PARSE", "Package selection requires name=path", "parse")
            name, path = item.split("=", 1)
            if name in selection:
                raise PkgError("P_DUPLICATE", "Duplicate selection", "parse")
            selection[name] = path
        document = freeze(args.workspace, args.root, selection)
        _write(args.out, document)
        return {"status": "locked", "output": str(args.out)}
    snapshot = resolve(args.workspace, args.lock or args.workspace / "ll.lock.json")
    if args.command == "link-pkg":
        bound = link(snapshot)
        _write(
            args.out,
            {
                "format": "pkg1-artifact",
                "spec": canonical_spec(bound.spec),
                "candidate": canonical_candidate(bound.candidate),
                "manifest": bound.manifest,
            },
        )
        return {
            "status": "linked",
            "bound_hash": bound.manifest["bound_hash"],
            "output": str(args.out),
        }
    bound = _bound(args.bound)
    if args.command == "check-pkg":
        result = verify_package(snapshot, bound)
        if result["status"] == "proved" and args.write_certificate:
            _write(args.write_certificate, result["certificate"])
        return result
    if not check_package_certificate(snapshot, bound, _load(args.certificate)):
        raise PkgError("P_BINDING", "Package certificate rejected", "bind")
    if args.entry.count(".") != 1:
        raise PkgError("P_UNBOUND", "Entry requires module.export", "link")
    module_name, export = args.entry.split(".")
    rows = cast(list[dict[str, object]], bound.manifest["functions"])
    for row in rows:
        if (
            row["package"] == snapshot.root
            and row["module"] == module_name
            and row["name"] == export
            and row["exported"] is True
        ):
            value = evaluate(
                validate(bound.spec, bound.candidate),
                decode_inputs(args.inputs),
                entry=cast(int, row["core_slot"]),
            )
            return {"status": "proved", "run_status": "returned", "result": encode_value(value)}
    raise PkgError("P_PRIVATE", "Entry is not a root package export", "link")


def execute(args: argparse.Namespace) -> int:
    try:
        result = _command(args)
    except PkgError as error:
        result = {"status": "invalid", "diagnostics": [error.to_dict()]}
    except LanguageError as error:
        result = {"status": "invalid", "diagnostics": [error.to_dict()]}
    except (OSError, UnicodeError):
        result = {
            "status": "invalid",
            "diagnostics": [PkgError("P_IO", "Package file I/O failed").to_dict()],
        }
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0 if result["status"] in {"locked", "linked", "proved"} else 1
