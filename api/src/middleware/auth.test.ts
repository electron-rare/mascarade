import { Hono } from "hono";
import { afterEach, describe, expect, it } from "vitest";
import { authMiddleware } from "./auth.js";

const ORIGINAL_API_KEY = process.env.MASCARADE_API_KEY;

function makeApp() {
  const app = new Hono();
  app.use("*", authMiddleware);
  app.get("/", (c) => c.json({ ok: true }));
  return app;
}

afterEach(() => {
  if (ORIGINAL_API_KEY === undefined) {
    delete process.env.MASCARADE_API_KEY;
  } else {
    process.env.MASCARADE_API_KEY = ORIGINAL_API_KEY;
  }
});

describe("authMiddleware", () => {
  it("allows requests when auth is disabled", async () => {
    delete process.env.MASCARADE_API_KEY;

    const res = await makeApp().request("/");

    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ ok: true });
  });

  it("accepts any configured key from a CSV list", async () => {
    process.env.MASCARADE_API_KEY = "alpha-key-123456,beta-key-7654321";

    const res = await makeApp().request("/", {
      headers: { Authorization: "Bearer beta-key-7654321" },
    });

    expect(res.status).toBe(200);
  });

  it("accepts the API key from the mascarade_key cookie", async () => {
    process.env.MASCARADE_API_KEY = "alpha-key-123456";

    const res = await makeApp().request("/", {
      headers: { Cookie: "mascarade_key=alpha-key-123456" },
    });

    expect(res.status).toBe(200);
  });

  it("rejects missing tokens when auth is enabled", async () => {
    process.env.MASCARADE_API_KEY = "alpha-key-123456";

    const res = await makeApp().request("/");

    expect(res.status).toBe(401);
    expect(await res.json()).toEqual({ error: "Token invalide ou manquant" });
  });

  it("rejects invalid tokens", async () => {
    process.env.MASCARADE_API_KEY = "alpha-key-123456,beta-key-7654321";

    const res = await makeApp().request("/", {
      headers: { Authorization: "Bearer wrong-key-999" },
    });

    expect(res.status).toBe(401);
    expect(await res.json()).toEqual({ error: "Token invalide ou manquant" });
  });
});
