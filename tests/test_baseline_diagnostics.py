"""M0: diagnostics are stable machine interfaces, including fallback paths."""

import json

import pytest

from llmlang.cli import main
from llmlang.diagnostics import diagnostic
from llmlang.model import LanguageError
from llmlang.web.model import Span, WebError


def test_supplied_feedback_cannot_override_envelope_contract():
    item = diagnostic(
        {
            "code": "E_PARSE",
            "schema": "foreign",
            "phase": "evil",
            "span": {"start": -1, "end": False},
            "symbol": 123,
            "message": [],
        }
    )
    assert item["schema"] == "diagnostic-v1"
    assert item["phase"] == "parse"
    assert item["span"] is None
    assert item["symbol"] is None
    assert item["message"] == ""


@pytest.mark.parametrize(
    "code,phase",
    [
        ("E_PARSE", "parse"),
        ("W_PROFILE", "parse"),
        ("E_IO", "io"),
        ("E_JSON", "transport"),
        ("E_CERTIFICATE", "verify"),
        ("E_SEARCH", "verify"),
        ("E_PROVIDER_TIMEOUT", "factory"),
        ("E_FACTORY_ATTEMPTS", "factory"),
        ("E_LIMIT", "resource"),
        ("W_TARGET", "target"),
        ("E_PRECONDITION", "execute"),
        ("E_TYPE", "validate"),
        ("W_UNBOUND", "validate"),
    ],
)
def test_diagnostic_phase_categories(code, phase):
    assert LanguageError(code, "detail").to_dict()["phase"] == phase


def test_verification_and_factory_direct_reports_have_envelopes():
    from llmlang.adapters import FileCandidates
    from llmlang.factory import run_factory
    from llmlang.model import Limits
    from llmlang.parser import parse_spec
    from llmlang.proof import VerificationReport

    report = VerificationReport("unverified", (), diagnostics=({"code": "E_SEARCH"},))
    assert report.to_dict()["diagnostics"][0]["phase"] == "verify"
    spec = parse_spec("(spec p0 (fn (params Int) (result Int) (requires true) (ensures true)))")
    result = run_factory(spec, FileCandidates([]), Limits(max_attempts=0)).to_dict()
    assert result["reason"]["schema"] == "diagnostic-v1"
    assert result["reason"]["span"] is None


def test_nested_factory_reports_match_cli_envelope():
    from llmlang.diagnostics import diagnostic_document
    from llmlang.factory import FactoryAttempt, FactoryResult

    attempt = FactoryAttempt(1, "invalid", None, 0, {"diagnostics": [{"code": "E_PARSE"}]})
    result = FactoryResult("invalid", None, attempts=(attempt,), reason={"code": "E_SPEC"})
    document = result.to_dict()
    assert document == diagnostic_document(document)
    assert document["attempts"][0]["feedback"]["diagnostics"][0]["phase"] == "parse"


def test_cli_rejects_stale_certificate_with_diagnostic(tmp_path, capsys):
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    certificate = tmp_path / "bad.json"
    certificate.write_text("{}")
    assert (
        main(
            [
                "run",
                "--spec",
                str(root / "examples/golden/identity.llspec"),
                "--candidate",
                str(root / "examples/golden/identity.ll"),
                "--certificate",
                str(certificate),
                "--inputs",
                "[]",
            ]
        )
        == 1
    )
    item = json.loads(capsys.readouterr().out)["diagnostics"][0]
    assert item["code"] == "E_CERTIFICATE"
    assert item["phase"] == "verify"
    assert item["symbol"] is None


def test_core_diagnostic_preserves_path_and_exposes_unknown_location():
    assert LanguageError("E_PARSE", "bad", (3,)).to_dict() == {
        "schema": "diagnostic-v1",
        "phase": "parse",
        "code": "E_PARSE",
        "message": "bad",
        "path": [3],
        "span": None,
        "symbol": None,
    }


def test_web_diagnostic_preserves_character_span():
    assert WebError("W_PARSE", "bad", Span(2, 5)).to_dict() == {
        "schema": "diagnostic-v1",
        "phase": "parse",
        "code": "W_PARSE",
        "message": "bad",
        "span": {"start": 2, "end": 5},
        "symbol": None,
    }


def test_cli_io_fallback_has_full_diagnostic(tmp_path, capsys):
    assert main(["compile-web", str(tmp_path / "missing"), "--out", str(tmp_path / "out")]) == 1
    diagnostic = json.loads(capsys.readouterr().out)["diagnostics"][0]
    assert diagnostic["phase"] == "io"
    assert diagnostic["code"] == "W_IO"
    assert diagnostic["span"] is None
    assert diagnostic["symbol"] is None
