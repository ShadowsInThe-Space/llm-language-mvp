import { resolve } from "node:path";

/** Trusted local runner configuration; no values are accepted from requests. */
export function hostSettings(environment = process.env, root = import.meta.dirname) {
  const url = new URL(environment.LLMLANG_GENERAL_BASE_URL ?? "http://127.0.0.1:8787");
  if (url.protocol !== "http:" || !["127.0.0.1", "localhost"].includes(url.hostname)
    || url.username || url.password || url.pathname !== "/" || url.search || url.hash) {
    throw new Error("A local HTTP origin without credentials, path, query or fragment is required");
  }
  return {
    origin: url.origin,
    ip: "127.0.0.1",
    port: url.port || "80",
    state: resolve(root, environment.LLMLANG_D1_STATE ?? ".state"),
  };
}
