import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.LLMLANG_GENERAL_BASE_URL ?? "http://127.0.0.1:8787";
export default defineConfig({
  testDir: "./e2e",
  timeout: 30000,
  expect: {timeout: 10000},
  globalTimeout: 240000,
  workers: 1,
  retries: 0,
  fullyParallel: false,
  reporter: [
    ["line"],
    ["json", {outputFile: "evidence/playwright.json"}],
    ["html", {outputFolder: "evidence/playwright-report", open: "never"}],
  ],
  use: {baseURL, trace: "retain-on-failure", screenshot: "only-on-failure"},
  webServer: process.env.LLMLANG_GENERAL_EXTERNAL_SERVER === "1" ? undefined : {
    command: "npm run start",
    url: baseURL,
    reuseExistingServer: false,
    timeout: 120000,
    gracefulShutdown: {signal: "SIGTERM", timeout: 10000},
    stdout: "pipe",
    stderr: "pipe",
  },
  projects: [
    {name: "chromium", use: {...devices["Desktop Chrome"]}},
    {name: "firefox", use: {...devices["Desktop Firefox"]}},
    {name: "webkit", use: {...devices["Desktop Safari"]}},
  ],
});
