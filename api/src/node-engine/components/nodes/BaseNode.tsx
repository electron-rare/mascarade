/**
 * BaseNode - Reusable wrapper component for consistent node UI
 *
 * Provides consistent visual styling and execution state display for all
 * node types in the graph editor. Wraps custom node content with:
 * - Execution state indicators (pending/running/complete/error)
 * - Input/output port handles
 * - Node label and category icon
 * - Error message display
 *
 * Inspired by:
 * - ReactFlow v12: Custom node patterns with Handle components
 * - TouchDesigner: Real-time execution state visualization
 * - ComfyUI: Node execution progress indicators
 *
 * Usage:
 * ```tsx
 * const CustomNode: NodeComponent = (props) => {
 *   return (
 *     <BaseNode {...props}>
 *       <div>Custom node content</div>
 *     </BaseNode>
 *   );
 * };
 * ```
 */

import { memo, ReactNode } from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import type { GraphNodeData } from '../../types/NodeTypes';
import type { NodePlugin } from '../../plugins/NodePluginAPI';

/**
 * Category color mapping (consistent with NodePalette)
 */
const CATEGORY_COLORS: Record<string, string> = {
  AI: '#8b5cf6',
  Hardware: '#ef4444',
  Audio: '#06b6d4',
  CAD: '#10b981',
  Workflow: '#f59e0b',
  Automation: '#ec4899'
};

/**
 * Execution state color mapping
 */
const STATE_COLORS: Record<GraphNodeData['executionState'], string> = {
  idle: '#6b7280',       // gray
  pending: '#f59e0b',    // amber
  running: '#3b82f6',    // blue
  complete: '#10b981',   // green
  error: '#ef4444'       // red
};

/**
 * Execution state labels
 */
const STATE_LABELS: Record<GraphNodeData['executionState'], string> = {
  idle: 'Idle',
  pending: 'Pending',
  running: 'Running',
  complete: 'Complete',
  error: 'Error'
};

/**
 * BaseNode component props
 */
export interface BaseNodeProps extends NodeProps<GraphNodeData> {
  /** Child content to render inside the node */
  children?: ReactNode;
  /** Plugin definition (for port rendering) */
  plugin?: NodePlugin;
  /** Whether to show port labels */
  showPortLabels?: boolean;
  /** Custom node className */
  className?: string;
}

/**
 * BaseNode component
 *
 * Reusable wrapper for all custom node types. Handles:
 * - Execution state visualization
 * - Input/output port rendering
 * - Error display
 * - Consistent styling
 *
 * @param props - Component props (ReactFlow NodeProps + custom props)
 * @returns Styled node wrapper component
 */
