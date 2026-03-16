import { Hono } from "hono";
import { emitStructuredLog } from "../lib/otel.js";

const nodes = new Hono();

type NodePort = {
  id: string;
  label: string;
  type: string | Record<string, unknown>;
  required: boolean;
  default?: unknown;
  description?: string;
};

type NodeTypeResponse = {
  id: string;
  domain: string;
  label: string;
  description: string;
  version: string;
  inputs: NodePort[];
  outputs: NodePort[];
  config_schema: Record<string, unknown>;
  tags: string[];
  deprecated: boolean;
  deprecated_by: string | null;
};

type NodeCatalogResponse = {
  node_types: NodeTypeResponse[];
  domains: string[];
  total_count: number;
};

/**
 * GET /catalog
 * Returns the catalog of available node types for the node engine.
 *
 * Phase 0 implementation: Returns empty catalog structure.
 * Will be enhanced in later phases to proxy to core NodeTypeRegistry.
 */
nodes.get("/catalog", async (c) => {
  emitStructuredLog({
    severity: "info",
    service: "api",
    message: "Fetching node catalog",
    source: "nodes.catalog",
  });

  // Phase 0: Return empty catalog structure
  // TODO: In Phase 1+, proxy to core /nodes/catalog endpoint
  const emptyResponse: NodeCatalogResponse = {
    node_types: [],
    domains: [],
    total_count: 0,
  };

  return c.json(emptyResponse);
});

/**
 * GET /catalog/:domain
 * Returns node types filtered by domain.
 *
 * Phase 0 implementation: Returns empty catalog structure.
 * Will be enhanced in later phases to proxy to core NodeTypeRegistry.
 */
nodes.get("/catalog/:domain", async (c) => {
  const domain = c.req.param("domain");

  emitStructuredLog({
    severity: "info",
    service: "api",
    message: `Fetching node catalog for domain: ${domain}`,
    source: "nodes.catalog",
  });

  // Phase 0: Return empty catalog structure
  // TODO: In Phase 1+, proxy to core /nodes/catalog?domain=X endpoint
  const emptyResponse: NodeCatalogResponse = {
    node_types: [],
    domains: [],
    total_count: 0,
  };

  return c.json(emptyResponse);
});

export { nodes };
