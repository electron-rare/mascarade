import { get, post } from "./client";

export interface Agent {
  name: string;
  description: string;
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
}

export const agentsApi = {
  list: () => get<{ agents: Agent[] }>("/api/agents"),

  create: (agent: {
    name: string;
    description: string;
    system_prompt: string;
    preferred_provider?: string;
    strategy?: string;
  }) => post<Agent>("/api/agents", agent),

  run: (name: string, messages: Message[]) =>
    post<LLMResponse>(`/api/agents/${name}/run`, { messages }),

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
  }) => post<{ results: OrchestrationResult[] }>("/api/agents/orchestrate", params),

  providers: () => get<{ providers: string[] }>("/api/agents/providers"),
};
