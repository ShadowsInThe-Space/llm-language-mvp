"""Generated server boundary tests with a controlled D1-shaped test double.

These tests demonstrate HTTP/codec/dispatch behavior, not provider execution.
"""

import json
import subprocess
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from llmlang.a1.ir import canonical_bytes
from llmlang.a1.source import lower_source
from llmlang.web.general.codecs import BoolType, NatType, TextType, emit_typescript_runtime
from llmlang.web.general.program import (
    DisplayColumn,
    ListView,
    ParamTransform,
    ProgramError,
    QueryAction,
    ViewStates,
    WebProgram,
    validate_program,
)
from llmlang.web.general.queries import (
    Column,
    ConditionalUpdate,
    Insert,
    Order,
    Param,
    Schema,
    SelectList,
    SelectUnique,
    Table,
)
from llmlang.web.general.server import emit_server


def application() -> WebProgram:
    schema = Schema((Table("items", (
        Column("id", TextType(64), primary_key=True), Column("title", TextType(32)),
        Column("done", BoolType()), Column("revision", NatType()),
        Column("__proto__", TextType(32)),
    )),))
    key = Param("id", TextType(64))
    expected, title = Param("expected", NatType()), Param("title", TextType(32))
    projection = ("title", "done", "revision", "__proto__")
    done = Param("done", BoolType())
    actions = (
        QueryAction("save", (key, title, done), Insert("items", (
            ("id", key), ("title", title), ("done", done), ("revision", 0),
            ("__proto__", "safe"),
        ), projection)),
        QueryAction("find", (key,), SelectUnique("items", "id", key, projection)),
        QueryAction("list", (), SelectList("items", projection, (Order("id"),), 2)),
        QueryAction("edit", (key, expected, title), ConditionalUpdate(
            "items", "id", key, "revision", expected, (("title", title),), projection)),
        QueryAction("private", (key,), SelectUnique("items", "id", key, projection),
                    "authenticated"),
        QueryAction("admin", (key,), SelectUnique("items", "id", key, projection), "admin"),
        QueryAction("__proto__", (), SelectUnique("items", "id", "one", projection)),
    )
    view = ListView("items", "list", (DisplayColumn("title", "Title"),),
                    ViewStates("Loading", "Failed", "Empty", "Ready"))
    return WebProgram("server_app", "Server", schema, actions, (view,))


def transformed_application(max_steps: int = 1000) -> WebProgram:
    program = application()
    save = program.actions[0]
    other = Param("other", TextType(32))
    query = replace(save.query, values=(
        ("id", save.params[0]), ("title", save.params[1]), ("done", save.params[2]),
        ("revision", 0), ("__proto__", other),
    ))
    transformed = replace(save, params=(*save.params, other), query=query, transforms=(
        ParamTransform("title", "prefix", ("other",)),
        ParamTransform("other", "prefix", ("title",)),
    ))
    source = f'''(a1src1 (limits {max_steps} 100 20)
      (fn prefix ((text (Text 32))) (Text 32)
        (let count Nat (const 1))
        (let result (Text 32) (text_prefix_codepoints text count)) (return result))
      (fn reset ((number Nat)) Nat (let zero Nat (const 0)) (return zero))
      (entry prefix) (entry reset))'''
    edit = replace(program.actions[3], transforms=(
        ParamTransform("expected", "reset", ("expected",)),
    ))
    actions = (transformed, *program.actions[1:3], edit, *program.actions[4:])
    return replace(program, actions=actions,
                   pure_library=canonical_bytes(lower_source(source)))


ROW = {"title": "Hello 🌍", "done": 1, "revision": 1, "__proto__": "safe"}


def input_value(action: str = "find", **fields: object) -> dict[str, object]:
    return {"record": action + "Input", "fields": fields or {"id": "one"}}


