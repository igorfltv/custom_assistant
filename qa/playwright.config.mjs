import { randomBytes } from "node:crypto";
import { fileURLToPath } from "node:url";
import { defineConfig } from "@playwright/test";

process.env.FORMA_QA_PASSWORD ||= randomBytes(24).toString("hex");
process.env.FORMA_QA_PORT ||= "24818";
const baseURL = "http://127.0.0.1:" + process.env.FORMA_QA_PORT;

export default defineConfig({
  testDir: ".",
  outputDir: "../.local/qa-browser",
  workers: 1,
  use: { baseURL, viewport: { width: 1440, height: 960 }, trace: "retain-on-failure" },
  webServer: {
    cwd: fileURLToPath(new URL("..", import.meta.url)),
    command: "uv run --project backend --locked python qa/server.py",
    url: baseURL + "/api/health",
    reuseExistingServer: false,
    gracefulShutdown: { signal: "SIGTERM", timeout: 5000 },
  },
});
