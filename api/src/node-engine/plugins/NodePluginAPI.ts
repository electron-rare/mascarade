/**
 * Node Plugin API - Universal interface for node-based execution engine
 *
 * Inspired by:
 * - ComfyUI: Typed ports with explicit input/output schemas
 * - Node-RED: Message passing and event-driven execution
 * - TouchDesigner: Typed connections and operator networks
 * - Max/MSP: Sync/async execution models
 */

/**
 * Node category taxonomy
 */
export enum NodeCategory {
  /** AI inference, LLM pipelines, model execution */
  AI = 'AI',
  /** Hardware control: ESP32, MIDI, DMX */
  Hardware = 'Hardware',
  /** Audio synthesis and processing (Tone.js) */
  Audio = 'Audio',
  /** CAD toolpath generation, G-code export */
  CAD = 'CAD',
  /** Logic, routing, control flow (if, switch, loop) */
  Workflow = 'Workflow',
  /** Triggers, schedules, webhooks, automation */
  Automation = 'Automation'
}

/**
 * Port data types for typed connections
 */
export type NodePortType =
  | 'string'
  | 'number'
  | 'boolean'
  | 'audio'
  | 'midi'
  | 'any';

/**
 * Node input/output port definition
 */
export interface NodePort {
  /** Unique port identifier (within the node) */
  id: string;
  /** Human-readable port label */
  label: string;
  /** Port data type (enforced during connection) */
  type: NodePortType;
  /** Whether this port must be connected for execution */
  required?: boolean;
  /** Default value when port is not connected */
  defaultValue?: unknown;
  /** Port description for documentation */
  description?: string;
}

/**
 * Execution context provided to nodes during graph execution
 *
 * Provides access to:
 * - Runtime state and message passing
 * - Graph execution metadata
 * - Logging and error reporting
 */
export interface ExecutionContext {
  /** Unique execution run ID */
  runId: string;
  /** Node instance ID in the graph */
  nodeId: string;
  /** Graph ID being executed */
  graphId: string;
  /** Emit execution state update (for real-time UI feedback) */
  emitState: (state: NodeExecutionState) => void;
  /** Log message during execution */
  log: (level: 'debug' | 'info' | 'warn' | 'error', message: string, meta?: Record<string, unknown>) => void;
  /** Abort signal for cancellation */
  signal?: AbortSignal;
  /** Shared execution state (isolated per run) */
  state: Map<string, unknown>;
}

/**
 * Node execution state for real-time feedback
 */
export type NodeExecutionState =
  | 'idle'
  | 'pending'
  | 'running'
  | 'complete'
  | 'error';

/**
 * Result of node execution
 */
export interface NodeExecutionResult {
  /** Output values keyed by port ID */
  outputs: Record<string, unknown>;
  /** Optional execution metadata (timing, resource usage, etc.) */
  meta?: Record<string, unknown>;
}

/**
 * Universal Node Plugin Interface
 *
 * All node plugins must implement this interface to be registered
 * and executed in the graph engine.
 *
 * Example:
 * ```typescript
 * const synthNode: NodePlugin = {
 *   id: 'tone-synth',
 *   category: NodeCategory.Audio,
 *   label: 'Tone.js Synth',
 *   description: 'Trigger synthesized audio notes',
 *   inputs: [
 *     { id: 'note', label: 'Note', type: 'string', required: true, defaultValue: 'C4' },
 *     { id: 'duration', label: 'Duration', type: 'string', defaultValue: '4n' }
 *   ],
 *   outputs: [
 *     { id: 'triggered', label: 'Triggered', type: 'boolean' }
 *   ],
 *   execute: async (inputs, context) => {
 *     // Execute synth logic
 *     return { outputs: { triggered: true } };
 *   }
 * };
 * ```
 */
export interface NodePlugin {
  /** Unique plugin identifier (used for registration) */
  id: string;
  /** Node category (determines palette grouping) */
  category: NodeCategory;
  /** Human-readable node label */
  label: string;
  /** Node description for documentation */
  description: string;
  /** Input port definitions */
  inputs: NodePort[];
  /** Output port definitions */
  outputs: NodePort[];

  /**
   * Core execution function
   *
   * Receives input values and execution context, returns output values.
   * Can be synchronous (for low-latency audio/logic nodes) or asynchronous
   * (for AI inference, network I/O, hardware control).
   *
   * @param inputs - Input values keyed by port ID
   * @param context - Execution context with runtime state and utilities
   * @returns Output values keyed by port ID, or full execution result
   *
   * @throws Error on execution failure (propagates to downstream nodes)
   */
  execute: (
    inputs: Record<string, unknown>,
    context: ExecutionContext
  ) => Promise<Record<string, unknown> | NodeExecutionResult> | Record<string, unknown> | NodeExecutionResult;

  /**
   * Lifecycle: Called when node is added to graph
   *
   * Use for:
   * - Resource initialization
   * - Hardware connection setup
   * - Persistent state allocation
   */
  onInit?: (context: ExecutionContext) => void | Promise<void>;

  /**
   * Lifecycle: Called when node is removed from graph
   *
   * Use for:
   * - Resource cleanup
   * - Hardware disconnection
   * - State persistence
   */
  onDestroy?: (context: ExecutionContext) => void | Promise<void>;

  /**
   * Lifecycle: Validate input values before execution
   *
   * Use for:
   * - Type coercion
   * - Range validation
   * - Complex constraints
   *
   * @param inputs - Input values to validate
   * @returns Validation errors (empty array if valid)
   */
  validate?: (inputs: Record<string, unknown>) => string[];

  /**
   * Plugin metadata
   */
  metadata?: {
    /** Plugin version (semver) */
    version?: string;
    /** Plugin author */
    author?: string;
    /** Plugin documentation URL */
    documentationUrl?: string;
    /** Plugin tags for search */
    tags?: string[];
    /** Whether plugin is experimental/unstable */
    experimental?: boolean;
  };
}

/**
 * Type guard to check if execution result is full result object
 */
export function isNodeExecutionResult(result: unknown): result is NodeExecutionResult {
  return (
    typeof result === 'object' &&
    result !== null &&
    'outputs' in result &&
    typeof (result as NodeExecutionResult).outputs === 'object'
  );
}

/**
 * Normalize execution result to standard format
 */
export function normalizeExecutionResult(
  result: Record<string, unknown> | NodeExecutionResult
): NodeExecutionResult {
  if (isNodeExecutionResult(result)) {
    return result;
  }
  return { outputs: result };
}
