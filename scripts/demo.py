"""Replay the real agent-authored artifacts through every MVP acceptance gate."""

import argparse
import hashlib
import json
from pathlib import Path

from llmlang.adapters import FileCandidates
from llmlang.core import evaluate, validate
from llmlang.factory import run_factory
from llmlang.model import encode_value
from llmlang.parser import parse_candidate, parse_spec
from llmlang.proof import baseline_hash, check_certificate, verify
from llmlang.transport import decode_value, write_json

ROOT = Path(__file__).resolve().parents[1]


def require(condition: object, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "demo")
    args = parser.parse_args()
    result: dict[str, object] = {"profile": "p0", "assurance": "A2-relative-to-TCB"}
    goldens = []
    for path in sorted((ROOT / "examples" / "golden").glob("*.llspec")):
        spec = parse_spec(path.read_text())
        candidate = parse_candidate(path.with_suffix(".ll").read_text())
        report = verify(spec, candidate)
        require(report.status == "proved", "Acceptance gate failed at demo line 33")
        require(
            report.certificate and check_certificate(spec, candidate, report.certificate),
            "Acceptance gate failed at demo line 34",
        )
        require(
            all(domain.status == "domain_nonempty" for domain in report.domains),
            "Acceptance gate failed at demo line 35",
        )
        fixture = json.loads(path.with_suffix(".json").read_text())
        program = validate(spec, candidate)
        for sample in fixture["samples"]:
            inputs = tuple(decode_value(value) for value in sample["inputs"])
            actual = evaluate(program, inputs, fixture["entry"])
            require(
                encode_value(actual) == sample["expected"], "Acceptance gate failed at demo line 41"
            )
        write_json(args.out / f"{path.stem}-proof.json", report.to_dict())
        goldens.append(
            {"task": path.stem, "status": report.status, "samples": len(fixture["samples"])}
        )
    require(len(goldens) == 10, "Acceptance gate failed at demo line 45")
    result["golden_programs"] = goldens

    provenance = json.loads((ROOT / "evidence" / "agent-provenance.json").read_text())
    hello = ROOT / "examples" / "hello"
    require(
        digest(hello / "hello.ll") == provenance["hello"]["source_sha256"],
        "Acceptance gate failed at demo line 50",
    )
    spec = parse_spec((hello / "hello.llspec").read_text())
    factory = run_factory(spec, FileCandidates([(hello / "hello.ll").read_text()]))
    require(
        factory.status == "proved" and factory.candidate and factory.verification,
        "Acceptance gate failed at demo line 53",
    )
    require(
        all(d.status == "domain_nonempty" for d in factory.verification.domains),
        "Acceptance gate failed at demo line 54",
    )
    certificate = factory.verification.certificate
    require(
        certificate and check_certificate(spec, factory.candidate, certificate),
        "Acceptance gate failed at demo line 56",
    )
    program = validate(spec, factory.candidate)
    codes = [evaluate(program, (index,)) for index in range(12)]
    require(
        all(type(code) is int and 0 <= code <= 127 for code in codes),
        "Acceptance gate failed at demo line 59",
    )
    output = "".join(chr(code) for code in codes)
    require(
        output == (hello / "expected.txt").read_text() == "Hello World\n",
        "Acceptance gate failed at demo line 61",
    )
    write_json(args.out / "hello-proof.json", factory.to_dict())
    (args.out / "hello.stdout").write_text(output)
    result["hello"] = {
        "status": "proved",
        "run_status": "returned",
        "output": output,
        "agent": provenance["hello"]["agent"],
        "baseline_hash": baseline_hash(spec),
    }

    repair = ROOT / "examples" / "agent-repair"
    require(
        digest(repair / "repaired.ll") == provenance["repair"]["source_sha256"],
        "Acceptance gate failed at demo line 69",
    )
    repair_spec = parse_spec((repair / "grant.llspec").read_text())
    require(
        baseline_hash(repair_spec) == provenance["repair"]["baseline_hash"],
        "Acceptance gate failed at demo line 71",
    )
    fixed = run_factory(
        repair_spec,
        FileCandidates(
            [
                (repair / "wrong.ll").read_text(),
                (repair / "repaired.ll").read_text(),
            ]
        ),
    )
    require(fixed.status == "proved" and fixed.candidate, "Acceptance gate failed at demo line 75")
    require(
        [attempt.status for attempt in fixed.attempts] == ["counterexample", "proved"],
        "Acceptance gate failed at demo line 76",
    )
    require(
        evaluate(validate(repair_spec, fixed.candidate), (7, 3)) == 3,
        "Acceptance gate failed at demo line 77",
    )
    write_json(args.out / "repair.json", fixed.to_dict())
    result["repair"] = {
        "status": "proved",
        "attempts": 2,
        "baseline_hash": fixed.baseline_hash,
        "input": ["7", "3"],
        "result": "3",
    }
    result["definition_of_done"] = "passed"
    result["generation_mode"] = "Replay of genuine session-agent outputs, not a new model request"
    write_json(args.out / "acceptance.json", result)
    print(output, end="")
    print("Definition of Done passed: 10 golden programs, agent Hello World, agent repair.")
    print(f"Evidence: {args.out / 'acceptance.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
