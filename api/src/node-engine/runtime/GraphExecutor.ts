/**
 * GraphExecutor - Topological graph execution engine
 *
 * Provides:
 * - Topological sort for execution order
 * - Cycle detection (rejects cyclic graphs)
 * - DAG validation
 * - Dependency analysis
 *
 * Inspired by:
 * - ComfyUI: Queue-based execution with topological ordering
 * - Node-RED: Flow execution with dependency resolution
 * - TouchDesigner: Operator network execution order
 */

import type { NodeGraph } from '../types/NodeTypes.js';

/**
 * GraphExecutor
 *
 * Analyzes node graphs and determines execution order using topological sort.
 * Detects and rejects cyclic graphs that would cause infinite loops.
 *
 * Usage:
 * ```typescript
 * const executor = new GraphExecutor();
 * const executionOrder = executor.getExecutionOrder(graph);
 * // executionOrder: ['nodeA', 'nodeB', 'nodeC']
 * ```
 */
export class GraphExecutor {
  /**
   * Validate graph structure
   *
   * Checks for:
   * - Duplicate node IDs
   * - Edges referencing non-existent nodes
   * - Cycles in the graph
   *
   * @param graph - Graph to validate
   * @returns Array of validation error messages (empty if valid)
   */
  validateGraph(graph: NodeGraph): string[] {
    const errors: string[] = [];

    // Validate node IDs are unique
    const nodeIds = new Set<string>();
    for (const node of graph.nodes) {
      if (nodeIds.has(node.id)) {
        errors.push(`Duplicate node ID: ${node.id}`);
      }
      nodeIds.add(node.id);
    }

    // Validate edges reference existing nodes
    for (const edge of graph.edges) {
      if (!nodeIds.has(edge.source)) {
        errors.push(`Edge ${edge.id} references non-existent source node: ${edge.source}`);
      }
      if (!nodeIds.has(edge.target)) {
        errors.push(`Edge ${edge.id} references non-existent target node: ${edge.target}`);
      }
    }

    // Validate graph is acyclic (no cycles)
    try {
      this.topologicalSort(graph);
    } catch (error) {
      if (error instanceof Error && error.message.toLowerCase().includes('cycle')) {
        errors.push(`Graph contains cycle: ${error.message}`);
      }
    }

    return errors;
  }

  /**
   * Get execution order for graph
   *
   * Validates the graph and returns topological sort order.
   *
   * @param graph - Graph to execute
   * @returns Array of node IDs in execution order
   * @throws Error if graph is invalid or contains cycles
   */
  getExecutionOrder(graph: NodeGraph): string[] {
    const errors = this.validateGraph(graph);
    if (errors.length > 0) {
      throw new Error(`Invalid graph: ${errors.join(', ')}`);
    }

    return this.topologicalSort(graph);
  }

  /**
   * Topological sort using Kahn's algorithm
   *
   * Returns nodes in dependency order (upstream nodes before downstream).
   * Detects and rejects cyclic graphs.
   *
   * Algorithm:
   * 1. Calculate in-degree (number of incoming edges) for each node
   * 2. Start with nodes that have in-degree 0 (no dependencies)
   * 3. Process each node, decrementing in-degree of downstream nodes
   * 4. If all nodes processed, return sorted order
   * 5. If nodes remain with non-zero in-degree, graph has cycle
   *
   * @param graph - Graph to sort
   * @returns Array of node IDs in topological order
   * @throws Error if graph contains cycle
   */
  topologicalSort(graph: NodeGraph): string[] {
    const { nodes, edges } = graph;

    // Handle empty graph
    if (nodes.length === 0) {
      return [];
    }

    // Build adjacency list and in-degree map
    const adjacencyList = new Map<string, string[]>();
    const inDegree = new Map<string, number>();

    // Initialize all nodes with in-degree 0
    for (const node of nodes) {
      adjacencyList.set(node.id, []);
      inDegree.set(node.id, 0);
    }

    // Build graph structure from edges
    for (const edge of edges) {
      // Add edge to adjacency list
      const neighbors = adjacencyList.get(edge.source) || [];
      neighbors.push(edge.target);
      adjacencyList.set(edge.source, neighbors);

      // Increment in-degree for target node
      inDegree.set(edge.target, (inDegree.get(edge.target) || 0) + 1);
    }

    // Find all nodes with in-degree 0 (no dependencies)
    const queue: string[] = [];
    for (const [nodeId, degree] of inDegree.entries()) {
      if (degree === 0) {
        queue.push(nodeId);
      }
    }

    // Process nodes in topological order
    const sorted: string[] = [];
    while (queue.length > 0) {
      // Remove node from queue and add to sorted list
      const nodeId = queue.shift()!;
      sorted.push(nodeId);

      // Process all neighbors (downstream nodes)
      const neighbors = adjacencyList.get(nodeId) || [];
      for (const neighbor of neighbors) {
        // Decrement in-degree of neighbor
        const newDegree = (inDegree.get(neighbor) || 0) - 1;
        inDegree.set(neighbor, newDegree);

        // If in-degree reaches 0, add to queue
        if (newDegree === 0) {
          queue.push(neighbor);
        }
      }
    }

    // Check if all nodes were processed
    if (sorted.length !== nodes.length) {
      // Some nodes have non-zero in-degree, indicating a cycle
      const remainingNodes = nodes
        .filter(node => !sorted.includes(node.id))
        .map(node => node.id);

      throw new Error(
        `Graph contains cycle. Nodes involved: ${remainingNodes.join(', ')}`
      );
    }

    return sorted;
  }