RUNNER = r'''
import fs from "node:fs";
import {stripTypeScriptTypes} from "node:module";
const source = name => fs.readFileSync(new URL(name, import.meta.url), "utf8");
fs.writeFileSync(new URL("./codecs", import.meta.url), stripTypeScriptTypes(source("./codecs.ts")));
fs.writeFileSync(new URL("./server.mjs", import.meta.url),
                 stripTypeScriptTypes(source("./server.ts")));
if (fs.existsSync(new URL("./a1-pure.ts", import.meta.url)))
  fs.writeFileSync(new URL("./a1-pure", import.meta.url),
                   stripTypeScriptTypes(source("./a1-pure.ts")));
const {createDispatcher} = await import("./server.mjs");
const payload = JSON.parse(fs.readFileSync(0, "utf8"));
const results = [];
for (const operation of payload.operations) {
  const calls = [], authCalls = [];
  const statement = {
    bind(...values) { calls.push({kind: "bind", values}); return this; },
    async all() {
      calls.push({kind: "all"});
      if (operation.dbError) throw new Error("SECRET provider SQL statement");
      let rows = operation.rows ?? [payload.row];
      if (operation.rowMode === "inherited") rows = [Object.create(payload.row)];
      return {success: operation.dbSuccess ?? true, results: rows};
    },
  };
  const db = {prepare(sql) { calls.push({kind: "prepare", sql}); return statement; }};
  const options = {allowedOrigin: "https://app.test", maxRequestBytes: operation.maxBytes ?? 32768,
                   bodyTimeoutMs: operation.timeoutMs ?? 5000};
  if (operation.authorize) options.authorize = (action, request, requirement) => {
    authCalls.push({action, origin: request.headers.get("origin"), requirement});
    if (operation.authorize === "throw") throw new Error("SECRET auth provider");
    return operation.authorize === "allow";
  };
  const dispatch = createDispatcher(db, options);
  const headers = {"content-type": operation.contentType ?? "application/json"};
  if (operation.origin !== null) headers.origin = operation.origin ?? "https://app.test";
  if (operation.contentLength !== undefined) headers["content-length"] = operation.contentLength;
  const method = operation.method ?? "POST";
  let body = operation.raw ?? JSON.stringify({action: operation.action ?? "find",
                                              input: operation.input ?? payload.input});
  if (operation.bytes) body = new Uint8Array(operation.bytes);
  if (operation.stream || operation.hang) {
    let index = 0;
    body = new ReadableStream({pull(controller) {
      if (operation.hang) return new Promise(() => {});
      if (index === operation.stream.length) controller.close();
      else controller.enqueue(new TextEncoder().encode(operation.stream[index++]));
    }});
  }
  const request = new Request("https://app.test/api", {method, headers,
    ...(method === "POST" ? {body, duplex: "half"} : {})});
  const response = await dispatch(request);
  results.push({status: response.status, body: await response.json(), calls, authCalls});
}
console.log(JSON.stringify(results));
'''


