import { Hono } from "hono";
import { coreClient } from "../client/core.js";
import { handleCoreError } from "../middleware/error.js";
import { validate } from "../validation/index.js";
import {
  UserCreateRequestSchema,
  UserUpdateRequestSchema,
  ApiKeyCreateRequestSchema,
  type UserCreateRequest,
  type UserUpdateRequest,
  type ApiKeyCreateRequest,
} from "../validation/schemas.js";

const users = new Hono();

/** List all users (admin only) */
users.get("/", async (c) => {
  try {
    const result = await coreClient.listUsers();
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Create a new user (admin only) */
users.post("/", validate(UserCreateRequestSchema), async (c) => {
  try {
    const body = c.get("validated" as never) as UserCreateRequest;
    const result = await coreClient.createUser(body as any);
    return c.json(result, 201);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Get a user by ID (admin only) */
users.get("/:userId", async (c) => {
  try {
    const userId = parseInt(c.req.param("userId"), 10);
    if (isNaN(userId) || userId <= 0) {
      return c.json({ error: "Invalid user ID" }, 400);
    }
    const result = await coreClient.getUser(userId);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Update a user (admin only) */
users.put("/:userId", validate(UserUpdateRequestSchema), async (c) => {
  try {
    const raw = c.req.param("userId");
    if (!raw) return c.json({ error: "Missing user ID" }, 400);
    const userId = parseInt(raw, 10);
    if (isNaN(userId) || userId <= 0) {
      return c.json({ error: "Invalid user ID" }, 400);
    }
    const body = c.get("validated" as never) as UserUpdateRequest;
    const result = await coreClient.updateUser(userId, body as any);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Delete a user (admin only) */
users.delete("/:userId", async (c) => {
  try {
    const raw = c.req.param("userId");
    if (!raw) return c.json({ error: "Missing user ID" }, 400);
    const userId = parseInt(raw, 10);
    if (isNaN(userId) || userId <= 0) {
      return c.json({ error: "Invalid user ID" }, 400);
    }
    const result = await coreClient.deleteUser(userId);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Create API key for a user (admin only) */
users.post("/:userId/api-keys", validate(ApiKeyCreateRequestSchema), async (c) => {
  try {
    const raw = c.req.param("userId");
    if (!raw) return c.json({ error: "Missing user ID" }, 400);
    const userId = parseInt(raw, 10);
    if (isNaN(userId) || userId <= 0) {
      return c.json({ error: "Invalid user ID" }, 400);
    }
    const body = c.get("validated" as never) as ApiKeyCreateRequest;
    const result = await coreClient.createApiKey(userId, body as any);
    return c.json(result, 201);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** List API keys for a user (admin only) */
users.get("/:userId/api-keys", async (c) => {
  try {
    const userId = parseInt(c.req.param("userId"), 10);
    if (isNaN(userId) || userId <= 0) {
      return c.json({ error: "Invalid user ID" }, 400);
    }
    const result = await coreClient.listApiKeys(userId);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Revoke an API key (admin only) */
users.delete("/:userId/api-keys/:keyId", async (c) => {
  try {
    const userId = parseInt(c.req.param("userId"), 10);
    const keyId = parseInt(c.req.param("keyId"), 10);
    if (isNaN(userId) || userId <= 0 || isNaN(keyId) || keyId <= 0) {
      return c.json({ error: "Invalid user ID or key ID" }, 400);
    }
    const result = await coreClient.revokeApiKey(userId, keyId);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

export { users };
