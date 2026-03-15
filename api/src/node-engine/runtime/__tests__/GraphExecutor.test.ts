/**
 * GraphExecutor Tests
 *
 * Validates topological sort and cycle detection for graph execution.
 */

import { describe, expect, it } from 'vitest';
import { GraphExecutor } from '../GraphExecutor.js';
import type { NodeGraph, GraphNode, GraphEdge } from '../../types/NodeTypes.js';
import type { NodePlugin } from '../../plugins/NodePluginAPI.js';
import { NodeCategory } from '../../plugins/NodePluginAPI.js';

// Helper to create a simple test plugin
function createTestPlugin(id: string, executeSync = true): NodePlugin {
  return {
    id,
    category: NodeCategory.Workflow,
    label: `Test Node ${id}`,
    description: 'Test node for graph execution',
    inputs: [{ id: 'input', label: 'Input', type: 'any' }],
    outputs: [{ id: 'output', label: 'Output', type: 'any' }],
    execute: executeSync
      ? (inputs) => ({ output: inputs.input })
      : async (inputs) => ({ output: inputs.input })
  };
}

// Helper to create a graph node
function createGraphNode(id: string, pluginId: string, position = { x: 0, y: 0 }): GraphNode {
  return {
    id,
    type: pluginId,
    position,
    data: {
      pluginId,
      label: `Node ${id}`,
      category: NodeCategory.Workflow,
      inputValues: {},
      executionState: 'idle'
    }
  };
}

// Helper to create a graph edge
function createGraphEdge(id: string, source: string, target: string): GraphEdge {
  return {
    id,
    source,
    sourceHandle: 'output',
    target,
    targetHandle: 'input'
  };
}

// Helper to create a complete graph
function createTestGraph(nodes: GraphNode[], edges: GraphEdge[]): NodeGraph {
  return {
    id: 'test-graph',
    name: 'Test Graph',
    nodes,
    edges,
    metadata: {
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      version: '1.0.0'
    }
  };
}

