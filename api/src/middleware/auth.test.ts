import { Hono } from "hono";
import { afterEach, describe, expect, it } from "vitest";
import { authMiddleware } from "./auth.js";

const ORIGINAL_API_KEY = process.env.MASCARADE_API_KEY;
const ORIGINAL_ALLOW_PUBLIC_API = process.env.MASCARADE_ALLOW_PUBLIC_API;
const ORIGINAL_ADMIN_KEYS = process.env.MASCARADE_RBAC_ADMIN_KEYS;
const ORIGINAL_OPERATOR_KEYS = process.env.MASCARADE_RBAC_OPERATOR_KEYS;
const ORIGINAL_VIEWER_KEYS = process.env.MASCARADE_RBAC_VIEWER_KEYS;

function makeApp() {
  const app = new Hono();
  app.use("*", authMiddleware);
  app.get("/", (c) => c.json({ ok: true }));
  app.get("/api/users", (c) => c.json({ ok: true }));
  app.get("/api/ops/monitor", (c) => c.json({ ok: true }));
  app.post("/api/ops/monitor", (c) => c.json({ ok: true }));
  app.post("/api/agents/run", (c) => c.json({ ok: true }));
  return app;
}

afterEach(() => {
  if (ORIGINAL_API_KEY === undefined) {
    delete process.env.MASCARADE_API_KEY;
  } else {
    process.env.MASCARADE_API_KEY = ORIGINAL_API_KEY;
  }

  if (ORIGINAL_ALLOW_PUBLIC_API === undefined) {
    delete process.env.MASCARADE_ALLOW_PUBLIC_API;
  } else {
    process.env.MASCARADE_ALLOW_PUBLIC_API = ORIGINAL_ALLOW_PUBLIC_API;
  }

  if (ORIGINAL_ADMIN_KEYS === undefined) {
    delete process.env.MASCARADE_RBAC_ADMIN_KEYS;
  } else {
    process.env.MASCARADE_RBAC_ADMIN_KEYS = ORIGINAL_ADMIN_KEYS;
  }

  if (ORIGINAL_OPERATOR_KEYS === undefined) {
    delete process.env.MASCARADE_RBAC_OPERATOR_KEYS;
  } else {
    process.env.MASCARADE_RBAC_OPERATOR_KEYS = ORIGINAL_OPERATOR_KEYS;
  }

  if (ORIGINAL_VIEWER_KEYS === undefined) {
    delete process.env.MASCARADE_RBAC_VIEWER_KEYS;
  } else {
    process.env.MASCARADE_RBAC_VIEWER_KEYS = ORIGINAL_VIEWER_KEYS;
  }
});

describe("authMiddleware", () => {
  it("fails closed when auth is not configured", async () => {
    delete process.env.MASCARADE_API_KEY;
    delete process.env.MASCARADE_ALLOW_PUBLIC_API;

    const res = await makeApp().request("/");

    expect(res.status).toBe(503);
    expect(await res.json()).toEqual({ error: "Authentification non configuree" });
  });

  it("allows requests only when public API is explicitly enabled", async () => {
    delete process.env.MASCARADE_API_KEY;
    process.env.MASCARADE_ALLOW_PUBLIC_API = "true";

    const res = await makeApp().request("/");

    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ ok: true });
  });

  it("accepts any configured key from a CSV list", async () => {
    process.env.MASCARADE_API_KEY = "alpha-key-123456,beta-key-7654321";
    process.env.MASCARADE_RBAC_OPERATOR_KEYS = "beta-key-7654321";

    const res = await makeApp().request("/", {
      headers: { Authorization: "Bearer beta-key-7654321" },
    });

    expect(res.status).toBe(200);
  });

  it("accepts the API key from the mascarade_key cookie", async () => {
    process.env.MASCARADE_API_KEY = "alpha-key-123456";
    process.env.MASCARADE_RBAC_ADMIN_KEYS = "alpha-key-123456";

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

  it("rejects valid legacy tokens without an assigned role", async () => {
    process.env.MASCARADE_API_KEY = "alpha-key-123456";
    delete process.env.MASCARADE_RBAC_ADMIN_KEYS;
    delete process.env.MASCARADE_RBAC_OPERATOR_KEYS;
    delete process.env.MASCARADE_RBAC_VIEWER_KEYS;

    const res = await makeApp().request("/", {
      headers: { Authorization: "Bearer alpha-key-123456" },
    });

    expect(res.status).toBe(403);
    expect(await res.json()).toEqual({ error: "Role non assigne pour ce token" });
  });

  it("requires admin access for user management", async () => {
    process.env.MASCARADE_API_KEY = "operator-key-123456";
    process.env.MASCARADE_RBAC_OPERATOR_KEYS = "operator-key-123456";

    const res = await makeApp().request("/api/users", {
      headers: { Authorization: "Bearer operator-key-123456" },
    });

    expect(res.status).toBe(403);
    expect(await res.json()).toEqual({ error: "Permissions insuffisantes" });
  });

  it("allows viewers on read-only ops routes", async () => {
    process.env.MASCARADE_API_KEY = "viewer-key-123456";
    process.env.MASCARADE_RBAC_VIEWER_KEYS = "viewer-key-123456";

    const res = await makeApp().request("/api/ops/monitor", {
      headers: { Authorization: "Bearer viewer-key-123456" },
    });

    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ ok: true });
  });

  it("keeps write ops routes admin-only", async () => {
    process.env.MASCARADE_API_KEY = "operator-key-123456";
    process.env.MASCARADE_RBAC_OPERATOR_KEYS = "operator-key-123456";

    const res = await makeApp().request("/api/ops/monitor", {
      method: "POST",
      headers: { Authorization: "Bearer operator-key-123456" },
    });

    expect(res.status).toBe(403);
    expect(await res.json()).toEqual({ error: "Permissions insuffisantes" });
  });

  it("allows operators on standard write routes", async () => {
    process.env.MASCARADE_API_KEY = "operator-key-123456";
    process.env.MASCARADE_RBAC_OPERATOR_KEYS = "operator-key-123456";

    const res = await makeApp().request("/api/agents/run", {
      method: "POST",
      headers: { Authorization: "Bearer operator-key-123456" },
    });

    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ ok: true });
  });
});
