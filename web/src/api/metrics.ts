import { get, post } from "./client";

export const metricsApi = {
  global: () => get<Record<string, unknown>>("/api/agents/metrics"),
  reset: () => post<{ status: string }>("/api/agents/metrics/reset"),
  provider: (name: string) =>
    get<Record<string, unknown>>(`/api/agents/metrics/${name}`),

  cacheStats: () => get<Record<string, unknown>>("/api/agents/cache/stats"),
  cacheReset: () => post<{ status: string }>("/api/agents/cache/reset"),

  lbStats: () =>
    get<Record<string, unknown>>("/api/agents/load-balancer/stats"),
  lbReset: () =>
    post<{ status: string }>("/api/agents/load-balancer/reset"),

  fallbackStats: () =>
    get<Record<string, unknown>>("/api/agents/fallback/stats"),
  fallbackReset: () =>
    post<{ status: string }>("/api/agents/fallback/reset"),
};
