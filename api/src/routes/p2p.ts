import { existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { Hono } from "hono";
import { load } from "js-yaml";

const p2p = new Hono();
const NODES_YAML_PATHS = [
  path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..", "..", "core", "scripts", "p2p", "nodes.yaml"),
  path.resolve(process.cwd(), "..", "core", "scripts", "p2p", "nodes.yaml"),
  path.resolve(process.cwd(), "core", "scripts", "p2p", "nodes.yaml"),
];

const NODE_HEALTH_TIMEOUT_MS = 2_500;

type UnknownRecord = Record<string, unknown>;
type FinetuneNodeRecord = UnknownRecord & {
  node_id: string;
  capabilities: string[];
};

function asRecord(value: unknown): UnknownRecord | null {
  return typeof value === "object" && value !== null && !Array.isArray(value) ? (value as UnknownRecord) : null;
}

function asString(value: unknown): string | null {
  return typeof value === "string" && value.trim().length > 0 ? value.trim() : null;
}

function normalizeNodeList(data: unknown): UnknownRecord[] {
  if (Array.isArray(data)) {
    return data.filter((entry): entry is UnknownRecord => asRecord(entry) !== null);
  }

  const payload = asRecord(data);
  if (!payload) {
    return [];
  }
  if (Array.isArray(payload.nodes)) {
    return (payload.nodes as unknown[]).filter((entry): entry is UnknownRecord => asRecord(entry) !== null);
  }
  return [payload];
}

function asStringList(value: unknown): string[] {
  if (typeof value === "string") {
    return [value];
  }
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((entry): entry is string => typeof entry === "string" && entry.trim().length > 0);
}

function resolveNodesYamlPath(): string {
  const found = NODES_YAML_PATHS.find((candidate) => existsSync(candidate));
  if (found) {
    return found;
  }
  return NODES_YAML_PATHS[0];
}

function pickNodeId(node: UnknownRecord, fallbackIndex: number): string {
  const candidates = [
    asString(node.node_id),
    asString(node.id),
    asString(node.peer_id),
    asString(node.host_id),
    asString(node.node_name),
    asString(node.name),
  ];

  const candidate = candidates.find((entry) => entry !== null);
  return candidate ?? `node-${fallbackIndex + 1}`;
}

function collectNodeCapabilities(node: UnknownRecord): string[] {
  const candidates: unknown[] = [node.capabilities, node.finetune, node.capability];
  const maybeRecord = asRecord(node.capabilities);
  if (maybeRecord && Object.prototype.hasOwnProperty.call(maybeRecord, "finetune")) {
    candidates.push((maybeRecord as UnknownRecord).finetune);
  }

  const normalized = new Set<string>();
  for (const candidate of candidates) {
    const asList = asStringList(candidate);
    if (asList.length > 0) {
      asList.forEach((entry) => normalized.add(entry.trim().toLowerCase()));
      continue;
    }

    const asMap = asRecord(candidate);
    if (asMap) {
      for (const [key, value] of Object.entries(asMap)) {
        if (typeof value === "string" && value.trim().length > 0 && key.toLowerCase().startsWith("ft-")) {
          normalized.add(key.toLowerCase());
        }
      }
    }
  }

  return [...normalized];
}

function normalizeNode(node: UnknownRecord, index: number): FinetuneNodeRecord {
  return {
    ...node,
    node_id: pickNodeId(node, index),
    capabilities: collectNodeCapabilities(node),
  };
}

function toHttpBaseUrl(value: unknown): string | null {
  const raw = asString(value);
  if (!raw) {
    return null;
  }

  const candidate = raw.startsWith("http://") || raw.startsWith("https://") ? raw : `http://${raw}`;

  try {
    const parsed = new URL(candidate);
    if (parsed.hostname && (parsed.protocol === "http:" || parsed.protocol === "https:")) {
      const normalized = `${parsed.protocol}//${parsed.host}`;
      return normalized.endsWith("/") ? normalized.slice(0, -1) : normalized;
    }
  } catch {
    return null;
  }
  return null;
}

function pickNodeBaseUrl(node: UnknownRecord): string | null {
  const candidates = [
    node.base_url,
    node.http_base_url,
    node.p2p_base_url,
    node.url,
    node.endpoint,
    node.address,
  ];
  for (const candidate of candidates) {
    const converted = toHttpBaseUrl(candidate);
    if (converted) {
      return converted;
    }
  }

  const host = asString(node.host);
  const port = (() => {
    if (typeof node.port === "number") {
      return Number.isInteger(node.port) ? node.port : null;
    }
    const portValue = asString(node.port);
    if (!portValue) {
      return null;
    }
    const parsed = Number.parseInt(portValue, 10);
    return Number.isInteger(parsed) ? parsed : null;
  })();

  if (host && Number.isInteger(port)) {
    return `http://${host}:${port}`;
  }

  return null;
}

async function probeNode(node: FinetuneNodeRecord): Promise<FinetuneNodeRecord & { health: UnknownRecord }> {
  const healthUrl = `${pickNodeBaseUrl(node) ?? ""}`.replace(/\/$/, "");
  const startedAt = Date.now();

  if (!healthUrl) {
    return {
      ...node,
      health: {
        url: null,
        ok: false,
        status: null,
        latency_ms: null,
        error: "Missing base URL",
      },
    };
  }

  const target = `${healthUrl}/health`;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), NODE_HEALTH_TIMEOUT_MS);
  try {
    const res = await fetch(target, { signal: controller.signal });
    clearTimeout(timeout);
    return {
      ...node,
      health: {
        url: target,
        ok: res.ok,
        status: res.status,
        latency_ms: Date.now() - startedAt,
        error: res.ok ? null : `HTTP ${res.status}`,
      },
    };
  } catch (error) {
    clearTimeout(timeout);
    return {
      ...node,
      health: {
        url: target,
        ok: false,
        status: null,
        latency_ms: Date.now() - startedAt,
        error: error instanceof Error ? error.message : "health probe failed",
      },
    };
  }
}

