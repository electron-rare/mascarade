/**
 * Universal Node Engine — TypeScript type definitions.
 *
 * Mirrors Python types from core/mascarade/node_engine/types.py
 * for type-safe integration in the Hono API layer and frontend.
 */

/**
 * Base port type identifiers for the Universal Node Engine.
 */
export type PrimitiveType =
  | "string"
  | "number"
  | "integer"
  | "boolean"
  | "binary"
  | "json"
  | "void";

/**
 * Composite type definitions supporting recursive nesting.
 */
export type CompositeType =
  | { kind: "array"; element: PortType }
  | { kind: "map"; key: PrimitiveType; value: PortType }
  | { kind: "optional"; inner: PortType }
  | { kind: "union"; variants: PortType[] }
  | { kind: "stream"; element: PortType };

/**
 * Domain-specific type extension registered at runtime.
 */
export type DomainType = {
  kind: "domain";
  domain: string;
  name: string;
  schema: Record<string, unknown>;
};

/**
 * Unified port type supporting primitives, composites, and domain extensions.
 */
export type PortType = PrimitiveType | CompositeType | DomainType;

/**
 * Definition of a single input or output port on a node.
 */
export interface NodePort {
  id: string;
  label: string;
  type: PortType;
  required: boolean;
  default?: unknown;
  description?: string;
}

/**
 * A typed connection between two node ports.
 */
export interface NodeConnection {
  id: string;
  sourceNodeId: string;
  sourcePortId: string;
  targetNodeId: string;
  targetPortId: string;
}

/**
 * Graph execution status.
 */
export type GraphStatus =
  | "draft"
  | "validated"
  | "compiled"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

/**
 * A node instance within a graph.
 */
export interface GraphNode {
  id: string;
  node_type: string;
  label: string;
  config: Record<string, unknown>;
  position: [number, number];
  domain?: string;
}

/**
 * A typed connection between two node ports.
 */
export interface GraphEdge {
  id: string;
  source_node: string;
  source_port: string;
  target_node: string;
  target_port: string;
}

/**
 * A complete node graph ready for execution.
 */
export interface Graph {
  id: string;
  name: string;
  version: number;
  status: GraphStatus;
  nodes: GraphNode[];
  edges: GraphEdge[];
  metadata: Record<string, unknown>;
}

/**
 * Runtime context passed to each node during execution.
 */
export interface ExecutionContext {
  graphId: string;
  runId: string;
  nodeId: string;
  config: Record<string, unknown>;
  metadata: Record<string, unknown>;
  isCancelled: () => boolean;
}

/**
 * Result from a single node execution.
 */
export interface NodeResult {
  node_id: string;
  outputs: Record<string, unknown>;
  error?: string;
  duration_ms: number;
  worker_name: string;
}

/**
 * Worker capability declaration for routing and scheduling.
 */
export interface NodeCapability {
  nodeTypes: string[];
  domain: string;
  supportsStreaming: boolean;
  supportsCancellation: boolean;
  maxConcurrent: number;
  requiresGpu: boolean;
  requiresHardware: boolean;
  estimatedMemoryMb: number;
}

/**
 * NodeWorker — TypeScript interface for domain workers.
 *
 * TypeScript counterpart to the Python NodeWorker ABC.
 * Used in the Hono API layer for type-safe worker integration
 * and in the frontend for capability-aware node rendering.
 */
export interface NodeWorker {
  readonly name: string;
  readonly domain: string;

  execute(
    nodeType: string,
    inputs: Record<string, unknown>,
    config: Record<string, unknown>,
    context: ExecutionContext,
  ): Promise<Record<string, unknown>>;

  validate(
    nodeType: string,
    inputs: Record<string, unknown>,
    config: Record<string, unknown>,
  ): Promise<string[]>;

  capabilities(): NodeCapability;

  onInit?(context: ExecutionContext): void | Promise<void>;
  onDestroy?(context: ExecutionContext): void | Promise<void>;

  readonly isAvailable: boolean;
}

/**
 * Node type definition in the registry.
 */
export interface NodeType {
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
  deprecated_by?: string;
}

/**
 * Serialized graph format (v1.0.0).
 */
export interface SerializedGraph {
  version: string;
  schema: string;
  graph: Graph;
}
