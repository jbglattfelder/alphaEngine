// Run inside mcr.microsoft.com/playwright:v1.56.1-noble (locally and in CI), so
// screenshots render with the same browser build and fonts everywhere.
const { defineConfig } = require("@playwright/test");

const PORT = 8123;

module.exports = defineConfig({
  testDir: ".",
  testMatch: /.*\.spec\.js/,
  timeout: 180_000,
  expect: {
    timeout: 20_000,
    toHaveScreenshot: { maxDiffPixels: 0, animations: "disabled", caret: "hide", scale: "css" },
  },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  snapshotPathTemplate: "{testDir}/__screenshots__/{testFilePath}/{arg}{ext}",
  use: {
    baseURL: `http://127.0.0.1:${PORT}/venue/`,
    browserName: "chromium",
    locale: "en-US",
    timezoneId: "Europe/Zurich",
    colorScheme: "dark",
    deviceScaleFactor: 1,
    viewport: { width: 1600, height: 960 },
  },
  webServer: {
    command: `node server.js`,
    url: `http://127.0.0.1:${PORT}/venue/`,
    reuseExistingServer: false,
    env: { PORT: String(PORT) },
  },
});