async function loadNodesFromYaml(): Promise<UnknownRecord[]> {
  const yamlPath = resolveNodesYamlPath();
  const yamlBody = await readFile(yamlPath, "utf8");
  const parsed = load(yamlBody);
  return normalizeNodeList(parsed);
}

function formatNodeFileError(error: unknown): { status: 404 | 500; body: UnknownRecord } {
  if (
    typeof error === "object" &&
    error !== null &&
    "code" in error &&
    (error as NodeJS.ErrnoException).code === "ENOENT"
  ) {
    return {
      status: 404,
      body: { error: "p2p nodes file not found", path: resolveNodesYamlPath() },
    };
  }
  if (error instanceof Error) {
    return {
      status: 500,
      body: { error: `Failed to load nodes file: ${error.message}` },
    };
  }
  return {
    status: 500,
    body: { error: "Failed to load nodes file" },
  };
}

/** Lister les noeuds p2p depuis scripts/p2p/nodes.yaml */
p2p.get("/nodes", async (c) => {
  try {
    const parsedNodes = await loadNodesFromYaml();
    const nodes = parsedNodes.map((node, index) => normalizeNode(node, index));
    return c.json(nodes);
  } catch (error) {
    const { status, body } = formatNodeFileError(error);
    return c.json(body, status);
  }
});

/** Ping chaque noeud connu et retourne un statut santé */
p2p.get("/health", async (c) => {
  try {
    const parsedNodes = await loadNodesFromYaml();
    const nodes = parsedNodes.map((node, index) => normalizeNode(node, index));
    const health = await Promise.all(nodes.map((node) => probeNode(node)));
    const healthyNodes = health.filter((entry) => entry.health.ok).length;
    return c.json({
      generated_at: new Date().toISOString(),
      total_nodes: health.length,
      healthy_nodes: healthyNodes,
      unhealthy_nodes: health.length - healthyNodes,
      nodes: health,
    });
  } catch (error) {
    const { status, body } = formatNodeFileError(error);
    if (status === 404 || status === 500) {
      return c.json(
        status === 404 ? body : { ...body, error: `Failed to probe node health: ${(body as UnknownRecord).error}` },
        status,
      );
    }
    return c.json({ error: "Failed to probe node health" }, 500);
  }
});

export { p2p };
