/**
 * End-to-End Test: Sequential Graph Execution (A→B→C)
 *
 * Verifies that a linear graph of 3 nodes executes in correct
 * topological order, with data flowing through each node sequentially.
 * Validates execution events are emitted in the expected order.
 */

import { describe, expect, it, beforeEach } from 'vitest';
import { GraphExecutor } from '../GraphExecutor.js';
import { NodeRunner } from '../NodeRunner.js';
import { ExecutionContextManager } from '../ExecutionContext.js';
import type { NodePlugin } from '../../plugins/NodePluginAPI.js';
import { NodeCategory } from '../../plugins/NodePluginAPI.js';
import type { NodeGraph, GraphNode, GraphEdge } from '../../types/NodeTypes.js';
import type { ExecutionEvent } from '../../types/ExecutionTypes.js';

/** Creates a workflow plugin that appends its label to a string */
function createPassthroughPlugin(id: string, label: string): NodePlugin {
  return {
    id,
    category: NodeCategory.Workflow,
    label,
    description: `Passthrough node ${label}`,
    inputs: [{ id: 'value', label: 'Value', type: 'string' }],
    outputs: [{ id: 'value', label: 'Value', type: 'string' }],
    execute: (inputs) => {
      const incoming = (inputs.value as string) || '';
      return { value: `${incoming}→${label}` };
    }
  };
}

function createNode(id: string, pluginId: string, x: number): GraphNode {
  return {
    id,
    type: pluginId,
    position: { x, y: 0 },
    data: {
      pluginId,
      label: `Node ${id}`,
      category: NodeCategory.Workflow,
      inputValues: {},
      executionState: 'idle'
    }
  };
}

function createEdge(source: string, target: string): GraphEdge {
  return {
    id: `${source}-${target}`,
    source,
    sourceHandle: 'value',
    target,
    targetHandle: 'value'
  };
}

