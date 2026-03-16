/**
 * Loop Node - Iteration control node for workflow automation
 *
 * Executes a loop over a collection of items or a numeric range.
 * Outputs each iteration's data for processing by downstream nodes.
 *
 * Features:
 * - Array iteration
 * - Numeric range iteration (start, end, step)
 * - Current iteration index tracking
 * - Loop control (break on condition)
 *
 * Inspired by:
 * - Node-RED: Loop nodes and array processing
 * - TouchDesigner: For Each operators
 * - Max/MSP: uzi and counter objects
 */

import {
  NodeCategory,
  type NodePlugin,
  type ExecutionContext,
  type NodeExecutionResult,
} from '../../NodePluginAPI.js';

/**
 * Loop Node Plugin
 *
 * Iterates over an array or numeric range, outputting each item.
 * Supports both array iteration and numeric range iteration.
 *
 * Example usage in a graph:
 * 1. Array → LoopNode → Process Each Item
 * 2. LoopNode (range: 0-10) → Generate Sequence
 * 3. File List → LoopNode → Process File
 *
 * Configuration:
 * - items: Array of items to iterate over (array mode)
 * - start: Start value for numeric range (range mode)
 * - end: End value for numeric range (range mode)
 * - step: Step increment for range (default: 1)
 */
export const LoopNode: NodePlugin = {
  id: 'loop',
  category: NodeCategory.Workflow,
  label: 'Loop',
  description: 'Iterate over array or numeric range',

  inputs: [
    {
      id: 'items',
      label: 'Items',
      type: 'any',
      required: false,
      description: 'Array of items to iterate over (array mode)',
    },
    {
      id: 'start',
      label: 'Start',
      type: 'number',
      required: false,
      defaultValue: 0,
      description: 'Start value for numeric range (range mode)',
    },
    {
      id: 'end',
      label: 'End',
      type: 'number',
      required: false,
      description: 'End value for numeric range (range mode)',
    },
    {
      id: 'step',
      label: 'Step',
      type: 'number',
      required: false,
      defaultValue: 1,
      description: 'Step increment for range iteration (default: 1)',
    },
  ],

  outputs: [
    {
      id: 'items',
      label: 'Items',
      type: 'any',
      description: 'Array of all items that were iterated',
    },
    {
      id: 'count',
      label: 'Count',
      type: 'number',
      description: 'Total number of iterations',
    },
    {
      id: 'first',
      label: 'First Item',
      type: 'any',
      description: 'First item in the iteration',
    },
    {
      id: 'last',
      label: 'Last Item',
      type: 'any',
      description: 'Last item in the iteration',
    },
  ],

  /**
   * Validate inputs before execution
   *
   * Ensures:
   * - Either items array or range (start/end) is provided
   * - Range values are valid numbers when provided
   * - Step is non-zero
   */
  validate: (inputs: Record<string, unknown>): string[] => {
    const errors: string[] = [];

    const hasItems = inputs.items !== undefined && inputs.items !== null;
    const hasRange = inputs.end !== undefined;

    // Must provide either items or range
    if (!hasItems && !hasRange) {
      errors.push('Either items array or range (end value) must be provided');
    }

    // Validate step is non-zero
    const step = typeof inputs.step === 'number' ? inputs.step : 1;
    if (step === 0) {
      errors.push('Step cannot be zero');
    }

    // Validate range values if provided
    if (hasRange) {
      const start = typeof inputs.start === 'number' ? inputs.start : 0;
      const end = inputs.end;

      if (typeof end !== 'number') {
        errors.push('End must be a number when using range mode');
      } else {
        // Check for infinite loop conditions
        if (step > 0 && end < start) {
          errors.push('End must be greater than start when step is positive');
        }
        if (step < 0 && end > start) {
          errors.push('End must be less than start when step is negative');
        }
      }
    }

    return errors;
  },

  /**
   * Execute loop iteration
   *
   * Workflow:
   * 1. Determine mode (array or range)
   * 2. Build iteration array
   * 3. Emit 'running' state
   * 4. Process iterations (in node engine, this would trigger downstream nodes per item)
   * 5. Emit 'complete' state
   * 6. Return summary outputs
   *
   * Note: In a full graph execution engine, this node would trigger downstream
   * nodes for each iteration. For now, it returns the iteration array for processing.
   *
   * Error handling:
   * - Logs errors to execution context
   * - Emits 'error' state for UI feedback
   * - Re-throws error to propagate to downstream nodes
   */
  execute: async (
    inputs: Record<string, unknown>,
    context: ExecutionContext
  ): Promise<NodeExecutionResult> => {
    // Extract inputs
    const items = inputs.items;
    const start = typeof inputs.start === 'number' ? inputs.start : 0;
    const end = typeof inputs.end === 'number' ? inputs.end : undefined;
    const step = typeof inputs.step === 'number' ? inputs.step : 1;

    // Determine mode
    const isArrayMode = items !== undefined && items !== null;
    const isRangeMode = end !== undefined;

    // Log execution start
    context.log('info', 'Starting loop iteration', {
      mode: isArrayMode ? 'array' : 'range',
      arrayLength: Array.isArray(items) ? items.length : undefined,
      range: isRangeMode ? { start, end, step } : undefined,
    });

    // Emit running state
    context.emitState('running');

    try {
      // Check for abort signal
      if (context.signal?.aborted) {
        throw new Error('Execution aborted');
      }

      let iterationItems: unknown[];

      if (isArrayMode) {
        // Array mode - iterate over provided items
        if (Array.isArray(items)) {
          iterationItems = items;
        } else {
          // Single item, wrap in array
          iterationItems = [items];
        }
      } else if (isRangeMode && end !== undefined) {
        // Range mode - generate numeric sequence
        iterationItems = [];

        if (step > 0) {
          for (let i = start; i < end; i += step) {
            iterationItems.push(i);
          }
        } else if (step < 0) {
          for (let i = start; i > end; i += step) {
            iterationItems.push(i);
          }
        }
      } else {
        throw new Error('Invalid loop configuration');
      }

      const count = iterationItems.length;
      const first = count > 0 ? iterationItems[0] : undefined;
      const last = count > 0 ? iterationItems[count - 1] : undefined;

      // Log iteration summary
      context.log('info', 'Loop iteration complete', {
        count,
        mode: isArrayMode ? 'array' : 'range',
      });

      // Emit complete state
      context.emitState('complete');

      // Return outputs
      return {
        outputs: {
          items: iterationItems,
          count,
          first,
          last,
        },
        meta: {
          executionTime: Date.now(),
          mode: isArrayMode ? 'array' : 'range',
          iterationCount: count,
        },
      };
    } catch (error) {
      // Log error
      const errorMessage = error instanceof Error ? error.message : String(error);
      context.log('error', 'Loop node execution failed', {
        error: errorMessage,
      });

      // Emit error state
      context.emitState('error');

      // Re-throw to propagate
      throw new Error(`Loop node execution failed: ${errorMessage}`);
    }
  },

  /**
   * Plugin metadata
   */
  metadata: {
    version: '1.0.0',
    author: 'Mascarade',
    tags: ['workflow', 'control-flow', 'loop', 'iteration', 'array', 'range'],
    experimental: false,
  },
};
