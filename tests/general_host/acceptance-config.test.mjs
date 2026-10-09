import assert from "node:assert/strict";
import { test } from "node:test";
import { immutableHostConfig } from "./acceptance-config.mjs";

test("immutable acceptance config preserves built routing, modules and bindings", () => {
  const built = {
    name: "fixture", main: "index.js", no_bundle: true,
    assets: {directory: "../client", binding: "ASSETS"},
    compatibility_flags: ["nodejs_compat"],
    rules: [{type: "ESModule", globs: ["**/*.js"]}],
    vars: {HOST_ALLOWED_ORIGIN: "http://127.0.0.1:8787"},
    d1_databases: [{binding: "DB", database_id: "test-only-id"}],
    build: {cwd: "."},
  };
  const original = structuredClone(built);
  const accepted = immutableHostConfig(built);
  assert.deepEqual(accepted, {...original,
    build: {cwd: ".", command: 'node -e ""', watch_dir: ["wrangler.json"]},
  });
  assert.deepEqual(built, original);
  accepted.assets.directory = "elsewhere";
  assert.equal(built.assets.directory, "../client");
});

test("acceptance setup requires a built worker and rejects malformed host config", () => {
  const valid = {main: "index.js", no_bundle: true, assets: {directory: "../client"}};
  assert.deepEqual(immutableHostConfig(valid).build,
    {command: 'node -e ""', watch_dir: ["wrangler.json"]});
  for (const invalid of [null, [], {}, {...valid, no_bundle: false},
    {...valid, main: ""}, {...valid, assets: {}}, {...valid, build: []}]) {
    assert.throws(() => immutableHostConfig(invalid), /built worker/);
  }
});
