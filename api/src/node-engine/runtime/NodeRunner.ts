/**
 * NodeRunner - Individual node execution wrapper
 *
 * Handles:
 * - Sync/async execution (both Promise and synchronous returns)
 * - Execution timeout enforcement
 * - Input validation
 * - State emission (pending → running → complete/error)
 * - Error handling and logging
 * - Performance tracking
 *
 * Inspired by:
 * - Max/MSP: Sync execution for audio paths, async for I/O
 * - ComfyUI: Queue-based execution with timeout handling
 * - Node-RED: Message passing with error propagation
 */

import type {
  NodePlugin,
  ExecutionContext,
  NodeExecutionResult
} from '../plugins/NodePluginAPI.js';
import { normalizeExecutionResult } from '../plugins/NodePluginAPI.js';
import type {
  NodeExecutionRecord,
  NodeExecutionOptions,
  ExecutionError
} from '../types/ExecutionTypes.js';
import { createExecutionError } from '../types/ExecutionTypes.js';

/**
 * NodeRunner - Executes a single node plugin
 *
 * Wraps node execution with:
 * - State management (idle → pending → running → complete/error)
 * - Timeout enforcement
 * - Input validation
 * - Error handling
 * - Performance tracking
 *
 * Usage:
 * ```typescript
 * const runner = new NodeRunner(plugin);
 * const result = await runner.execute(inputs, context, { timeout: 5000 });
 * ```
 */
export class NodeRunner {
  private plugin: NodePlugin;

  constructor(plugin: NodePlugin) {
    this.plugin = plugin;
  }

  /**
   * Execute the node with given inputs
   *
   * @param inputs - Input values keyed by port ID
   * @param context - Execution context
   * @param options - Execution options (timeout, validation)
   * @returns Node execution record with outputs and metadata
   *
   * @throws Error if execution fails (after emitting error state)
   */
  async execute(
    inputs: Record<string, unknown>,
    context: ExecutionContext,
    options?: NodeExecutionOptions
  ): Promise<NodeExecutionRecord> {
    const startTime = Date.now();
    const startedAt = new Date().toISOString();

    // Initialize execution record
    const record: NodeExecutionRecord = {
      nodeId: context.nodeId,
      pluginId: this.plugin.id,
      state: 'pending',
      inputs,
      startedAt
    };

    try {
      // Emit pending state
      context.emitState('pending');
      context.log('debug', `Node execution starting`, {
        pluginId: this.plugin.id,
        inputs
      });

      // Validate inputs
      if (!options?.skipValidation) {
        this.validateInputs(inputs, context);
      }

      // Check for abort signal
      if (context.signal?.aborted) {
        throw new Error('Execution aborted before node started');
      }

      // Emit running state
      context.emitState('running');
      record.state = 'running';

      // Execute with timeout
      const result = await this.executeWithTimeout(inputs, context, options?.timeout);

      // Calculate duration
      const completedAt = new Date().toISOString();
      const duration = Date.now() - startTime;

      // Update record with success
      record.state = 'complete';
      record.outputs = result.outputs;
      record.completedAt = completedAt;
      record.duration = duration;

      // Emit complete state
      context.emitState('complete');
      context.log('info', `Node execution completed`, {
        pluginId: this.plugin.id,
        duration,
        outputs: result.outputs
      });

      return record;

    } catch (error) {
      // Calculate duration even for errors
      const completedAt = new Date().toISOString();
      const duration = Date.now() - startTime;

      // Create structured error
      const executionError = this.createError(error, context);

      // Update record with error
      record.state = 'error';
      record.error = executionError;
      record.completedAt = completedAt;
      record.duration = duration;

      // Emit error state
      context.emitState('error');
      context.log('error', `Node execution failed: ${executionError.message}`, {
        pluginId: this.plugin.id,
        error: executionError,
        duration
      });

      // Re-throw to propagate error
      throw error;
    }
  }

