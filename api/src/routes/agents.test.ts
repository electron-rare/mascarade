import { Hono } from "hono";
import { afterEach, describe, expect, it, vi } from "vitest";
import { coreClient } from "../client/core.js";
import { agents } from "./agents.js";

const ORIGINAL_FETCH = global.fetch;

function makeApp() {
  const app = new Hono();
  app.route("/v1/api/agents", agents);
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

describe("agents provider mutations", () => {
  it("publishes a unified agent catalog with Mascarade and CLI agents", async () => {
    vi.spyOn(coreClient, "listAgents").mockResolvedValue({
      agents: [
        {
          name: "agent-zero",
          description: "Generalist operator copilot",
          builtin: true,
          preferred_provider: "openai",
          preferred_model: "openai:gpt-4.1-mini",
          preferred_role: "generalist",
        },
        {
          name: "research-lab",
          description: "Long-form research assistant",
          builtin: false,
          preferred_provider: "google",
          preferred_model: "gemini-2.5-flash",
          preferred_role: "research",
        },
      ] as any,
    });
    vi.spyOn(coreClient, "cliAgentsStatus").mockResolvedValue({
      agents: {
        vibe: {
          available: true,
          binary: "vibe",
          provider: "Mistral (Devstral)",
          modes: ["fim", "chat"],
        },
        codex: {
          available: true,
          binary: "codex",
          provider: "OpenAI (o4-mini)",
          modes: ["review", "exec"],
        },
        "claude-code": {
          available: false,
          binary: "claude",
          provider: "Anthropic (Sonnet/Opus)",
          modes: ["interactive", "print"],
        },
      },
    });

    const res = await makeApp().request("/v1/api/agents/catalog");
    const payload = await res.json();

    expect(res.status).toBe(200);
    expect(payload).toEqual({
      object: "list",
      data: [
        {
          id: "agent:agent-zero",
          object: "agent",
          kind: "mascarade-agent",
          name: "agent-zero",
          label: "Agent Zero",
          description: "Generalist operator copilot",
          builtin: true,
          available: true,
          provider: "openai",
          model: "openai:gpt-4.1-mini",
          preferred_provider: "openai",
          preferred_model: "openai:gpt-4.1-mini",
          preferred_role: "generalist",
          binary: null,
          modes: ["run"],
        },
        {
          id: "agent:research-lab",
          object: "agent",
          kind: "mascarade-agent",
          name: "research-lab",
          label: "Research Lab",
          description: "Long-form research assistant",
          builtin: false,
          available: true,
          provider: "google",
          model: "gemini-2.5-flash",
          preferred_provider: "google",
          preferred_model: "gemini-2.5-flash",
          preferred_role: "research",
          binary: null,
          modes: ["run"],
        },
        {
          id: "cli-agent:codex",
          object: "agent",
          kind: "cli-agent",
          name: "codex",
          label: "Codex",
          description: "CLI agent via codex",
          builtin: false,
          available: true,
          provider: "OpenAI (o4-mini)",
          model: null,
          preferred_provider: null,
          preferred_model: null,
          preferred_role: null,
          binary: "codex",
          modes: ["exec", "review"],
        },
        {
          id: "cli-agent:vibe",
          object: "agent",
          kind: "cli-agent",
          name: "vibe",
          label: "Vibe",
          description: "CLI agent via vibe",
          builtin: false,
          available: true,
          provider: "Mistral (Devstral)",
          model: null,
          preferred_provider: null,
          preferred_model: null,
          preferred_role: null,
          binary: "vibe",
          modes: ["chat", "fim"],
        },
        {
          id: "cli-agent:claude-code",
          object: "agent",
          kind: "cli-agent",
          name: "claude-code",
          label: "Claude Code",
          description: "CLI agent via claude",
          builtin: false,
          available: false,
          provider: "Anthropic (Sonnet/Opus)",
          model: null,
          preferred_provider: null,
          preferred_model: null,
          preferred_role: null,
          binary: "claude",
          modes: ["interactive", "print"],
        },
      ],
    });
  });

  it("proxies provider saves through ops-agent and rehydrates provider status", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          status: "ok",
          updated_env: ["OLLAMA_ENABLED"],
          restarted_services: ["core"],
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    vi.spyOn(coreClient, "providersStatus").mockResolvedValue({
      providers: [{ name: "ollama", active: true, configured: true }] as any,
    });

    const res = await makeApp().request("/v1/api/agents/providers/ollama/key", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ keys: { OLLAMA_ENABLED: "true" } }),
    });

    expect(res.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("http://ops-agent:9200/providers/ollama");
    expect(await res.json()).toEqual({
      status: "ok",
      active: true,
      configured: true,
      updated_env: ["OLLAMA_ENABLED"],
      restarted_services: ["core"],
    });
  });

  it("proxies provider clears through ops-agent and returns the refreshed state", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          status: "ok",
          message: "Provider settings cleared",
          cleared_env: ["OLLAMA_BASE_URL", "OLLAMA_ENABLED"],
          restarted_services: ["core"],
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    vi.spyOn(coreClient, "providersStatus").mockResolvedValue({
      providers: [{ name: "ollama", active: false, configured: false }] as any,
    });

    const res = await makeApp().request("/v1/api/agents/providers/ollama/clear", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });

    expect(res.status).toBe(200);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("http://ops-agent:9200/providers/ollama/clear");
    expect(await res.json()).toEqual({
      status: "ok",
      active: false,
      configured: false,
      message: "Provider settings cleared",
      cleared_env: ["OLLAMA_BASE_URL", "OLLAMA_ENABLED"],
      restarted_services: ["core"],
    });
  });

  it("passes field-scoped provider clears through to ops-agent", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          status: "ok",
          message: "Provider settings cleared",
          cleared_env: ["OLLAMA_BASE_URL"],
          restarted_services: ["core"],
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    vi.spyOn(coreClient, "providersStatus").mockResolvedValue({
      providers: [{ name: "ollama", active: true, configured: true }] as any,
    });

    const res = await makeApp().request("/v1/api/agents/providers/ollama/clear", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fields: ["OLLAMA_BASE_URL"] }),
    });

    expect(res.status).toBe(200);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("http://ops-agent:9200/providers/ollama/clear");
    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({
      method: "POST",
      body: JSON.stringify({ fields: ["OLLAMA_BASE_URL"] }),
    });
    expect(await res.json()).toEqual({
      status: "ok",
      active: true,
      configured: true,
      message: "Provider settings cleared",
      cleared_env: ["OLLAMA_BASE_URL"],
      restarted_services: ["core"],
    });
  });

  it("requires project_id when running an agent", async () => {
    const res = await makeApp().request("/v1/api/agents/test-agent/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages: [{ role: "user", content: "hello" }],
      }),
    });

    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toBe("Validation failed");
  });

  it("forwards scoped agent runs to core", async () => {
    vi.spyOn(coreClient, "runAgent").mockResolvedValue({
      content: "ok",
      model: "gpt-4",
      provider: "openai",
      usage: { input_tokens: 1, output_tokens: 1, total_tokens: 2 },
    } as any);

    const res = await makeApp().request("/v1/api/agents/test-agent/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project_id: "project-alpha",
        knowledge_scope: "federated",
        federation_scope: ["project-alpha", "project-beta"],
        messages: [{ role: "user", content: "hello" }],
      }),
    });

    expect(res.status).toBe(200);
    expect(coreClient.runAgent).toHaveBeenCalledWith(
      "test-agent",
      [{ role: "user", content: "hello" }],
      {
        projectId: "project-alpha",
        knowledgeScope: "federated",
        federationScope: ["project-alpha", "project-beta"],
      },
    );
  });

  it("requires project_id when sending a routed prompt", async () => {
    const res = await makeApp().request("/v1/api/agents/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages: [{ role: "user", content: "hello" }],
      }),
    });

    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toBe("Validation failed");
  });

  it("forwards scoped routed prompts to core", async () => {
    vi.spyOn(coreClient, "send").mockResolvedValue({
      content: "ok",
      model: "gpt-4",
      provider: "openai",
      usage: { input_tokens: 1, output_tokens: 1, total_tokens: 2 },
    } as any);

    const res = await makeApp().request("/v1/api/agents/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project_id: "project-alpha",
        messages: [{ role: "user", content: "hello" }],
      }),
    });

    expect(res.status).toBe(200);
    expect(coreClient.send).toHaveBeenCalledWith({
      project_id: "project-alpha",
      knowledge_scope: "project",
      messages: [{ role: "user", content: "hello" }],
    });
  });

  it("requires project_id for knowledge-scribe run-and-push", async () => {
    const res = await makeApp().request("/v1/api/agents/knowledge-scribe/run-and-push", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages: [{ role: "user", content: "hello" }],
      }),
    });

    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toBe("Validation failed");
  });

  it("forwards scoped knowledge-scribe requests to core", async () => {
    vi.spyOn(coreClient, "knowledgeScribeRunAndPush").mockResolvedValue({
      content: "note",
      model: "gpt-4",
      provider: "openai",
      usage: { input_tokens: 1, output_tokens: 1, total_tokens: 2 },
      pushed_to_knowledge_base: true,
    } as any);

    const res = await makeApp().request("/v1/api/agents/knowledge-scribe/run-and-push", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project_id: "project-alpha",
        knowledge_scope: "project",
        messages: [{ role: "user", content: "hello" }],
        push_to: "memo-7",
      }),
    });

    expect(res.status).toBe(200);
    expect(coreClient.knowledgeScribeRunAndPush).toHaveBeenCalledWith({
      project_id: "project-alpha",
      knowledge_scope: "project",
      messages: [{ role: "user", content: "hello" }],
      push_to: "memo-7",
    });
  });
});