describe('End-to-End: Sequential Graph A→B→C', () => {
  let executor: GraphExecutor;
  let contextManager: ExecutionContextManager;
  let events: ExecutionEvent[];
  let graph: NodeGraph;

  const pluginA = createPassthroughPlugin('plugin-a', 'A');
  const pluginB = createPassthroughPlugin('plugin-b', 'B');
  const pluginC = createPassthroughPlugin('plugin-c', 'C');

  const plugins = new Map<string, NodePlugin>([
    ['plugin-a', pluginA],
    ['plugin-b', pluginB],
    ['plugin-c', pluginC]
  ]);

  beforeEach(() => {
    executor = new GraphExecutor();
    contextManager = new ExecutionContextManager();
    events = [];

    graph = {
      id: 'test-graph',
      name: 'A→B→C Test',
      nodes: [
        createNode('node-a', 'plugin-a', 0),
        createNode('node-b', 'plugin-b', 200),
        createNode('node-c', 'plugin-c', 400)
      ],
      edges: [
        createEdge('node-a', 'node-b'),
        createEdge('node-b', 'node-c')
      ],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    };
  });

  it('determines correct execution order A→B→C', () => {
    const order = executor.getExecutionOrder(graph);
    expect(order).toEqual(['node-a', 'node-b', 'node-c']);
  });

  it('validates graph has no cycles', () => {
    expect(executor.hasCycle(graph)).toBe(false);
    expect(executor.validateGraph(graph)).toEqual([]);
  });

  it('identifies root and leaf nodes', () => {
    expect(executor.getRootNodes(graph)).toEqual(['node-a']);
    expect(executor.getLeafNodes(graph)).toEqual(['node-c']);
  });

  it('executes nodes sequentially with data flowing through', async () => {
    const order = executor.getExecutionOrder(graph);
    const runId = 'run-e2e-001';
    const executionLog: string[] = [];
    const nodeOutputs = new Map<string, Record<string, unknown>>();

    const eventEmitter = (event: ExecutionEvent) => {
      events.push(event);
    };

    for (const nodeId of order) {
      const node = graph.nodes.find(n => n.id === nodeId)!;
      const plugin = plugins.get(node.data.pluginId)!;
      const runner = new NodeRunner(plugin);

      // Gather inputs from upstream nodes
      const inputs: Record<string, unknown> = {};
      for (const edge of graph.edges) {
        if (edge.target === nodeId) {
          const upstreamOutputs = nodeOutputs.get(edge.source);
          if (upstreamOutputs && edge.sourceHandle) {
            inputs[edge.targetHandle || 'value'] = upstreamOutputs[edge.sourceHandle];
          }
        }
      }

      const context = contextManager.createContext(runId, nodeId, graph.id, {
        pluginId: node.data.pluginId,
        eventEmitter
      });

      const record = await runner.execute(inputs, context, { skipValidation: true });
      executionLog.push(nodeId);
      if (record.outputs) {
        nodeOutputs.set(nodeId, record.outputs);
      }
    }

    // Verify execution order
    expect(executionLog).toEqual(['node-a', 'node-b', 'node-c']);

    // Verify data flow: each node appends its label
    expect(nodeOutputs.get('node-a')).toEqual({ value: '→A' });
    expect(nodeOutputs.get('node-b')).toEqual({ value: '→A→B' });
    expect(nodeOutputs.get('node-c')).toEqual({ value: '→A→B→C' });
  });

  it('emits state events in correct order for each node', async () => {
    const order = executor.getExecutionOrder(graph);
    const runId = 'run-e2e-002';
    const nodeOutputs = new Map<string, Record<string, unknown>>();

    const eventEmitter = (event: ExecutionEvent) => {
      events.push(event);
    };

    for (const nodeId of order) {
      const node = graph.nodes.find(n => n.id === nodeId)!;
      const plugin = plugins.get(node.data.pluginId)!;
      const runner = new NodeRunner(plugin);

      const inputs: Record<string, unknown> = {};
      for (const edge of graph.edges) {
        if (edge.target === nodeId) {
          const upstreamOutputs = nodeOutputs.get(edge.source);
          if (upstreamOutputs && edge.sourceHandle) {
            inputs[edge.targetHandle || 'value'] = upstreamOutputs[edge.sourceHandle];
          }
        }
      }

      const context = contextManager.createContext(runId, nodeId, graph.id, {
        pluginId: node.data.pluginId,
        eventEmitter
      });

      const record = await runner.execute(inputs, context, { skipValidation: true });
      if (record.outputs) {
        nodeOutputs.set(nodeId, record.outputs);
      }
    }

    // Extract state events only
    const stateEvents = events
      .filter((e): e is Extract<ExecutionEvent, { type: 'node.state' }> => e.type === 'node.state');

    // Each node emits: pending → running → complete (3 states × 3 nodes = 9)
    expect(stateEvents).toHaveLength(9);

    // Verify sequential order: A's states, then B's states, then C's states
    const stateSequence = stateEvents.map(e => `${e.nodeId}:${e.state}`);
    expect(stateSequence).toEqual([
      'node-a:pending', 'node-a:running', 'node-a:complete',
      'node-b:pending', 'node-b:running', 'node-b:complete',
      'node-c:pending', 'node-c:running', 'node-c:complete'
    ]);
  });

  it('handles error in middle node and stops execution', async () => {
    // Create a plugin that throws an error
    const failingPlugin: NodePlugin = {
      id: 'plugin-fail',
      category: NodeCategory.Workflow,
      label: 'Failing Node',
      description: 'Node that always fails',
      inputs: [{ id: 'value', label: 'Value', type: 'string' }],
      outputs: [{ id: 'value', label: 'Value', type: 'string' }],
      execute: () => {
        throw new Error('Node B failed intentionally');
      }
    };

    const failGraph: NodeGraph = {
      ...graph,
      nodes: [
        createNode('node-a', 'plugin-a', 0),
        createNode('node-b', 'plugin-fail', 200),
        createNode('node-c', 'plugin-c', 400)
      ]
    };

    const failPlugins = new Map<string, NodePlugin>([
      ['plugin-a', pluginA],
      ['plugin-fail', failingPlugin],
      ['plugin-c', pluginC]
    ]);

    const order = executor.getExecutionOrder(failGraph);
    const runId = 'run-e2e-003';
    const executedNodes: string[] = [];
    const nodeOutputs = new Map<string, Record<string, unknown>>();
    let errorNodeId: string | null = null;

    for (const nodeId of order) {
      const node = failGraph.nodes.find(n => n.id === nodeId)!;
      const plugin = failPlugins.get(node.data.pluginId)!;
      const runner = new NodeRunner(plugin);

      const inputs: Record<string, unknown> = {};
      for (const edge of failGraph.edges) {
        if (edge.target === nodeId) {
          const upstreamOutputs = nodeOutputs.get(edge.source);
          if (upstreamOutputs && edge.sourceHandle) {
            inputs[edge.targetHandle || 'value'] = upstreamOutputs[edge.sourceHandle];
          }
        }
      }

      const context = contextManager.createContext(runId, nodeId, failGraph.id, {
        pluginId: node.data.pluginId
      });

      try {
        const record = await runner.execute(inputs, context, { skipValidation: true });
        executedNodes.push(nodeId);
        if (record.outputs) {
          nodeOutputs.set(nodeId, record.outputs);
        }
      } catch {
        errorNodeId = nodeId;
        break; // Stop execution on error
      }
    }

    // A executed successfully, B failed, C never ran
    expect(executedNodes).toEqual(['node-a']);
    expect(errorNodeId).toBe('node-b');
  });

  it('supports abort mid-execution', async () => {
    const runId = 'run-e2e-004';
    const executedNodes: string[] = [];

    // Create plugin that triggers abort during execution
    const abortTriggerPlugin: NodePlugin = {
      id: 'plugin-abort',
      category: NodeCategory.Workflow,
      label: 'Abort Trigger',
      description: 'Triggers abort during execution',
      inputs: [{ id: 'value', label: 'Value', type: 'string' }],
      outputs: [{ id: 'value', label: 'Value', type: 'string' }],
      execute: (_inputs, context) => {
        contextManager.abort(runId);
        return { value: 'aborted' };
      }
    };

    const abortGraph: NodeGraph = {
      ...graph,
      nodes: [
        createNode('node-a', 'plugin-abort', 0),
        createNode('node-b', 'plugin-b', 200),
        createNode('node-c', 'plugin-c', 400)
      ]
    };

    const order = executor.getExecutionOrder(abortGraph);

    for (const nodeId of order) {
      if (contextManager.isAborted(runId)) {
        break;
      }

      const node = abortGraph.nodes.find(n => n.id === nodeId)!;
      const pluginId = node.data.pluginId;
      const plugin = pluginId === 'plugin-abort' ? abortTriggerPlugin : plugins.get(pluginId)!;
      const runner = new NodeRunner(plugin);

      const context = contextManager.createContext(runId, nodeId, abortGraph.id, {
        pluginId
      });

      try {
        const record = await runner.execute({}, context, { skipValidation: true });
        executedNodes.push(nodeId);
      } catch {
        // Node A's execute succeeds but runner detects abort after
        executedNodes.push(nodeId + ':aborted');
        break;
      }
    }

    // Node A triggered the abort; B and C never ran
    expect(executedNodes).toHaveLength(1);
    expect(contextManager.isAborted(runId)).toBe(true);
  });
});
