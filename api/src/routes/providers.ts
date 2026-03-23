import { Hono } from "hono";
import { coreClient } from "../client/core.js";
import { handleCoreError } from "../middleware/error.js";
import {
  CodestralFIMRequestSchema,
  type CodestralFIMRequest,
} from "../validation/index.js";

const providers = new Hono();

providers.post("/codestral/fim", async (c) => {
  try {
    let raw: unknown;
    try {
      raw = await c.req.json();
    } catch {
      return c.json({ error: "Validation failed", details: [{ message: "Request body is not valid JSON" }] }, 400);
    }
    const parsed = CodestralFIMRequestSchema.safeParse(raw);
    if (!parsed.success) {
      return c.json({
        error: "Validation failed",
        details: parsed.error.issues.map((issue: { path: (string | number)[]; message: string; code: string }) => ({
          path: issue.path.join("."),
          message: issue.message,
          code: issue.code,
        })),
      }, 400);
    }

    const body = parsed.data as CodestralFIMRequest;
    const result = await coreClient.codestralFillInMiddle(body);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

export { providers };
