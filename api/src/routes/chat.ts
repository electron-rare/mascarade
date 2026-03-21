import { Hono, type Context } from "hono";
import type { ContentfulStatusCode } from "hono/utils/http-status";
import { getCoreAuthHeaders } from "../client/core.js";
import { handleCoreError } from "../middleware/error.js";
import { stream } from "hono/streaming";
import { ChatCompletionRequestSchema, type ChatCompletionRequest } from "../validation/index.js";

const chat = new Hono();
const CORE_URL = (process.env.CORE_URL || "http://localhost:8100").replace(/\/+$/, "");
const REQUEST_TIMEOUT_MS = parseInt(process.env.CORE_TIMEOUT_MS || "30000", 10);

/**
 * POST /completions
 * OpenAI-compatible chat completions endpoint with SSE streaming support
 * Mounted at /api/v1/chat, so full path is /api/v1/chat/completions
 */
chat.post("/completions", async (c: Context) => {
  try {
    let raw: unknown;
    try {
      raw = await c.req.json();
    } catch {
      return c.json({ error: "Validation failed", details: [{ message: "Request body is not valid JSON" }] }, 400);
    }
    const parsed = ChatCompletionRequestSchema.safeParse(raw);
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
    const body: ChatCompletionRequest = parsed.data;
    const isStreaming = body.stream === true;

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
      const upstream = await fetch(`${CORE_URL}/v1/chat/completions`, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      clearTimeout(timer);

      if (!upstream.ok) {
        const text = await upstream.text();
        let errorBody: unknown = text;
        try {
          errorBody = JSON.parse(text);
        } catch {
          // keep text
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

      if (isStreaming) {
        // Forward SSE stream from core to client
        return stream(c, async (stream) => {
          if (!upstream.body) {
            await stream.write("data: {\"error\": \"No response body from core\"}\n\n");
            return;
          }

          const reader = upstream.body.getReader();
          const decoder = new TextDecoder();

          try {
            while (true) {
              const { done, value } = await reader.read();
              if (done) break;

              const chunk = decoder.decode(value, { stream: true });
              await stream.write(chunk);
            }
          } catch (error) {
            await stream.write(`data: {"error": "Stream error: ${error}"}\n\n`);
          } finally {
            reader.releaseLock();
          }
        });
      } else {
        // Non-streaming: return JSON response
        const data = await upstream.json();
        return c.json(data);
      }
    } finally {
      clearTimeout(timer);
    }
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

export { chat };