  /**
   * Get direct dependencies for a node
   *
   * Returns all nodes that must execute before the given node
   * (i.e., all nodes with edges pointing to the target node).
   *
   * @param graph - Graph containing the node
   * @param nodeId - Target node ID
   * @returns Array of node IDs that are direct dependencies
   */
  getDependencies(graph: NodeGraph, nodeId: string): string[] {
    const dependencies: string[] = [];

    // Find all edges where target is the given node
    for (const edge of graph.edges) {
      if (edge.target === nodeId) {
        dependencies.push(edge.source);
      }
    }

    return dependencies;
  }

  /**
   * Get direct dependents for a node
   *
   * Returns all nodes that depend on the given node
   * (i.e., all nodes with edges coming from the source node).
   *
   * @param graph - Graph containing the node
   * @param nodeId - Source node ID
   * @returns Array of node IDs that depend on this node
   */
  getDependents(graph: NodeGraph, nodeId: string): string[] {
    const dependents: string[] = [];

    // Find all edges where source is the given node
    for (const edge of graph.edges) {
      if (edge.source === nodeId) {
        dependents.push(edge.target);
      }
    }

    return dependents;
  }

  /**
   * Check if graph contains a cycle
   *
   * Uses topological sort to detect cycles.
   *
   * @param graph - Graph to check
   * @returns true if graph contains a cycle, false otherwise
   */
  hasCycle(graph: NodeGraph): boolean {
    try {
      this.topologicalSort(graph);
      return false;
    } catch (error) {
      if (error instanceof Error && error.message.toLowerCase().includes('cycle')) {
        return true;
      }
      throw error;
    }
  }

  /**
   * Get all root nodes (nodes with no dependencies)
   *
   * These are the nodes that should execute first.
   *
   * @param graph - Graph to analyze
   * @returns Array of node IDs with no incoming edges
   */
  getRootNodes(graph: NodeGraph): string[] {
    const nodesWithIncomingEdges = new Set<string>();

    for (const edge of graph.edges) {
      nodesWithIncomingEdges.add(edge.target);
    }

    return graph.nodes
      .filter(node => !nodesWithIncomingEdges.has(node.id))
      .map(node => node.id);
  }

  /**
   * Get all leaf nodes (nodes with no dependents)
   *
   * These are the nodes that execute last.
   *
   * @param graph - Graph to analyze
   * @returns Array of node IDs with no outgoing edges
   */
  getLeafNodes(graph: NodeGraph): string[] {
    const nodesWithOutgoingEdges = new Set<string>();

    for (const edge of graph.edges) {
      nodesWithOutgoingEdges.add(edge.source);
    }

    return graph.nodes
      .filter(node => !nodesWithOutgoingEdges.has(node.id))
      .map(node => node.id);
  }

  /**
   * Get execution depth for each node
   *
   * Depth is the longest path from any root node to the given node.
   * Nodes at the same depth can potentially execute in parallel.
   *
   * @param graph - Graph to analyze
   * @returns Map of node ID to execution depth
   */
  getExecutionDepth(graph: NodeGraph): Map<string, number> {
    const sorted = this.topologicalSort(graph);
    const depth = new Map<string, number>();

    // Initialize all nodes with depth 0
    for (const node of graph.nodes) {
      depth.set(node.id, 0);
    }

    // Process nodes in topological order
    for (const nodeId of sorted) {
      const currentDepth = depth.get(nodeId) || 0;

      // Update depth of all dependents
      const dependents = this.getDependents(graph, nodeId);
      for (const dependent of dependents) {
        const dependentDepth = depth.get(dependent) || 0;
        depth.set(dependent, Math.max(dependentDepth, currentDepth + 1));
      }
    }

    return depth;
  }

  /**
   * Get nodes grouped by execution level
   *
   * Nodes at the same level can execute in parallel.
   *
   * @param graph - Graph to analyze
   * @returns Array of arrays, where each sub-array contains nodes at the same level
   */
  getExecutionLevels(graph: NodeGraph): string[][] {
    const depthMap = this.getExecutionDepth(graph);
    const levels: string[][] = [];

    // Group nodes by depth
    for (const [nodeId, depth] of depthMap.entries()) {
      if (!levels[depth]) {
        levels[depth] = [];
      }
      levels[depth].push(nodeId);
    }

    return levels;
  }
}
