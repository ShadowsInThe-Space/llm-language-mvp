import { spawn } from "node:child_process";
import { resolve } from "node:path";
import { hostSettings } from "./settings.mjs";

const root = import.meta.dirname;
const settings = hostSettings();
const child = spawn(process.execPath, [
  resolve(root, "node_modules/wrangler/bin/wrangler.js"),
  "dev", "--local", "--config", "dist/server/wrangler.json", "--ip", settings.ip,
  "--port", settings.port, "--persist-to", settings.state,
  "--var", `HOST_ALLOWED_ORIGIN:${settings.origin}`,
], {cwd: root, stdio: "inherit"});
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => child.kill(signal));
child.on("error", error => {console.error(error); process.exitCode = 1;});
child.on("exit", code => {process.exitCode = code ?? 1;});
