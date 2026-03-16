/**
 * Client HTTP vers le core Python Mascarade.
 */

const CORE_URL = process.env.CORE_URL || "http://localhost:8100";

function configuredCoreApiKeys(): string[] {
  return (process.env.MASCARADE_API_KEY || "")
    .split(",")
    .map((key) => key.trim())
    .filter((key) => key.length >= 16);
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
  routing_policy?: string | null;
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
  routing_policy?: string | null;
  routing_selected_by?: string | null;
  routing_transport?: string | null;
  routing_latency_ms?: number | null;
  mcp_server?: string | null;
  mcp_tool?: string | null;
  mcp_status?: string | null;
  mcp_transport?: string | null;
  mcp_latency_ms?: number | null;
  mcp_protocol_version?: string | null;
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

export interface AgentTemplate {
  id: string;
  name: string;
  description: string;
  system_prompt: string;
  preferred_provider?: string | null;
  preferred_model?: string | null;
  preferred_role?: string | null;
  strategy?: string;
  temperature?: number;
  max_tokens?: number;
  category?: string;
  tags?: string[];
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
    routing_policy?: string;
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

  providerHealth() {
    return request<Record<string, unknown>>("/health/providers");
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

  getAgentMetrics(name: string) {
    return request<Record<string, unknown>>(`/agents/${encodeURIComponent(name)}/metrics`);
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
    routing_policy?: string;
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
      routing_policy?: string;
      temperature?: number;
      max_tokens?: number;
    },
  ) {
    return request<AgentInfo>(`/agents/${encodeURIComponent(name)}`, {
      method: "PUT",
      body: JSON.stringify(body),
    });
  },

  deleteAgent(name: string) {
    return request<{ status: string; message?: string }>(`/agents/${encodeURIComponent(name)}`, {
      method: "DELETE",
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
        routing_policy?: string | null;
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
        transport?: string | null;
        latency_ms?: number | null;
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
    routing_policy?: string;
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

  // --- Knowledge Base ---

  knowledgeBaseSearch(query: string) {
    return request<{ results: { id: string; title: string; url: string }[] }>(
      `/knowledge-base/search?q=${encodeURIComponent(query)}`,
    );
  },

  knowledgeBaseReadPage(pageId: string) {
    return request<{ page_id: string; content: string }>(
      `/knowledge-base/pages/${encodeURIComponent(pageId)}`,
    );
  },

  knowledgeBaseAppend(pageId: string, content: string) {
    return request<{ status: string; page_id: string }>(
      `/knowledge-base/pages/${encodeURIComponent(pageId)}/append`,
      { method: "POST", body: JSON.stringify({ content }) },
    );
  },

  knowledgeBaseCreatePage(body: { parent_id: string; title: string; content?: string }) {
    return request<{ page_id: string }>("/knowledge-base/pages", {
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

  knowledgeScribeRunAndPush(body: {
    messages: { role: string; content: string }[];
    push_to?: string;
    run_id?: string;
  }) {
    return request<
      LLMResponse & {
        pushed_to_knowledge_base: boolean;
        knowledge_base_page_id?: string;
        knowledge_base_provider?: string;
        knowledge_base_provider_label?: string;
        run_id?: string;
      }
    >(
      "/agents/knowledge-scribe/run-and-push",
      { method: "POST", body: JSON.stringify(body) },
    );
  },

  githubDispatchListWorkflows() {
    return request<{
      ok: boolean;
      repo?: string;
      workflows?: { file: string; label: string; description: string }[];
    }>("/mcp/github-dispatch/workflows");
  },

  githubDispatchDispatch(body: {
    workflow_file: string;
    ref?: string;
    inputs?: Record<string, string | number | boolean>;
    run_id?: string;
  }) {
    return request<{
      ok: boolean;
      workflow_file: string;
      dispatch_id: string;
      status: string;
      auth_mode?: string;
    }>("/mcp/github-dispatch/dispatch", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  githubDispatchStatus(body: { dispatch_id: string; run_id?: string }) {
    return request<{
      ok: boolean;
      dispatch_id: string;
      status: string;
      conclusion?: string | null;
    }>("/mcp/github-dispatch/status", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  freecadRuntimeInfo(run_id?: string) {
    const search = run_id ? `?run_id=${encodeURIComponent(run_id)}` : "";
    return request<{
      ok: boolean;
      runtime: string;
      version: string;
      workspace_root?: string;
      run_id: string;
    }>(`/mcp/freecad/runtime${search}`);
  },

  freecadCreateDocument(body: {
    output_path: string;
    name?: string;
    primitive?: "box";
    length?: number;
    width?: number;
    height?: number;
    run_id?: string;
  }) {
    return request<{
      ok: boolean;
      document_path: string;
      document_name?: string;
      object_count?: number;
      size_bytes?: number;
      run_id: string;
    }>("/mcp/freecad/documents", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  freecadExportDocument(body: {
    document_path: string;
    output_path: string;
    run_id?: string;
  }) {
    return request<{
      ok: boolean;
      output_path: string;
      size_bytes?: number;
      run_id: string;
    }>("/mcp/freecad/export", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  freecadRunScript(body: { script: string; output_path?: string; run_id?: string }) {
    return request<{
      ok: boolean;
      output_path?: string;
      result?: Record<string, unknown>;
      run_id: string;
    }>("/mcp/freecad/script", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  openscadRuntimeInfo(run_id?: string) {
    const search = run_id ? `?run_id=${encodeURIComponent(run_id)}` : "";
    return request<{
      ok: boolean;
      runtime: string;
      version: string;
      workspace_root?: string;
      run_id: string;
    }>(`/mcp/openscad/runtime${search}`);
  },

  openscadValidateModel(body: { source: string; run_id?: string }) {
    return request<{
      ok: boolean;
      artifact_size_bytes?: number;
      run_id: string;
    }>("/mcp/openscad/validate", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  openscadRenderModel(body: { source: string; output_path: string; run_id?: string }) {
    return request<{
      ok: boolean;
      output_path: string;
      size_bytes?: number;
      run_id: string;
    }>("/mcp/openscad/render", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  openscadExportModel(body: { source: string; output_path: string; run_id?: string }) {
    return request<{
      ok: boolean;
      output_path: string;
      size_bytes?: number;
      run_id: string;
    }>("/mcp/openscad/export", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  kicadGenerateSchematic(body: {
    requirements: string;
    library?: string;
    run_id?: string;
  }) {
    return request<{
      ok: boolean;
      schematic_path?: string;
      component_count?: number;
      net_count?: number;
      run_id: string;
    }>("/mcp/kicad/schematic", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  kicadOptimizeLayout(body: {
    schematic_data: Record<string, unknown>;
    constraints?: Record<string, unknown>;
    run_id?: string;
  }) {
    return request<{
      ok: boolean;
      layout_path?: string;
      optimization_score?: number;
      run_id: string;
    }>("/mcp/kicad/layout", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  kicadCreateFootprint(body: {
    component_description: string;
    datasheet_url?: string;
    run_id?: string;
  }) {
    return request<{
      ok: boolean;
      footprint_path?: string;
      pad_count?: number;
      run_id: string;
    }>("/mcp/kicad/footprint", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  kicadCheckDRC(body: {
    layout_data: Record<string, unknown>;
    rules?: Record<string, unknown>;
    run_id?: string;
  }) {
    return request<{
      ok: boolean;
      violations?: Array<Record<string, unknown>>;
      violation_count?: number;
      run_id: string;
    }>("/mcp/kicad/drc", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  kicadExportManufacturing(body: {
    layout_data: Record<string, unknown>;
    bom_data?: Record<string, unknown>;
    format?: string;
    run_id?: string;
  }) {
    return request<{
      ok: boolean;
      output_files?: string[];
      format?: string;
      run_id: string;
    }>("/mcp/kicad/manufacturing", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  industrialMcpServers() {
    return request<{
      items: Array<{
        key: string;
        transport: string;
        timeout_s: number;
        cwd?: string;
        command?: string[];
        launcher?: string;
      }>;
    }>("/mcp/industrial/servers");
  },

  industrialMcpRuntime(serverKey: string) {
    return request<{
      ok: boolean;
      server_key: string;
      protocol_version: string;
      server_info: Record<string, unknown>;
      tool_count: number;
      resource_count: number;
      prompt_count: number;
      tools: Record<string, unknown>[];
      resources: Record<string, unknown>[];
      prompts: Record<string, unknown>[];
      health?: Record<string, unknown>;
      contract?: Record<string, unknown>;
    }>(`/mcp/industrial/${encodeURIComponent(serverKey)}/runtime`);
  },

  industrialMcpResource(serverKey: string, uri: string) {
    return request<{
      uri: string;
      payload: Record<string, unknown>;
      raw_text: string;
      mime_type?: string;
    }>(`/mcp/industrial/${encodeURIComponent(serverKey)}/resource?uri=${encodeURIComponent(uri)}`);
  },

  industrialMcpPlatform() {
    return request<{
      servers: Array<{
        key: string;
        transport: string;
        timeout_s: number;
        cwd?: string;
        command?: string[];
        launcher?: string;
        ok: boolean;
        runtime_ok: boolean;
        error?: string;
        protocol_version?: string;
        tool_count?: number;
        resource_count?: number;
        prompt_count?: number;
        health?: Record<string, unknown>;
        contract?: Record<string, unknown>;
      }>;
      summary: Record<string, unknown>;
      topology: Record<string, unknown>;
      vendor_contracts: Record<string, unknown>;
    }>("/mcp/industrial/platform");
  },

  // --- Fine-tuning ---

  finetunePipeline(body: { task: string; domain?: string; max_model_size_gb?: number }) {
    return request<{ status: string; task_id?: string }>("/finetune/pipeline", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  finetuneStack() {
    return request<{ stack: string[]; recommended: string }>("/finetune/stack");
  },

  deleteFinetuneLog(name: string) {
    return request<{ status: string }>(`/finetune/logs/${encodeURIComponent(name)}`, {
      method: "DELETE",
    });
  },

  industrialMcpTool(
    serverKey: string,
    toolName: string,
    body: { arguments?: Record<string, unknown>; run_id?: string },
  ) {
    return request<{
      ok: boolean;
      run_id: string;
      server_key: string;
      tool_name: string;
      protocol_version?: string | null;
      server_name?: string | null;
      message: string;
      payload: Record<string, unknown>;
    }>(`/mcp/industrial/${encodeURIComponent(serverKey)}/tools/${encodeURIComponent(toolName)}`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  // --- Authentication ---

  verifyToken(token: string) {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    };
    return fetch(`${CORE_URL}/auth/me`, {
      headers,
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    }).then(async (res) => {
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
      return res.json() as Promise<{
        id: number;
        username: string;
        email: string;
        role_id: number;
        is_active: boolean;
        rate_limits?: {
          requests_per_minute?: number | null;
          requests_per_hour?: number | null;
          requests_per_day?: number | null;
          tokens_per_day?: number | null;
        } | null;
      }>;
    });
  },

  // --- User Management ---

  listUsers() {
    return request<{ users: Array<{ id: number; username: string; email: string; role_id: number; is_active: boolean; created_at: string; updated_at: string }> }>("/users");
  },

  createUser(body: { username: string; email: string; role_id: number }) {
    return request<{ id: number; username: string; email: string; role_id: number; is_active: boolean; created_at: string; updated_at: string }>("/users", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  getUser(userId: number) {
    return request<{ id: number; username: string; email: string; role_id: number; is_active: boolean; created_at: string; updated_at: string }>(`/users/${userId}`);
  },

  updateUser(userId: number, body: { username?: string; email?: string; role_id?: number; is_active?: boolean }) {
    return request<{ id: number; username: string; email: string; role_id: number; is_active: boolean; created_at: string; updated_at: string }>(`/users/${userId}`, {
      method: "PUT",
      body: JSON.stringify(body),
    });
  },

  // --- Qdrant ---

  qdrantHealth() {
    return request<Record<string, unknown>>("/qdrant/health");
  },

  qdrantListCollections() {
    return request<{ collections: Array<{ name: string }> }>("/qdrant/collections");
  },

  qdrantGetCollection(collectionName: string) {
    return request<Record<string, unknown>>(
      `/qdrant/collections/${encodeURIComponent(collectionName)}`,
    );
  },

  qdrantCreateCollection(
    collectionName: string,
    body: {
      vector_size: number;
      distance?: string;
      on_disk_payload?: boolean;
    },
  ) {
    return request<Record<string, unknown>>(
      `/qdrant/collections/${encodeURIComponent(collectionName)}`,
      { method: "PUT", body: JSON.stringify(body) },
    );
  },

  qdrantDeleteCollection(collectionName: string) {
    return request<Record<string, unknown>>(
      `/qdrant/collections/${encodeURIComponent(collectionName)}`,
      { method: "DELETE" },
    );
  },

  qdrantUpsertPoints(
    collectionName: string,
    body: {
      points: Array<{
        id: string | number;
        vector: number[];
        payload?: Record<string, unknown>;
      }>;
      wait?: boolean;
    },
  ) {
    return request<Record<string, unknown>>(
      `/qdrant/collections/${encodeURIComponent(collectionName)}/points`,
      { method: "POST", body: JSON.stringify(body) },
    );
  },

  qdrantSearch(
    collectionName: string,
    body: {
      query_vector: number[];
      limit?: number;
      score_threshold?: number;
      with_payload?: boolean;
      with_vector?: boolean;
      filter_conditions?: Record<string, unknown>;
    },
  ) {
    return request<{
      points: Array<{
        id: string | number;
        score: number;
        payload?: Record<string, unknown>;
        vector?: number[];
      }>;
    }>(`/qdrant/collections/${encodeURIComponent(collectionName)}/search`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  deleteUser(userId: number) {
    return request<{ status: string }>(`/users/${userId}`, {
      method: "DELETE",
    });
  },

  // --- API Key Management ---

  createApiKey(userId: number, body: { name: string; expires_at?: string }) {
    return request<{ id: number; key: string; key_prefix: string; name: string; created_at: string; expires_at: string | null }>(`/users/${userId}/api-keys`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  listApiKeys(userId: number) {
    return request<{ api_keys: Array<{ id: number; key_prefix: string; name: string; created_at: string; expires_at: string | null; last_used_at: string | null }> }>(`/users/${userId}/api-keys`);
  },

  revokeApiKey(userId: number, keyId: number) {
    return request<{ status: string }>(`/users/${userId}/api-keys/${keyId}`, {
      method: "DELETE",
    });
  },

  qdrantRecommend(
    collectionName: string,
    body: {
      positive: Array<string | number>;
      negative?: Array<string | number>;
      limit?: number;
      score_threshold?: number;
      with_payload?: boolean;
      with_vector?: boolean;
      filter_conditions?: Record<string, unknown>;
    },
  ) {
    return request<{
      points: Array<{
        id: string | number;
        score: number;
        payload?: Record<string, unknown>;
        vector?: number[];
      }>;
    }>(`/qdrant/collections/${encodeURIComponent(collectionName)}/recommend`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  async qdrantUploadDocuments(collectionName: string, formData: FormData) {
    const headers = getCoreAuthHeaders();
    const res = await fetch(`${CORE_URL}/qdrant/collections/${encodeURIComponent(collectionName)}/upload`, {
      method: "POST",
      headers,
      body: formData,
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });
    if (!res.ok) {
      const text = await res.text();
      let msg = `Core API error ${res.status}`;
      try {
        const json = JSON.parse(text);
        if (json.detail) msg = json.detail;
        else if (json.error) msg = json.error;
        else if (json.message) msg = json.message;
      } catch {
        // keep default message
      }
      throw new CoreApiError(msg, res.status, text);
    }
    return res.json();
  },

  qdrantSemanticSearch(
    collectionName: string,
    body: {
      query: string;
      limit?: number;
      score_threshold?: number;
    },
  ) {
    return request<{
      results: Array<{
        id: string | number;
        score: number;
        text?: string;
        metadata?: Record<string, unknown>;
      }>;
      query: string;
      collection: string;
    }>(`/qdrant/collections/${encodeURIComponent(collectionName)}/semantic-search`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  qdrantRAGQuery(
    collectionName: string,
    body: {
      query: string;
      limit?: number;
      model?: string;
      temperature?: number;
    },
  ) {
    return request<{
      answer: string;
      chunks: Array<{
        text: string;
        score: number;
        source: string;
      }>;
      query: string;
      collection: string;
      model: string;
      provider: string;
    }>(`/qdrant/collections/${encodeURIComponent(collectionName)}/rag-query`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  // --- Mesh Operations ---

  meshImport(body: { data: string; format: string; run_id?: string }) {
    return request<{
      ok: boolean;
      run_id: string;
      protocol_version?: string;
      server_name?: string;
      message: string;
      payload: Record<string, unknown>;
    }>("/mcp/mesh/import", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  meshExport(body: {
    mesh: Record<string, unknown>;
    format: string;
    options?: Record<string, unknown>;
    run_id?: string;
  }) {
    return request<{
      ok: boolean;
      run_id: string;
      protocol_version?: string;
      server_name?: string;
      message: string;
      payload: Record<string, unknown>;
    }>("/mcp/mesh/export", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  meshSimplify(body: {
    mesh: Record<string, unknown>;
    target_ratio: number;
    preserve_boundaries?: boolean;
    run_id?: string;
  }) {
    return request<{
      ok: boolean;
      run_id: string;
      protocol_version?: string;
      server_name?: string;
      message: string;
      payload: Record<string, unknown>;
    }>("/mcp/mesh/simplify", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  meshBoolean(body: {
    mesh_a: Record<string, unknown>;
    mesh_b: Record<string, unknown>;
    operation: string;
    run_id?: string;
  }) {
    return request<{
      ok: boolean;
      run_id: string;
      protocol_version?: string;
      server_name?: string;
      message: string;
      payload: Record<string, unknown>;
    }>("/mcp/mesh/boolean", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  // --- Toolpath Operations ---

  toolpathGenerate(body: {
    mesh: Record<string, unknown>;
    tool: Record<string, unknown>;
    strategy: string;
    stock?: Record<string, unknown>;
    run_id?: string;
  }) {
    return request<{
      ok: boolean;
      run_id: string;
      gcode: {
        program: string;
        estimated_time_s: number;
        bounds: Record<string, number>;
        tool_changes: number;
      };
      toolpath: {
        moves: Array<Record<string, unknown>>;
        unit: string;
        tool_id: string;
      };
    }>("/mcp/toolpath/generate", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  toolpathOptimize(body: {
    toolpath: Record<string, unknown>;
    objective: string;
    constraints?: Record<string, unknown>;
    run_id?: string;
  }) {
    return request<{
      ok: boolean;
      run_id: string;
      toolpath: {
        moves: Array<Record<string, unknown>>;
        unit: string;
        tool_id: string;
      };
      gcode: {
        program: string;
        estimated_time_s: number;
        bounds: Record<string, number>;
        tool_changes: number;
      };
      improvement_pct: number;
    }>("/mcp/toolpath/optimize", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  // --- Templates ---

  listTemplates() {
    return request<{ templates: unknown[] }>("/orchestrate/templates");
  },

  getTemplate(templateId: string) {
    return request<unknown>(`/orchestrate/templates/${encodeURIComponent(templateId)}`);
  },

  deployTemplate(templateId: string, body: { input: string; routing_overrides?: Record<string, unknown> }) {
    return request<{
      run_id: string;
      template_id: string;
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
    }>(`/orchestrate/templates/${encodeURIComponent(templateId)}/deploy`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },
};
