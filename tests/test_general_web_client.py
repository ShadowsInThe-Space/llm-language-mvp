# ruff: noqa: E501
"""Generated client behavior is exercised as plain TypeScript, not claimed browser evidence."""

import os
import shutil
import subprocess
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from llmlang.a1.ir import canonical_bytes
from llmlang.a1.source import parse_source as parse_pure_source
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
    ParamTransform,
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

    def test_executable_pure_transform_and_internal_helpers_stay_server_only(self) -> None:
        source = """(a1src1 (limits 100 10 8)
          (fn server_only_preview ((text (Text 32))) (Text 32)
            (let result (Text 32) (call server_only_shorten text)) (return result))
          (fn server_only_shorten ((text (Text 32))) (Text 32)
            (let count Nat (const 2))
            (let result (Text 32) (text_prefix_codepoints text count)) (return result))
          (entry server_only_preview))"""
        original = application()
        transform = ParamTransform("title", "server_only_preview", ("title",))
        transformed = replace(original, pure_library=canonical_bytes(parse_pure_source(source).module),
                              actions=(replace(original.actions[0], transforms=(transform,)),
                                       *original.actions[1:]))
        client = emit_client(transformed)
        self.assertEqual(client, emit_client(original))
        for server_detail in ("server_only_preview", "server_only_shorten", "text_prefix_codepoints",
                              "a1-pure", "invokePure", "transforms", "pure_library", "a1-ir-v1"):
            self.assertNotIn(server_detail, client)
        different_body = source.replace("(const 2)", "(const 3)")
        self.assertEqual(client, emit_client(replace(
            transformed, pure_library=canonical_bytes(parse_pure_source(different_body).module))))

    def test_actionable_controls_have_a_hydration_gate(self) -> None:
        source = emit_client(application())
        self.assertIn('const [ready, setReady] = useState(false)', source)
        self.assertIn('setReady(true)', source)
        self.assertIn('<fieldset disabled={!ready}>', source)
        self.assertIn('disabled={!ready || state.status === "loading"}', source)
        self.assertIn('disabled={!ready} onClick={() => controller.clear', source)
        self.assertIn('if (ready) void controller.submitForm', source)

    @unittest.skipUnless(os.environ.get("LLMLANG_REACT_TOOLCHAIN"),
                         "Pinned React SSR/hydration toolchain unavailable")
    def test_actual_generated_react_ssr_and_hydrated_dom(self) -> None:
        toolchain = Path(os.environ["LLMLANG_REACT_TOOLCHAIN"]).resolve()
        script = r'''
const assert = require('node:assert/strict');
const React = require('react');
const {renderToString} = require('react-dom/server');
const {JSDOM} = require('jsdom');
const App = require('./App.js').default;
const element = () => React.createElement(React.StrictMode, null, React.createElement(App));
const html = renderToString(element());
const dom = new JSDOM('<div id="root">' + html + '</div>', {
  url: 'http://localhost:8787/', pretendToBeVisual: true,
});
const {document} = dom.window;
const ssrFieldset = document.querySelector('fieldset');
assert.ok(ssrFieldset.disabled, 'SSR form must remain inert');
for (const button of document.querySelectorAll('button'))
  assert.ok(button.disabled || button.closest('fieldset[disabled]'), 'SSR button is active');
for (const control of document.querySelectorAll('input,select'))
  assert.ok(control.disabled || control.closest('fieldset[disabled]'), 'SSR control is active');
let submitted = false;
document.querySelector('form').addEventListener('submit', () => submitted = true);
document.querySelector('button[type="submit"]').click();
assert.equal(submitted, false, 'SSR disabled submit must not cause a native submit');
global.window = dom.window; global.document = document;
global.HTMLElement = dom.window.HTMLElement;
global.IS_REACT_ACT_ENVIRONMENT = true;
const {hydrateRoot} = require('react-dom/client');
(async () => {
  let root;
  await React.act(async () => {
    root = hydrateRoot(document.getElementById('root'), element());
  });
  assert.equal(document.querySelector('fieldset').disabled, false, 'Hydration enables controls');
  for (const button of document.querySelectorAll('button')) assert.equal(button.disabled, false);
  for (const input of document.querySelectorAll('input,select')) {
    assert.equal(input.labels.length, 1);
    assert.equal(input.labels[0].htmlFor, input.id);
  }
  const form = document.querySelector('form');
  let prevented;
  await React.act(async () => {
    prevented = !form.dispatchEvent(new dom.window.Event('submit', {bubbles:true,cancelable:true}));
  });
  assert.equal(prevented, true, 'Hydrated handler prevents native form navigation');
  assert.equal(document.querySelector('[role="alert"]').textContent, 'Failed');
  await React.act(async () => root.unmount());
  dom.window.close();
  console.log('actual React SSR and hydrated DOM passed');
})().catch(error => {console.error(error);process.exitCode=1;});
'''
        with tempfile.TemporaryDirectory(prefix="hydration-", dir=toolchain) as directory:
            folder = Path(directory)
            (folder / "App.tsx").write_text(emit_client(application()))
            (folder / "codecs.ts").write_text(emit_typescript_runtime())
            (folder / "package.json").write_text('{"type":"commonjs"}')
            (folder / "test.cjs").write_text(script)
            compiled = subprocess.run([
                str(toolchain / "node_modules/.bin/tsc"), "--strict", "--target", "ES2022",
                "--module", "commonjs", "--moduleResolution", "node", "--jsx", "react-jsx",
                "--esModuleInterop", "--lib", "DOM,ES2022", "--types", "react",
                "App.tsx", "codecs.ts",
            ], cwd=folder, text=True, capture_output=True, check=False, timeout=30)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            result = subprocess.run(["node", str(folder / "test.cjs")], text=True,
                                    capture_output=True, check=False, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("actual React SSR and hydrated DOM passed", result.stdout)

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
