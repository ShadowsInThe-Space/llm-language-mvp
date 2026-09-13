import { readFileSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import { pathToFileURL } from "node:url";

// Execute emitted TypeScript unchanged. Only the D1-shaped transport is adapted;
// statement preparation, parameter binding and persistence use real SQLite.
const input = JSON.parse(readFileSync(0, "utf8"));
const modules = await Promise.all(input.modules.map((path) => import(pathToFileURL(path).href)));
let sqlite = new DatabaseSync(input.database);
if (input.initialize !== false) sqlite.exec(readFileSync(input.schema, "utf8"));

function databaseAdapter(fault = false) {
  return {
    prepare(sql) {
      if (fault) throw new Error("private database secret token=do-not-leak");
      return {
        bind(...parameters) {
          return {
            async first() {
              return sqlite.prepare(sql).get(...parameters) ?? null;
            },
            async all() {
              return { results: sqlite.prepare(sql).all(...parameters) };
            },
          };
        },
      };
    },
  };
}

async function request(operation) {
  const module = modules[operation.module ?? 0];
  const method = operation.method ?? "GET";
  const headers = new Headers();
  if (operation.origin !== null) {
    headers.set("origin", operation.origin ?? "https://app.example.test");
  }
  if (operation.contentType !== null) {
    headers.set("content-type", operation.contentType ?? "application/json");
  }
  if (operation.contentLength !== undefined) {
    headers.set("content-length", String(operation.contentLength));
  }
  if (operation.key !== undefined) headers.set("Idempotency-Key", operation.key);
  let body;
  if (method !== "GET" && method !== "HEAD") {
    const bytes = operation.rawBytes
      ? Uint8Array.from(operation.rawBytes)
      : new TextEncoder().encode(operation.rawBody ?? JSON.stringify(operation.body));
    body = operation.stream
      ? new ReadableStream({
          start(controller) {
            for (let start = 0; start < bytes.length; start += 137) {
              controller.enqueue(bytes.slice(start, start + 137));
            }
            controller.close();
          },
        })
      : bytes;
  }
  const nativeRequest = new Request(
    `https://app.example.test/api/store/${encodeURIComponent(operation.slot ?? "greeting")}`
      + (operation.query ? `?${operation.query}` : ""),
    { method, headers, body, duplex: "half" },
  );
  const response = await module.handleStore(
    nativeRequest,
    operation.databaseNull ? null : databaseAdapter(operation.databaseFault),
    module.appConfig,
    operation.slot ?? "greeting",
  );
  return {
    status: response.status,
    body: JSON.parse(await response.text()),
    headers: Object.fromEntries(response.headers),
  };
}

const results = [];
for (const operation of input.operations) {
  if (operation.kind === "reopen") {
    sqlite.close();
    sqlite = new DatabaseSync(input.database);
    results.push({ reopened: true });
  } else if (operation.kind === "parallel") {
    results.push(await Promise.all(operation.requests.map(request)));
  } else if (operation.kind === "sql") {
    sqlite.prepare(operation.sql).run(...operation.parameters);
    results.push({ sql: true });
  } else {
    results.push(await request(operation));
  }
}
const rows = sqlite.prepare(input.profile === "w2"
  ? "SELECT app_id, store_id, id, value FROM w2_entries ORDER BY sequence"
  : "SELECT app_id, store_id, value FROM w1_values ORDER BY app_id, store_id").all();
sqlite.close();
process.stdout.write(JSON.stringify({ results, rows, configs: modules.map((module) => module.appConfig) }));
