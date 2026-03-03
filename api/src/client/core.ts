/**
 * Client HTTP vers le core Python Mascarade.
 */

const CORE_URL = process.env.CORE_URL || "http://localhost:8100";

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
  const res = await fetch(`${CORE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
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
    return request<LLMResponse>(`/agents/${name}/run`, {
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
};
