# ruff: noqa: E501
"""Generated client behavior is exercised as plain TypeScript, not claimed browser evidence."""

import shutil
import subprocess
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from llmlang.web.general.client import emit_client
from llmlang.web.general.codecs import (
    BoolType,
    IntType,
    NatType,
    TextType,
    emit_typescript_runtime,
)
from llmlang.web.general.program import (
    DetailView,
    DisplayColumn,
    FormView,
    InputField,
    ListView,
    ProgramError,
    QueryAction,
    Selection,
    ViewStates,
    WebProgram,
)
from llmlang.web.general.queries import (
    Column,
    Insert,
    Order,
    Param,
    Schema,
    SelectList,
    SelectUnique,
    Table,
)


def application(table: str = "entries", title: str = "title") -> WebProgram:
    fields = (("id", TextType(64)), (title, TextType(32)), ("count", NatType()),
              ("delta", IntType()), ("done", BoolType()))
    schema = Schema((Table(table, tuple(Column(name, kind, primary_key=name == "id")
                                       for name, kind in fields) +
                           (Column("private_secret", TextType(64)),)),))
    params = tuple(Param(name, kind) for name, kind in fields)
    columns = tuple(name for name, _ in fields)
    states = ViewStates("Loading", "Failed", "Nothing here", "Ready")
    return WebProgram("example", "Example", schema, (
        QueryAction("save", params, Insert(table, tuple((param.name, param) for param in params) +
                                          (("private_secret", "SERVER_ONLY_SECRET"),), columns)),
        QueryAction("list", (), SelectList(table, columns, (Order(title),), 5)),
        QueryAction("detail", (Param("selected_id", TextType(64)),),
                    SelectUnique(table, "id", Param("selected_id", TextType(64)), columns)),
    ), (
        FormView("editor", "save", (
            InputField("id", "ID"), InputField(title, "Title", "select", (("First", "alpha"), ("Second", "beta"))),
            InputField("count", "Count"), InputField("delta", "Delta"), InputField("done", "Done", "checkbox"),
        ), states),
        ListView("listing", "list", (DisplayColumn(title, "Title"),), states,
                 Selection("selected", "selected_id", "id")),
        DetailView("selected", "detail", (DisplayColumn(title, "Title"),), states),
    ))


