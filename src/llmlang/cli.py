"""User-facing CLI: execute only freshly verified or independently checked code."""

import argparse
import json
import os
import sys
from dataclasses import replace
from pathlib import Path

from llmlang.core import evaluate, validate
from llmlang.model import Candidate, LanguageError, Limits, Program, Specification, encode_value
from llmlang.parser import canonical_candidate, parse_candidate, parse_spec
from llmlang.proof import check_certificate, verify
from llmlang.transport import decode_inputs, load_json, read_text, write_json


def _emit(value: object) -> None:
    print(json.dumps(value, ensure_ascii=True, sort_keys=True))


def _positive(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="LLM-Language P0 proof-carrying function factory")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("check", "run", "hello", "factory"):
        command = commands.add_parser(name)
        command.add_argument("--spec", type=Path, required=True)
        command.add_argument("--max-branches", type=_positive, default=4096)
        command.add_argument("--solver-timeout-ms", type=_positive, default=3000)
        if name != "factory":
            command.add_argument("--candidate", type=Path, required=True)
        if name == "check":
            command.add_argument("--write-certificate", type=Path)
        if name in {"run", "hello"}:
            command.add_argument("--certificate", type=Path)
            command.add_argument("--entry", type=int)
        if name == "run":
            command.add_argument("--inputs", required=True, help="JSON array of tagged values")
        if name == "hello":
            command.add_argument("--length", type=_positive, default=12)
            command.add_argument("--report", type=Path)
        if name == "factory":
            source = command.add_mutually_exclusive_group(required=True)
            source.add_argument("--candidate-file", type=Path, action="append")
            source.add_argument("--endpoint")
            command.add_argument("--model")
            command.add_argument("--api-key-env", default="LLMLANG_API_KEY")
            command.add_argument("--max-attempts", type=_positive, default=3)
            command.add_argument("--output", type=Path)
            command.add_argument("--report", type=Path)
    return parser


def _checked_program(
    spec: Specification, candidate: Candidate, certificate_path: Path | None, limits: Limits
) -> Program | None:
    if certificate_path is not None:
        raw = load_json(
            read_text(certificate_path, limits.max_certificate_bytes), limits.max_certificate_bytes
        )
        if not isinstance(raw, dict) or not check_certificate(spec, candidate, raw, limits):
            _emit({"status": "unverified", "diagnostics": [{"code": "E_CERTIFICATE"}]})
            return None
    else:
        report = verify(spec, candidate, limits)
        if report.status != "proved" or report.certificate is None:
            _emit(report.to_dict())
            return None
        if not check_certificate(spec, candidate, report.certificate, limits):
            _emit({"status": "unverified", "diagnostics": [{"code": "E_CERTIFICATE"}]})
            return None
    return validate(spec, candidate, limits)


def _factory(args: argparse.Namespace, spec: Specification, limits: Limits) -> int:
    from llmlang.adapters import CandidateProvider, FileCandidates, OpenAICompatibleProvider
    from llmlang.factory import run_factory

    provider: CandidateProvider
    if args.candidate_file:
        provider = FileCandidates(
            [read_text(path, limits.max_source_bytes) for path in args.candidate_file]
        )
    else:
        if not args.model:
            raise LanguageError("E_CONFIG", "--model is required with --endpoint")
        provider = OpenAICompatibleProvider(
            endpoint=args.endpoint, model=args.model, api_key=os.environ.get(args.api_key_env)
        )
    result = run_factory(spec, provider, replace(limits, max_attempts=args.max_attempts))
    document = result.to_dict()
    if args.report:
        write_json(args.report, document)
    if result.status == "proved" and result.candidate is not None and args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(canonical_candidate(result.candidate) + "\n", encoding="utf-8")
    _emit(document)
    return 0 if result.status == "proved" else 1


def _hello(args: argparse.Namespace, program: Program, limits: Limits) -> int:
    if args.length > limits.max_nodes:
        raise LanguageError("E_LIMIT", "Output length exceeds budget")
    values = tuple(evaluate(program, (index,), args.entry, limits) for index in range(args.length))
    if any(type(value) is not int or not 0 <= value <= 127 for value in values):
        raise LanguageError("E_OUTPUT", "Host text output requires ASCII Int code points")
    output = "".join(chr(value) for value in values)
    if args.report:
        write_json(
            args.report,
            {
                "status": "proved",
                "run_status": "returned",
                "output": output,
                "codepoints": [encode_value(value) for value in values],
                "note": "Each character came from the checked P0 function; host handles stdout.",
            },
        )
    sys.stdout.write(output)
    return 0


def _execute(args: argparse.Namespace, program: Program, limits: Limits) -> int:
    # The Core proof and an individual host execution have independent statuses.
    try:
        if args.command == "hello":
            return _hello(args, program, limits)
        inputs = decode_inputs(args.inputs, limits)
        result = evaluate(program, inputs, args.entry, limits)
        _emit({"status": "proved", "run_status": "returned", "result": encode_value(result)})
        return 0
    except LanguageError as exc:
        if exc.code in {"E_JSON", "E_ENCODING"}:
            raise
        if exc.code in {"E_LIMIT", "E_RESOURCE"}:
            outcome = "resource_exhausted"
        elif exc.code in {"E_PRECONDITION", "E_VALUE", "E_TYPE", "E_CALL"}:
            outcome = "input_rejected"
        else:
            outcome = "host_error"
        _emit({"status": "proved", "run_status": outcome, "diagnostics": [exc.to_dict()]})
        return 1


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    limits = Limits(max_branches=args.max_branches, solver_timeout_ms=args.solver_timeout_ms)
    try:
        spec = parse_spec(read_text(args.spec, limits.max_source_bytes), limits)
        if args.command == "factory":
            return _factory(args, spec, limits)
        candidate = parse_candidate(read_text(args.candidate, limits.max_source_bytes), limits)
        if args.command == "check":
            report = verify(spec, candidate, limits)
            if args.write_certificate and report.status == "proved" and report.certificate:
                write_json(args.write_certificate, report.certificate)
            _emit(report.to_dict())
            return 0 if report.status == "proved" else 1
        program = _checked_program(spec, candidate, args.certificate, limits)
        if program is None:
            return 1
        return _execute(args, program, limits)
    except LanguageError as exc:
        status = "unverified" if exc.code == "E_LIMIT" else "invalid"
        _emit({"status": status, "diagnostics": [exc.to_dict()]})
        return 1
    except (OSError, UnicodeError):
        _emit(
            {"status": "invalid", "diagnostics": [{"code": "E_IO", "message": "File I/O failed"}]}
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
