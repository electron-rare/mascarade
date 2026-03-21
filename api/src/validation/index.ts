import { z, type ZodIssue } from "zod";
import type { Context, Next } from "hono";

/**
 * Hono middleware that validates the JSON request body against a Zod schema.
 *
 * On success the parsed (and default-filled) data is stored under `c.get("validated")`.
 * On failure a 400 response is returned with structured error details.
 *
 * Usage:
 *   import { validate } from "../validation/index.js";
 *   import { SendRequestSchema } from "../validation/schemas.js";
 *
 *   agents.post("/send", validate(SendRequestSchema), async (c) => {
 *     const body = c.get("validated") as SendRequest;
 *     ...
 *   });
 */
export function validate<T extends z.ZodType>(schema: T) {
  return async (c: Context, next: Next) => {
    let raw: unknown;
    try {
      raw = await c.req.json();
    } catch {
      return c.json(
        {
          error: "Validation failed",
          details: [{ message: "Request body is not valid JSON" }],
        },
        400,
      );
    }

    const result = schema.safeParse(raw);
    if (!result.success) {
      return c.json(
        {
          error: "Validation failed",
          details: result.error.issues.map((issue: ZodIssue) => ({
            path: issue.path.join("."),
            message: issue.message,
            code: issue.code,
          })),
        },
        400,
      );
    }

    c.set("validated", result.data);
    return next();
  };
}

/**
 * Validate query-string parameters against a Zod schema.
 *
 * Collects all query params into a plain object (coercing `limit` etc. via
 * the schema's own transforms/coercions) and stores the result under
 * `c.get("validatedQuery")`.
 */
export function validateQuery<T extends z.ZodType>(schema: T) {
  return async (c: Context, next: Next) => {
    const raw: Record<string, string> = {};
    for (const [key, value] of Object.entries(c.req.query())) {
      raw[key] = value;
    }

    const result = schema.safeParse(raw);
    if (!result.success) {
      return c.json(
        {
          error: "Query validation failed",
          details: result.error.issues.map((issue: ZodIssue) => ({
            path: issue.path.join("."),
            message: issue.message,
            code: issue.code,
          })),
        },
        400,
      );
    }

    c.set("validatedQuery", result.data);
    return next();
  };
}

export * from "./schemas.js";