export const BaseNode = memo(function BaseNode(props: BaseNodeProps) {
  const {
    data,
    children,
    plugin,
    showPortLabels = false,
    className = '',
    selected
  } = props;

  const {
    label,
    category,
    executionState = 'idle',
    error,
  } = data;

  // Get category color for visual coding
  const categoryColor = CATEGORY_COLORS[category] || '#6b7280';
  const stateColor = STATE_COLORS[executionState];

  // Node container style
  const containerStyle: React.CSSProperties = {
    minWidth: '180px',
    backgroundColor: '#2a2a2a',
    border: `2px solid ${selected ? '#fff' : stateColor}`,
    borderLeft: `4px solid ${categoryColor}`,
    borderRadius: '8px',
    boxShadow: selected
      ? '0 8px 24px rgba(0, 0, 0, 0.4)'
      : '0 4px 12px rgba(0, 0, 0, 0.3)',
    color: '#e0e0e0',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    overflow: 'hidden',
    transition: 'all 0.2s ease-in-out'
  };

  return (
    <div className={`base-node ${className}`} style={containerStyle}>
      {/* Node header */}
      <div style={styles.header}>
        <div style={styles.headerLeft}>
          <span style={styles.label}>{label}</span>
          <span style={styles.category}>{category}</span>
        </div>
        <div style={styles.headerRight}>
          <div
            style={{
              ...styles.stateIndicator,
              backgroundColor: stateColor
            }}
            title={STATE_LABELS[executionState]}
          />
        </div>
      </div>

      {/* Execution state badge (when running/pending) */}
      {(executionState === 'running' || executionState === 'pending') && (
        <div style={styles.stateBadge}>
          <div style={styles.spinner} />
          <span style={styles.stateLabel}>{STATE_LABELS[executionState]}...</span>
        </div>
      )}

      {/* Error display */}
      {executionState === 'error' && error && (
        <div style={styles.errorBanner}>
          <span style={styles.errorIcon}>⚠️</span>
          <span style={styles.errorText}>{error}</span>
        </div>
      )}

      {/* Node content */}
      <div style={styles.content}>
        {children}
      </div>

      {/* Input handles (connection points) */}
      {plugin?.inputs.map((input, index) => (
        <Handle
          key={`input-${input.id}`}
          type="target"
          position={Position.Left}
          id={input.id}
          style={{
            ...styles.handle,
            top: `${((index + 1) / (plugin.inputs.length + 1)) * 100}%`,
            background: input.required ? '#ef4444' : '#6b7280'
          }}
          title={showPortLabels ? input.label : input.description || input.label}
        />
      ))}

      {/* Output handles (connection points) */}
      {plugin?.outputs.map((output, index) => (
        <Handle
          key={`output-${output.id}`}
          type="source"
          position={Position.Right}
          id={output.id}
          style={{
            ...styles.handle,
            top: `${((index + 1) / (plugin.outputs.length + 1)) * 100}%`,
            background: '#10b981'
          }}
          title={showPortLabels ? output.label : output.description || output.label}
        />
      ))}
    </div>
  );
});

/**
 * Component styles
 */
const styles = {
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '10px 12px',
    backgroundColor: '#1e1e1e',
    borderBottom: '1px solid #333'
  } as React.CSSProperties,

  headerLeft: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: '2px'
  } as React.CSSProperties,

  headerRight: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px'
  } as React.CSSProperties,

  label: {
    fontSize: '14px',
    fontWeight: 600,
    color: '#e0e0e0'
  } as React.CSSProperties,

  category: {
    fontSize: '11px',
    color: '#888',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.5px'
  } as React.CSSProperties,

  stateIndicator: {
    width: '10px',
    height: '10px',
    borderRadius: '50%',
    border: '2px solid #1e1e1e',
    transition: 'background-color 0.3s ease'
  } as React.CSSProperties,

  stateBadge: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '6px 12px',
    backgroundColor: '#1a2332',
    borderBottom: '1px solid #2563eb'
  } as React.CSSProperties,

  spinner: {
    width: '12px',
    height: '12px',
    border: '2px solid #3b82f6',
    borderTopColor: 'transparent',
    borderRadius: '50%',
    animation: 'spin 0.8s linear infinite'
  } as React.CSSProperties,

  stateLabel: {
    fontSize: '12px',
    color: '#3b82f6',
    fontWeight: 500
  } as React.CSSProperties,

  errorBanner: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '8px 12px',
    backgroundColor: '#2a1416',
    borderBottom: '1px solid #ef4444'
  } as React.CSSProperties,

  errorIcon: {
    fontSize: '14px'
  } as React.CSSProperties,

  errorText: {
    fontSize: '12px',
    color: '#fca5a5',
    flex: 1,
    lineHeight: '1.4'
  } as React.CSSProperties,

  content: {
    padding: '12px',
    minHeight: '40px'
  } as React.CSSProperties,

  handle: {
    width: '10px',
    height: '10px',
    border: '2px solid #1e1e1e',
    transition: 'all 0.2s ease'
  } as React.CSSProperties
};

/**
 * CSS animation for spinner
 * Note: This should ideally be in a separate CSS file
 */
if (typeof document !== 'undefined') {
  const styleSheet = document.createElement('style');
  styleSheet.textContent = `
    @keyframes spin {
      from { transform: rotate(0deg); }
      to { transform: rotate(360deg); }
    }
  `;
  document.head.appendChild(styleSheet);
}

/**
 * Export default for easier imports
 */
export default BaseNode;
