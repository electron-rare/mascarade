import { Hono } from "hono";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as authLib from "../lib/auth.js";
import { auth } from "./auth.js";

const ORIGINAL_API_KEY = process.env.MASCARADE_API_KEY;

function makeApp() {
  const app = new Hono();
  app.route("/api/auth", auth);
  return app;
}

afterEach(() => {
  vi.restoreAllMocks();
  if (ORIGINAL_API_KEY === undefined) {
    delete process.env.MASCARADE_API_KEY;
  } else {
    process.env.MASCARADE_API_KEY = ORIGINAL_API_KEY;
  }
});

describe("auth routes", () => {
  it("creates a session cookie from a configured API key in the body", async () => {
    process.env.MASCARADE_API_KEY = "alpha-key-123456";

    const res = await makeApp().request("/api/auth/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key: "alpha-key-123456", persist: true }),
    });

    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ status: "ok" });
    const cookie = res.headers.get("set-cookie") || "";
    expect(cookie).toContain("mascarade_key=alpha-key-123456");
    expect(cookie).toContain("HttpOnly");
    expect(cookie).toContain("SameSite=Strict");
    expect(cookie).toContain("Max-Age=");
  });

  it("accepts a bearer token passed in the Authorization header", async () => {
    process.env.MASCARADE_API_KEY = "alpha-key-123456";

    const res = await makeApp().request("/api/auth/session", {
      method: "POST",
      headers: { Authorization: "Bearer alpha-key-123456" },
    });

    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ status: "ok" });
  });

  it("rejects invalid tokens when auth is configured", async () => {
    process.env.MASCARADE_API_KEY = "alpha-key-123456";
    vi.spyOn(authLib, "validateToken").mockResolvedValue(null);

    const res = await makeApp().request("/api/auth/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key: "wrong-key-999999" }),
    });

    expect(res.status).toBe(401);
    expect(await res.json()).toEqual({ error: "Token invalide ou manquant" });
  });

  it("fails closed when no auth backend is configured", async () => {
    delete process.env.MASCARADE_API_KEY;

    const res = await makeApp().request("/api/auth/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key: "alpha-key-123456" }),
    });

    expect(res.status).toBe(503);
    expect(await res.json()).toEqual({ error: "Authentification non configuree" });
  });

  it("clears the session cookie", async () => {
    const res = await makeApp().request("/api/auth/session", {
      method: "DELETE",
    });

    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ status: "ok" });
    const cookie = res.headers.get("set-cookie") || "";
    expect(cookie).toContain("mascarade_key=");
    expect(cookie).toContain("Max-Age=0");
  });
});