/**
 * End-to-End Test: Graph Save/Load Roundtrip
 *
 * Verifies that a graph with 3+ nodes and edges can be saved via
 * the persistence API, then loaded back with all data intact.
 * Tests the full create → read → list → update → delete lifecycle.
 */

import { describe, expect, it, beforeEach, afterEach } from 'vitest';
import { promises as fs } from 'node:fs';
import { join } from 'node:path';
import { Hono } from 'hono';
import { nodeEngine } from '../../../routes/node-engine.js';
import { NodeCategory } from '../../plugins/NodePluginAPI.js';
import type { GraphNode, GraphEdge } from '../../types/NodeTypes.js';

const TEST_GRAPHS_DIR = join(process.cwd(), 'data', 'node-engine', 'graphs');

function createTestNode(id: string, pluginId: string, x: number, y: number): GraphNode {
  return {
    id,
    type: pluginId,
    position: { x, y },
    data: {
      pluginId,
      label: `Test ${id}`,
      category: NodeCategory.Workflow,
      inputValues: { threshold: 0.5 },
      executionState: 'idle'
    }
  };
}

function createTestEdge(source: string, target: string, sourceHandle = 'output', targetHandle = 'input'): GraphEdge {
  return {
    id: `${source}-${target}`,
    source,
    sourceHandle,
    target,
    targetHandle
  };
}

