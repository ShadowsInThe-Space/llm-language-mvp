"""Emit the w1 server, its host boundary, and its fixed version-one schema."""

from __future__ import annotations

import json
from pathlib import Path

from .model import WebApp
from .parser import validate_app

_TEMPLATES = Path(__file__).with_name("templates")
_FILES = {
    "lib/w1-server.ts": "server.ts.tmpl",
    "app/api/store/[slot]/route.ts": "route.ts.tmpl",
    "db/w1.ts": "db-host.ts.tmpl",
    "db/schema.ts": "db-schema.ts.tmpl",
}


def emit_server(app: WebApp) -> dict[str, str]:
    """Generate static capabilities; source text never becomes SQL or host code."""
    validate_app(app)
    config = {
        "appId": app.name,
        "stores": {
            store.name: {
                "maxBytes": store.max_bytes,
                "read": any(
                    action.store == store.name and action.effect == "read" for action in app.actions
                ),
                "write": any(
                    action.store == store.name and action.effect == "write"
                    for action in app.actions
                ),
            }
            for store in app.stores
        },
    }
    serialized = json.dumps(config, ensure_ascii=True, separators=(",", ":"))
    output = {
        target: (_TEMPLATES / template)
        .read_text(encoding="utf-8")
        .replace("__W1_CONFIG__", serialized)
        for target, template in _FILES.items()
    }
    if app.profile == "w2":
        runtime = (
            output["lib/w1-server.ts"]
            .replace(
                "export async function handleStore(", "export async function handleSingleStore("
            )
            .replace(
                "first<T>(): Promise<T | null>;",
                "first<T>(): Promise<T | null>;\n  all<T>(): Promise<{results: T[]}>;",
            )
        )
        output["lib/w1-server.ts"] = runtime + (_TEMPLATES / "history-server.ts.tmpl").read_text()
        output["db/schema.ts"] = (
            output["db/schema.ts"].replace(
                "{ check, primaryKey, sqliteTable, text }",
                "{ check, index, integer, primaryKey, sqliteTable, text, uniqueIndex }",
            )
            + (_TEMPLATES / "history-schema.ts.tmpl").read_text()
        )
        output["llmlang/migrate-w1-to-w2.sql"] = (
            "INSERT INTO w2_entries(app_id,store_id,id,value,created_at)\n"
            "SELECT app_id,store_id,'legacy',value,"
            "strftime('%Y-%m-%dT%H:%M:%fZ','now') FROM w1_values\n"
            "WHERE 1 ON CONFLICT(app_id,store_id,id) DO NOTHING;\n"
        )
    return output
