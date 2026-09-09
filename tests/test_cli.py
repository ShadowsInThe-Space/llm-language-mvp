"""Process-level user behavior; no mocking of language verification."""

import json
import os
import subprocess
import sys
from pathlib import Path


def invoke(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "llmlang", *args],
        text=True,
        capture_output=True,
        timeout=45,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).parents[1] / "src")},
        check=False,
    )


def identity(tmp_path: Path) -> tuple[Path, Path]:
    spec = tmp_path / "identity.llspec"
    candidate = tmp_path / "identity.ll"
    spec.write_text(
        "(spec p0 (fn (params Int) (result Int) (requires true) (ensures (int.eq result (var 0)))))"
    )
    candidate.write_text("(candidate p0 (body (var 0)))")
    return spec, candidate


def test_check_reports_actual_certificate(tmp_path: Path) -> None:
    spec, candidate = identity(tmp_path)
    certificate = tmp_path / "proof.json"
    result = invoke(
        "check",
        "--spec",
        str(spec),
        "--candidate",
        str(candidate),
        "--write-certificate",
        str(certificate),
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert json.loads(result.stdout)["status"] == "proved"
    assert certificate.exists()


def test_run_preserves_large_integer(tmp_path: Path) -> None:
    spec, candidate = identity(tmp_path)
    value = "900719925474099312345678901234567890"
    result = invoke(
        "run",
        "--spec",
        str(spec),
        "--candidate",
        str(candidate),
        "--inputs",
        json.dumps([{"type": "Int", "value": value}]),
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert json.loads(result.stdout)["result"] == {"type": "Int", "value": value}


def test_unproved_program_never_runs(tmp_path: Path) -> None:
    spec, candidate = identity(tmp_path)
    candidate.write_text("(candidate p0 (body 0))")
    result = invoke(
        "run",
        "--spec",
        str(spec),
        "--candidate",
        str(candidate),
        "--inputs",
        '[{"type":"Int","value":"7"}]',
    )
    assert result.returncode != 0
    assert json.loads(result.stdout)["status"] == "counterexample"


def test_tampered_certificate_is_not_replaced_silently(tmp_path: Path) -> None:
    spec, candidate = identity(tmp_path)
    proof = tmp_path / "proof.json"
    proof.write_text('{"checker":"fake","obligations":{}}')
    result = invoke(
        "run",
        "--spec",
        str(spec),
        "--candidate",
        str(candidate),
        "--certificate",
        str(proof),
        "--inputs",
        '[{"type":"Int","value":"7"}]',
    )
    assert result.returncode != 0
    assert json.loads(result.stdout)["status"] == "unverified"


def test_duplicate_json_fields_rejected(tmp_path: Path) -> None:
    spec, candidate = identity(tmp_path)
    result = invoke(
        "run",
        "--spec",
        str(spec),
        "--candidate",
        str(candidate),
        "--inputs",
        '[{"type":"Int","value":"1","value":"2"}]',
    )
    assert result.returncode != 0
    assert json.loads(result.stdout)["status"] == "invalid"


def test_help_is_available() -> None:
    result = invoke("--help")
    assert result.returncode == 0
    assert "factory" in result.stdout


def test_invalid_runtime_input_does_not_invalidate_core_proof(tmp_path: Path) -> None:
    spec, candidate = identity(tmp_path)
    result = invoke(
        "run",
        "--spec",
        str(spec),
        "--candidate",
        str(candidate),
        "--inputs",
        '[{"type":"Bool","value":true}]',
    )
    assert result.returncode != 0
    report = json.loads(result.stdout)
    assert report["status"] == "proved"
    assert report["run_status"] == "input_rejected"


def test_precondition_rejection_is_a_run_outcome(tmp_path: Path) -> None:
    spec, candidate = identity(tmp_path)
    spec.write_text(spec.read_text().replace("(requires true)", "(requires (int.le 0 (var 0)))"))
    result = invoke(
        "run",
        "--spec",
        str(spec),
        "--candidate",
        str(candidate),
        "--inputs",
        '[{"type":"Int","value":"-1"}]',
    )
    assert result.returncode != 0
    report = json.loads(result.stdout)
    assert report["status"] == "proved"
    assert report["run_status"] == "input_rejected"
