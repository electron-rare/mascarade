import type { AgentInfo, CliAgentsStatusResponse } from "../client/core.js";

export type AgentCatalogEntry = {
  id: string;
  object: "agent";
  kind: "mascarade-agent" | "cli-agent";
  name: string;
  label: string;
  description: string | null;
  builtin: boolean;
  available: boolean;
  provider: string | null;
  model: string | null;
  preferred_provider: string | null;
  preferred_model: string | null;
  preferred_role: string | null;
  binary: string | null;
  modes: string[];
};

export type AgentCatalogResponse = {
  object: "list";
  data: AgentCatalogEntry[];
};

function humanizeAgentName(name: string) {
  return name
    .split(/[-_]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function buildMascaradeAgentEntry(agent: AgentInfo): AgentCatalogEntry {
  return {
    id: `agent:${agent.name}`,
    object: "agent",
    kind: "mascarade-agent",
    name: agent.name,
    label: humanizeAgentName(agent.name),
    description: agent.description || null,
    builtin: Boolean(agent.builtin),
    available: true,
    provider: agent.preferred_provider ?? null,
    model: agent.preferred_model ?? null,
    preferred_provider: agent.preferred_provider ?? null,
    preferred_model: agent.preferred_model ?? null,
    preferred_role: agent.preferred_role ?? null,
    binary: null,
    modes: ["run"],
  };
}

function buildCliAgentEntry(
  name: string,
  descriptor: CliAgentsStatusResponse["agents"][keyof CliAgentsStatusResponse["agents"]],
): AgentCatalogEntry {
  return {
    id: `cli-agent:${name}`,
    object: "agent",
    kind: "cli-agent",
    name,
    label: humanizeAgentName(name),
    description: `CLI agent via ${descriptor.binary}`,
    builtin: false,
    available: descriptor.available,
    provider: descriptor.provider,
    model: null,
    preferred_provider: null,
    preferred_model: null,
    preferred_role: null,
    binary: descriptor.binary,
    modes: [...descriptor.modes].sort((a, b) => a.localeCompare(b)),
  };
}

function catalogKindScore(kind: AgentCatalogEntry["kind"]) {
  return kind === "mascarade-agent" ? 0 : 1;
}

export function buildAgentCatalog(
  agents: AgentInfo[],
  cliAgents: CliAgentsStatusResponse["agents"],
): AgentCatalogResponse {
  const data = [
    ...agents.map(buildMascaradeAgentEntry),
    ...Object.entries(cliAgents).map(([name, descriptor]) => buildCliAgentEntry(name, descriptor)),
  ].sort((a, b) => {
    return catalogKindScore(a.kind) - catalogKindScore(b.kind) ||
      Number(b.builtin) - Number(a.builtin) ||
      Number(b.available) - Number(a.available) ||
      a.label.localeCompare(b.label);
  });

  return {
    object: "list",
    data,
  };
}