class ServerTests(unittest.TestCase):
    def run_operations(
        self, *operations: dict[str, object], program: WebProgram | None = None,
    ) -> list[dict]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            selected = application() if program is None else program
            (root / "server.ts").write_text(emit_server(selected))
            pure = validate_program(selected).snapshot().get("pure_library")
            if pure is not None and pure.get("role") == "executable":
                from llmlang.a1.runtime import emit_typescript_runtime as emit_pure_runtime

                (root / "a1-pure.ts").write_text(emit_pure_runtime(
                    pure["ir"], entries=tuple(pure["entries"]),
                ))
            (root / "codecs.ts").write_text(emit_typescript_runtime())
            (root / "package.json").write_text('{"type":"module"}')
            (root / "run.mjs").write_text(RUNNER)
            result = subprocess.run(["node", str(root / "run.mjs")],
                input=json.dumps({"operations": operations, "row": ROW, "input": input_value()}),
                capture_output=True, text=True, check=True, timeout=20)
            return json.loads(result.stdout)

    def test_emitter_validates_program_and_is_deterministic(self) -> None:
        program = application()
        self.assertEqual(emit_server(program), emit_server(program))
        with self.assertRaises(ProgramError):
            emit_server(replace(program, views=()))
        self.assertNotIn("request.text()", emit_server(program))

    def test_template_marker_literals_remain_data_in_action_metadata(self) -> None:
        original = application()
        for marker in ("__PURE_IMPORT__", "__TRANSFORM_FUNCTION__", "__ACTION_METADATA__"):
            save = original.actions[0]
            query = replace(save.query, values=tuple(
                (name, marker if name == "__proto__" else value)
                for name, value in save.query.values
            ))
            program = replace(original, actions=(replace(save, query=query), *original.actions[1:]))
            with self.subTest(marker=marker):
                self.assertTrue('"value":"' + marker + '"' in emit_server(program))

    def test_valid_wire_input_binds_sql_and_nominal_result(self) -> None:
        result, = self.run_operations({})
        self.assertEqual(result["status"], 200)
        value = result["body"]
        self.assertEqual(value["tag"], "Some")
        self.assertEqual(value["value"], {"record": "findRow", "fields": {
            "title": "Hello 🌍", "done": True, "revision": "1", "__proto__": "safe"}})
        self.assertEqual(result["calls"][1], {"kind": "bind", "values": ["one"]})
        self.assertIn('WHERE "id" = ?', result["calls"][0]["sql"])

    def test_insert_boolean_and_constant_bindings_have_no_sql_interpolation(self) -> None:
        payload = "'; DROP TABLE items;--"
        results = self.run_operations(
            {"action": "save", "input": input_value("save", id="one", title=payload, done=False)},
            {"action": "save", "input": input_value("save", id="one", title="ok", done=True),
             "rows": []},
        )
        self.assertEqual(results[0]["status"], 200)
        self.assertEqual(results[0]["body"]["record"], "saveRow")
        self.assertEqual(results[0]["calls"][1]["values"], ["one", payload, 0, 0, "safe"])
        self.assertNotIn(payload, results[0]["calls"][0]["sql"])
        self.assertEqual(results[1]["status"], 500)

    def test_pure_transforms_bind_actual_results_using_original_arguments(self) -> None:
        program = transformed_application()
        wire = input_value("save", id="one", title="Alpha", done=False, other="Beta")
        result, = self.run_operations({"action": "save", "input": wire}, program=program)
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["calls"][1]["values"], ["one", "B", 0, 0, "A"])
        self.assertIn('import {invokePure} from "./a1-pure"', emit_server(program))
        self.assertNotIn('from "./a1-pure"', emit_server(application()))
        unused = replace(application(), pure_library=program.pure_library)
        self.assertNotIn('from "./a1-pure"', emit_server(unused))

    def test_pure_runtime_failure_is_generic_and_precedes_database(self) -> None:
        program = transformed_application(max_steps=1)
        wire = input_value("save", id="one", title="Alpha", done=False, other="Beta")
        result, = self.run_operations({"action": "save", "input": wire}, program=program)
        self.assertEqual(result["status"], 422)
        self.assertEqual(result["body"], {"error": "InvalidInput"})
        self.assertEqual(result["calls"], [])

    def test_transform_precedes_query_revision_overflow_validation(self) -> None:
        wire = input_value("edit", id="one", expected="9007199254740991", title="new")
        result, = self.run_operations({"action": "edit", "input": wire},
                                     program=transformed_application())
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["calls"][1]["values"], ["new", "one", 0])

    def test_protected_actions_authorize_before_running_pure_transform(self) -> None:
        original = transformed_application(max_steps=1)
        save = replace(original.actions[0], authorization="admin")
        program = replace(original, actions=(save, *original.actions[1:]))
        wire = input_value("save", id="one", title="Alpha", done=False, other="Beta")
        results = self.run_operations({"action": "save", "input": wire},
            {"action": "save", "input": wire, "authorize": "deny"},
            {"action": "save", "input": wire, "authorize": "allow"}, program=program)
        self.assertEqual([result["status"] for result in results], [403, 403, 422])
        self.assertTrue(all(result["calls"] == [] for result in results))

    def test_transport_envelope_and_typed_input_fail_before_database(self) -> None:
        operations = (
            {"origin": "https://evil.test"}, {"origin": None}, {"method": "GET"},
            {"contentType": "text/plain"}, {"raw": '{"action":"find","action":"admin","input":{}}'},
            {"action": "unknown"}, {"raw": '{"action":"find","input":{},"db":"evil"}'},
            {"input": {"record": "findInput", "fields": {"id": "one", "admin": True}}},
            {"input": input_value(id=4)}, {"input": input_value(id="🌍" * 17)},
            {"bytes": [255]}, {"action": "list", "input": {"capability": "db.write"}},
        )
        expected = [403, 403, 405, 415, 400, 400, 400, 422, 400, 422, 400, 422]
        for result, status in zip(self.run_operations(*operations), expected, strict=True):
            self.assertEqual(result["status"], status)
            self.assertEqual(result["calls"], [])

    def test_stream_body_byte_and_time_budgets(self) -> None:
        results = self.run_operations(
            {"stream": ["x" * 20000, "x" * 20000]},
            {"contentLength": "999999"}, {"contentLength": "invalid"},
            {"hang": True, "timeoutMs": 5}, {"raw": "{}", "maxBytes": 1},
        )
        self.assertEqual([result["status"] for result in results], [413, 413, 400, 408, 413])
        self.assertTrue(all(result["calls"] == [] for result in results))

    def test_private_and_admin_require_trusted_host_authorization(self) -> None:
        results = self.run_operations(
            {"action": "private", "input": input_value("private")},
            {"action": "admin", "input": input_value("admin"), "authorize": "deny"},
            {"action": "admin", "input": input_value("admin"), "authorize": "throw"},
            {"action": "admin", "input": input_value("admin"), "authorize": "allow"},
        )
        self.assertEqual([result["status"] for result in results], [403, 403, 403, 200])
        self.assertTrue(all(result["calls"] == [] for result in results[:-1]))
        self.assertEqual(results[-1]["authCalls"], [{"action": "admin",
                                                   "origin": "https://app.test",
                                                   "requirement": "admin"}])

    def test_database_results_fail_closed_without_provider_details(self) -> None:
        rows = ({**ROW, "done": True}, {**ROW, "done": 2}, {**ROW, "revision": 9007199254740992},
                {**ROW, "title": None}, {**ROW, "title": "🌍" * 9}, {**ROW, "extra": "unexpected"})
        results = self.run_operations(*({"rows": [row]} for row in rows),
                                     {"rowMode": "inherited"}, {"dbError": True},
                                     {"dbSuccess": False}, {"rows": [ROW, ROW]})
        for result in results:
            self.assertEqual(result["status"], 500)
            self.assertNotIn("SECRET", json.dumps(result["body"]))
            self.assertNotIn("SQL", json.dumps(result["body"]))

    def test_cas_binds_exact_integer_strings_and_conflict_is_explicit(self) -> None:
        wire = input_value("edit", id="one", expected="0", title="new")
        results = self.run_operations({"action": "edit", "input": wire, "rows": []},
                                     {"action": "edit", "input": wire},
                                     {"action": "edit", "input": input_value("edit", id="one",
                                         expected="9007199254740991", title="new")})
        self.assertEqual([result["status"] for result in results], [409, 200, 422])
        self.assertEqual(results[0]["body"], {"error": "ConditionNotMet"})
        self.assertEqual(results[1]["calls"][1]["values"], ["new", "one", 0])
        self.assertEqual(results[2]["calls"], [])

    def test_optional_none_empty_list_and_prototype_named_action(self) -> None:
        results = self.run_operations({"rows": []}, {"action": "list", "input": {}, "rows": []},
                                     {"action": "__proto__", "input": {}})
        self.assertEqual(results[0]["body"], {"tag": "None", "value": None})
        self.assertEqual(results[1]["body"], [])
        self.assertEqual(results[2]["status"], 200)
        self.assertEqual(results[2]["body"]["value"]["fields"]["__proto__"], "safe")


if __name__ == "__main__":
    unittest.main()
