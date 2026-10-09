#!/usr/bin/env node
/** Bounded §7.3 target probe against actual local D1, never an HTTP endpoint. */
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
import { hostSettings } from "./settings.mjs";

const root = import.meta.dirname;
const settings = hostSettings();
assert.equal(process.argv.length, 2, "This probe accepts no SQL or request arguments");

// All inputs are fixed test-only values. Capacity aggregates every actor in the
// same scope; policy, aggregate capacity and replay exclusion belong to the
// mutation statement. No read/worker decision/write sequence is used.
function reservation(scope, actor, request) {
  return `INSERT INTO __llmlang_m3_reservations (scope, actor, request_id, quantity)
    SELECT '${scope}', '${actor}', '${request}', 1
    FROM __llmlang_m3_capacities AS slot
    WHERE slot.scope = '${scope}' AND slot.enabled = 1
      AND COALESCE((SELECT SUM(quantity) FROM __llmlang_m3_reservations
        WHERE scope = slot.scope), 0) + 1 <= slot.capacity
      AND NOT EXISTS (SELECT 1 FROM __llmlang_m3_reservations
        WHERE scope = slot.scope AND actor = '${actor}' AND request_id = '${request}')
    RETURNING scope, actor, request_id, quantity`;
}
const statements = [
  `CREATE TABLE __llmlang_m3_capacities (
    scope TEXT PRIMARY KEY, capacity INTEGER NOT NULL CHECK(capacity >= 0),
    enabled INTEGER NOT NULL CHECK(enabled IN (0, 1)))`,
  `CREATE TABLE __llmlang_m3_reservations (
    scope TEXT NOT NULL, actor TEXT NOT NULL, request_id TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK(quantity = 1),
    PRIMARY KEY(scope, actor, request_id))`,
  `INSERT INTO __llmlang_m3_capacities (scope, capacity, enabled)
    VALUES ('allowed', 1, 1), ('blocked', 1, 0)`,
  reservation("allowed", "actor-one", "request-one"),
  "SELECT changes() AS changed",
  reservation("allowed", "actor-one", "request-one"),
  "SELECT changes() AS changed",
  reservation("allowed", "actor-two", "request-two"),
  "SELECT changes() AS changed",
  reservation("blocked", "actor-one", "request-one"),
  "SELECT changes() AS changed",
  `SELECT slot.scope, slot.capacity,
    COALESCE(SUM(reservation.quantity), 0) AS reserved
    FROM __llmlang_m3_capacities AS slot
    LEFT JOIN __llmlang_m3_reservations AS reservation ON reservation.scope = slot.scope
    GROUP BY slot.scope, slot.capacity ORDER BY slot.scope ASC`,
];

// Passing multiple SQL statements never establishes the application's batch
// transaction contract. Each mutation is independently conditional. Pinned
// Wrangler strips meta.changes from local JSON, so read SQLite changes()
// immediately after each mutation and verify RETURNING independently.
const output = execFileSync(process.execPath, [
  resolve(root, "node_modules/wrangler/bin/wrangler.js"),
  "d1", "execute", "llmlang-general-acceptance", "--local", "--config", "wrangler.jsonc",
  "--persist-to", settings.state, "--command", statements.join(";\n") + ";", "--json",
], {cwd: root, encoding: "utf8", timeout: 60000, maxBuffer: 1024 * 1024});
const results = JSON.parse(output);
assert.ok(Array.isArray(results), "Wrangler must return per-statement D1 results");
assert.equal(results.length, statements.length, "Every probe statement needs a result");
for (const result of results) assert.equal(result.success, true, "D1 statement failed");
const changes = [4, 6, 8, 10].map(index => {
  const rows = results[index].results;
  assert.ok(Array.isArray(rows) && rows.length === 1, "Each mutation needs its own changes() result");
  return rows[0].changed;
});
assert.deepEqual(changes, [1, 0, 0, 0],
  "Initial reservation must insert once; replay, full capacity and blocked policy must not insert");
assert.deepEqual(results[3].results, [
  {scope: "allowed", actor: "actor-one", request_id: "request-one", quantity: 1},
], "The initial mutation must return exactly its inserted row");
for (const index of [5, 7, 9]) assert.deepEqual(results[index].results, [],
  "Rejected conditional mutations must return no inserted rows");
assert.deepEqual(results[11].results, [
  {scope: "allowed", capacity: 1, reserved: 1},
  {scope: "blocked", capacity: 1, reserved: 0},
], "Confirmed reservations must remain within each scope's capacity");
console.log(JSON.stringify({
  evidence: "actual local D1 conditional INSERT SELECT: initial/replay/capacity/policy",
  changes,
  limitation: "single-statement target probe; no batch-transaction or concurrent booking claim",
}));
