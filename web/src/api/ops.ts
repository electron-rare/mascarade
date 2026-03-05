import { get } from "./client";

export type OpsMonitor = {
  timestamp: string;
  gateway: {
    api: { ok: boolean; status: number };
    core: boolean;
  };
  ai: {
    ollama: {
      ok: boolean;
      status: number;
      latency_ms: number;
      models: number;
      error?: string;
    };
    qdrant: {
      ok: boolean;
      status: number;
      latency_ms: number;
      collections: number;
      error?: string;
    };
  };
  services: {
    name: string;
    url: string;
    ok: boolean;
    status: number;
    latency_ms: number;
    error?: string;
  }[];
  core_metrics: {
    ok: boolean;
    status: number;
    data: Record<string, unknown> | null;
    error?: string;
  };
};

export const opsApi = {
  monitor: () => get<OpsMonitor>("/api/ops/monitor"),
};

