/**
 * Demo app for NodeEditor and NodePalette components
 *
 * Standalone demo to verify:
 * - ReactFlow canvas renders correctly (subtask-3-1)
 * - NodePalette sidebar with 6 categories (subtask-3-2)
 * - Drag-and-drop functionality
 */

import { createRoot } from 'react-dom/client';
import { NodeEditor } from './components/NodeEditor';
import { NodePalette } from './components/NodePalette';

/**
 * Demo app wrapper component
 */
function DemoApp() {
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
      <div style={{ flex: 1 }}>
        <NodeEditor
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

const root = document.getElementById('root');
if (root) {
  createRoot(root).render(<DemoApp />);
} else {
  console.error('Root element not found');
}
