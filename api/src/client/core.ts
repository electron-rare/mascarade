/**
 * Client HTTP vers le core Python Mascarade.
 */

const CORE_URL = process.env.CORE_URL || "http://localhost:8100";

function configuredCoreApiKeys(): string[] {
  return (process.env.MASCARADE_API_KEY || "")
    .split(",")
    .map((key) => key.trim())
    .filter((key) => key.length >= 8);
}

export function getCoreAuthHeaders(): Record<string, string> {
  const [coreApiKey] = configuredCoreApiKeys();
  return coreApiKey ? { Authorization: `Bearer ${coreApiKey}` } : {};
}

export class CoreApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly coreBody?: unknown,
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
  system_prompt?: string;
  preferred_provider?: string | null;
  preferred_model?: string | null;
  preferred_role?: string | null;
  strategy?: string;
  temperature?: number;
  max_tokens?: number;
  builtin?: boolean;
}

export interface AgentTraceEvent {
  id: string;
  ts: string;
  run_id: string;
  mode: string;
  event_type: string;
  step: number;
  severity: "debug" | "info" | "warning" | "error" | "critical";
  agent_name?: string | null;
  from_agent?: string | null;
  to_agent?: string | null;
  prompt_excerpt?: string | null;
  content_excerpt?: string | null;
  provider?: string | null;
  model?: string | null;
  routing_role?: string | null;
  routing_provider?: string | null;
  routing_model?: string | null;
  token_usage?: { input_tokens?: number; output_tokens?: number } | null;
  error?: string | null;
  message: string;
}

export interface ClusterIdentity {
  node_id: string;
  role: string;
  label: string;
  base_url: string | null;
  providers: string[];
  provider_models: Record<string, string[]>;
  agents: number;
  cluster_enabled: boolean;
}

export interface ClusterPeerStatus {
  peer_id: string;
  role: string;
  base_url: string;
  ok: boolean;
  status: number;
  latency_ms: number;
  error?: string | null;
  remote_node_id?: string | null;
  remote_label?: string | null;
  providers?: string[] | null;
  provider_models?: Record<string, string[]> | null;
  agents?: number | null;
  last_seen?: string | null;
}

export interface ProviderFieldStatus {
  env: string;
  label: string;
  configured: boolean;
  hint: string;
  secret: boolean;
  classification?: string;
  criticality?: string;
  auth_modes?: string[];
}

export interface ProviderStatus {
  name: string;
  label: string;
  classification?: string;
  criticality?: string;
  required_when?: string;
  used_by?: string[];
  configured: boolean;
  active: boolean;
  fields: ProviderFieldStatus[];
  default_model: string | null;
  models: string[];
  enabled?: boolean;
  toggle_env?: string;
  auth_mode?: string;
  auth_mode_env?: string;
  auth_modes?: string[];
}

const REQUEST_TIMEOUT_MS = parseInt(process.env.CORE_TIMEOUT_MS || "30000", 10);

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...getCoreAuthHeaders(),
  };
  const res = await fetch(`${CORE_URL}${path}`, {
    headers,
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    ...options,
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

    const message =
      typeof parsedBody === "object" && parsedBody !== null
        ? ((parsedBody as Record<string, unknown>).error as string | undefined) ||
          ((parsedBody as Record<string, unknown>).detail as string | undefined) ||
          `Core API error ${res.status}`
        : text || `Core API error ${res.status}`;

    throw new CoreApiError(message, res.status, parsedBody);
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

  providersStatus() {
    return request<{ providers: ProviderStatus[] }>("/providers/status");
  },

  updateProviderKey(name: string, keys: Record<string, string>) {
    return request<{ status: string; active: boolean; message?: string }>(
      `/providers/${encodeURIComponent(name)}/key`,
      { method: "PUT", body: JSON.stringify({ keys }) },
    );
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
    preferred_model?: string;
    preferred_role?: string;
    strategy?: string;
    temperature?: number;
    max_tokens?: number;
  }) {
    return request<AgentInfo>("/agents", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  listAgents() {
    return request<{ agents: AgentInfo[] }>("/agents");
  },

  getAgent(name: string) {
    return request<AgentInfo>(`/agents/${encodeURIComponent(name)}`);
  },

  updateAgent(
    name: string,
    body: {
      description: string;
      system_prompt: string;
      preferred_provider?: string | null;
      preferred_model?: string | null;
      preferred_role?: string | null;
      strategy?: string;
      temperature?: number;
      max_tokens?: number;
    },
  ) {
    return request<AgentInfo>(`/agents/${encodeURIComponent(name)}`, {
      method: "PUT",
      body: JSON.stringify(body),
    });
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
    routing_overrides?: Record<
      string,
      {
        preferred_role?: string | null;
        preferred_provider?: string | null;
        preferred_model?: string | null;
      }
    >;
  }) {
    return request<{
      run_id: string;
      mode: string;
      results: {
        agent: string;
        step: number;
        content: string;
        model: string;
        provider: string;
        error?: string;
        remote?: boolean;
        selected_by?: string;
        peer_id?: string | null;
        node_id?: string | null;
        role?: string | null;
      }[];
    }>("/orchestrate", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  recentAgentTraces(params?: {
    limit?: number;
    run_id?: string;
    agent_name?: string;
    event_type?: string;
  }) {
    const search = new URLSearchParams();
    if (params?.limit) search.set("limit", String(params.limit));
    if (params?.run_id) search.set("run_id", params.run_id);
    if (params?.agent_name) search.set("agent_name", params.agent_name);
    if (params?.event_type) search.set("event_type", params.event_type);
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return request<{ events: AgentTraceEvent[]; count: number }>(`/agent-traces/recent${suffix}`);
  },

  runAgentTraces(runId: string, limit?: number) {
    const suffix = limit ? `?limit=${encodeURIComponent(String(limit))}` : "";
    return request<{ run_id: string; events: AgentTraceEvent[]; count: number }>(
      `/agent-traces/${encodeURIComponent(runId)}${suffix}`,
    );
  },

  clusterIdentity() {
    return request<ClusterIdentity>("/cluster/identity");
  },

  clusterPeers() {
    return request<{ node: ClusterIdentity; peers: ClusterPeerStatus[] }>("/cluster/peers");
  },

  clusterForwardSend(body: {
    peer_id?: string;
    preferred_role?: string;
    allow_local?: boolean;
    messages: { role: string; content: string }[];
    strategy?: string;
    provider?: string;
    model?: string;
    system?: string | null;
    temperature?: number;
    max_tokens?: number;
  }) {
    return request<{
      peer_id: string | null;
      selected_by: string;
      remote: boolean;
      latency_ms: number;
      node_id: string;
      role: string;
      content: string;
      model: string;
      provider: string;
      usage: { input_tokens: number; output_tokens: number };
    }>("/cluster/forward/send", {
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
    return fetch(`${CORE_URL}/comfyui/image?${params}`, {
      headers: getCoreAuthHeaders(),
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });
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
