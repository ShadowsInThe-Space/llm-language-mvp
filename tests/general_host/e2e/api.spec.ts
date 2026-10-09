import {randomUUID} from "node:crypto";
import {expect, test, type APIRequestContext, type TestInfo} from "@playwright/test";

function identifier(info: TestInfo, suffix: string): string {
  return `api-${Date.now()}-${info.project.name}-${suffix}-${randomUUID().slice(0, 6)}`;
}

function input(action: string, fields: Record<string, string | boolean>) {
  return {record: `${action}Input`, fields};
}

function call(request: APIRequestContext, app: string, origin: string,
              action: string, fields: Record<string, string | boolean>) {
  return request.post(`/api/${app}`, {headers: {origin}, data: {
    action, input: input(action, fields),
  }});
}

for (const app of ["history", "tasks"] as const) {
  test(`${app}: origin and injected authority/parameters are rejected without writes`,
    async ({request, baseURL}, info) => {
      const origin = new URL(baseURL ?? "http://127.0.0.1:8787").origin;
      const attacks = [
        {name: "origin", headers: {origin: "https://attacker.invalid"}, status: 403},
        {name: "absent-origin", headers: {}, status: 403},
        {name: "envelope-admin", headers: {origin}, status: 400,
          extra: {"identity.admin": true}},
        {name: "envelope-params", headers: {origin}, status: 400,
          extra: {params: {admin: true}}},
        {name: "field-admin", headers: {origin}, status: 422,
          fields: {"identity.admin": true}},
        {name: "field-authority", headers: {origin}, status: 422,
          fields: {authorization: "admin"}},
      ];
      for (const attack of attacks) {
        const id = identifier(info, attack.name);
        const response = await request.post(`/api/${app}`, {headers: attack.headers, data: {
          action: "save", input: {record: "saveInput", fields: {
            id, title: "This write must be rejected", ...attack.fields,
          }}, ...attack.extra,
        }});
        const rejectedBody = await response.text();
        const rejectedContext = JSON.stringify({app, project: info.project.name,
          attack: attack.name, id, phase: "rejected-save", status: response.status(),
          body: rejectedBody});
        expect(response.status(), rejectedContext).toBe(attack.status);
        const absent = await call(request, app, origin, "fetch", {selected_id: id});
        const absentBody = await absent.text();
        const absentContext = JSON.stringify({app, project: info.project.name,
          attack: attack.name, id, phase: "absence-fetch", status: absent.status(),
          body: absentBody});
        expect(absent.status(), absentContext).toBe(200);
        expect(JSON.parse(absentBody), absentContext).toEqual({tag: "None", value: null});
      }
    });
}

test("tasks: concurrent real D1 revision updates have one winner and one conflict",
  async ({request, baseURL}, info) => {
    const origin = new URL(baseURL ?? "http://127.0.0.1:8787").origin;
    const id = identifier(info, "cas");
    const saved = await call(request, "tasks", origin, "save", {id, title: "Original task"});
    expect(saved.status()).toBe(200);
    const candidates = [
      {id, title: `First line\n${"😀é漢x\n".repeat(200)}`, revision: "0", done: true, priority: "3"},
      {id, title: `Second line\n${"🧠n\u0303猫\n".repeat(200)}`, revision: "0", done: false, priority: "7"},
    ];
    const results = await Promise.all(candidates.map(fields =>
      call(request, "tasks", origin, "update", fields),
    ));
    expect(results.map(result => result.status()).sort((a, b) => a - b)).toEqual([200, 409]);
    const winner = results.findIndex(result => result.status() === 200);
    const loser = 1 - winner;
    expect(await results[loser].json()).toEqual({error: "ConditionNotMet"});
    const expected = {
      id, title: candidates[winner].title,
      revision: "1", done: candidates[winner].done, priority: candidates[winner].priority,
    };
    expect(await results[winner].json()).toEqual({tag: "Some", value: {
      record: "updateRow", fields: expected,
    }});
    const persisted = await call(request, "tasks", origin, "fetch", {selected_id: id});
    expect(persisted.status()).toBe(200);
    expect(await persisted.json()).toEqual({tag: "Some", value: {
      record: "fetchRow", fields: expected,
    }});
  });
