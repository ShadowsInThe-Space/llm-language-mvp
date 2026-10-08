"""Generated source targets with a real SQLite adapter, not D1 acceptance.

Node's SQLite engine executes emitted schema and prepared query statements. Only
imports in temporary test copies gain TypeScript extensions for Node execution.
"""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from llmlang.web.general.build import compile_source

EXAMPLES = Path(__file__).resolve().parents[1] / "examples/web/general"
TITLE = "😀é漢x" * 40 + "tail"
UPDATED_TITLE = "🧠n\u0303猫" * 40 + "trailing"

RUNNER = r'''
import fs from "node:fs";
import {DatabaseSync} from "node:sqlite";
import {createDispatcher} from "./server.ts";
const payload = JSON.parse(fs.readFileSync(0, "utf8"));
const filename = new URL("./application.sqlite", import.meta.url).pathname;
let database = new DatabaseSync(filename);
database.exec(fs.readFileSync(new URL("./schema.sql", import.meta.url), "utf8"));
const adapter = {
  prepare(sql) {
    const statement = database.prepare(sql);
    let values = [];
    return {
      bind(...bound) { values = bound; return this; },
      async all() { return {success: true, results: statement.all(...values)}; },
    };
  },
};
const dispatch = createDispatcher(adapter, {allowedOrigin: "https://app.test"});
const results = [];
try {
  for (const operation of payload.operations) {
    if (operation.reopenBefore) {
      database.close();
      database = new DatabaseSync(filename);
    }
    const request = new Request("https://app.test/api", {
      method: "POST",
      headers: {origin: "https://app.test", "content-type": "application/json"},
      body: JSON.stringify({action: operation.action, input: operation.input}),
    });
    const response = await dispatch(request);
    // This independent inspection uses a trusted test fixture table identifier.
    const stored = database.prepare(`SELECT * FROM "${payload.table}" ORDER BY "id"`).all();
    results.push({status: response.status, body: await response.json(), stored});
  }
} finally {
  database.close();
}
console.log(JSON.stringify(results));
'''


def input_value(action: str, **fields: object) -> dict[str, object]:
    return {"record": action + "Input", "fields": fields}


class SQLiteTargetTests(unittest.TestCase):
    def run_application(self, name: str, table: str, operations: list[dict]) -> list[dict]:
        source = (EXAMPLES / f"{name}.webapp").read_text(encoding="utf-8")
        build = compile_source(source,
            library_sources={"common": (EXAMPLES / "common.webuilib").read_text(encoding="utf-8")},
            pure_sources={"helpers": (EXAMPLES / "helpers.a1src").read_text(encoding="utf-8")})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for filename in ("server.ts", "codecs.ts", "a1-pure.ts"):
                text = build.files[filename]
                text = text.replace('from "./codecs"', 'from "./codecs.ts"')
                text = text.replace('from "./a1-pure"', 'from "./a1-pure.ts"')
                (root / filename).write_text(text, encoding="utf-8")
            (root / "schema.sql").write_text(build.files["schema.sql"], encoding="utf-8")
            (root / "package.json").write_text('{"type":"module"}', encoding="utf-8")
            (root / "run.mjs").write_text(RUNNER, encoding="utf-8")
            result = subprocess.run(["node", str(root / "run.mjs")],
                input=json.dumps({"table": table, "operations": operations}),
                capture_output=True, text=True, check=True, timeout=20)
            return json.loads(result.stdout)

    def test_history_source_pure_preview_queries_and_reopened_database(self):
        self.assertGreater(len(TITLE), 120)
        self.assertLessEqual(len(TITLE.encode("utf-8")), 512)
        expected = TITLE[:120]
        operations = [
            {"action": "save", "input": input_value("save", id="history-1", title=TITLE)},
            {"action": "browse", "input": {}},
            {"action": "fetch", "input": input_value("fetch", selected_id="history-1")},
            {"action": "fetch", "input": input_value("fetch", selected_id="history-1"),
             "reopenBefore": True},
        ]
        saved, listed, detail, reopened = self.run_application("history", "entries", operations)
        self.assertEqual([value["status"] for value in (saved, listed, detail, reopened)],
                         [200, 200, 200, 200])
        self.assertEqual(saved["body"], {"record": "saveRow", "fields": {
            "id": "history-1", "title": expected}})
        self.assertEqual(saved["stored"], [{"id": "history-1", "title": expected, "revision": 0}])
        self.assertEqual(listed["body"], [{"record": "browseRow", "fields": {
            "id": "history-1", "title": expected}}])
        self.assertEqual(detail["body"], {"tag": "Some", "value": {
            "record": "fetchRow", "fields": {
                "id": "history-1", "title": expected, "revision": "0"}}})
        self.assertEqual(reopened, detail)

    def test_task_source_pure_preview_atomic_revision_and_persistence(self):
        self.assertGreater(len(UPDATED_TITLE), 120)
        self.assertLessEqual(len(UPDATED_TITLE.encode("utf-8")), 512)
        operations = [
            {"action": "save", "input": input_value("save", id="task-1", title=TITLE)},
            {"action": "browse", "input": {}},
            {"action": "fetch", "input": input_value("fetch", selected_id="task-1")},
            {"action": "update", "input": input_value("update", id="task-1",
                title=UPDATED_TITLE, revision="0", done=True, priority="3")},
            {"action": "update", "input": input_value("update", id="task-1",
                title="Must not replace stored task", revision="0", done=False, priority="99")},
            {"action": "fetch", "input": input_value("fetch", selected_id="task-1"),
             "reopenBefore": True},
        ]
        saved, listed, detail, updated, stale, reopened = self.run_application(
            "tasks", "tasks", operations)
        self.assertEqual([value["status"] for value in
                         (saved, listed, detail, updated, stale, reopened)],
                         [200, 200, 200, 200, 409, 200])
        self.assertEqual(saved["stored"], [{"id": "task-1", "title": TITLE[:120],
            "revision": 0, "done": 0, "priority": 0}])
        initial = {"id": "task-1", "title": TITLE[:120],
                   "revision": "0", "done": False, "priority": "0"}
        self.assertEqual(listed["body"], [{"record": "browseRow", "fields": initial}])
        self.assertEqual(detail["body"], {"tag": "Some", "value": {
            "record": "fetchRow", "fields": initial}})
        fields = {"id": "task-1", "title": UPDATED_TITLE[:120],
                  "revision": "1", "done": True, "priority": "3"}
        self.assertEqual(updated["body"], {"tag": "Some", "value": {
            "record": "updateRow", "fields": fields}})
        self.assertEqual(updated["stored"], [{"id": "task-1", "title": UPDATED_TITLE[:120],
            "revision": 1, "done": 1, "priority": 3}])
        self.assertEqual(stale["body"], {"error": "ConditionNotMet"})
        self.assertEqual(stale["stored"], updated["stored"])
        self.assertEqual(reopened["stored"], updated["stored"])
        self.assertEqual(reopened["body"], {"tag": "Some", "value": {
            "record": "fetchRow", "fields": fields}})


if __name__ == "__main__":
    unittest.main()
