#!/usr/bin/env node
/**
 * Real generated API/local D1 acceptance; Node native fetch, no database double.
 *
 * Protocol:
 *   node tests/general_host/check-d1.mjs seed [BASE_URL]
 *   Stop the built host, then restart it with the SAME Wrangler --persist-to dir.
 *   node tests/general_host/check-d1.mjs check-restart [BASE_URL]
 *
 * Default BASE_URL is http://127.0.0.1:8787. The trusted host allowedOrigin must
 * equal BASE_URL's origin. `seed` expects a fresh acceptance database and writes
 * fixed IDs; reuse of those IDs fails rather than silently accepting stale data.
 * `check-restart` performs reads only. A persisted history receipt records which
 * concurrent CAS candidate won, allowing the second process to check exact values
 * without a sidecar file or assuming a deterministic scheduling winner.
 *
 * Requests use closed {action,input} envelopes; inputs are nominal <action>Input
 * records (or {} when empty). Success is direct nominal record/Option/list JSON;
 * Int/Nat are canonical decimal STRINGS, Bool is a JSON boolean. The generated
 * pure title_preview function stores the first 120 Unicode code points.
 *
 * Passing seed alone is not restart evidence. This runner never starts, mocks,
 * resets or substitutes the host/database; CI owns process restart and storage.
 */
import assert from "node:assert/strict";

const HISTORY_ID = "restart-history";
const TASK_ID = "restart-task";
const RECEIPT_ID = "restart-cas-winner";
const INVALID_ID = "restart-invalid-task";
const PARAMS_ID = "restart-invalid-params";
const HISTORY_SOURCE = "Grüße 🌍 東京 " + "é".repeat(130);
const TASK_SOURCE = "Aufgabe 🧭 café 東京 " + "😀".repeat(90);
const CANDIDATES = [
  {branch: "A", title: "CAS Sieger A 🌍 " + "é".repeat(130), done: true, priority: "7"},
  {branch: "B", title: "CAS Sieger B 東京 " + "界".repeat(130), done: false, priority: "9"},
];
const MAX_NAT = 9007199254740991n;
const preview = text => Array.from(text).slice(0, 120).join("");

function exactObject(value, names, context) {
  assert.ok(value !== null && typeof value === "object" && !Array.isArray(value),
    `${context}: expected an object`);
  assert.deepEqual(Object.keys(value).sort(), [...names].sort(), `${context}: wrong field set`);
  return value;
}
function record(value, name, names, context) {
  exactObject(value, ["record", "fields"], context);
  assert.equal(value.record, name, `${context}: wrong nominal record`);
  return exactObject(value.fields, names, `${context}.fields`);
}
function canonicalNat(value, context) {
  assert.equal(typeof value, "string", `${context}: Nat must be a decimal string`);
  assert.match(value, /^(?:0|[1-9][0-9]*)$/, `${context}: noncanonical Nat`);
  assert.ok(value.length <= 16 && BigInt(value) <= MAX_NAT, `${context}: unsafe Nat`);
}
function some(value, action, fields, context) {
  exactObject(value, ["tag", "value"], context);
  assert.equal(value.tag, "Some", `${context}: expected existing record`);
  return record(value.value, `${action}Row`, fields, `${context}.value`);
}
function none(value, context) {
  assert.deepEqual(value, {tag: "None", value: null}, `${context}: unexpected persisted record`);
}
function taskFields(candidate) {
  return {id: TASK_ID, title: preview(candidate.title), revision: "1",
    done: candidate.done, priority: candidate.priority};
}
function validateTask(fields, expected, context) {
  exactObject(fields, ["id", "title", "revision", "done", "priority"], context);
  canonicalNat(fields.revision, `${context}.revision`);
  canonicalNat(fields.priority, `${context}.priority`);
  assert.equal(typeof fields.done, "boolean", `${context}: Bool must remain boolean`);
  assert.deepEqual(fields, expected, `${context}: stored task fields changed`);
}

