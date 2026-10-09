import { spawn } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { immutableHostConfig } from "./acceptance-config.mjs";
import { hostSettings } from "./settings.mjs";

const root = import.meta.dirname;
const settings = hostSettings();
// Keep relative built module/assets paths unchanged by placing host config
// beside the original. The compiler output and original build stay untouched.
const acceptanceConfig = resolve(root, "dist/server/wrangler.acceptance.json");
const builtConfig = JSON.parse(readFileSync(resolve(root, "dist/server/wrangler.json"), "utf8"));
writeFileSync(acceptanceConfig, JSON.stringify(immutableHostConfig(builtConfig)) + "\n");
const child = spawn(process.execPath, [
  resolve(root, "node_modules/wrangler/bin/wrangler.js"),
  "dev", "--local", "--config", acceptanceConfig, "--ip", settings.ip,
  "--port", settings.port, "--persist-to", settings.state,
  "--var", `HOST_ALLOWED_ORIGIN:${settings.origin}`,
], {cwd: root, stdio: "inherit"});
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => child.kill(signal));
child.on("error", error => {console.error(error); process.exitCode = 1;});
child.on("exit", code => {process.exitCode = code ?? 1;});