  /**
   * Validate node inputs
   *
   * Checks:
   * - Required ports have values
   * - Custom plugin validation (if defined)
   *
   * @param inputs - Input values to validate
   * @param context - Execution context for logging
   * @throws Error if validation fails
   */
  private validateInputs(
    inputs: Record<string, unknown>,
    context: ExecutionContext
  ): void {
    // Check required ports
    for (const port of this.plugin.inputs) {
      if (port.required && !(port.id in inputs)) {
        // Use default value if available
        if (port.defaultValue !== undefined) {
          inputs[port.id] = port.defaultValue;
        } else {
          throw new Error(
            `Required input port '${port.id}' (${port.label}) is missing`
          );
        }
      }
    }

    // Apply default values for missing optional ports
    for (const port of this.plugin.inputs) {
      if (!(port.id in inputs) && port.defaultValue !== undefined) {
        inputs[port.id] = port.defaultValue;
      }
    }

    // Custom plugin validation
    if (this.plugin.validate) {
      const errors = this.plugin.validate(inputs);
      if (errors.length > 0) {
        throw new Error(
          `Input validation failed: ${errors.join(', ')}`
        );
      }
    }

    context.log('debug', 'Input validation passed', {
      pluginId: this.plugin.id
    });
  }

  /**
   * Execute node with timeout enforcement
   *
   * Handles both synchronous and asynchronous execute functions.
   * Uses Promise.race for timeout enforcement with AbortController.
   *
   * @param inputs - Input values
   * @param context - Execution context
   * @param timeout - Optional timeout in milliseconds
   * @returns Normalized execution result
   */
  private async executeWithTimeout(
    inputs: Record<string, unknown>,
    context: ExecutionContext,
    timeout?: number
  ): Promise<NodeExecutionResult> {
    // Execute the plugin (handles both sync and async)
    const executePromise = Promise.resolve(
      this.plugin.execute(inputs, context)
    );

    // No timeout - execute directly
    if (!timeout) {
      // Check abort signal before returning
      if (context.signal?.aborted) {
        throw new Error('Execution aborted');
      }
      const result = await executePromise;
      return normalizeExecutionResult(result);
    }

    // Create timeout promise
    const timeoutPromise = new Promise<never>((_, reject) => {
      setTimeout(() => {
        reject(new Error(
          `Node execution timed out after ${timeout}ms`
        ));
      }, timeout);
    });

    // Create abort promise (if signal provided)
    let abortPromise: Promise<never> | null = null;
    if (context.signal) {
      abortPromise = new Promise<never>((_, reject) => {
        const onAbort = () => {
          reject(new Error('Execution aborted'));
        };
        context.signal!.addEventListener('abort', onAbort, { once: true });
      });
    }

    // Race execution against timeout and abort
    const promises = abortPromise
      ? [executePromise, timeoutPromise, abortPromise]
      : [executePromise, timeoutPromise];

    const result = await Promise.race(promises);
    return normalizeExecutionResult(result);
  }

  /**
   * Create structured execution error from thrown error
   *
   * @param error - Thrown error (Error or unknown)
   * @param context - Execution context
   * @returns Structured execution error
   */
  private createError(
    error: unknown,
    context: ExecutionContext
  ): ExecutionError {
    const message = error instanceof Error ? error.message : String(error);
    const stack = error instanceof Error ? error.stack : undefined;

    // Extract error code if available
    const code = (error as any)?.code;

    return createExecutionError(message, {
      code,
      nodeId: context.nodeId,
      pluginId: this.plugin.id,
      stack,
      extra: {
        errorType: error instanceof Error ? error.constructor.name : typeof error
      }
    });
  }

  /**
   * Get plugin metadata
   *
   * @returns Node plugin instance
   */
  getPlugin(): NodePlugin {
    return this.plugin;
  }

  /**
   * Execute lifecycle: onInit
   *
   * Called when node is added to graph.
   *
   * @param context - Execution context
   */
  async init(context: ExecutionContext): Promise<void> {
    if (this.plugin.onInit) {
      context.log('debug', 'Initializing node', {
        pluginId: this.plugin.id
      });
      await Promise.resolve(this.plugin.onInit(context));
    }
  }

  /**
   * Execute lifecycle: onDestroy
   *
   * Called when node is removed from graph.
   *
   * @param context - Execution context
   */
  async destroy(context: ExecutionContext): Promise<void> {
    if (this.plugin.onDestroy) {
      context.log('debug', 'Destroying node', {
        pluginId: this.plugin.id
      });
      await Promise.resolve(this.plugin.onDestroy(context));
    }
  }
}