async function main() {
  const [mode, address = "http://127.0.0.1:8787", ...extra] = process.argv.slice(2);
  assert.ok(["seed", "check-restart"].includes(mode) && extra.length === 0,
    "Usage: node tests/general_host/check-d1.mjs seed|check-restart [BASE_URL]");
  const base = new URL(address);
  assert.ok(["http:", "https:"].includes(base.protocol)
    && base.pathname === "/" && !base.search && !base.hash && !base.username && !base.password,
    "BASE_URL must be an HTTP(S) origin without a path, query or credentials");
  assert.ok(["127.0.0.1", "localhost", "[::1]"].includes(base.hostname),
    "This acceptance runner only writes to a loopback local host");
  const origin = base.origin;
  let requests = 0;
  async function send(app, envelope, expectedStatus, context, suppliedOrigin = origin) {
    const url = new URL(`/api/${app}`, base);
    let response;
    try {
      response = await fetch(url, {method: "POST", headers: {
        "Content-Type": "application/json", "Origin": suppliedOrigin,
      }, body: JSON.stringify(envelope), signal: AbortSignal.timeout(10000)});
    } catch (error) {
      throw new Error(`${context}: cannot reach real built host at ${url}: ${error.message}`);
    }
    requests++;
    assert.match(response.headers.get("content-type") ?? "", /^application\/json\b/i,
      `${context}: response is not JSON`);
    let body;
    try { body = await response.json(); }
    catch { throw new Error(`${context}: response was invalid JSON (HTTP ${response.status})`); }
    if (expectedStatus !== null)
      assert.equal(response.status, expectedStatus, `${context}: unexpected HTTP status`);
    return {status: response.status, body};
  }
  function envelope(action, fields) {
    return {action, input: {record: `${action}Input`, fields}};
  }
  async function invoke(app, action, fields, status = 200, context = `${app}.${action}`) {
    return send(app, envelope(action, fields), status, context);
  }
  async function fetchRow(app, id) {
    return (await invoke(app, "fetch", {selected_id: id}, 200, `${app}.fetch(${id})`)).body;
  }
  function rejection(result, label, context) {
    assert.deepEqual(result.body, {error: label}, `${context}: wrong rejection envelope`);
  }
  async function storedTask(candidate, context) {
    const fields = some(await fetchRow("tasks", TASK_ID), "fetch",
      ["id", "title", "revision", "done", "priority"], context);
    validateTask(fields, taskFields(candidate), context);
  }
  async function verifyPersistence() {
    const history = some(await fetchRow("history", HISTORY_ID), "fetch",
      ["id", "title", "revision"], "history persistence");
    canonicalNat(history.revision, "history persistence.revision");
    assert.deepEqual(history, {id: HISTORY_ID, title: preview(HISTORY_SOURCE), revision: "0"},
      "history persistence: Unicode/pure preview changed");
    const receipt = some(await fetchRow("history", RECEIPT_ID), "fetch",
      ["id", "title", "revision"], "winner receipt persistence");
    assert.equal(receipt.id, RECEIPT_ID, "winner receipt identity changed");
    assert.equal(receipt.revision, "0", "winner receipt revision changed");
    const winner = CANDIDATES.find(candidate => candidate.branch === receipt.title);
    assert.ok(winner, "winner receipt must name the actual A/B CAS winner");
    await storedTask(winner, "task persistence");
    none(await fetchRow("tasks", INVALID_ID), "invalid typed input persistence");
    none(await fetchRow("tasks", PARAMS_ID), "extra envelope persistence");
    return winner;
  }

  if (mode === "seed") {
    for (const [app, id] of [["history", HISTORY_ID], ["history", RECEIPT_ID],
      ["tasks", TASK_ID], ["tasks", INVALID_ID], ["tasks", PARAMS_ID]])
      none(await fetchRow(app, id), `fresh seed ${app}/${id}`);
    const history = record((await invoke("history", "save",
      {id: HISTORY_ID, title: HISTORY_SOURCE})).body, "saveRow", ["id", "title"], "history save");
    assert.deepEqual(history, {id: HISTORY_ID, title: preview(HISTORY_SOURCE)},
      "history save must execute the pure Unicode title transform");
    const task = record((await invoke("tasks", "save", {id: TASK_ID, title: TASK_SOURCE})).body,
      "saveRow", ["id", "title"], "task save");
    assert.deepEqual(task, {id: TASK_ID, title: preview(TASK_SOURCE)}, "task save changed Unicode");
    const initial = some(await fetchRow("tasks", TASK_ID), "fetch",
      ["id", "title", "revision", "done", "priority"], "task initial state");
    validateTask(initial, {id: TASK_ID, title: preview(TASK_SOURCE), revision: "0",
      done: false, priority: "0"}, "task initial state");

    const race = await Promise.all(CANDIDATES.map(candidate => invoke("tasks", "update", {
      id: TASK_ID, title: candidate.title, revision: "0",
      done: candidate.done, priority: candidate.priority,
    }, null, `CAS candidate ${candidate.branch}`)));
    assert.deepEqual(race.map(result => result.status).sort(), [200, 409],
      "same-revision concurrent CAS must have exactly one winner and one ConditionNotMet");
    const winningIndex = race.findIndex(result => result.status === 200);
    const winner = CANDIDATES[winningIndex];
    const winningFields = some(race[winningIndex].body, "update",
      ["id", "title", "revision", "done", "priority"], "CAS winner");
    validateTask(winningFields, taskFields(winner), "CAS winner");
    rejection(race[1 - winningIndex], "ConditionNotMet", "CAS loser");
    await storedTask(winner, "state after CAS race");

    rejection(await send("tasks", {action: "admin", input: {}}, 400, "unknown admin action"),
      "InvalidRequest", "unknown admin action");
    rejection(await invoke("tasks", "save", {id: INVALID_ID, title: "Must not persist", admin: true},
      422, "extra identity input"), "InvalidInput", "extra identity input");
    rejection(await send("tasks", {...envelope("save", {id: PARAMS_ID, title: "Must not persist"}),
      params: {admin: true}}, 400, "extra envelope params"), "InvalidRequest", "extra envelope params");
    const updateFields = {id: TASK_ID, title: "MUST NOT REPLACE WINNER", revision: "1",
      done: !winner.done, priority: "999"};
    rejection(await invoke("tasks", "update", {...updateFields, admin: true}, 422,
      "forged update identity"), "InvalidInput", "forged update identity");
    rejection(await invoke("tasks", "update", {...updateFields, priority: "9007199254740992"},
      422, "unsafe integer update"), "InvalidInput", "unsafe integer update");
    rejection(await send("tasks", envelope("update", updateFields), 403, "foreign origin",
      "https://evil.invalid"), "Forbidden", "foreign origin");
    await storedTask(winner, "invalid requests must not alter winner");
    none(await fetchRow("tasks", INVALID_ID), "invalid input must not create a row");
    none(await fetchRow("tasks", PARAMS_ID), "extra envelope must not create a row");

    const receipt = record((await invoke("history", "save", {id: RECEIPT_ID, title: winner.branch})).body,
      "saveRow", ["id", "title"], "winner receipt");
    assert.deepEqual(receipt, {id: RECEIPT_ID, title: winner.branch}, "winner receipt changed");
    await verifyPersistence();
    console.log(JSON.stringify({mode, origin, requests, winner: winner.branch,
      evidence: "actual built host/local D1: Unicode, pure transforms, CAS, invalid-input no-write"}));
  } else {
    const winner = await verifyPersistence();
    console.log(JSON.stringify({mode, origin, requests, winner: winner.branch,
      evidence: "read-only persisted records after host restart; caller owns same persist directory"}));
  }
}

try { await main(); }
catch (error) {
  console.error(`Local D1 acceptance failed: ${error.message}`);
  process.exitCode = 1;
}
