import { defineConfig, devices } from "@playwright/test";

const WEB_PORT = 4173;
const API_PORT = 3111;
const EXTERNAL_ONLY = process.env.PW_EXTERNAL_ONLY === "1";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  timeout: 30_000,

  reporter: process.env.CI
    ? [["github"], ["html", { open: "never", outputFolder: "playwright-report" }]]
    : [["list"], ["html", { open: "never" }]],

  projects: [
    {
      name: "web",
      testMatch: "tests/web/**/*.spec.ts",
      use: {
        ...devices["Desktop Chrome"],
        baseURL: `http://localhost:${WEB_PORT}`,
        screenshot: "only-on-failure",
        video: "retain-on-failure",
      },
    },
    {
      name: "api",
      testMatch: "tests/api/**/*.spec.ts",
      use: {
        baseURL: `http://localhost:${API_PORT}`,
      },
    },
    {
      name: "ops-saillant",
      testMatch: "tests/external/**/*.spec.ts",
      use: {
        ...devices["Desktop Chrome"],
        baseURL: "https://ops.saillant.cc",
        screenshot: "only-on-failure",
        video: "retain-on-failure",
      },
    },
  ],

  webServer: EXTERNAL_ONLY
    ? undefined
    : [
        {
          command: `npm run build --prefix ../web && npm run preview --prefix ../web -- --port ${WEB_PORT} --strictPort`,
          url: `http://localhost:${WEB_PORT}`,
          reuseExistingServer: !process.env.CI,
          timeout: 120_000,
        },
        {
          command: `node mock-api/server.mjs`,
          url: `http://localhost:${API_PORT}/health`,
          reuseExistingServer: false,
          timeout: 10_000,
        },
      ],
});
