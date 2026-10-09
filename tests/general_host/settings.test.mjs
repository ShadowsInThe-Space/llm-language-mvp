import assert from "node:assert/strict";
import { test } from "node:test";
import { resolve } from "node:path";
import { hostSettings } from "./settings.mjs";

test("local host configuration captures the trusted origin and persistence path", () => {
  const settings = hostSettings({}, "/tmp/general-fixture");
  assert.equal(settings.origin, "http://127.0.0.1:8787");
  assert.equal(settings.ip, "127.0.0.1");
  assert.equal(settings.port, "8787");
  assert.equal(settings.state, resolve("/tmp/general-fixture/.state"));
  const other = hostSettings({
    LLMLANG_GENERAL_BASE_URL: "http://localhost:8790",
    LLMLANG_D1_STATE: "/tmp/disposable-d1",
  }, "/tmp/general-fixture");
  assert.equal(other.origin, "http://localhost:8790");
  assert.equal(other.ip, "127.0.0.1");
  assert.equal(other.port, "8790");
  assert.equal(other.state, "/tmp/disposable-d1");
});

test("the acceptance runner cannot target a remote origin or alter origin via path", () => {
  for (const url of [
    "https://127.0.0.1:8787", "http://example.com:8787", "http://127.0.0.1:8787/path",
    "http://user:password@localhost:8787", "http://localhost:8787?origin=elsewhere",
    "http://localhost:8787#fragment", "not-a-url",
  ]) {
    assert.throws(() => hostSettings({LLMLANG_GENERAL_BASE_URL: url}, "/tmp/general-fixture"));
  }
});
