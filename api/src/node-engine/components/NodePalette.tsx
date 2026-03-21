/**
 * NodePalette - Sidebar with draggable node categories
 *
 * Provides a categorized palette of draggable nodes that can be placed
 * onto the ReactFlow canvas. Organized into 6 categories:
 * - AI: LLM inference, embeddings, AI pipelines
 * - Hardware: MIDI, DMX, ESP32 control
 * - Audio: Tone.js synthesis and processing
 * - CAD: Toolpath generation, G-code export
 * - Workflow: Logic nodes (if, switch, loop)
 * - Automation: Triggers, schedules, webhooks
 *
 * Inspired by:
 * - Node-RED: Category-based node palette
 * - TouchDesigner: Operator palette with search
 * - Blender: Tool sidebar with tabs
 */

import { useState, DragEvent } from 'react';
import type { NodePlugin, NodeCategory } from '../plugins/NodePluginAPI';
import type { PaletteItem, PaletteGroup } from '../types/NodeTypes';

/**
 * NodePalette component props
 */
export interface NodePaletteProps {
  /** Available node plugins (from PluginRegistry) */
  plugins?: NodePlugin[];
  /** Callback when node is dragged onto canvas */
  onNodeDragStart?: (pluginId: string, category: NodeCategory) => void;
  /** Initial expanded category (optional) */
  initialCategory?: NodeCategory;
  /** Whether palette is collapsible */
  collapsible?: boolean;
}

/**
 * Example/placeholder nodes for each category
 *
 * These will be replaced by actual plugins from the registry in later phases.
 * For now, they demonstrate the palette UI structure.
 */
const EXAMPLE_NODES: Record<NodeCategory, PaletteItem[]> = {
  AI: [
    {
      id: 'llm-inference',
      category: 'AI' as NodeCategory,
      label: 'LLM Inference',
      description: 'Execute LLM prompt using Mascarade router',
      tags: ['ai', 'llm', 'inference']
    },
    {
      id: 'text-embeddings',
      category: 'AI' as NodeCategory,
      label: 'Text Embeddings',
      description: 'Generate text embeddings for semantic search',
      tags: ['ai', 'embeddings']
    }
  ],
  Hardware: [
    {
      id: 'midi-output',
      category: 'Hardware' as NodeCategory,
      label: 'MIDI Output',
      description: 'Send MIDI messages to external devices',
      tags: ['midi', 'hardware']
    },
    {
      id: 'dmx-output',
      category: 'Hardware' as NodeCategory,
      label: 'DMX Output',
      description: 'Control DMX lighting fixtures',
      tags: ['dmx', 'lighting', 'hardware']
    },
    {
      id: 'esp32-control',
      category: 'Hardware' as NodeCategory,
      label: 'ESP32 Control',
      description: 'Send commands to ESP32 devices',
      tags: ['esp32', 'iot', 'hardware']
    }
  ],
  Audio: [
    {
      id: 'tone-synth',
      category: 'Audio' as NodeCategory,
      label: 'Tone.js Synth',
      description: 'Synthesize audio notes in browser',
      tags: ['audio', 'synth', 'tone.js']
    },
    {
      id: 'tone-fm-synth',
      category: 'Audio' as NodeCategory,
      label: 'FM Synth',
      description: 'FM synthesis with Tone.js',
      tags: ['audio', 'synth', 'fm']
    }
  ],
  CAD: [
    {
      id: 'gcode-generator',
      category: 'CAD' as NodeCategory,
      label: 'G-code Generator',
      description: 'Generate G-code from toolpath',
      tags: ['cad', 'gcode', 'cnc']
    },
    {
      id: 'toolpath-preview',
      category: 'CAD' as NodeCategory,
      label: 'Toolpath Preview',
      description: 'Visualize toolpath geometry',
      tags: ['cad', 'preview']
    }
  ],
  Workflow: [
    {
      id: 'if-node',
      category: 'Workflow' as NodeCategory,
      label: 'If',
      description: 'Conditional branching',
      tags: ['logic', 'control', 'if']
    },
    {
      id: 'switch-node',
      category: 'Workflow' as NodeCategory,
      label: 'Switch',
      description: 'Multi-way branching',
      tags: ['logic', 'control', 'switch']
    },
    {
      id: 'loop-node',
      category: 'Workflow' as NodeCategory,
      label: 'Loop',
      description: 'Iterate over collection',
      tags: ['logic', 'control', 'loop']
    }
  ],
  Automation: [
    {
      id: 'timer-trigger',
      category: 'Automation' as NodeCategory,
      label: 'Timer Trigger',
      description: 'Trigger execution on interval',
      tags: ['automation', 'trigger', 'timer']
    },
    {
      id: 'webhook-node',
      category: 'Automation' as NodeCategory,
      label: 'Webhook',
      description: 'HTTP webhook endpoint',
      tags: ['automation', 'webhook', 'http']
    }
  ]
};

/**
 * Category metadata (labels and icons)
 */
