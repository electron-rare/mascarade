/**
 * Switch Node - Multi-way branching node for workflow control
 *
 * Routes execution to one of multiple outputs based on a value or expression.
 * Similar to switch/case statements in programming languages.
 *
 * Features:
 * - Multiple output branches
 * - Value-based routing
 * - Default case support
 * - Type-aware matching (string, number, boolean)
 *
 * Inspired by:
 * - Node-RED: Switch node with multiple rules
 * - TouchDesigner: Select/Switch operators
 * - Max/MSP: switch/case/route objects
 */

import {
  NodeCategory,
  type NodePlugin,
  type ExecutionContext,
  type NodeExecutionResult,
} from '../../NodePluginAPI.js';

/**
 * Switch Node Plugin
 *
 * Evaluates a value and routes to a matching output case.
 * Supports default case when no match is found.
 *
 * Example usage in a graph:
 * 1. State Machine → SwitchNode (state) → [idle, running, error] handlers
 * 2. User Role → SwitchNode → [admin, user, guest] permissions
 *
 * Configuration:
 * - value: Value to match against cases
 * - cases: Array of case values to match
 * - data: Optional data to pass through to the selected output
 */
export const SwitchNode: NodePlugin = {
  id: 'switch',
  category: NodeCategory.Workflow,
  label: 'Switch',
  description: 'Multi-way branching - route execution based on value matching',

  inputs: [
    {
      id: 'value',
      label: 'Value',
      type: 'any',
      required: true,
      description: 'Value to match against cases',
    },
    {
      id: 'case0',
      label: 'Case 0',
      type: 'any',
      required: false,
      description: 'First case value to match',
    },
    {
      id: 'case1',
      label: 'Case 1',
      type: 'any',
      required: false,
      description: 'Second case value to match',
    },
    {
      id: 'case2',
      label: 'Case 2',
      type: 'any',
      required: false,
      description: 'Third case value to match',
    },
    {
      id: 'case3',
      label: 'Case 3',
      type: 'any',
      required: false,
      description: 'Fourth case value to match',
    },
    {
      id: 'data',
      label: 'Data',
      type: 'any',
      required: false,
      description: 'Optional data to pass through to the selected output',
    },
  ],

  outputs: [
    {
      id: 'output0',
      label: 'Output 0',
      type: 'any',
      description: 'Outputs data when value matches case0',
    },
    {
      id: 'output1',
      label: 'Output 1',
      type: 'any',
      description: 'Outputs data when value matches case1',
    },
    {
      id: 'output2',
      label: 'Output 2',
      type: 'any',
      description: 'Outputs data when value matches case2',
    },
    {
      id: 'output3',
      label: 'Output 3',
      type: 'any',
      description: 'Outputs data when value matches case3',
    },
    {
      id: 'default',
      label: 'Default',
      type: 'any',
      description: 'Outputs data when no case matches',
    },
    {
      id: 'matched_index',
      label: 'Matched Index',
      type: 'number',
      description: 'Index of matched case (-1 for default)',
    },
  ],

  /**
   * Validate inputs before execution
   *
   * Ensures:
   * - Value is provided
   * - At least one case is defined
   */
  validate: (inputs: Record<string, unknown>): string[] => {
    const errors: string[] = [];

    // Validate value exists
    if (inputs.value === undefined || inputs.value === null) {
      errors.push('Value must be provided');
    }

    // Check if at least one case is defined
    const hasCases = ['case0', 'case1', 'case2', 'case3'].some(
      (key) => inputs[key] !== undefined
    );

    if (!hasCases) {
      errors.push('At least one case must be defined');
    }

    return errors;
  },

  /**
   * Execute switch/case routing
   *
   * Workflow:
   * 1. Extract value and case definitions
   * 2. Emit 'running' state
   * 3. Match value against cases (strict equality)
   * 4. Route data to matching output or default
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
    const value = inputs.value;
    const data = inputs.data;

    // Build case array
    const cases = [
      inputs.case0,
      inputs.case1,
      inputs.case2,
      inputs.case3,
    ];

    // Log execution start
    context.log('info', 'Matching value against cases', {
      value,
      caseCount: cases.filter((c) => c !== undefined).length,
      hasData: data !== undefined,
    });

    // Emit running state
    context.emitState('running');

    try {
      // Check for abort signal
      if (context.signal?.aborted) {
        throw new Error('Execution aborted');
      }

      // Find matching case (strict equality)
      let matchedIndex = -1;
      for (let i = 0; i < cases.length; i++) {
        if (cases[i] !== undefined && cases[i] === value) {
          matchedIndex = i;
          break;
        }
      }

      // Log match result
      context.log('info', 'Case matching complete', {
        matchedIndex,
        matched: matchedIndex >= 0,
        matchedValue: matchedIndex >= 0 ? cases[matchedIndex] : undefined,
      });

      // Emit complete state
      context.emitState('complete');

      // Build outputs - data goes to matching output or default
      const outputs: Record<string, unknown> = {
        output0: undefined,
        output1: undefined,
        output2: undefined,
        output3: undefined,
        default: undefined,
        matched_index: matchedIndex,
      };

      if (matchedIndex >= 0) {
        outputs[`output${matchedIndex}`] = data;
      } else {
        outputs.default = data;
      }

      // Return outputs
      return {
        outputs,
        meta: {
          executionTime: Date.now(),
          matchedIndex,
          value,
          matched: matchedIndex >= 0,
        },
      };
    } catch (error) {
      // Log error
      const errorMessage = error instanceof Error ? error.message : String(error);
      context.log('error', 'Switch node execution failed', {
        error: errorMessage,
      });

      // Emit error state
      context.emitState('error');

      // Re-throw to propagate
      throw new Error(`Switch node execution failed: ${errorMessage}`);
    }
  },

  /**
   * Plugin metadata
   */
  metadata: {
    version: '1.0.0',
    author: 'Mascarade',
    tags: ['workflow', 'control-flow', 'switch', 'case', 'routing', 'branching'],
    experimental: false,
  },
};
