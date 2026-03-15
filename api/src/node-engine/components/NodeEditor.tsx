/**
 * NodeEditor - Main ReactFlow canvas component
 *
 * This is the primary visual node graph editor component.
 * Uses ReactFlow v12 (@xyflow/react) with useNodesState/useEdgesState hooks.
 *
 * Key patterns:
 * - nodeTypes and edgeTypes defined OUTSIDE component (prevents re-registration bugs)
 * - Uses hooks for state management (not manual useState)
 * - Compatible with GraphNode/GraphEdge types from NodeTypes.ts
 *
 * Inspired by:
 * - ReactFlow v12 best practices
 * - TouchDesigner: Real-time canvas updates
 * - Node-RED: Flow-based visual programming
 */

import { useCallback, useEffect, MouseEvent } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  Node,
  Edge,
  NodeTypes,
  EdgeTypes,
  BackgroundVariant,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import type { GraphNode, GraphEdge } from '../types/NodeTypes';
import { ExampleNode } from './nodes/ExampleNode';

/**
 * Node type registry
 *
 * Maps node type strings to React components.
 * CRITICAL: Defined OUTSIDE component to prevent ReactFlow re-registration bugs.
 *
 * Example node registered for demonstration of BaseNode wrapper.
 */
const nodeTypes: NodeTypes = {
  'example-node': ExampleNode
};

/**
 * Edge type registry
 *
 * Maps edge type strings to React components.
 * CRITICAL: Defined OUTSIDE component to prevent ReactFlow re-registration bugs.
 *
 * Using default ReactFlow edges for now.
 */
const edgeTypes: EdgeTypes = {};

/**
 * Initial empty state
 *
 * Starting with an empty canvas. Nodes will be added via:
 * - Drag-and-drop from NodePalette (subtask-3-2)
 * - Graph load from persistence (phase-9)
 */
const initialNodes: Node[] = [];
const initialEdges: Edge[] = [];

/**
 * NodeEditor component props
 */
export interface NodeEditorProps {
  /** Optional initial graph to load */
  initialGraph?: {
    nodes: GraphNode[];
    edges: GraphEdge[];
  };
  /** Callback when graph changes */
  onGraphChange?: (nodes: Node[], edges: Edge[]) => void;
  /** Callback when node is selected */
  onNodeSelect?: (nodeId: string | null) => void;
  /** Callback when graph is executed */
  onExecute?: () => void;
}

/**
 * NodeEditor - Main ReactFlow canvas component
 *
 * Renders the visual node graph editor with:
 * - Zoom and pan controls
 * - Background grid
 * - MiniMap for navigation
 * - Drag-to-connect edges
 * - Node selection
 *
 * @param props - Component props
 * @returns ReactFlow canvas component
 */
export function NodeEditor(props: NodeEditorProps = {}) {
  const {
    initialGraph,
    onGraphChange,
    onNodeSelect,
    onExecute,
  } = props;

  // Initialize nodes/edges from props or empty state
  // Note: GraphNode is compatible with ReactFlow Node type
  const [nodes, setNodes, onNodesChange] = useNodesState(
    (initialGraph?.nodes as unknown as Node[]) || initialNodes
  );
  const [edges, setEdges, onEdgesChange] = useEdgesState(
    (initialGraph?.edges as unknown as Edge[]) || initialEdges
  );

  /**
   * Handle new edge connections
   *
   * Called when user drags from an output port to an input port.
   * Validates connection and adds edge to graph.
   */
  const onConnect = useCallback(
    (connection: Connection) => {
      // Add edge using ReactFlow's addEdge helper
      // (handles connection validation)
      setEdges((eds) => addEdge(connection, eds));
    },
    [setEdges]
  );

  /**
   * Handle node selection
   *
   * Called when user clicks on a node.
   */
  const onNodeClick = useCallback(
    (_event: MouseEvent, node: Node) => {
      if (onNodeSelect) {
        onNodeSelect(node.id);
      }
    },
    [onNodeSelect]
  );

  /**
   * Handle pane click (deselect all)
   *
   * Called when user clicks on empty canvas.
   */
  const onPaneClick = useCallback(() => {
    if (onNodeSelect) {
      onNodeSelect(null);
    }
  }, [onNodeSelect]);

  /**
   * Notify parent of graph changes
   *
   * Called whenever nodes or edges change.
   */
  useEffect(() => {
    if (onGraphChange) {
      onGraphChange(nodes, edges);
    }
  }, [nodes, edges, onGraphChange]);

  return (
    <div style={{ width: '100%', height: '100vh' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeClick={onNodeClick}
        onPaneClick={onPaneClick}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        attributionPosition="bottom-right"
      >
        {/* Background grid */}
        <Background
          variant={BackgroundVariant.Dots}
          gap={16}
          size={1}
        />

        {/* Zoom/pan controls */}
        <Controls />

        {/* MiniMap for navigation */}
        <MiniMap
          nodeStrokeWidth={3}
          zoomable
          pannable
        />
      </ReactFlow>
    </div>
  );
}

/**
 * Export default for easier imports
 */
export default NodeEditor;
