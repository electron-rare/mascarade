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

import { useCallback, useEffect, useState, useRef, MouseEvent } from 'react';
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
import '../styles/node-editor.css';
import * as Tone from 'tone';

import type { GraphNode, GraphEdge } from '../types/NodeTypes';
import type { ExecutionEvent } from '../types/ExecutionTypes';
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

  // Audio context state
  // Tone.js requires user gesture to start audio context (browser autoplay policy)
  const [audioInitialized, setAudioInitialized] = useState(false);

  // WebSocket connection state
  const wsRef = useRef<WebSocket | null>(null);
  const [wsConnected, setWsConnected] = useState(false);

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
   * Handle audio initialization
   *
   * Starts the Tone.js audio context. Required by browser autoplay policies
   * to be called after a user gesture (button click, etc.).
   *
   * This enables audio nodes (ToneSynthNode, etc.) to play sounds.
   */
  const handleStartAudio = useCallback(async () => {
    try {
      await Tone.start();
      setAudioInitialized(true);
    } catch (error) {
      console.error('Failed to start audio context:', error);
    }
  }, []);

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

  /**
   * WebSocket connection and execution event handling
   *
   * Connects to the WebSocket server at /ws/execution and listens for
   * real-time execution events. Updates node visual state based on events.
   */
  useEffect(() => {
    // Determine WebSocket URL (ws:// or wss:// based on current protocol)
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/execution`;

    // Create WebSocket connection
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    // Handle connection open
    ws.onopen = () => {
      setWsConnected(true);

      // Subscribe to all execution events
      ws.send(JSON.stringify({ type: 'subscribe_all' }));
    };

    // Handle incoming messages
    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);

        // Handle execution events
        if (message.type === 'execution_event') {
          const execEvent = message.event as ExecutionEvent;

          // Handle graph started - reset all nodes to idle
          if (execEvent.type === 'graph.started') {
            setNodes((nds) =>
              nds.map((node) => ({
                ...node,
                data: {
                  ...node.data,
                  executionState: 'idle',
                  error: undefined,
                },
              }))
            );
          }

          // Handle node state changes
          else if (execEvent.type === 'node.state') {
            const { nodeId, state } = execEvent;

            // Update the node's execution state
            setNodes((nds) =>
              nds.map((node) => {
                if (node.id === nodeId) {
                  return {
                    ...node,
                    data: {
                      ...node.data,
                      executionState: state,
                    },
                  };
                }
                return node;
              })
            );
          }

          // Handle node output events (update last outputs)
          else if (execEvent.type === 'node.output') {
            const { nodeId, outputs } = execEvent;

            setNodes((nds) =>
              nds.map((node) => {
                if (node.id === nodeId) {
                  return {
                    ...node,
                    data: {
                      ...node.data,
                      lastOutputs: outputs,
                    },
                  };
                }
                return node;
              })
            );
          }

          // Handle node error events
          else if (execEvent.type === 'node.error') {
            const { nodeId, error } = execEvent;

            setNodes((nds) =>
              nds.map((node) => {
                if (node.id === nodeId) {
                  return {
                    ...node,
                    data: {
                      ...node.data,
                      executionState: 'error',
                      error: error.message,
                    },
                  };
                }
                return node;
              })
            );
          }
        }
      } catch (error) {
        // Silently ignore parse errors (e.g., ping/pong messages)
      }
    };

    // Handle connection close
    ws.onclose = () => {
      setWsConnected(false);
    };

    // Handle errors
    ws.onerror = (error) => {
      setWsConnected(false);
    };

    // Cleanup on unmount
    return () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
      wsRef.current = null;
    };
  }, []); // Empty dependency array - connect once on mount

  return (
    <div style={{ width: '100%', height: '100vh', position: 'relative' }}>
      {/* Audio initialization button */}
      <button
        className="audio-init-button"
        onClick={handleStartAudio}
        disabled={audioInitialized}
        style={{
          position: 'absolute',
          top: '10px',
          left: '10px',
          zIndex: 10,
          padding: '8px 16px',
          backgroundColor: audioInitialized ? '#10b981' : '#ef4444',
          color: '#fff',
          border: 'none',
          borderRadius: '6px',
          cursor: audioInitialized ? 'default' : 'pointer',
          fontSize: '14px',
          fontWeight: '500',
          transition: 'all 0.2s ease',
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.3)',
          opacity: audioInitialized ? 0.8 : 1,
        }}
      >
        {audioInitialized ? '✓ Audio Ready' : '▶ Start Audio'}
      </button>

      {/* WebSocket connection status */}
      <div
        style={{
          position: 'absolute',
          top: '50px',
          left: '10px',
          zIndex: 10,
          padding: '6px 12px',
          backgroundColor: wsConnected ? '#10b981' : '#6b7280',
          color: '#fff',
          border: 'none',
          borderRadius: '6px',
          fontSize: '12px',
          fontWeight: '500',
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.3)',
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
        }}
        title={wsConnected ? 'WebSocket connected - real-time updates active' : 'WebSocket disconnected'}
      >
        <span
          style={{
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            backgroundColor: wsConnected ? '#fff' : '#333',
            animation: wsConnected ? 'pulse 2s infinite' : 'none',
          }}
        />
        {wsConnected ? 'Live' : 'Offline'}
      </div>

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
