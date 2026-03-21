/**
 * Execution Types - Runtime execution state and messaging
 *
 * These types describe the execution runtime behavior:
 * - Graph execution lifecycle
 * - Real-time execution events (for WebSocket)
 * - Execution errors and diagnostics
 * - Execution configuration and options
 *
 * Complementary to ExecutionContext in NodePluginAPI.ts
 */

import type { NodeExecutionState } from '../plugins/NodePluginAPI';

/**
 * Overall graph execution status
 */
export type GraphExecutionStatus =
  | 'idle'        // Graph not executing
  | 'preparing'   // Topological sort, validation
  | 'running'     // Executing nodes
  | 'paused'      // Execution paused (for debugging)
  | 'completed'   // All nodes executed successfully
  | 'failed'      // Execution stopped due to error
  | 'cancelled';  // Execution cancelled by user

/**
 * Graph execution result
 *
 * Returned when a graph execution completes (success or failure).
 */
export interface GraphExecutionResult {
  /** Execution run ID */
  runId: string;
  /** Graph ID that was executed */
  graphId: string;
  /** Final execution status */
  status: GraphExecutionStatus;
  /** Execution start time */
  startedAt: string;
  /** Execution end time */
  completedAt: string;
  /** Total execution duration (ms) */
  duration: number;
  /** Per-node execution results */
  nodeResults: Map<string, NodeExecutionRecord>;
  /** Execution error (if failed) */
  error?: ExecutionError;
  /** Execution metadata */
  metadata?: Record<string, unknown>;
}

/**
 * Node execution record
 *
 * Tracks execution state and outputs for a single node instance.
 */
export interface NodeExecutionRecord {
  /** Node instance ID */
  nodeId: string;
  /** Plugin ID */
  pluginId: string;
  /** Execution state */
  state: NodeExecutionState;
  /** Node inputs (resolved values) */
  inputs: Record<string, unknown>;
  /** Node outputs (from execute function) */
  outputs?: Record<string, unknown>;
  /** Execution start time */
  startedAt?: string;
  /** Execution end time */
  completedAt?: string;
  /** Execution duration (ms) */
  duration?: number;
  /** Execution error (if any) */
  error?: ExecutionError;
  /** Execution logs */
  logs?: ExecutionLog[];
}

/**
 * Execution error
 *
 * Structured error information for debugging and display.
 */
export interface ExecutionError {
  /** Error message */
  message: string;
  /** Error code (for programmatic handling) */
  code?: string;
  /** Node ID where error occurred */
  nodeId?: string;
  /** Plugin ID where error occurred */
  pluginId?: string;
  /** Stack trace (for debugging) */
  stack?: string;
  /** Additional error context */
  context?: Record<string, unknown>;
  /** Timestamp */
  timestamp: string;
}

/**
 * Execution log entry
 */
export interface ExecutionLog {
  /** Log level */
  level: 'debug' | 'info' | 'warn' | 'error';
  /** Log message */
  message: string;
  /** Timestamp */
  timestamp: string;
  /** Node ID (if node-specific log) */
  nodeId?: string;
  /** Additional metadata */
  meta?: Record<string, unknown>;
}

/**
 * Real-time execution event
 *
 * Sent via WebSocket to update UI during graph execution.
 */
export type ExecutionEvent =
  | GraphStartedEvent
  | GraphCompletedEvent
  | GraphFailedEvent
  | NodeStateChangedEvent
  | NodeOutputEvent
  | NodeErrorEvent
  | ExecutionLogEvent;

/**
 * Graph execution started event
 */
export interface GraphStartedEvent {
  type: 'graph.started';
  runId: string;
  graphId: string;
  timestamp: string;
  /** Number of nodes to execute */
  nodeCount: number;
  /** Execution order (topologically sorted node IDs) */
  executionOrder: string[];
}

/**
 * Graph execution completed event
 */
export interface GraphCompletedEvent {
  type: 'graph.completed';
  runId: string;
  graphId: string;
  timestamp: string;
  duration: number;
  /** Number of nodes executed successfully */
  successCount: number;
}

/**
 * Graph execution failed event
 */
export interface GraphFailedEvent {
  type: 'graph.failed';
  runId: string;
  graphId: string;
  timestamp: string;
  error: ExecutionError;
}

/**
 * Node execution state changed event
 */
export interface NodeStateChangedEvent {
  type: 'node.state';
  runId: string;
  nodeId: string;
  pluginId: string;
  state: NodeExecutionState;
  timestamp: string;
}

/**
 * Node produced output event
 */
export interface NodeOutputEvent {
  type: 'node.output';
  runId: string;
  nodeId: string;
  pluginId: string;
  outputs: Record<string, unknown>;
  timestamp: string;
  duration: number;
}

/**
 * Node execution error event
 */
export interface NodeErrorEvent {
  type: 'node.error';
  runId: string;
  nodeId: string;
  pluginId: string;
  error: ExecutionError;
  timestamp: string;
}

/**
 * Execution log event
 */
export interface ExecutionLogEvent {
  type: 'execution.log';
  runId: string;
  log: ExecutionLog;
}

/**
 * Graph execution configuration
 */
export interface ExecutionConfig {
  /** Maximum execution time per node (ms) */
  nodeTimeout?: number;
  /** Maximum total graph execution time (ms) */
  graphTimeout?: number;
  /** Whether to stop on first error */
  stopOnError?: boolean;
  /** Whether to skip validation */
  skipValidation?: boolean;
  /** Execution mode */
  mode?: 'normal' | 'debug' | 'dry-run';
  /** Abort signal for cancellation */
  signal?: AbortSignal;
  /** Initial execution state (for resuming) */
  initialState?: Map<string, unknown>;
}

/**
 * Execution options for single node
 */
export interface NodeExecutionOptions {
  /** Input value overrides */
  inputOverrides?: Record<string, unknown>;
  /** Execution timeout (ms) */
  timeout?: number;
  /** Skip validation */
  skipValidation?: boolean;
  /** Abort signal */
  signal?: AbortSignal;
}

/**
 * Type guard for execution events
 */
export function isExecutionEvent(event: unknown): event is ExecutionEvent {
  return (
    typeof event === 'object' &&
    event !== null &&
    'type' in event &&
    typeof (event as { type: unknown }).type === 'string'
  );
}

/**
 * Type guard for graph execution result
 */
export function isGraphExecutionResult(result: unknown): result is GraphExecutionResult {
  return (
    typeof result === 'object' &&
    result !== null &&
    'runId' in result &&
    'status' in result &&
    'nodeResults' in result
  );
}

/**
 * Create execution error
 *
 * @param message - Error message
 * @param context - Additional context
 * @returns Structured execution error
 */
export function createExecutionError(
  message: string,
  context?: {
    code?: string;
    nodeId?: string;
    pluginId?: string;
    stack?: string;
    extra?: Record<string, unknown>;
  }
): ExecutionError {
  return {
    message,
    code: context?.code,
    nodeId: context?.nodeId,
    pluginId: context?.pluginId,
    stack: context?.stack,
    context: context?.extra,
    timestamp: new Date().toISOString()
  };
}

/**
 * Create execution log entry
 *
 * @param level - Log level
 * @param message - Log message
 * @param context - Additional context
 * @returns Execution log entry
 */
export function createExecutionLog(
  level: 'debug' | 'info' | 'warn' | 'error',
  message: string,
  context?: {
    nodeId?: string;
    meta?: Record<string, unknown>;
  }
): ExecutionLog {
  return {
    level,
    message,
    timestamp: new Date().toISOString(),
    nodeId: context?.nodeId,
    meta: context?.meta
  };
}
