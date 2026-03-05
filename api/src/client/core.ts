/**
 * Client HTTP vers le core Python Mascarade.
 */

const CORE_URL = process.env.CORE_URL || "http://localhost:8100";
const CORE_API_KEY = process.env.MASCARADE_API_KEY || "";

export class CoreApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "CoreApiError";
  }
}

export interface LLMResponse {
  content: string;
  model: string;
  provider: string;
  usage: { input_tokens: number; output_tokens: number };
}

export interface AgentInfo {
  name: string;
  description: string;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (CORE_API_KEY) {
    headers["Authorization"] = `Bearer ${CORE_API_KEY}`;
  }
  const res = await fetch(`${CORE_URL}${path}`, {
    headers,
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new CoreApiError(`Core API error ${res.status}: ${text}`, res.status);
  }
  return res.json() as Promise<T>;
}

export const coreClient = {
  health() {
    return request<{ status: string; providers: string[]; agents: number }>("/health");
  },

  send(body: {
    messages: { role: string; content: string }[];
    strategy?: string;
    provider?: string;
    model?: string;
    system?: string;
    temperature?: number;
    max_tokens?: number;
  }) {
    return request<LLMResponse>("/send", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  listProviders() {
    return request<{ providers: string[] }>("/providers");
  },

  getMetrics() {
    return request<Record<string, unknown>>("/metrics");
  },

  getProviderMetrics(provider: string) {
    return request<Record<string, unknown>>(`/metrics/${encodeURIComponent(provider)}`);
  },

  resetMetrics() {
    return request<{ status: string }>("/metrics/reset", { method: "POST" });
  },

  getCacheStats() {
    return request<Record<string, unknown>>("/cache/stats");
  },

  resetCache() {
    return request<{ status: string }>("/cache/reset", { method: "POST" });
  },

  getLoadBalancerStats() {
    return request<Record<string, unknown>>("/load-balancer/stats");
  },

  resetLoadBalancer() {
    return request<{ status: string }>("/load-balancer/reset", { method: "POST" });
  },

  getFallbackStats() {
    return request<Record<string, unknown>>("/fallback/stats");
  },

  resetFallback() {
    return request<{ status: string }>("/fallback/reset", { method: "POST" });
  },

  createAgent(body: {
    name: string;
    description: string;
    system_prompt: string;
    preferred_provider?: string;
    strategy?: string;
  }) {
    return request<AgentInfo>("/agents", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  listAgents() {
    return request<{ agents: AgentInfo[] }>("/agents");
  },

  runAgent(name: string, messages: { role: string; content: string }[]) {
    return request<LLMResponse>(`/agents/${encodeURIComponent(name)}/run`, {
      method: "POST",
      body: JSON.stringify({ messages }),
    });
  },

  orchestrate(body: {
    agent_names: string[];
    prompt: string;
    mode?: string;
  }) {
    return request<{
      results: {
        agent: string;
        step: number;
        content: string;
        model: string;
        provider: string;
      }[];
    }>("/orchestrate", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  // --- Notion ---

  notionSearch(query: string) {
    return request<{ results: { id: string; title: string; url: string }[] }>(
      `/notion/search?q=${encodeURIComponent(query)}`,
    );
  },

  notionReadPage(pageId: string) {
    return request<{ page_id: string; content: string }>(
      `/notion/pages/${encodeURIComponent(pageId)}`,
    );
  },

  notionAppend(pageId: string, content: string) {
    return request<{ status: string; page_id: string }>(
      `/notion/pages/${encodeURIComponent(pageId)}/append`,
      { method: "POST", body: JSON.stringify({ content }) },
    );
  },

  notionCreatePage(body: { parent_id: string; title: string; content?: string }) {
    return request<{ page_id: string }>("/notion/pages", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  // --- ComfyUI ---

  comfyuiStatus() {
    return request<Record<string, unknown>>("/comfyui/status");
  },

  comfyuiQueue() {
    return request<Record<string, unknown>>("/comfyui/queue");
  },

  comfyuiModels(modelType: string = "checkpoints") {
    return request<{ models: string[]; type: string }>(
      `/comfyui/models/${encodeURIComponent(modelType)}`,
    );
  },

  comfyuiGenerate(body: {
    prompt: string;
    negative_prompt?: string;
    checkpoint?: string;
    width?: number;
    height?: number;
    steps?: number;
    cfg?: number;
    seed?: number;
  }) {
    return request<{
      prompt_id: string;
      images: { filename: string; subfolder: string; type: string }[];
      status: string;
    }>("/comfyui/generate", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  comfyuiQueueWorkflow(workflow: Record<string, unknown>) {
    return request<{ prompt_id: string }>("/comfyui/workflow", {
      method: "POST",
      body: JSON.stringify({ workflow }),
    });
  },

  comfyuiHistory(promptId: string) {
    return request<Record<string, unknown>>(`/comfyui/history/${encodeURIComponent(promptId)}`);
  },

  comfyuiInterrupt() {
    return request<{ status: string }>("/comfyui/interrupt", {
      method: "POST",
    });
  },

  comfyuiImage(filename: string, subfolder?: string, type?: string) {
    const params = new URLSearchParams({ filename });
    if (subfolder) params.set("subfolder", subfolder);
    if (type) params.set("type", type);
    const headers: Record<string, string> = {};
    if (CORE_API_KEY) {
      headers["Authorization"] = `Bearer ${CORE_API_KEY}`;
    }
    return fetch(`${CORE_URL}/comfyui/image?${params}`, { headers });
  },

  notionScribeRunAndPush(body: {
    messages: { role: string; content: string }[];
    push_to?: string;
  }) {
    return request<LLMResponse & { pushed_to_notion: boolean; notion_page_id?: string }>(
      "/agents/notion-scribe/run-and-push",
      { method: "POST", body: JSON.stringify(body) },
    );
  },
};
