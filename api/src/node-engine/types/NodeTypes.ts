/**
 * Node Types - Visual graph node definitions for ReactFlow
 *
 * These types describe the visual graph structure (nodes + edges)
 * as rendered in the ReactFlow canvas, separate from the plugin
 * definitions in NodePluginAPI.ts.
 *
 * Inspired by:
 * - ReactFlow: Node/Edge data structures
 * - ComfyUI: Graph serialization format
 * - Node-RED: Flow definition JSON
 */

import type { NodeCategory, NodePortType } from '../plugins/NodePluginAPI';

/**
 * Position on canvas
 * (Compatible with ReactFlow's XYPosition type when @xyflow/react is installed)
 */
export interface XYPosition {
  x: number;
  y: number;
}

/**
 * CSS properties type
 * (Compatible with React.CSSProperties when React types are installed)
 */
export type CSSProperties = Record<string, string | number>;

/**
 * Visual node instance in the graph
 *
 * This represents a specific instance of a plugin placed on the canvas.
 * Multiple instances of the same plugin can exist with different IDs.
 *
 * Note: When @xyflow/react is installed, this will be compatible with
 * ReactFlow's Node<GraphNodeData> type.
 */
export interface GraphNode {
  /** Unique node instance ID (not the plugin ID) */
  id: string;
  /** Plugin type identifier (references registered plugin) */
  type: string;
  /** Position on canvas */
  position: XYPosition;
  /** Node instance data */
  data: GraphNodeData;
  /** Optional styling overrides */
  style?: CSSProperties;
  /** ReactFlow node class name */
  className?: string;
  /** Whether node is currently selected */
  selected?: boolean;
  /** Whether node is draggable */
  draggable?: boolean;
}

/**
 * Node instance data payload
 */
export interface GraphNodeData {
  /** Plugin ID this node instantiates */
  pluginId: string;
  /** Human-readable label (can override plugin default) */
  label: string;
  /** Node category (from plugin) */
  category: NodeCategory;
  /** Input port values (overrides for defaults) */
  inputValues: Record<string, unknown>;
  /** Current execution state */
  executionState: 'idle' | 'pending' | 'running' | 'complete' | 'error';
  /** Last execution error (if any) */
  error?: string;
  /** Last execution outputs */
  lastOutputs?: Record<string, unknown>;
  /** Custom node metadata */
  metadata?: Record<string, unknown>;
}

/**
 * Visual edge (connection) between nodes
 *
 * Connects an output port of one node to an input port of another.
 *
 * Note: When @xyflow/react is installed, this will be compatible with
 * ReactFlow's Edge type.
 */
export interface GraphEdge {
  /** Unique edge ID */
  id: string;
  /** Source node instance ID */
  source: string;
  /** Source output port ID */
  sourceHandle: string;
  /** Target node instance ID */
  target: string;
  /** Target input port ID */
  targetHandle: string;
  /** Edge type (default: 'default') */
  type?: string;
  /** Edge label */
  label?: string;
  /** Animated edge (shows data flow) */
  animated?: boolean;
  /** Edge styling */
  style?: CSSProperties;
  /** Edge class name */
  className?: string;
}

/**
 * Complete node graph definition
 *
 * This is the serializable representation of a node graph,
 * suitable for save/load and API transport.
 */
export interface NodeGraph {
  /** Graph ID (UUID) */
  id: string;
  /** Graph name (user-defined) */
  name: string;
  /** Graph description */
  description?: string;
  /** Visual nodes */
  nodes: GraphNode[];
  /** Connections between nodes */
  edges: GraphEdge[];
  /** Graph metadata */
  metadata: {
    /** Creation timestamp */
    createdAt: string;
    /** Last update timestamp */
    updatedAt: string;
    /** Graph author/creator */
    author?: string;
    /** Graph version (for migration) */
    version: string;
    /** Graph tags for organization */
    tags?: string[];
    /** Custom metadata */
    custom?: Record<string, unknown>;
  };
}

/**
 * Port connection info
 *
 * Describes a connection endpoint on a node.
 */
export interface PortConnection {
  /** Node instance ID */
  nodeId: string;
  /** Port ID */
  portId: string;
  /** Port type */
  portType: NodePortType;
}

/**
 * Node palette item
 *
 * Represents a draggable plugin in the node palette UI.
 */
export interface PaletteItem {
  /** Plugin ID */
  id: string;
  /** Category */
  category: NodeCategory;
  /** Display label */
  label: string;
  /** Description */
  description: string;
  /** Icon name or component */
  icon?: string;
  /** Whether plugin is experimental */
  experimental?: boolean;
  /** Plugin tags for search */
  tags?: string[];
}

/**
 * Node palette group (category)
 */
export interface PaletteGroup {
  /** Category */
  category: NodeCategory;
  /** Display label */
  label: string;
  /** Category icon */
  icon?: string;
  /** Items in this category */
  items: PaletteItem[];
  /** Whether group is expanded in UI */
  expanded?: boolean;
}

/**
 * Type guard for GraphNode
 */
export function isGraphNode(node: unknown): node is GraphNode {
  return (
    typeof node === 'object' &&
    node !== null &&
    'id' in node &&
    'type' in node &&
    'position' in node &&
    'data' in node
  );
}

/**
 * Type guard for GraphEdge
 */
export function isGraphEdge(edge: unknown): edge is GraphEdge {
  return (
    typeof edge === 'object' &&
    edge !== null &&
    'id' in edge &&
    'source' in edge &&
    'target' in edge &&
    'sourceHandle' in edge &&
    'targetHandle' in edge
  );
}

/**
 * Validate node graph structure
 *
 * @param graph - Graph to validate
 * @returns Validation errors (empty array if valid)
 */
export function validateGraph(graph: NodeGraph): string[] {
  const errors: string[] = [];

  // Validate required fields
  if (!graph.id) {
    errors.push('Graph must have an ID');
  }
  if (!graph.name) {
    errors.push('Graph must have a name');
  }
  if (!Array.isArray(graph.nodes)) {
    errors.push('Graph nodes must be an array');
  }
  if (!Array.isArray(graph.edges)) {
    errors.push('Graph edges must be an array');
  }

  // Validate node IDs are unique
  const nodeIds = new Set<string>();
  for (const node of graph.nodes || []) {
    if (nodeIds.has(node.id)) {
      errors.push(`Duplicate node ID: ${node.id}`);
    }
    nodeIds.add(node.id);
  }

  // Validate edges reference existing nodes
  for (const edge of graph.edges || []) {
    if (!nodeIds.has(edge.source)) {
      errors.push(`Edge ${edge.id} references non-existent source node: ${edge.source}`);
    }
    if (!nodeIds.has(edge.target)) {
      errors.push(`Edge ${edge.id} references non-existent target node: ${edge.target}`);
    }
  }

  return errors;
}

/**
 * Create a new empty graph
 *
 * @param name - Graph name
 * @returns Empty graph with metadata
 */
export function createEmptyGraph(name: string): NodeGraph {
  return {
    id: crypto.randomUUID(),
    name,
    description: '',
    nodes: [],
    edges: [],
    metadata: {
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      version: '1.0.0',
      tags: []
    }
  };
}
