import { Hono, type Context } from "hono";
import type { ContentfulStatusCode } from "hono/utils/http-status";
import { stream } from "hono/streaming";
import { getCoreAuthHeaders } from "../client/core.js";
import { handleCoreError } from "../middleware/error.js";
import {
  OllamaChatRequestSchema,
  type OllamaChatRequest,
  OllamaGenerateRequestSchema,
  type OllamaGenerateRequest,
} from "../validation/index.js";

const ollama = new Hono();
const CORE_URL = (process.env.CORE_URL || "http://localhost:8100").replace(/\/+$/, "");
const REQUEST_TIMEOUT_MS = parseInt(process.env.CORE_TIMEOUT_MS || "30000", 10);

function validationError(c: Context, error: unknown) {
  if (typeof error === "object" && error !== null && "issues" in error) {
    const issues = (error as { issues?: Array<{ path: (string | number)[]; message: string; code: string }> }).issues;
    return c.json(
      {
        error: "Validation failed",
        details: (issues || []).map((issue) => ({
          path: issue.path.join("."),
          message: issue.message,
          code: issue.code,
        })),
      },
      400,
    );
  }
  return c.json({ error: "Validation failed" }, 400);
}

async function parseJsonBody(c: Context) {
  try {
    return await c.req.json();
  } catch {
    return undefined;
  }
}

async function proxyCoreJson(
  c: Context,
  path: string,
  body?: unknown,
  options?: { streamBody?: boolean; contentType?: string },
) {
  const headers = new Headers({
    "Content-Type": "application/json",
    ...getCoreAuthHeaders(),
  });
  const authHeader = c.req.header("Authorization");
  if (authHeader) {
    headers.set("Authorization", authHeader);
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const upstream = await fetch(`${CORE_URL}${path}`, {
      method: body === undefined ? "GET" : "POST",
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });
    clearTimeout(timer);

    if (!upstream.ok) {
      const text = await upstream.text();
      let errorBody: unknown = text;
      try {
        errorBody = JSON.parse(text);
      } catch {
        // keep raw text
      }
      const status = (upstream.status >= 500 ? 502 : upstream.status) as ContentfulStatusCode;
      return c.json(
        {
          error:
            typeof errorBody === "object" && errorBody !== null
              ? (errorBody as Record<string, unknown>).error ||
                (errorBody as Record<string, unknown>).detail ||
                `Core API error ${upstream.status}`
              : text || `Core API error ${upstream.status}`,
          core_status: upstream.status,
        },
        status,
      );
    }

    if (options?.streamBody) {
      c.header("Content-Type", options.contentType || upstream.headers.get("content-type") || "application/x-ndjson");
      return stream(c, async (bodyStream) => {
        if (!upstream.body) {
          return;
        }
        const reader = upstream.body.getReader();
        const decoder = new TextDecoder();
        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            await bodyStream.write(decoder.decode(value, { stream: true }));
          }
        } finally {
          reader.releaseLock();
        }
      });
    }

    const payload = await upstream.json();
    return c.json(payload);
  } finally {
    clearTimeout(timer);
  }
}

ollama.get("/tags", async (c) => {
  try {
    return await proxyCoreJson(c, "/api/tags");
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

ollama.post("/chat", async (c) => {
  const raw = await parseJsonBody(c);
  if (raw === undefined) {
    return c.json({ error: "Validation failed", details: [{ message: "Request body is not valid JSON" }] }, 400);
  }
  const parsed = OllamaChatRequestSchema.safeParse(raw);
  if (!parsed.success) {
    return validationError(c, parsed.error);
  }

  const body: OllamaChatRequest = parsed.data;
  try {
    return await proxyCoreJson(c, "/api/chat", body, {
      streamBody: body.stream === true,
      contentType: "application/x-ndjson",
    });
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

ollama.post("/generate", async (c) => {
  const raw = await parseJsonBody(c);
  if (raw === undefined) {
    return c.json({ error: "Validation failed", details: [{ message: "Request body is not valid JSON" }] }, 400);
  }
  const parsed = OllamaGenerateRequestSchema.safeParse(raw);
  if (!parsed.success) {
    return validationError(c, parsed.error);
  }

  const body: OllamaGenerateRequest = parsed.data;
  try {
    return await proxyCoreJson(c, "/api/generate", body, {
      streamBody: body.stream === true,
      contentType: "application/x-ndjson",
    });
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

export { ollama };
