/**
 * If Node - Conditional branching node for workflow control
 *
 * Evaluates a boolean condition and routes execution to either the "then" or "else" branch.
 * Supports both simple boolean inputs and expression-based conditions.
 *
 * Features:
 * - Boolean condition evaluation
 * - Dual output paths (then/else)
 * - Pass-through data on both branches
 * - Support for truthy/falsy value conversion
 *
 * Inspired by:
 * - Node-RED: Switch/route nodes for flow control
 * - TouchDesigner: Switch TOP for conditional routing
 * - Max/MSP: gate~ and select objects
 */

import {
  NodeCategory,
  type NodePlugin,
  type ExecutionContext,
  type NodeExecutionResult,
} from '../../NodePluginAPI.js';

/**
 * If Node Plugin
 *
 * Evaluates a condition and outputs to either the "then" or "else" branch.
 * Allows passing data through the selected branch.
 *
 * Example usage in a graph:
 * 1. Sensor → IfNode (condition: value > threshold) → Alarm
 * 2. User Input → IfNode → Success Path / Error Path
 *
 * Configuration:
 * - condition: Boolean or truthy/falsy value to evaluate
 * - data: Optional data to pass through to the selected branch
 */
export const IfNode: NodePlugin = {
  id: 'if',
  category: NodeCategory.Workflow,
  label: 'If',
  description: 'Conditional branching - route execution based on boolean condition',

  inputs: [
    {
      id: 'condition',
      label: 'Condition',
      type: 'boolean',
      required: true,
      description: 'Boolean condition to evaluate (truthy/falsy values accepted)',
    },
    {
      id: 'data',
      label: 'Data',
      type: 'any',
      required: false,
      description: 'Optional data to pass through to the selected branch',
    },
  ],

  outputs: [
    {
      id: 'then',
      label: 'Then',
      type: 'any',
      description: 'Outputs data when condition is true',
    },
    {
      id: 'else',
      label: 'Else',
      type: 'any',
      description: 'Outputs data when condition is false',
    },
    {
      id: 'result',
      label: 'Result',
      type: 'boolean',
      description: 'The evaluated condition result',
    },
  ],

  /**
   * Validate inputs before execution
   *
   * Ensures:
   * - Condition is provided
   */
  validate: (inputs: Record<string, unknown>): string[] => {
    const errors: string[] = [];

    // Validate condition exists
    if (inputs.condition === undefined || inputs.condition === null) {
      errors.push('Condition must be provided');
    }

    return errors;
  },

  /**
   * Execute conditional branching
   *
   * Workflow:
   * 1. Extract and evaluate condition
   * 2. Convert to boolean (handle truthy/falsy)
   * 3. Emit 'running' state
   * 4. Output data to appropriate branch
   * 5. Emit 'complete' state
   * 6. Return outputs
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
    const condition = inputs.condition;
    const data = inputs.data;

    // Log execution start
    context.log('info', 'Evaluating condition', {
      condition,
      hasData: data !== undefined,
    });

    // Emit running state
    context.emitState('running');

    try {
      // Check for abort signal
      if (context.signal?.aborted) {
        throw new Error('Execution aborted');
      }

      // Convert condition to boolean (handle truthy/falsy)
      const result = Boolean(condition);

      // Log evaluation result
      context.log('info', 'Condition evaluated', {
        result,
        branch: result ? 'then' : 'else',
      });

      // Emit complete state
      context.emitState('complete');

      // Return outputs - data goes to appropriate branch
      return {
        outputs: {
          then: result ? data : undefined,
          else: result ? undefined : data,
          result,
        },
        meta: {
          executionTime: Date.now(),
          branch: result ? 'then' : 'else',
          conditionValue: condition,
        },
      };
    } catch (error) {
      // Log error
      const errorMessage = error instanceof Error ? error.message : String(error);
      context.log('error', 'If node execution failed', {
        error: errorMessage,
      });

      // Emit error state
      context.emitState('error');

      // Re-throw to propagate
      throw new Error(`If node execution failed: ${errorMessage}`);
    }
  },

  /**
   * Plugin metadata
   */
  metadata: {
    version: '1.0.0',
    author: 'Mascarade',
    tags: ['workflow', 'control-flow', 'conditional', 'branching', 'if-else'],
    experimental: false,
  },
};
