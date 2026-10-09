import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
import { hostSettings } from "./settings.mjs";

// Apply generated SQL once to fresh disposable state; requests never initialize it.
const root = import.meta.dirname;
const settings = hostSettings();
for (const name of ["history", "tasks"]) {
  execFileSync(process.execPath, [
    resolve(root, "node_modules/wrangler/bin/wrangler.js"),
    "d1", "execute", "llmlang-general-acceptance", "--local", "--config", "wrangler.jsonc",
    "--persist-to", settings.state, "--file", `generated/${name}/schema.sql`, "--yes",
  ], {cwd: root, stdio: "inherit", timeout: 60000});
}
