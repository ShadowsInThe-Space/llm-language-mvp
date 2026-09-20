"""M0 compatibility gates for the frozen source, proof, and web corpus.

These tests deliberately consume the checked-in baseline rather than regenerating
it.  A changed serializer, digest domain, certificate, or web emitter therefore
fails at the compatibility boundary.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from llmlang.model import LanguageError
from llmlang.parser import canonical_candidate, canonical_spec, parse_candidate, parse_spec
from llmlang.proof import baseline_hash, candidate_hash, check_certificate
from llmlang.web.build import WebBuild, compile_source, verify_build, write_build
from llmlang.web.model import WebError
from llmlang.web.parser import parse_app

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "tests/fixtures/m0-v1.json").read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _p0_paths(name: str) -> tuple[Path, Path]:
    if name == "hello":
        return ROOT / "examples/hello/hello.llspec", ROOT / "examples/hello/hello.ll"
    return ROOT / f"examples/golden/{name}.llspec", ROOT / f"examples/golden/{name}.ll"


def test_frozen_p0_canonical_bytes_and_hashes() -> None:
    assert set(FIXTURE["p0"]) == {
        *(
            f"examples/golden/{name}.llspec"
            for name in (
                "abs",
                "access_rule",
                "clamp",
                "grant",
                "identity",
                "maximum",
                "minimum",
                "nonnegative_difference",
                "overlap_length",
                "tiered_fee",
            )
        ),
        "examples/hello/hello.llspec",
    }
    for relative, expected in FIXTURE["p0"].items():
        spec_path = ROOT / relative
        candidate_path = spec_path.with_suffix(".ll")
        spec = parse_spec(spec_path.read_text(encoding="utf-8"))
        candidate = parse_candidate(candidate_path.read_text(encoding="utf-8"))
        assert canonical_spec(spec) == expected["canonical_spec"]
        assert canonical_candidate(candidate) == expected["canonical_candidate"]
        assert baseline_hash(spec) == expected["baseline_hash"]
        assert candidate_hash(candidate) == expected["candidate_hash"]


def test_hash_drift_mutation_is_caught_by_frozen_digest_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec_path, _ = _p0_paths("identity")
    spec = parse_spec(spec_path.read_text())
    expected = FIXTURE["p0"]["examples/golden/identity.llspec"]["baseline_hash"]
    import llmlang.proof as proof

    def frozen_gate() -> None:
        assert proof.baseline_hash(spec) == expected

    monkeypatch.setattr(proof, "_digest", lambda *args: "0" * 64)
    with pytest.raises(AssertionError):
        frozen_gate()


def test_frozen_raw_historical_files_are_byte_identical() -> None:
    for relative, expected in FIXTURE["raw_sha256"].items():
        path = ROOT / relative
        assert path.is_file(), relative
        assert _sha256(path) == expected, relative


def test_raw_source_drift_mutation_is_caught_by_frozen_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    relative = "examples/golden/identity.llspec"
    expected = FIXTURE["raw_sha256"][relative]

    def frozen_gate() -> None:
        assert _sha256(ROOT / relative) == expected

    import sys

    monkeypatch.setattr(sys.modules[__name__], "_sha256", lambda path: "0" * 64)
    with pytest.raises(AssertionError):
        frozen_gate()


@pytest.mark.parametrize("proof_path", sorted((ROOT / "evidence/acceptance").glob("*-proof.json")))
def test_historical_acceptance_certificate_is_independently_checkable(proof_path: Path) -> None:
    name = proof_path.name.removesuffix("-proof.json")
    spec_path, candidate_path = _p0_paths(name)
    report = json.loads(proof_path.read_text(encoding="utf-8"))
    certificate = report.get("certificate") or report["verification"]["certificate"]
    spec = parse_spec(spec_path.read_text(encoding="utf-8"))
    candidate = parse_candidate(candidate_path.read_text(encoding="utf-8"))
    assert check_certificate(spec, candidate, certificate)


def test_certificate_checker_does_not_call_solver(monkeypatch: pytest.MonkeyPatch) -> None:
    spec_path, candidate_path = _p0_paths("identity")
    report = json.loads((ROOT / "evidence/acceptance/identity-proof.json").read_text())
    spec = parse_spec(spec_path.read_text())
    candidate = parse_candidate(candidate_path.read_text())

    # Make any accidental import of the untrusted solver fail immediately.  The
    # checker must remain usable in an environment without z3 installed.
    monkeypatch.setitem(__import__("sys").modules, "llmlang.solver", None)
    assert check_certificate(spec, candidate, report["certificate"])


def test_stale_certificate_after_source_or_spec_change_is_rejected() -> None:
    spec_path, candidate_path = _p0_paths("identity")
    report = json.loads((ROOT / "evidence/acceptance/identity-proof.json").read_text())
    spec_source = spec_path.read_text()
    candidate_source = candidate_path.read_text()
    certificate = report["certificate"]
    spec = parse_spec(spec_source)
    candidate = parse_candidate(candidate_source)
    assert check_certificate(spec, candidate, certificate)
    changed_candidate = parse_candidate(
        candidate_source.replace("(var 0)", "(int.add (var 0) 0)", 1)
    )
    assert not check_certificate(spec, changed_candidate, certificate)
    changed_spec = parse_spec(spec_source.replace("(var 0))))", "(int.add (var 0) 0))))", 1))
    assert not check_certificate(changed_spec, candidate, certificate)


def test_stale_certificate_bypass_mutation_is_caught_by_rejection_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec_path, candidate_path = _p0_paths("identity")
    report = json.loads((ROOT / "evidence/acceptance/identity-proof.json").read_text())
    spec = parse_spec(spec_path.read_text())
    changed = parse_candidate(candidate_path.read_text().replace("(var 0)", "0", 1))
    certificate = report["certificate"]
    import llmlang.proof as proof

    def frozen_gate() -> None:
        assert not proof.check_certificate(spec, changed, certificate)

    monkeypatch.setattr(proof, "check_certificate", lambda *args, **kwargs: True)
    with pytest.raises(AssertionError):
        frozen_gate()


def test_unknown_profiles_are_rejected_for_p0_and_web() -> None:
    with pytest.raises(LanguageError) as p0_error:
        parse_spec("(spec p1 (fn (params Int) (result Int) (requires true) (ensures true)))")
    assert p0_error.value.code == "E_PARSE"
    with pytest.raises(LanguageError) as candidate_error:
        parse_candidate("(candidate p1 (body 0))")
    assert candidate_error.value.code == "E_PARSE"
    with pytest.raises(WebError) as web_error:
        parse_app(
            "(app w3 demo (store text (Text 8)) (action read (read text)) "
            '(page "/" (title "Demo") (output out "Output")))'
        )
    assert web_error.value.code == "W_PROFILE"


def test_incompatible_profile_bypass_mutation_is_caught_by_profile_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys

    compatibility = sys.modules[__name__]

    source = "(spec p1 (fn (params Int) (result Int) (requires true) (ensures true)))"
    valid = parse_spec("(spec p0 (fn (params Int) (result Int) (requires true) (ensures true)))")

    def frozen_gate() -> None:
        with pytest.raises(LanguageError):
            compatibility.parse_spec(source)

    monkeypatch.setattr(compatibility, "parse_spec", lambda _: valid)
    with pytest.raises(pytest.fail.Exception, match="DID NOT RAISE"):
        frozen_gate()


def test_frozen_web_manifests_and_sources_match_compiler_output() -> None:
    assert set(FIXTURE["web"]) == {
        "examples/web/hello-history.llapp",
        "examples/web/hello.llapp",
        "examples/web/notes.llapp",
    }
    for relative, expected in FIXTURE["web"].items():
        source = (ROOT / relative).read_text(encoding="utf-8")
        build = compile_source(source)
        assert build.manifest == expected
        for name, metadata in expected["files"].items():
            content = build.files[name].encode("utf-8")
            assert len(content) == metadata["bytes"]
            assert hashlib.sha256(content).hexdigest() == metadata["sha256"]


def test_identical_artifact_bytes_have_distinct_paths_and_tampering_fails(tmp_path: Path) -> None:
    source = (ROOT / "examples/web/hello.llapp").read_text(encoding="utf-8")
    build = compile_source(source)
    duplicate_files = copy.copy(build.files)
    duplicate_files["duplicate/db-w1.ts"] = build.files["db/w1.ts"]
    duplicate = WebBuild(build.app, duplicate_files, build.manifest)
    duplicate_destination = write_build(duplicate, tmp_path / "duplicate")
    assert not verify_build(duplicate_destination)
    destination = write_build(build, tmp_path / "build")
    assert verify_build(destination)
    second = write_build(build, tmp_path / "another-output")
    assert {
        path.relative_to(destination).as_posix(): path.read_bytes()
        for path in destination.rglob("*")
        if path.is_file()
    } == {
        path.relative_to(second).as_posix(): path.read_bytes()
        for path in second.rglob("*")
        if path.is_file()
    }
    target = destination / "app/page.tsx"
    target.write_text(target.read_text() + "\n", encoding="utf-8")
    assert not verify_build(destination)
