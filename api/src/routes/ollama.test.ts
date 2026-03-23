import { Hono } from "hono";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ollama } from "./ollama.js";

const ORIGINAL_FETCH = global.fetch;

function makeApp() {
  const app = new Hono();
  app.route("/api", ollama);
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

describe("ollama compatibility routes", () => {
  it("proxies the Ollama tag catalog to the core", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          models: [{ name: "auto", model: "auto" }],
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const res = await makeApp().request("/api/tags");
    const payload = await res.json();

    expect(res.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("http://localhost:8100/api/tags");
    expect(payload).toEqual({ models: [{ name: "auto", model: "auto" }] });
  });

  it("defaults project scope when proxying /api/chat", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          model: "apple-coreml:qwen3.5-4b-onnx-q4f16",
          message: { role: "assistant", content: "ok" },
          done: true,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const res = await makeApp().request("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: "auto",
        stream: false,
        messages: [{ role: "user", content: "hello" }],
      }),
    });

    expect(res.status).toBe(200);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("http://localhost:8100/api/chat");
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(JSON.parse(String(init.body))).toEqual({
      project_id: "default",
      knowledge_scope: "project",
      model: "auto",
      stream: false,
      messages: [{ role: "user", content: "hello" }],
    });
  });

  it("defaults project scope when proxying /api/generate", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          model: "auto:cheap",
          response: "ok",
          done: true,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const res = await makeApp().request("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: "auto:cheap",
        stream: false,
        prompt: "hello",
      }),
    });

    expect(res.status).toBe(200);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("http://localhost:8100/api/generate");
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(JSON.parse(String(init.body))).toEqual({
      project_id: "default",
      knowledge_scope: "project",
      model: "auto:cheap",
      stream: false,
      prompt: "hello",
    });
  });
});
