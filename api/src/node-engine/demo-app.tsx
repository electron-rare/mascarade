/**
 * Demo app for NodeEditor and NodePalette components
 *
 * Standalone demo to verify:
 * - ReactFlow canvas renders correctly (subtask-3-1)
 * - NodePalette sidebar with 6 categories (subtask-3-2)
 * - Drag-and-drop functionality
 * - BaseNode execution state display (subtask-3-3)
 */

import { createRoot } from 'react-dom/client';
import { useState } from 'react';
import { NodeEditor } from './components/NodeEditor';
import { NodePalette } from './components/NodePalette';
import type { GraphNode, GraphEdge } from './types/NodeTypes';
import './styles/node-editor.css';

/**
 * Demo nodes showing different execution states
 */
const demoNodes: GraphNode[] = [
  {
    id: 'demo-1',
    type: 'example-node',
    position: { x: 100, y: 100 },
    data: {
      pluginId: 'example-node',
      label: 'Idle Node',
      category: 'Workflow',
      inputValues: {},
      executionState: 'idle'
    }
  },
  {
    id: 'demo-2',
    type: 'example-node',
    position: { x: 350, y: 100 },
    data: {
      pluginId: 'example-node',
      label: 'Running Node',
      category: 'AI',
      inputValues: {},
      executionState: 'running'
    }
  },
  {
    id: 'demo-3',
    type: 'example-node',
    position: { x: 100, y: 250 },
    data: {
      pluginId: 'example-node',
      label: 'Complete Node',
      category: 'Audio',
      inputValues: {},
      executionState: 'complete',
      lastOutputs: { result: 'Success!', value: 42 }
    }
  },
  {
    id: 'demo-4',
    type: 'example-node',
    position: { x: 350, y: 250 },
    data: {
      pluginId: 'example-node',
      label: 'Error Node',
      category: 'Hardware',
      inputValues: {},
      executionState: 'error',
      error: 'Connection timeout: Device not responding'
    }
  }
];

const demoEdges: GraphEdge[] = [];

/**
 * Demo app wrapper component
 */
function DemoApp() {
  const [showDemo, setShowDemo] = useState(true);

  return (
    <div style={{ display: 'flex', width: '100vw', height: '100vh' }}>
      {/* Node Palette Sidebar */}
      <NodePalette
        onNodeDragStart={(pluginId, category) => {
          console.log('Dragging node:', pluginId, 'from category:', category);
        }}
        collapsible={true}
      />

      {/* ReactFlow Canvas */}
      <div style={{ flex: 1, position: 'relative' }}>
        {/* Demo toggle button */}
        <div style={styles.controls}>
          <button
            onClick={() => setShowDemo(!showDemo)}
            style={styles.button}
          >
            {showDemo ? 'Hide' : 'Show'} Demo Nodes
          </button>
        </div>

        <NodeEditor
          initialGraph={showDemo ? { nodes: demoNodes, edges: demoEdges } : undefined}
          onGraphChange={(nodes, edges) => {
            console.log('Graph changed:', { nodeCount: nodes.length, edgeCount: edges.length });
          }}
          onNodeSelect={(nodeId) => {
            console.log('Node selected:', nodeId);
          }}
        />
      </div>
    </div>
  );
}

/**
 * Component styles
 */
const styles = {
  controls: {
    position: 'absolute' as const,
    top: '16px',
    right: '16px',
    zIndex: 10,
    display: 'flex',
    gap: '8px'
  },
  button: {
    padding: '8px 16px',
    backgroundColor: '#2a2a2a',
    color: '#e0e0e0',
    border: '1px solid #444',
    borderRadius: '6px',
    cursor: 'pointer',
    fontSize: '14px',
    fontWeight: 500,
    transition: 'all 0.2s',
    ':hover': {
      backgroundColor: '#333',
      borderColor: '#555'
    }
  }
};

const root = document.getElementById('root');
if (root) {
  createRoot(root).render(<DemoApp />);
} else {
  console.error('Root element not found');
}