const CATEGORY_INFO: Record<NodeCategory, { label: string; icon: string; color: string }> = {
  AI: { label: 'AI', icon: '🤖', color: '#8b5cf6' },
  Hardware: { label: 'Hardware', icon: '⚙️', color: '#ef4444' },
  Audio: { label: 'Audio', icon: '🎵', color: '#06b6d4' },
  CAD: { label: 'CAD', icon: '📐', color: '#10b981' },
  Workflow: { label: 'Workflow', icon: '🔀', color: '#f59e0b' },
  Automation: { label: 'Automation', icon: '⚡', color: '#ec4899' }
};

/**
 * NodePalette component
 *
 * Renders a sidebar with categorized, draggable nodes.
 * Nodes can be dragged onto the ReactFlow canvas to add them to the graph.
 */
export function NodePalette(props: NodePaletteProps) {
  const {
    plugins = [],
    onNodeDragStart,
    initialCategory = 'AI' as NodeCategory,
    collapsible = false
  } = props;

  const [activeCategory, setActiveCategory] = useState<NodeCategory>(initialCategory);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  /**
   * Build palette groups from plugins or use example nodes
   */
  const paletteGroups = buildPaletteGroups(plugins);

  /**
   * Handle drag start for a node
   *
   * Sets the plugin ID and category in the drag event so the canvas
   * can create the appropriate node on drop.
   */
  const handleDragStart = (event: DragEvent, item: PaletteItem) => {
    // Store plugin ID and category in drag data
    event.dataTransfer.setData('application/reactflow', item.id);
    event.dataTransfer.setData('application/node-plugin-id', item.id);
    event.dataTransfer.setData('application/node-category', item.category);
    event.dataTransfer.effectAllowed = 'move';

    // Notify parent component
    if (onNodeDragStart) {
      onNodeDragStart(item.id, item.category as NodeCategory);
    }
  };

  /**
   * Filter nodes by search query
   */
  const filterNodes = (items: PaletteItem[]): PaletteItem[] => {
    if (!searchQuery.trim()) {
      return items;
    }

    const query = searchQuery.toLowerCase();
    return items.filter(item =>
      item.label.toLowerCase().includes(query) ||
      item.description.toLowerCase().includes(query) ||
      item.tags?.some(tag => tag.toLowerCase().includes(query))
    );
  };

  // Get current category's nodes
  const currentGroup = paletteGroups.find(g => g.category === activeCategory);
  const currentNodes = currentGroup ? filterNodes(currentGroup.items) : [];

  if (isCollapsed && collapsible) {
    return (
      <div style={styles.collapsedContainer}>
        <button
          style={styles.expandButton}
          onClick={() => setIsCollapsed(false)}
          title="Expand node palette"
        >
          ▶
        </button>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <h3 style={styles.title}>Node Palette</h3>
        {collapsible && (
          <button
            style={styles.collapseButton}
            onClick={() => setIsCollapsed(true)}
            title="Collapse palette"
          >
            ◀
          </button>
        )}
      </div>

      {/* Search bar */}
      <div style={styles.searchContainer}>
        <input
          type="text"
          placeholder="Search nodes..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          style={styles.searchInput}
        />
      </div>

      {/* Category tabs */}
      <div style={styles.categoryTabs}>
        {paletteGroups.map(group => {
          const info = CATEGORY_INFO[group.category];
          const isActive = group.category === activeCategory;

          return (
            <button
              key={group.category}
              style={{
                ...styles.categoryTab,
                ...(isActive ? styles.categoryTabActive : {}),
                borderLeftColor: info.color
              }}
              onClick={() => setActiveCategory(group.category)}
              title={group.label}
            >
              <span style={styles.categoryIcon}>{info.icon}</span>
              <span style={styles.categoryLabel}>{info.label}</span>
              <span style={styles.categoryCount}>({group.items.length})</span>
            </button>
          );
        })}
      </div>

      {/* Node list */}
      <div style={styles.nodeList}>
        {currentNodes.length === 0 ? (
          <div style={styles.emptyState}>
            {searchQuery ? (
              <p>No nodes match &quot;{searchQuery}&quot;</p>
            ) : (
              <p>No nodes in this category</p>
            )}
          </div>
        ) : (
          currentNodes.map(item => {
            const info = CATEGORY_INFO[item.category as NodeCategory];

            return (
              <div
                key={item.id}
                draggable
                onDragStart={(e) => handleDragStart(e, item)}
                style={{
                  ...styles.nodeItem,
                  borderLeftColor: info.color
                }}
                title={item.description}
              >
                <div style={styles.nodeHeader}>
                  <span style={styles.nodeIcon}>{info.icon}</span>
                  <span style={styles.nodeLabel}>{item.label}</span>
                </div>
                <div style={styles.nodeDescription}>
                  {item.description}
                </div>
                {item.experimental && (
                  <span style={styles.experimentalBadge}>Experimental</span>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Footer with hint */}
      <div style={styles.footer}>
        <p style={styles.hint}>💡 Drag nodes onto the canvas</p>
      </div>
    </div>
  );
}

/**
 * Build palette groups from plugins
 *
 * If no plugins provided, uses example nodes for demonstration.
 */
function buildPaletteGroups(plugins: NodePlugin[]): PaletteGroup[] {
  // All categories in order
  const categories: NodeCategory[] = [
    'AI' as NodeCategory,
    'Hardware' as NodeCategory,
    'Audio' as NodeCategory,
    'CAD' as NodeCategory,
    'Workflow' as NodeCategory,
    'Automation' as NodeCategory
  ];

  if (plugins.length === 0) {
    // Use example nodes (for demo/development)
    return categories.map(category => ({
      category,
      label: CATEGORY_INFO[category].label,
      icon: CATEGORY_INFO[category].icon,
      items: EXAMPLE_NODES[category],
      expanded: true
    }));
  }

  // Build from actual plugins
  return categories.map(category => {
    const categoryPlugins = plugins.filter(p => p.category === category);
    const items: PaletteItem[] = categoryPlugins.map(p => ({
      id: p.id,
      category: p.category,
      label: p.label,
      description: p.description,
      tags: p.metadata?.tags,
      experimental: p.metadata?.experimental
    }));

    return {
      category,
      label: CATEGORY_INFO[category].label,
      icon: CATEGORY_INFO[category].icon,
      items,
      expanded: true
    };
  });
}

/**
 * Component styles
 */
const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column' as const,
    width: '280px',
    height: '100%',
    backgroundColor: '#1e1e1e',
    borderRight: '1px solid #333',
    color: '#e0e0e0',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
  },
  collapsedContainer: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '40px',
    height: '100%',
    backgroundColor: '#1e1e1e',
    borderRight: '1px solid #333'
  },
  expandButton: {
    padding: '8px',
    backgroundColor: '#333',
    color: '#e0e0e0',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    fontSize: '16px'
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '16px',
    borderBottom: '1px solid #333'
  },
  title: {
    margin: 0,
    fontSize: '16px',
    fontWeight: 600
  },
  collapseButton: {
    padding: '4px 8px',
    backgroundColor: 'transparent',
    color: '#888',
    border: 'none',
    cursor: 'pointer',
    fontSize: '14px'
  },
  searchContainer: {
    padding: '12px 16px',
    borderBottom: '1px solid #333'
  },
  searchInput: {
    width: '100%',
    padding: '8px 12px',
    backgroundColor: '#2a2a2a',
    color: '#e0e0e0',
    border: '1px solid #444',
    borderRadius: '4px',
    fontSize: '14px',
    outline: 'none'
  },
  categoryTabs: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: '2px',
    padding: '8px',
    borderBottom: '1px solid #333'
  },
  categoryTab: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '10px 12px',
    backgroundColor: '#2a2a2a',
    color: '#e0e0e0',
    border: 'none',
    borderLeft: '3px solid transparent',
    borderRadius: '4px',
    cursor: 'pointer',
    fontSize: '14px',
    textAlign: 'left' as const,
    transition: 'background-color 0.2s'
  },
  categoryTabActive: {
    backgroundColor: '#333'
  },
  categoryIcon: {
    fontSize: '16px'
  },
  categoryLabel: {
    flex: 1,
    fontWeight: 500
  },
  categoryCount: {
    fontSize: '12px',
    color: '#888'
  },
  nodeList: {
    flex: 1,
    overflowY: 'auto' as const,
    padding: '8px'
  },
  nodeItem: {
    padding: '12px',
    marginBottom: '8px',
    backgroundColor: '#2a2a2a',
    border: '1px solid #444',
    borderLeft: '3px solid',
    borderRadius: '4px',
    cursor: 'grab',
    transition: 'all 0.2s',
    '&:hover': {
      backgroundColor: '#333',
      borderColor: '#555'
    },
    '&:active': {
      cursor: 'grabbing'
    }
  },
  nodeHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    marginBottom: '4px'
  },
  nodeIcon: {
    fontSize: '16px'
  },
  nodeLabel: {
    fontSize: '14px',
    fontWeight: 500
  },
  nodeDescription: {
    fontSize: '12px',
    color: '#888',
    lineHeight: '1.4'
  },
  experimentalBadge: {
    display: 'inline-block',
    marginTop: '6px',
    padding: '2px 6px',
    fontSize: '10px',
    color: '#f59e0b',
    backgroundColor: '#2a1f0a',
    border: '1px solid #f59e0b',
    borderRadius: '3px',
    fontWeight: 600,
    textTransform: 'uppercase' as const
  },
  emptyState: {
    padding: '24px',
    textAlign: 'center' as const,
    color: '#888',
    fontSize: '14px'
  },
  footer: {
    padding: '12px 16px',
    borderTop: '1px solid #333',
    backgroundColor: '#1a1a1a'
  },
  hint: {
    margin: 0,
    fontSize: '12px',
    color: '#666',
    textAlign: 'center' as const
  }
};

/**
 * Export default for easier imports
 */
export default NodePalette;
