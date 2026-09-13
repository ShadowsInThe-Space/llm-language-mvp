from __future__ import annotations

import json

from llmlang.web.parser import parse_app
from llmlang.web.server import emit_server


def test_generated_server_registers_only_declared_capabilities() -> None:
    app = parse_app(
        '(app w1 notes (store first (Text 12)) (store second (Text 24)) '
        '(action save (write first)) (action load (read second)) '
        '(page "/" (title "Notes") (output result "Value")))'
    )
    files = emit_server(app)
    runtime = files["lib/w1-server.ts"]
    config_source = runtime.split("export const appConfig: AppConfig = ", 1)[1].split(
        ";\n", 1
    )[0]
    assert json.loads(config_source) == {
        "appId": "notes",
        "stores": {
            "first": {"maxBytes": 12, "read": False, "write": True},
            "second": {"maxBytes": 24, "read": True, "write": False},
        },
    }


def test_server_artifacts_do_not_depend_on_ui_initial_values() -> None:
    source = (
        '(app w1 notes (store message (Text 100)) '
        '(action save (write message)) '
        '(page "/" (title "Notes") '
        '(input input_text "Text" (for message) (initial "REPLACE")) '
        '(output result "Value")))'
    )
    first = emit_server(parse_app(source.replace("REPLACE", "Hello World")))
    second = emit_server(parse_app(source.replace("REPLACE", "Other text")))
    assert first == second
    assert set(first) == {
        "lib/w1-server.ts",
        "app/api/store/[slot]/route.ts",
        "db/w1.ts",
        "db/schema.ts",
    }
