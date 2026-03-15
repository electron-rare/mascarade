/**
 * ExampleNode - Simple demonstration node using BaseNode wrapper
 *
 * This is a minimal example showing how to use BaseNode for custom nodes.
 * It demonstrates:
 * - Using BaseNode wrapper for consistent styling
 * - Displaying custom content inside the node
 * - Accessing node data and execution state
 */

import { NodeProps } from '@xyflow/react';
import { BaseNode } from './BaseNode';
import type { GraphNodeData } from '../../types/NodeTypes';
import type { NodePlugin } from '../../plugins/NodePluginAPI';

/**
 * Example plugin definition
 * This would normally come from the PluginRegistry
 */
const examplePlugin: NodePlugin = {
  id: 'example-node',
  category: 'Workflow',
  label: 'Example Node',
  description: 'Simple demonstration node',
  inputs: [
    { id: 'input1', label: 'Input 1', type: 'string', required: true },
    { id: 'input2', label: 'Input 2', type: 'number' }
  ],
  outputs: [
    { id: 'output1', label: 'Output 1', type: 'string' },
    { id: 'output2', label: 'Output 2', type: 'number' }
  ],
  execute: async (inputs) => {
    return { output1: 'Hello', output2: 42 };
  }
};

/**
 * ExampleNode component
 *
 * Uses BaseNode wrapper to handle execution state display and port rendering.
 * Custom content is rendered inside the BaseNode wrapper.
 */
export function ExampleNode(props: NodeProps<GraphNodeData>) {
  const { data } = props;

  return (
    <BaseNode {...props} plugin={examplePlugin}>
      {/* Custom node content */}
      <div style={styles.content}>
        <div style={styles.field}>
          <label style={styles.label}>Status:</label>
          <span style={styles.value}>
            {data.executionState || 'idle'}
          </span>
        </div>

        {data.lastOutputs && (
          <div style={styles.field}>
            <label style={styles.label}>Last output:</label>
            <pre style={styles.output}>
              {JSON.stringify(data.lastOutputs, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </BaseNode>
  );
}

/**
 * Component styles
 */
const styles = {
  content: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: '8px'
  },
  field: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: '4px'
  },
  label: {
    fontSize: '11px',
    color: '#888',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.5px'
  },
  value: {
    fontSize: '13px',
    color: '#e0e0e0'
  },
  output: {
    fontSize: '11px',
    color: '#10b981',
    backgroundColor: '#1a2e1e',
    padding: '6px',
    borderRadius: '4px',
    margin: 0,
    overflow: 'auto',
    maxHeight: '100px'
  }
};

/**
 * Export default for easier imports
 */
export default ExampleNode;
