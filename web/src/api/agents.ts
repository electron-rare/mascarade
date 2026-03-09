import { get, post, put } from "./client";

export interface Agent {
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

export interface Message {
  role: string;
  content: string;
}

export interface LLMResponse {
  content: string;
  model: string;
  provider: string;
  usage?: { input_tokens: number; output_tokens: number };
}

export interface OrchestrationResult {
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
}

export const agentsApi = {
  list: () => get<{ agents: Agent[] }>("/api/agents"),

  create: (agent: {
    name: string;
    description: string;
    system_prompt: string;
    preferred_provider?: string;
    preferred_model?: string;
    preferred_role?: string;
    strategy?: string;
    temperature?: number;
    max_tokens?: number;
  }) => post<Agent>("/api/agents", agent),

  get: (name: string) => get<Agent>(`/api/agents/${encodeURIComponent(name)}`),

  update: (
    name: string,
    agent: {
      description: string;
      system_prompt: string;
      preferred_provider?: string | null;
      preferred_model?: string | null;
      preferred_role?: string | null;
      strategy?: string;
      temperature?: number;
      max_tokens?: number;
    },
  ) => put<Agent>(`/api/agents/${encodeURIComponent(name)}`, agent),

  run: (name: string, messages: Message[]) =>
    post<LLMResponse>(`/api/agents/${encodeURIComponent(name)}/run`, { messages }),

  send: (params: {
    messages: Message[];
    strategy?: string;
    provider?: string;
    model?: string;
    system?: string;
    temperature?: number;
    max_tokens?: number;
  }) => post<LLMResponse>("/api/agents/send", params),

  orchestrate: (params: {
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
  }) =>
    post<{ run_id: string; mode: string; results: OrchestrationResult[] }>(
      "/api/agents/orchestrate",
      params,
    ),

  providers: () => get<{ providers: string[] }>("/api/agents/providers"),
};