describe('GraphExecutor', () => {
  describe('topologicalSort', () => {
    it('sorts a linear graph A→B→C correctly', () => {
      const nodes = [
        createGraphNode('a', 'test-plugin'),
        createGraphNode('b', 'test-plugin'),
        createGraphNode('c', 'test-plugin')
      ];
      const edges = [
        createGraphEdge('e1', 'a', 'b'),
        createGraphEdge('e2', 'b', 'c')
      ];
      const graph = createTestGraph(nodes, edges);

      const executor = new GraphExecutor();
      const sorted = executor.topologicalSort(graph);

      expect(sorted).toEqual(['a', 'b', 'c']);
    });

    it('sorts a diamond graph correctly (A→B, A→C, B→D, C→D)', () => {
      const nodes = [
        createGraphNode('a', 'test-plugin'),
        createGraphNode('b', 'test-plugin'),
        createGraphNode('c', 'test-plugin'),
        createGraphNode('d', 'test-plugin')
      ];
      const edges = [
        createGraphEdge('e1', 'a', 'b'),
        createGraphEdge('e2', 'a', 'c'),
        createGraphEdge('e3', 'b', 'd'),
        createGraphEdge('e4', 'c', 'd')
      ];
      const graph = createTestGraph(nodes, edges);

      const executor = new GraphExecutor();
      const sorted = executor.topologicalSort(graph);

      // A must come first, D must come last
      expect(sorted[0]).toBe('a');
      expect(sorted[3]).toBe('d');
      // B and C can be in any order in the middle
      expect(sorted.slice(1, 3).sort()).toEqual(['b', 'c']);
    });

    it('handles disconnected nodes (isolated nodes with no edges)', () => {
      const nodes = [
        createGraphNode('a', 'test-plugin'),
        createGraphNode('b', 'test-plugin'),
        createGraphNode('isolated', 'test-plugin')
      ];
      const edges = [
        createGraphEdge('e1', 'a', 'b')
      ];
      const graph = createTestGraph(nodes, edges);

      const executor = new GraphExecutor();
      const sorted = executor.topologicalSort(graph);

      expect(sorted).toHaveLength(3);
      expect(sorted).toContain('a');
      expect(sorted).toContain('b');
      expect(sorted).toContain('isolated');
      // A must come before B
      expect(sorted.indexOf('a')).toBeLessThan(sorted.indexOf('b'));
    });

    it('handles empty graph', () => {
      const graph = createTestGraph([], []);

      const executor = new GraphExecutor();
      const sorted = executor.topologicalSort(graph);

      expect(sorted).toEqual([]);
    });

    it('handles graph with single node', () => {
      const nodes = [createGraphNode('single', 'test-plugin')];
      const graph = createTestGraph(nodes, []);

      const executor = new GraphExecutor();
      const sorted = executor.topologicalSort(graph);

      expect(sorted).toEqual(['single']);
    });
  });

  describe('cycle detection', () => {
    it('detects simple cycle A→B→A', () => {
      const nodes = [
        createGraphNode('a', 'test-plugin'),
        createGraphNode('b', 'test-plugin')
      ];
      const edges = [
        createGraphEdge('e1', 'a', 'b'),
        createGraphEdge('e2', 'b', 'a')
      ];
      const graph = createTestGraph(nodes, edges);

      const executor = new GraphExecutor();

      expect(() => {
        executor.topologicalSort(graph);
      }).toThrow(/cycle/i);
    });

    it('detects self-loop A→A', () => {
      const nodes = [createGraphNode('a', 'test-plugin')];
      const edges = [createGraphEdge('e1', 'a', 'a')];
      const graph = createTestGraph(nodes, edges);

      const executor = new GraphExecutor();

      expect(() => {
        executor.topologicalSort(graph);
      }).toThrow(/cycle/i);
    });

    it('detects complex cycle A→B→C→D→B', () => {
      const nodes = [
        createGraphNode('a', 'test-plugin'),
        createGraphNode('b', 'test-plugin'),
        createGraphNode('c', 'test-plugin'),
        createGraphNode('d', 'test-plugin')
      ];
      const edges = [
        createGraphEdge('e1', 'a', 'b'),
        createGraphEdge('e2', 'b', 'c'),
        createGraphEdge('e3', 'c', 'd'),
        createGraphEdge('e4', 'd', 'b') // Creates cycle
      ];
      const graph = createTestGraph(nodes, edges);

      const executor = new GraphExecutor();

      expect(() => {
        executor.topologicalSort(graph);
      }).toThrow(/cycle/i);
    });

    it('accepts acyclic graph with multiple paths', () => {
      const nodes = [
        createGraphNode('a', 'test-plugin'),
        createGraphNode('b', 'test-plugin'),
        createGraphNode('c', 'test-plugin')
      ];
      const edges = [
        createGraphEdge('e1', 'a', 'b'),
        createGraphEdge('e2', 'a', 'c'),
        createGraphEdge('e3', 'b', 'c')
      ];
      const graph = createTestGraph(nodes, edges);

      const executor = new GraphExecutor();

      // Should not throw
      const sorted = executor.topologicalSort(graph);
      expect(sorted).toHaveLength(3);
      expect(sorted[0]).toBe('a');
      expect(sorted[2]).toBe('c');
    });
  });

  describe('validateGraph', () => {
    it('accepts valid DAG', () => {
      const nodes = [
        createGraphNode('a', 'test-plugin'),
        createGraphNode('b', 'test-plugin')
      ];
      const edges = [
        createGraphEdge('e1', 'a', 'b')
      ];
      const graph = createTestGraph(nodes, edges);

      const executor = new GraphExecutor();
      const errors = executor.validateGraph(graph);

      expect(errors).toEqual([]);
    });

    it('detects edges referencing non-existent nodes', () => {
      const nodes = [createGraphNode('a', 'test-plugin')];
      const edges = [
        createGraphEdge('e1', 'a', 'nonexistent')
      ];
      const graph = createTestGraph(nodes, edges);

      const executor = new GraphExecutor();
      const errors = executor.validateGraph(graph);

      expect(errors.length).toBeGreaterThan(0);
      expect(errors.some(e => e.includes('nonexistent'))).toBe(true);
    });

    it('detects duplicate node IDs', () => {
      const nodes = [
        createGraphNode('a', 'test-plugin'),
        createGraphNode('a', 'test-plugin') // Duplicate ID
      ];
      const graph = createTestGraph(nodes, []);

      const executor = new GraphExecutor();
      const errors = executor.validateGraph(graph);

      expect(errors.length).toBeGreaterThan(0);
      expect(errors.some(e => e.includes('duplicate') || e.includes('Duplicate'))).toBe(true);
    });

    it('detects cycles during validation', () => {
      const nodes = [
        createGraphNode('a', 'test-plugin'),
        createGraphNode('b', 'test-plugin')
      ];
      const edges = [
        createGraphEdge('e1', 'a', 'b'),
        createGraphEdge('e2', 'b', 'a')
      ];
      const graph = createTestGraph(nodes, edges);

      const executor = new GraphExecutor();
      const errors = executor.validateGraph(graph);

      expect(errors.length).toBeGreaterThan(0);
      expect(errors.some(e => e.includes('cycle') || e.includes('Cycle'))).toBe(true);
    });
  });

  describe('getExecutionOrder', () => {
    it('returns execution order for valid graph', () => {
      const nodes = [
        createGraphNode('a', 'test-plugin'),
        createGraphNode('b', 'test-plugin'),
        createGraphNode('c', 'test-plugin')
      ];
      const edges = [
        createGraphEdge('e1', 'a', 'b'),
        createGraphEdge('e2', 'b', 'c')
      ];
      const graph = createTestGraph(nodes, edges);

      const executor = new GraphExecutor();
      const order = executor.getExecutionOrder(graph);

      expect(order).toEqual(['a', 'b', 'c']);
    });

    it('throws error for invalid graph', () => {
      const nodes = [
        createGraphNode('a', 'test-plugin'),
        createGraphNode('b', 'test-plugin')
      ];
      const edges = [
        createGraphEdge('e1', 'a', 'b'),
        createGraphEdge('e2', 'b', 'a')
      ];
      const graph = createTestGraph(nodes, edges);

      const executor = new GraphExecutor();

      expect(() => {
        executor.getExecutionOrder(graph);
      }).toThrow();
    });
  });

  describe('getDependencies', () => {
    it('returns direct dependencies for a node', () => {
      const nodes = [
        createGraphNode('a', 'test-plugin'),
        createGraphNode('b', 'test-plugin'),
        createGraphNode('c', 'test-plugin'),
        createGraphNode('d', 'test-plugin')
      ];
      const edges = [
        createGraphEdge('e1', 'a', 'd'),
        createGraphEdge('e2', 'b', 'd'),
        createGraphEdge('e3', 'c', 'd')
      ];
      const graph = createTestGraph(nodes, edges);

      const executor = new GraphExecutor();
      const deps = executor.getDependencies(graph, 'd');

      expect(deps.sort()).toEqual(['a', 'b', 'c']);
    });

    it('returns empty array for node with no dependencies', () => {
      const nodes = [
        createGraphNode('a', 'test-plugin'),
        createGraphNode('b', 'test-plugin')
      ];
      const edges = [
        createGraphEdge('e1', 'a', 'b')
      ];
      const graph = createTestGraph(nodes, edges);

      const executor = new GraphExecutor();
      const deps = executor.getDependencies(graph, 'a');

      expect(deps).toEqual([]);
    });

    it('returns empty array for isolated node', () => {
      const nodes = [createGraphNode('isolated', 'test-plugin')];
      const graph = createTestGraph(nodes, []);

      const executor = new GraphExecutor();
      const deps = executor.getDependencies(graph, 'isolated');

      expect(deps).toEqual([]);
    });
  });
});
