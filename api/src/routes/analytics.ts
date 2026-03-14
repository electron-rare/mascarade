import { Hono } from "hono";
import { getCoreAuthHeaders } from "../client/core.js";
import { handleCoreError } from "../middleware/error.js";

const analytics = new Hono();
const CORE_URL = process.env.CORE_URL || "http://localhost:8100";
const REQUEST_TIMEOUT_MS = parseInt(process.env.CORE_TIMEOUT_MS || "30000", 10);

analytics.get("/v1/benchmarks", async (c) => {
  try {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...getCoreAuthHeaders(),
    };

    const res = await fetch(`${CORE_URL}/v1/analytics/benchmarks`, {
      headers,
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });

    if (!res.ok) {
      const text = await res.text();
      let parsedBody: unknown = text;
      if (text) {
        try {
          parsedBody = JSON.parse(text);
        } catch {
          parsedBody = text;
        }
      }

      const errorResponse = handleCoreError({
        status: res.status,
        message: `Core API error ${res.status}`,
        coreBody: parsedBody,
      });
      return c.json(errorResponse.body, errorResponse.status);
    }

    const data = await res.json();
    return c.json(data);
  } catch (error) {
    const errorResponse = handleCoreError(error);
    return c.json(errorResponse.body, errorResponse.status);
  }
});

export { analytics };
