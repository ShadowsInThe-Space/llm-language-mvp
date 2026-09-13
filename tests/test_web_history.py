"""w2 behavioral regression: real SQLite history, preservation and scoped reads."""

import json
import os
import subprocess
from pathlib import Path

import pytest

from llmlang.web.build import compile_source
from llmlang.web.model import WebError
from llmlang.web.parser import canonical_app, parse_app

ROOT = Path(__file__).parent
SOURCE = (ROOT.parent / "examples/web/hello.llapp").read_text().replace("app w1", "app w2")
SOURCE = SOURCE.replace(
    '(output result "Gespeicherter Text")',
    '(output result "Gespeicherter Text") (clear reset "Anzeige leeren" (output result))',
)
ONE = "00000000-0000-4000-8000-000000000001"
TWO = "00000000-0000-4000-8000-000000000002"


def run(tmp_path: Path, operations: list[dict[str, object]], legacy: bool = False) -> dict:
    modules = []
    for index, source in enumerate((SOURCE, SOURCE.replace("hello_ai_world", "other_app"))):
        file = tmp_path / f"runtime{index}.ts"
        file.write_text(compile_source(source).files["lib/w1-server.ts"])
        modules.append(str(file))
    migration = Path(os.environ.get("LLMLANG_W2_SCHEMA", ROOT / "web_runtime/w2-reference.sql"))
    schema = (ROOT / "web_runtime/reference-schema.sql").read_text()
    if legacy:
        schema += (
            "\nINSERT INTO w1_values VALUES ('hello_ai_world','greeting','Vorhandener Text');\n"
        )
    schema += "\n" + migration.read_text()
    schema_file = tmp_path / "schema.sql"
    schema_file.write_text(schema)
    result = subprocess.run(
        ["node", str(ROOT / "web_runtime/run.mjs")],
        input=json.dumps(
            {
                "modules": modules,
                "database": str(tmp_path / "db.sqlite"),
                "schema": str(schema_file),
                "profile": "w2",
                "operations": operations,
            }
        ),
        text=True,
        capture_output=True,
        check=True,
        timeout=30,
    )
    return json.loads(result.stdout)


def save(value: str, key: str = ONE, **extra: object) -> dict[str, object]:
    return {"method": "POST", "body": {"value": value}, "key": key, **extra}


def test_profile_canonicalization_and_clear_target_validation() -> None:
    app = parse_app(SOURCE)
    assert app.profile == "w2"
    assert parse_app(canonical_app(app)) == app
    with pytest.raises(WebError):
        parse_app(SOURCE.replace("(output result))", "(output message))"))
    with pytest.raises(WebError):
        parse_app(SOURCE.replace("app w2", "app w1"))


def test_history_survives_repeated_saves_retries_and_process_reopen(tmp_path: Path) -> None:
    output = run(
        tmp_path,
        [
            save("Erster 🌍"),
            save("Zweiter", TWO),
            save("Erster 🌍"),
            {"query": "entries=1"},
            {"kind": "reopen"},
            {"query": f"id={ONE}"},
        ],
    )
    assert len(output["rows"]) == 2
    assert [x["preview"] for x in output["results"][3]["body"]["entries"]] == [
        "Zweiter",
        "Erster 🌍",
    ]
    assert output["results"][-1]["body"] == {"found": True, "value": "Erster 🌍"}


def test_migration_preserves_existing_single_value(tmp_path: Path) -> None:
    output = run(tmp_path, [{"query": "entries=1"}, {"query": "id=legacy"}], legacy=True)
    assert output["results"][0]["body"]["entries"][0]["id"] == "legacy"
    assert output["results"][1]["body"]["value"] == "Vorhandener Text"


def test_conflicting_retry_and_foreign_app_cannot_modify_or_read_entry(tmp_path: Path) -> None:
    output = run(
        tmp_path,
        [
            save("Keep"),
            save("Overwrite"),
            {"module": 1, "query": f"id={ONE}"},
            {"query": f"id={ONE}"},
        ],
    )
    assert [x["status"] for x in output["results"]] == [200, 409, 404, 200]
    assert output["rows"][0]["value"] == "Keep"


@pytest.mark.parametrize(
    "operation,status",
    [
        (save("No", origin="https://evil.test"), 403),
        (save("No", key="invalid"), 400),
        (save("🌍" * 1025), 422),
        (save("No", rawBody='{"value":"one","value":"two"}'), 400),
        ({"method": "DELETE", "body": {}, "query": f"id={ONE}"}, 405),
        ({"query": "entries=1&before=-1"}, 400),
        ({"query": "entries=1&id=legacy"}, 400),
    ],
)
def test_invalid_requests_leave_history_unchanged(
    tmp_path: Path, operation: dict, status: int
) -> None:
    output = run(tmp_path, [operation])
    assert output["results"][0]["status"] == status
    assert output["rows"] == []


def test_listing_is_paginated_and_previews_preserve_unicode_boundaries(tmp_path: Path) -> None:
    operations = [
        save("🌍" * 90 + str(i), f"00000000-0000-4000-8000-{i:012d}") for i in range(1, 24)
    ]
    operations.extend([{"query": "entries=1"}, {"query": "entries=1&before=4"}])
    output = run(tmp_path, operations)
    first, second = [result["body"] for result in output["results"][-2:]]
    assert len(first["entries"]) == 20 and first["nextCursor"] == "4"
    assert len(second["entries"]) == 3 and second["nextCursor"] is None
    assert first["entries"][0]["preview"] == "🌍" * 80
