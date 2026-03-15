import { Hono } from "hono";
import { afterEach, describe, expect, it, vi } from "vitest";
import { coreClient } from "../client/core.js";
import { users } from "./users.js";

const ORIGINAL_FETCH = global.fetch;

function makeApp() {
  const app = new Hono();
  app.route("/api/users", users);
  return app;
}

afterEach(() => {
  vi.restoreAllMocks();
  if (ORIGINAL_FETCH === undefined) {
    // @ts-expect-error test cleanup for environments without fetch
    delete global.fetch;
  } else {
    global.fetch = ORIGINAL_FETCH;
  }
});

describe("user management", () => {
  it("lists all users", async () => {
    vi.spyOn(coreClient, "listUsers").mockResolvedValue({
      users: [
        {
          id: 1,
          username: "admin",
          email: "admin@example.com",
          role_id: 1,
          is_active: true,
          created_at: "2026-03-13T00:00:00Z",
          updated_at: "2026-03-13T00:00:00Z",
        },
      ],
    });

    const res = await makeApp().request("/api/users", {
      method: "GET",
    });

    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.users).toHaveLength(1);
    expect(data.users[0].username).toBe("admin");
  });

  it("creates a new user", async () => {
    vi.spyOn(coreClient, "createUser").mockResolvedValue({
      id: 2,
      username: "testuser",
      email: "test@example.com",
      role_id: 2,
      is_active: true,
      created_at: "2026-03-13T00:00:00Z",
      updated_at: "2026-03-13T00:00:00Z",
    });

    const res = await makeApp().request("/api/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: "testuser",
        email: "test@example.com",
        role_id: 2,
      }),
    });

    expect(res.status).toBe(201);
    const data = await res.json();
    expect(data.username).toBe("testuser");
    expect(data.email).toBe("test@example.com");
  });

  it("gets a user by ID", async () => {
    vi.spyOn(coreClient, "getUser").mockResolvedValue({
      id: 1,
      username: "admin",
      email: "admin@example.com",
      role_id: 1,
      is_active: true,
      created_at: "2026-03-13T00:00:00Z",
      updated_at: "2026-03-13T00:00:00Z",
    });

    const res = await makeApp().request("/api/users/1", {
      method: "GET",
    });

    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.username).toBe("admin");
  });

  it("rejects invalid user ID", async () => {
    const res = await makeApp().request("/api/users/invalid", {
      method: "GET",
    });

    expect(res.status).toBe(400);
    const data = await res.json();
    expect(data.error).toBe("Invalid user ID");
  });

  it("updates a user", async () => {
    vi.spyOn(coreClient, "updateUser").mockResolvedValue({
      id: 1,
      username: "admin",
      email: "newemail@example.com",
      role_id: 1,
      is_active: true,
      created_at: "2026-03-13T00:00:00Z",
      updated_at: "2026-03-13T01:00:00Z",
    });

    const res = await makeApp().request("/api/users/1", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: "newemail@example.com",
      }),
    });

    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.email).toBe("newemail@example.com");
  });

  it("deletes a user", async () => {
    vi.spyOn(coreClient, "deleteUser").mockResolvedValue({
      status: "ok",
    });

    const res = await makeApp().request("/api/users/1", {
      method: "DELETE",
    });

    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.status).toBe("ok");
  });
});

describe("api key management", () => {
  it("creates an API key for a user", async () => {
    vi.spyOn(coreClient, "createApiKey").mockResolvedValue({
      id: 1,
      key: "msk_test_1234567890abcdef",
      key_prefix: "msk_test_1234",
      name: "Test Key",
      created_at: "2026-03-13T00:00:00Z",
      expires_at: null,
    });

    const res = await makeApp().request("/api/users/1/api-keys", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: "Test Key",
      }),
    });

    expect(res.status).toBe(201);
    const data = await res.json();
    expect(data.key).toBe("msk_test_1234567890abcdef");
    expect(data.name).toBe("Test Key");
  });

  it("lists API keys for a user", async () => {
    vi.spyOn(coreClient, "listApiKeys").mockResolvedValue({
      api_keys: [
        {
          id: 1,
          key_prefix: "msk_test_1234",
          name: "Test Key",
          created_at: "2026-03-13T00:00:00Z",
          expires_at: null,
          last_used_at: null,
        },
      ],
    });

    const res = await makeApp().request("/api/users/1/api-keys", {
      method: "GET",
    });

    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.api_keys).toHaveLength(1);
    expect(data.api_keys[0].name).toBe("Test Key");
  });

  it("revokes an API key", async () => {
    vi.spyOn(coreClient, "revokeApiKey").mockResolvedValue({
      status: "ok",
    });

    const res = await makeApp().request("/api/users/1/api-keys/1", {
      method: "DELETE",
    });

    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.status).toBe("ok");
  });

  it("rejects invalid user ID in API key routes", async () => {
    const res = await makeApp().request("/api/users/invalid/api-keys", {
      method: "GET",
    });

    expect(res.status).toBe(400);
    const data = await res.json();
    expect(data.error).toBe("Invalid user ID");
  });

  it("rejects invalid key ID when revoking", async () => {
    const res = await makeApp().request("/api/users/1/api-keys/invalid", {
      method: "DELETE",
    });

    expect(res.status).toBe(400);
    const data = await res.json();
    expect(data.error).toBe("Invalid user ID or key ID");
  });
});
