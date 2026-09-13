"""Independent end-to-end tests for compiler output and real SQLite persistence.

Set LLMLANG_W1_SCHEMA to a real generated Drizzle SQL migration to repeat the
same tests against the production schema. The default is an independent schema
oracle from the frozen specification; it is not represented as migration evidence.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
from pathlib import Path
from typing import Any

import pytest

from llmlang.web.build import compile_source

RUNTIME = Path(__file__).parent / "web_runtime"
HELLO = """(app w1 hello_demo
  (store greeting (Text 4096))
  (action save_greeting (write greeting))
  (action load_greeting (read greeting))
  (page "/"
    (title "Agenten-Webseite")
    (input message "Neuer Text" (for greeting) (initial "Hello new AI World"))
    (button save "Speichern" (invoke save_greeting (input message)) (into result))
    (button show "Anzeigen" (invoke load_greeting) (into result))
    (output result "Gespeicherter Text")))"""
STUDIO = """(app w1 studio_notes
  (store announcement (Text 8))
  (store rehearsal_note (Text 16))
  (action publish (write announcement))
  (action read_announcement (read announcement))
  (action save_note (write rehearsal_note))
  (action read_note (read rehearsal_note))
  (page "/"
    (title "Probeplan")
    (output note_view "Notiz")
    (input note_text "Probe" (for rehearsal_note) (initial "Freitag"))
    (button note_save "Notiz speichern" (invoke save_note (input note_text)) (into note_view))
    (button note_load "Notiz laden" (invoke read_note) (into note_view))
    (output announcement_view "Ansage")
    (input announcement_text "Ansagetext" (for announcement) (initial "Start"))
    (button publish_button "Publizieren"
      (invoke publish (input announcement_text)) (into announcement_view))
    (button announcement_button "Ansage laden"
      (invoke read_announcement) (into announcement_view))))"""


def put(value: str, **overrides: Any) -> dict[str, Any]:
    return {"method": "PUT", "body": {"value": value}, **overrides}


def compiled_module(tmp_path: Path, source: str, index: int) -> Path:
    build = compile_source(source)
    destination = tmp_path / f"generated-{index}"
    for name, content in build.files.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return destination / "lib" / "w1-server.ts"


def execute(
    tmp_path: Path, operations: list[dict[str, Any]], *sources: str, initialize: bool = True
) -> dict[str, Any]:
    modules = [compiled_module(tmp_path, source, i) for i, source in enumerate(sources or (HELLO,))]
    payload = {
        "modules": [str(module) for module in modules],
        "database": str(tmp_path / "actual.sqlite"),
        "schema": os.environ.get("LLMLANG_W1_SCHEMA", str(RUNTIME / "reference-schema.sql")),
        "operations": operations,
        "initialize": initialize,
    }
    result = subprocess.run(
        ["node", "--disable-warning=ExperimentalWarning", str(RUNTIME / "run.mjs")],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        timeout=25,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_real_sqlite_persistence_empty_and_no_initial_seed(tmp_path: Path) -> None:
    report = execute(
        tmp_path,
        [{}, put("Hello new AI World"), {"kind": "reopen"}, {}, put(""), {"kind": "reopen"}, {}],
    )
    responses = report["results"]
    assert responses[0]["body"] == {"found": False}
    assert responses[1]["body"] == {"found": True, "value": "Hello new AI World"}
    assert responses[3]["body"] == responses[1]["body"]
    assert responses[6]["body"] == {"found": True, "value": ""}
    with sqlite3.connect(tmp_path / "actual.sqlite") as connection:
        assert connection.execute("SELECT value FROM w1_values").fetchone() == ("",)


def test_new_runtime_process_reads_previous_committed_value(tmp_path: Path) -> None:
    execute(tmp_path, [put("Frischer Prozess 😀")])
    result = execute(tmp_path, [{}], initialize=False)
    assert result["results"][0]["body"] == {"found": True, "value": "Frischer Prozess 😀"}


def test_exact_wire_byte_limit_allows_valid_small_value(tmp_path: Path) -> None:
    body = '{"value":"x"}'
    body += " " * (32768 - len(body.encode("utf-8")))
    result = execute(tmp_path, [{"method": "PUT", "rawBody": body, "stream": True}, {}])
    assert result["results"][0]["status"] == 200
    assert result["results"][1]["body"] == {"found": True, "value": "x"}


@pytest.mark.parametrize("value", [None, "\0", "a" * 4097])
def test_database_constraints_reject_invalid_direct_writes(
    tmp_path: Path, value: str | None
) -> None:
    execute(tmp_path, [put("sentinel")])
    with sqlite3.connect(tmp_path / "actual.sqlite") as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("UPDATE w1_values SET value = ?", (value,))
        assert connection.execute("SELECT value FROM w1_values").fetchone() == ("sentinel",)


@pytest.mark.parametrize(
    "value",
    [
        "  ä e\u0301 😀 العربية \" ' \\  ",
        "line\rreturn\nfeed\r\nboth",
        "</script><script>globalThis.injected=true</script><img src=x onerror=alert(1)>",
        "'); DROP TABLE w1_values; --",
        "a" * 4096,
        "😀" * 1024,
    ],
)
def test_exact_text_and_utf8_boundaries_survive_reopen(tmp_path: Path, value: str) -> None:
    report = execute(tmp_path, [put(value), {"kind": "reopen"}, {}, put("after"), {}])
    assert report["results"][0]["status"] == 200
    assert report["results"][2]["body"] == {"found": True, "value": value}
    assert report["results"][4]["body"] == {"found": True, "value": "after"}


@pytest.mark.parametrize(
    ("bad_request", "status"),
    [
        (put("a" * 4097), 422),
        (put("😀" * 1024 + "x"), 422),
        (put("\0"), 422),
        ({"method": "PUT", "rawBody": '{"value":"\\ud800"}'}, 422),
        ({"method": "PUT", "rawBody": '{"value":"\\udfff"}'}, 422),
        ({"method": "PUT", "rawBody": '{"value":"a","value":"b"}'}, 400),
        ({"method": "PUT", "rawBody": '{"value":"a","va\\u006cue":"b"}'}, 400),
        ({"method": "PUT", "body": {"value": "x", "extra": True}}, 400),
        ({"method": "PUT", "body": {"value": 17}}, 400),
        ({"method": "PUT", "body": ["value", "x"]}, 400),
        ({"method": "PUT", "body": None}, 400),
        ({"method": "PUT", "rawBody": "{broken"}, 400),
        (
            {
                "method": "PUT",
                "rawBytes": [123, 34, 118, 97, 108, 117, 101, 34, 58, 34, 255, 34, 125],
            },
            400,
        ),
        (put("x", origin="https://evil.example.test"), 403),
        (put("x", origin="https://app.example.test.evil.test"), 403),
        (put("x", origin="null"), 403),
        (put("x", origin=None), 403),
        (put("x", contentType="text/plain"), 415),
        (put("x", contentType=None), 415),
        (put("x", method="POST"), 405),
        (put("x", slot="../greeting"), 404),
        (put("x", slot="constructor"), 404),
        (put("x", slot="__proto__"), 404),
        ({"method": "PUT", "rawBody": " " * 32769, "stream": True}, 413),
        ({"method": "PUT", "rawBody": " " * 32769, "stream": True, "contentLength": 1}, 413),
        ({"method": "PUT", "rawBody": '{"value":"' + "\\u0061" * 5500 + '"}', "stream": True}, 413),
    ],
)
def test_invalid_requests_never_mutate_the_existing_value(
    tmp_path: Path, bad_request: dict[str, Any], status: int
) -> None:
    report = execute(tmp_path, [put("sentinel"), bad_request, {}])
    rejected = report["results"][1]
    assert rejected["status"] == status, rejected
    assert isinstance(rejected["body"]["error"]["code"], str)
    assert report["results"][2]["body"] == {"found": True, "value": "sentinel"}
    assert "access-control-allow-origin" not in rejected["headers"]


def test_small_declared_type_is_enforced_for_write_and_db_read(tmp_path: Path) -> None:
    report = execute(
        tmp_path,
        [
            put("😀😀", slot="announcement"),
            put("😀😀x", slot="announcement"),
            {"slot": "announcement"},
            {"kind": "sql", "sql": "UPDATE w1_values SET value=?", "parameters": ["too large"]},
            {"slot": "announcement"},
        ],
        STUDIO,
    )
    assert report["results"][0]["status"] == 200
    assert report["results"][1]["status"] == 422
    assert report["results"][2]["body"] == {"found": True, "value": "😀😀"}
    assert report["results"][4]["status"] == 503


def test_two_slot_program_and_app_identity_are_independent(tmp_path: Path) -> None:
    second_app = STUDIO.replace("studio_notes", "other_notes")
    renamed_ui = STUDIO.replace('"Probeplan"', '"Neuer Plan"').replace('"Freitag"', '"Dienstag"')
    report = execute(
        tmp_path,
        [
            put("Start A", slot="announcement"),
            put("Probe B", slot="rehearsal_note"),
            {"slot": "announcement", "module": 1},
            put("Other", slot="announcement", module=1),
            {"kind": "reopen"},
            {"slot": "announcement", "module": 2},
            {"slot": "rehearsal_note", "module": 2},
            {"slot": "announcement", "module": 1},
        ],
        STUDIO,
        second_app,
        renamed_ui,
    )
    assert report["results"][2]["body"] == {"found": False}
    assert report["results"][5]["body"] == {"found": True, "value": "Start A"}
    assert report["results"][6]["body"] == {"found": True, "value": "Probe B"}
    assert report["results"][7]["body"] == {"found": True, "value": "Other"}
    assert len(report["rows"]) == 3


def test_storage_errors_do_not_leak_or_invent_success(tmp_path: Path) -> None:
    report = execute(
        tmp_path,
        [
            put("sentinel"),
            put("x", databaseFault=True),
            {"databaseFault": True},
            {"databaseNull": True},
            put("x", databaseNull=True),
            {},
        ],
    )
    for result in report["results"][1:5]:
        assert result["status"] == 503
        assert result["body"]["error"]["code"] == "STORAGE_UNAVAILABLE"
        assert "private database" not in json.dumps(result)
        assert "do-not-leak" not in json.dumps(result)
    assert report["results"][5]["body"] == {"found": True, "value": "sentinel"}


def test_concurrent_writes_are_whole_and_headers_disable_caching(tmp_path: Path) -> None:
    values = ["a" * 2048, "😀" * 512]
    report = execute(
        tmp_path, [{"kind": "parallel", "requests": [put(value) for value in values]}, {}]
    )
    writes = report["results"][0]
    assert [response["body"]["value"] for response in writes] == values
    assert report["results"][1]["body"]["value"] in values
    for response in [*writes, report["results"][1]]:
        assert response["headers"]["cache-control"] == "no-store"
        assert response["headers"]["x-content-type-options"] == "nosniff"
        assert response["headers"]["content-type"].startswith("application/json")


def test_effect_capabilities_come_from_declarations(tmp_path: Path) -> None:
    source = """(app w1 restricted
      (store incoming (Text 32))
      (store public_text (Text 32))
      (action write_incoming (write incoming))
      (action read_public (read public_text))
      (page "/" (title "Berechtigte Effekte") (output answer "Ergebnis")))"""
    report = execute(
        tmp_path,
        [
            put("okay", slot="incoming"),
            {"slot": "incoming"},
            put("blocked", slot="public_text"),
            {"slot": "public_text"},
        ],
        source,
    )
    assert [result["status"] for result in report["results"]] == [200, 405, 405, 200]
    assert report["results"][3]["body"] == {"found": False}


def test_build_is_deterministic_and_second_app_changes_generated_behavior() -> None:
    hello = compile_source(HELLO)
    whitespace = compile_source(HELLO.replace("\n", "  \n  "))
    studio = compile_source(STUDIO)
    assert hello.files == whitespace.files
    assert hello.manifest == whitespace.manifest
    assert hello.files["app/page.tsx"] != studio.files["app/page.tsx"]
    assert "Hello new AI World" not in studio.files["app/page.tsx"]
    assert "Probeplan" in studio.files["app/page.tsx"]