class ClientTests(unittest.TestCase):
    def test_emission_is_deterministic_checked_and_domain_independent(self) -> None:
        first = emit_client(application())
        self.assertEqual(first, emit_client(application()))
        other = emit_client(application("customers", "name"))
        self.assertIn('"name"', other)
        self.assertNotIn('"column":"title"', other)
        for secret in ("SERVER_ONLY_SECRET", "private_secret", "INSERT INTO", "SELECT ",
                       "identity.admin", "authorization", "node:", "Buffer", "D1Database"):
            self.assertNotIn(secret, first)
        self.assertIn('from "react"', first)
        self.assertIn("htmlFor={id}", first)
        self.assertIn('endpoint = "/api/general"', first)
        self.assertIn('type="checkbox"', first)
        self.assertIn("<select", first)
        self.assertIn('inputMode="numeric"', first)
        self.assertIn("new TextEncoder()", first)
        with self.assertRaises(ProgramError):
            emit_client(replace(application(), title=""))

    @unittest.skipUnless(shutil.which("node"), "Node TypeScript execution unavailable")
    def test_controller_codec_failure_clear_and_stale_response_behavior(self) -> None:
        source = emit_client(application())
        runtime = source.split("// BEGIN GENERAL CLIENT RUNTIME\n", 1)[1].split(
            "// END GENERAL CLIENT RUNTIME", 1)[0]
        script = r'''
import assert from 'node:assert/strict';
import {createClientController} from './controller.ts';
const pending = [];
const calls = [];
let transportFailure = false;
const fetcher = async (endpoint, options) => {
  calls.push({endpoint, options, body: JSON.parse(options.body)});
  if (transportFailure) throw new Error('transport unavailable');
  return await new Promise(resolve => pending.push(resolve));
};
const client = createClientController('/custom/general', fetcher);
const row = (id, title = 'alpha') => ({record:'detailRow',fields:{id,title,count:'2',delta:'-1',done:false}});
const response = (value, status = 200) => new Response(JSON.stringify(value), {status,headers:{'Content-Type':'application/json'}});
let updates = 0;
const unsubscribe = client.subscribe(() => updates++);
const draft = {id:'one',title:'alpha',count:'2',delta:'-1',done:false};
let operation = client.submitForm('editor', draft);
assert.equal(client.getState('editor').status, 'loading');
assert.deepEqual(calls[0].body, {action:'save',input:{record:'saveInput',fields:draft}});
assert.equal(calls[0].endpoint, '/custom/general');
assert.equal(calls[0].options.credentials, 'same-origin');
assert.equal(calls[0].options.redirect, 'error');
pending.shift()(response({...row('one'),record:'saveRow'})); await operation;
assert.equal(client.getState('editor').status, 'success');
assert.equal(client.getState('editor').value.fields.count, 2);
const confirmed = client.getState('editor').value;
operation = client.submitForm('editor', {...draft, id:'bad'});
pending.shift()(response({error:'ServiceUnavailable'}, 500)); await operation;
assert.equal(client.getState('editor').status, 'error');
assert.deepEqual(client.getState('editor').value, confirmed);
transportFailure = true;
await client.submitForm('editor', draft);
assert.equal(client.getState('editor').status, 'error');
assert.deepEqual(client.getState('editor').value, confirmed);
transportFailure = false;
const beforeInvalid = calls.length;
for (const count of ['01', '+1', '1.0', '9007199254740992', '-0', '-1']) {
  await client.submitForm('editor', {...draft, count});
  assert.equal(client.getState('editor').status, 'error');
  assert.deepEqual(client.getState('editor').value, confirmed);
}
assert.equal(calls.length, beforeInvalid);
operation = client.loadList('listing');
assert.deepEqual(calls.at(-1).body, {action:'list',input:{}});
pending.shift()(response([])); await operation;
assert.equal(client.getState('listing').status, 'empty');
operation = client.loadList('listing');
pending.shift()(response([{...row('one'), record:'listRow'}])); await operation;
const listed = client.getState('listing').value.list[0];
const first = client.selectRow('listing', listed);
const firstCall = calls.at(-1);
const second = client.selectRow('listing', {...listed,fields:{...listed.fields,id:'two'}});
assert.equal(firstCall.options.signal.aborted, true);
const resolveFirst = pending.shift();
pending.shift()(response({tag:'Some',value:row('two','beta')})); await second;
resolveFirst(response({tag:'Some',value:row('one')})); await first;
assert.equal(client.getState('selected').value.value.fields.id, 'two');
operation = client.selectRow('listing', listed);
const obsolete = pending.shift();
const beforeClear = calls.length;
client.clear('selected');
assert.equal(client.getState('selected').status, 'empty');
assert.equal(client.getState('selected').value, null);
assert.equal(calls.at(-1).options.signal.aborted, true);
obsolete(response({tag:'Some',value:row('one')})); await operation;
assert.equal(client.getState('selected').value, null);
client.clear('editor');
assert.equal(calls.length, beforeClear);
assert.equal(client.getState('editor').value, null);
operation = client.loadList('listing');
pending.shift()(response([{...row('one'),record:'listRow',fields:{...row('one').fields,count:2}}])); await operation;
assert.equal(client.getState('listing').status, 'error');
assert.equal(client.getState('listing').value.list.length, 1);
for (const malformed of [
  response({list:[],capacity:'5'}),
  response([{...row('one'),record:'wrong'}]),
  response([{...row('one'),record:'listRow',fields:{...row('one').fields,extra:true}}]),
  new Response('[1]',{headers:{'Content-Type':'application/json'}}),
  new Response('[{"record":"listRow","record":"listRow","fields":{}}]',{headers:{'Content-Type':'application/json'}}),
  new Response('[]',{headers:{'Content-Type':'text/plain'}}),
  new Response('[]',{headers:{'Content-Type':'application/json','content-length':'32769'}}),
  new Response(' '.repeat(32769),{headers:{'Content-Type':'application/json'}}),
]) {
  operation = client.loadList('listing'); pending.shift()(malformed); await operation;
  assert.equal(client.getState('listing').status, 'error');
  assert.equal(client.getState('listing').value.list.length, 1);
}
operation = client.selectRow('listing', listed);
pending.shift()(response({tag:'None',value:null})); await operation;
assert.equal(client.getState('selected').status, 'empty');
assert.equal(client.getState('selected').value.tag, 'None');
assert.throws(() => client.loadList('selected'));
assert.throws(() => createClientController('https://elsewhere.invalid/api', fetcher));
assert.ok(updates > 0); unsubscribe(); client.dispose();
console.log('controller behavior passed');
'''
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "codecs.ts").write_text(emit_typescript_runtime())
            (folder / "controller.ts").write_text(runtime.replace('"./codecs"', '"./codecs.ts"'))
            (folder / "test.ts").write_text(script)
            result = subprocess.run(["node", str(folder / "test.ts")], text=True, capture_output=True,
                                    check=False, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("controller behavior passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
