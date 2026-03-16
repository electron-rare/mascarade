/**
 * ExecutionContext - Message passing and state management for node execution
 *
 * Provides:
 * - Isolated execution contexts for concurrent graph runs
 * - Message passing via shared state map
 * - Execution logging and diagnostics
 * - Real-time state emission for UI updates
 * - Abort signal support for cancellation
 *
 * Inspired by:
 * - Node-RED: Message passing pattern with `msg` object
 * - ComfyUI: Execution queue with isolated state
 * - TouchDesigner: Operator execution context
 */

import type { ExecutionContext, NodeExecutionState } from '../plugins/NodePluginAPI.js';
import type { ExecutionLog, ExecutionEvent } from '../types/ExecutionTypes.js';
import { createExecutionLog } from '../types/ExecutionTypes.js';

/**
 * Execution context factory and manager
 *
 * Creates isolated execution contexts for concurrent graph executions.
 * Each context maintains its own state, logs, and event emitters.
 *
 * Usage:
 * ```typescript
 * const manager = new ExecutionContextManager();
 * const context = manager.createContext('run-123', 'node-abc', 'graph-xyz');
 * context.log('info', 'Node starting');
 * context.state.set('result', 42);
 * ```
 */
export class ExecutionContextManager {
  private contexts: Map<string, ExecutionContextData> = new Map();

  /**
   * Create a new isolated execution context
   *
   * @param runId - Unique execution run ID
   * @param nodeId - Node instance ID
   * @param graphId - Graph ID being executed
   * @param options - Optional configuration
   * @returns Isolated execution context for the node
   */
  createContext(
    runId: string,
    nodeId: string,
    graphId: string,
    options?: ExecutionContextOptions
  ): ExecutionContext {
    // Get or create execution data for this run
    let runData = this.contexts.get(runId);
    if (!runData) {
      runData = {
        runId,
        graphId,
        state: new Map<string, unknown>(),
        logs: [],
        eventEmitter: options?.eventEmitter,
        abortController: new AbortController()
      };
      this.contexts.set(runId, runData);
    }

    // Create context for this specific node
    const context: ExecutionContext = {
      runId,
      nodeId,
      graphId,
      state: runData.state,
      signal: runData.abortController.signal,

      emitState: (state: NodeExecutionState) => {
        if (runData.eventEmitter) {
          const event: ExecutionEvent = {
            type: 'node.state',
            runId,
            nodeId,
            pluginId: options?.pluginId || 'unknown',
            state,
            timestamp: new Date().toISOString()
          };
          runData.eventEmitter(event);
        }
      },

      log: (level, message, meta) => {
        const log = createExecutionLog(level, message, { nodeId, meta });
        runData.logs.push(log);

        // Emit log event for real-time updates
        if (runData.eventEmitter) {
          const event: ExecutionEvent = {
            type: 'execution.log',
            runId,
            log
          };
          runData.eventEmitter(event);
        }
      }
    };

    return context;
  }

  /**
   * Get execution state for a run
   *
   * @param runId - Execution run ID
   * @returns Execution state map, or undefined if run doesn't exist
   */
  getState(runId: string): Map<string, unknown> | undefined {
    return this.contexts.get(runId)?.state;
  }

  /**
   * Get execution logs for a run
   *
   * @param runId - Execution run ID
   * @returns Array of execution logs
   */
  getLogs(runId: string): ExecutionLog[] {
    return this.contexts.get(runId)?.logs || [];
  }

  /**
   * Abort an execution
   *
   * Triggers the abort signal for all nodes in the execution.
   *
   * @param runId - Execution run ID
   * @returns true if execution was aborted, false if run doesn't exist
   */
  abort(runId: string): boolean {
    const runData = this.contexts.get(runId);
    if (!runData) {
      return false;
    }

    runData.abortController.abort();
    return true;
  }

  /**
   * Check if an execution has been aborted
   *
   * @param runId - Execution run ID
   * @returns true if execution is aborted
   */
  isAborted(runId: string): boolean {
    return this.contexts.get(runId)?.abortController.signal.aborted || false;
  }

  /**
   * Clean up execution context
   *
   * Removes all state and logs for a completed execution.
   * Should be called after execution completes to prevent memory leaks.
   *
   * @param runId - Execution run ID
   * @returns true if context was cleaned up, false if run doesn't exist
   */
  cleanup(runId: string): boolean {
    return this.contexts.delete(runId);
  }

  /**
   * Get all active execution run IDs
   *
   * @returns Array of active run IDs
   */
  getActiveRuns(): string[] {
    return Array.from(this.contexts.keys());
  }

  /**
   * Get number of active executions
   *
   * @returns Count of active executions
   */
  getActiveCount(): number {
    return this.contexts.size;
  }

  /**
   * Clean up all execution contexts
   *
   * Useful for testing and shutdown.
   */
  cleanupAll(): void {
    this.contexts.clear();
  }
}

/**
 * Internal execution context data
 *
 * Stores shared state for an entire graph execution run.
 */
interface ExecutionContextData {
  /** Execution run ID */
  runId: string;
  /** Graph ID */
  graphId: string;
  /** Shared execution state (message passing between nodes) */
  state: Map<string, unknown>;
  /** Execution logs */
  logs: ExecutionLog[];
  /** Event emitter for real-time updates */
  eventEmitter?: ExecutionEventEmitter;
  /** Abort controller for cancellation */
  abortController: AbortController;
}

/**
 * Execution event emitter function type
 */
export type ExecutionEventEmitter = (event: ExecutionEvent) => void;

/**
 * Options for creating an execution context
 */
export interface ExecutionContextOptions {
  /** Plugin ID (for event emission) */
  pluginId?: string;
  /** Event emitter for real-time updates */
  eventEmitter?: ExecutionEventEmitter;
  /** Initial state (for resuming executions) */
  initialState?: Map<string, unknown>;
}
