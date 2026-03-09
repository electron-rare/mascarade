import { afterEach, describe, expect, it } from "vitest";
import {
  getGitHubDispatchAccessToken,
  normalizeGitHubDispatchAuthMode,
  normalizeGitHubPrivateKey,
} from "./githubDispatchAuth.js";

const ORIGINAL_ENV = { ...process.env };

afterEach(() => {
  process.env = { ...ORIGINAL_ENV };
});

describe("normalizeGitHubDispatchAuthMode", () => {
  it("defaults to token for unknown values", () => {
    expect(normalizeGitHubDispatchAuthMode("")).toBe("token");
    expect(normalizeGitHubDispatchAuthMode("weird")).toBe("token");
  });

  it("accepts app mode", () => {
    expect(normalizeGitHubDispatchAuthMode("app")).toBe("app");
  });
});

describe("normalizeGitHubPrivateKey", () => {
  it("restores escaped line breaks", () => {
    expect(normalizeGitHubPrivateKey("line1\\nline2")).toBe("line1\nline2");
  });
});

describe("getGitHubDispatchAccessToken", () => {
  it("returns the configured token in token mode", async () => {
    process.env.GITHUB_DISPATCH_AUTH_MODE = "token";
    process.env.KILL_LIFE_GITHUB_TOKEN = "ghp_test_token_123456789";

    await expect(getGitHubDispatchAccessToken(process.env)).resolves.toMatchObject({
      authMode: "token",
      token: "ghp_test_token_123456789",
      expiresAt: null,
    });
  });

  it("rejects app mode when required fields are missing", async () => {
    process.env.GITHUB_DISPATCH_AUTH_MODE = "app";
    process.env.GITHUB_APP_ID = "";
    process.env.GITHUB_APP_PRIVATE_KEY = "";
    process.env.GITHUB_APP_INSTALLATION_ID = "";

    await expect(getGitHubDispatchAccessToken(process.env)).rejects.toThrow(
      /Missing GITHUB_APP_ID, GITHUB_APP_PRIVATE_KEY, or GITHUB_APP_INSTALLATION_ID/,
    );
  });
});