describe('End-to-End: Graph Save/Load Roundtrip', () => {
  let app: Hono;
  const graphId = 'test-graph';
  const savedIds: string[] = [];

  const testNodes: GraphNode[] = [
    createTestNode('node-1', 'workflow-trigger', 0, 0),
    createTestNode('node-2', 'ai-llm-inference', 250, 0),
    createTestNode('node-3', 'workflow-logger', 500, 0),
    createTestNode('node-4', 'workflow-condition', 250, 150),
  ];

  const testEdges: GraphEdge[] = [
    createTestEdge('node-1', 'node-2'),
    createTestEdge('node-2', 'node-3'),
    createTestEdge('node-1', 'node-4'),
  ];

  beforeEach(() => {
    app = new Hono();
    app.route('/api/node-engine', nodeEngine);
  });

  afterEach(async () => {
    // Clean up test graph files
    for (const id of savedIds) {
      try {
        await fs.unlink(join(TEST_GRAPHS_DIR, `${id}.json`));
      } catch {
        // ignore
      }
    }
    savedIds.length = 0;
  });

  it('saves a graph with 4 nodes and 3 edges via POST', async () => {
    const res = await app.request('/api/node-engine/graphs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        id: graphId,
        name: 'test-graph',
        description: 'E2E roundtrip test',
        nodes: testNodes,
        edges: testEdges,
      }),
    });

    expect(res.status).toBe(201);
    const body = await res.json();
    savedIds.push(body.id);

    expect(body.id).toBe(graphId);
    expect(body.name).toBe('test-graph');
    expect(body.nodes).toHaveLength(4);
    expect(body.edges).toHaveLength(3);
    expect(body.metadata.nodes_count).toBe(4);
    expect(body.metadata.edges_count).toBe(3);
  });

  it('loads the saved graph via GET and verifies all data intact', async () => {
    // Save
    const createRes = await app.request('/api/node-engine/graphs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        id: graphId,
        name: 'test-graph',
        description: 'E2E roundtrip test',
        nodes: testNodes,
        edges: testEdges,
      }),
    });
    expect(createRes.status).toBe(201);
    savedIds.push(graphId);

    // Load
    const loadRes = await app.request(`/api/node-engine/graphs/${graphId}`);
    expect(loadRes.status).toBe(200);
    const loaded = await loadRes.json();

    // Verify structure
    expect(loaded.id).toBe(graphId);
    expect(loaded.name).toBe('test-graph');
    expect(loaded.description).toBe('E2E roundtrip test');
    expect(loaded.nodes).toHaveLength(4);
    expect(loaded.edges).toHaveLength(3);

    // Verify node data preserved exactly
    for (let i = 0; i < testNodes.length; i++) {
      const original = testNodes[i];
      const restored = loaded.nodes[i];
      expect(restored.id).toBe(original.id);
      expect(restored.type).toBe(original.type);
      expect(restored.position).toEqual(original.position);
      expect(restored.data.pluginId).toBe(original.data.pluginId);
      expect(restored.data.label).toBe(original.data.label);
      expect(restored.data.inputValues).toEqual(original.data.inputValues);
      expect(restored.data.executionState).toBe(original.data.executionState);
    }

    // Verify edge data preserved exactly
    for (let i = 0; i < testEdges.length; i++) {
      const original = testEdges[i];
      const restored = loaded.edges[i];
      expect(restored.id).toBe(original.id);
      expect(restored.source).toBe(original.source);
      expect(restored.sourceHandle).toBe(original.sourceHandle);
      expect(restored.target).toBe(original.target);
      expect(restored.targetHandle).toBe(original.targetHandle);
    }
  });

  it('lists saved graphs and finds the test graph', async () => {
    // Save
    const createRes = await app.request('/api/node-engine/graphs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        id: graphId,
        name: 'test-graph',
        nodes: testNodes,
        edges: testEdges,
      }),
    });
    expect(createRes.status).toBe(201);
    savedIds.push(graphId);

    // List
    const listRes = await app.request('/api/node-engine/graphs');
    expect(listRes.status).toBe(200);
    const listBody = await listRes.json();

    expect(listBody.total).toBeGreaterThanOrEqual(1);
    const found = listBody.graphs.find((g: { id: string }) => g.id === graphId);
    expect(found).toBeDefined();
    expect(found.name).toBe('test-graph');
    expect(found.nodes_count).toBe(4);
    expect(found.edges_count).toBe(3);
  });

  it('updates a saved graph and verifies changes persist', async () => {
    // Save
    await app.request('/api/node-engine/graphs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        id: graphId,
        name: 'test-graph',
        nodes: testNodes,
        edges: testEdges,
      }),
    });
    savedIds.push(graphId);

    // Add a 5th node and update
    const updatedNodes = [
      ...testNodes,
      createTestNode('node-5', 'audio-synth', 500, 150),
    ];
    const updatedEdges = [
      ...testEdges,
      createTestEdge('node-4', 'node-5'),
    ];

    const updateRes = await app.request(`/api/node-engine/graphs/${graphId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: 'test-graph-updated',
        nodes: updatedNodes,
        edges: updatedEdges,
      }),
    });
    expect(updateRes.status).toBe(200);

    // Reload and verify
    const loadRes = await app.request(`/api/node-engine/graphs/${graphId}`);
    const loaded = await loadRes.json();

    expect(loaded.name).toBe('test-graph-updated');
    expect(loaded.nodes).toHaveLength(5);
    expect(loaded.edges).toHaveLength(4);
    expect(loaded.metadata.nodes_count).toBe(5);
    expect(loaded.metadata.edges_count).toBe(4);
  });

  it('deletes a graph and verifies it is gone', async () => {
    // Save
    await app.request('/api/node-engine/graphs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        id: graphId,
        name: 'test-graph',
        nodes: testNodes,
        edges: testEdges,
      }),
    });
    // Don't add to savedIds since we're deleting it

    // Delete
    const deleteRes = await app.request(`/api/node-engine/graphs/${graphId}`, {
      method: 'DELETE',
    });
    expect(deleteRes.status).toBe(200);

    // Verify gone
    const loadRes = await app.request(`/api/node-engine/graphs/${graphId}`);
    expect(loadRes.status).toBe(404);
  });

  it('full roundtrip: create → load → verify graph is executable', async () => {
    // Create graph
    const createRes = await app.request('/api/node-engine/graphs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        id: graphId,
        name: 'test-graph',
        nodes: testNodes,
        edges: testEdges,
      }),
    });
    expect(createRes.status).toBe(201);
    savedIds.push(graphId);

    // Load graph
    const loadRes = await app.request(`/api/node-engine/graphs/${graphId}`);
    const loaded = await loadRes.json();

    // Verify loaded graph can be validated by GraphExecutor
    const { GraphExecutor } = await import('../GraphExecutor.js');
    const executor = new GraphExecutor();

    // Convert REST API format to NodeGraph format for executor
    const graphForExecution = {
      id: loaded.id,
      name: loaded.name,
      nodes: loaded.nodes,
      edges: loaded.edges,
      createdAt: loaded.metadata.created_at,
      updatedAt: loaded.metadata.updated_at,
    };

    const errors = executor.validateGraph(graphForExecution);
    expect(errors).toEqual([]);

    // Verify topological order is valid
    const order = executor.getExecutionOrder(graphForExecution);
    expect(order).toHaveLength(4);

    // node-1 must come before node-2, node-3, and node-4
    const idx1 = order.indexOf('node-1');
    const idx2 = order.indexOf('node-2');
    const idx3 = order.indexOf('node-3');
    const idx4 = order.indexOf('node-4');

    expect(idx1).toBeLessThan(idx2);
    expect(idx2).toBeLessThan(idx3);
    expect(idx1).toBeLessThan(idx4);
  });

  it('rejects duplicate graph IDs on save', async () => {
    // Save first
    await app.request('/api/node-engine/graphs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        id: graphId,
        name: 'test-graph',
        nodes: testNodes,
        edges: testEdges,
      }),
    });
    savedIds.push(graphId);

    // Try to save again with same ID
    const res = await app.request('/api/node-engine/graphs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        id: graphId,
        name: 'test-graph-duplicate',
        nodes: [],
        edges: [],
      }),
    });
    expect(res.status).toBe(409);
  });

  it('returns 404 for non-existent graph', async () => {
    const res = await app.request('/api/node-engine/graphs/does-not-exist');
    expect(res.status).toBe(404);
  });
});
