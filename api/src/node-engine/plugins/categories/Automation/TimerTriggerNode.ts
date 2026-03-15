/**
 * Timer Trigger Node - Time-based execution trigger for automation
 *
 * Triggers execution after a specified delay or at regular intervals.
 * Useful for scheduled tasks, polling, and periodic automation workflows.
 *
 * Features:
 * - One-shot delay trigger
 * - Repeating interval trigger
 * - Configurable timing in milliseconds
 * - Pass-through data support
 * - Trigger count tracking
 *
 * Inspired by:
 * - Node-RED: Inject/delay nodes for time-based automation
 * - TouchDesigner: Timer CHOP for periodic triggers
 * - Max/MSP: metro object for interval-based triggering
 */

import {
  NodeCategory,
  type NodePlugin,
  type ExecutionContext,
  type NodeExecutionResult,
} from '../../NodePluginAPI.js';

/**
 * Timer Trigger Node Plugin
 *
 * Executes after a delay or at regular intervals, useful for:
 * - Scheduled automation workflows
 * - Periodic data polling
 * - Timed event sequences
 * - Delayed execution chains
 *
 * Example usage in a graph:
 * 1. TimerTrigger (5000ms) → Data Fetch → Process → Store
 * 2. TimerTrigger (interval: 1000ms) → Sensor Check → Alert If Threshold
 *
 * Configuration:
 * - delay: Milliseconds to wait before triggering (for one-shot)
 * - interval: Milliseconds between repeated triggers (0 = one-shot only)
 * - maxTriggers: Maximum number of triggers (0 = unlimited for intervals)
 * - data: Optional data to emit on each trigger
 */
export const TimerTriggerNode: NodePlugin = {
  id: 'timer-trigger',
  category: NodeCategory.Automation,
  label: 'Timer Trigger',
  description: 'Trigger execution after delay or at regular intervals',

  inputs: [
    {
      id: 'delay',
      label: 'Delay (ms)',
      type: 'number',
      required: true,
      defaultValue: 1000,
      description: 'Milliseconds to wait before first trigger',
    },
    {
      id: 'interval',
      label: 'Interval (ms)',
      type: 'number',
      required: false,
      defaultValue: 0,
      description: 'Milliseconds between repeated triggers (0 = one-shot)',
    },
    {
      id: 'maxTriggers',
      label: 'Max Triggers',
      type: 'number',
      required: false,
      defaultValue: 0,
      description: 'Maximum number of triggers (0 = unlimited)',
    },
    {
      id: 'data',
      label: 'Data',
      type: 'any',
      required: false,
      description: 'Optional data to emit on each trigger',
    },
  ],

  outputs: [
    {
      id: 'trigger',
      label: 'Trigger',
      type: 'any',
      description: 'Emits data on each trigger',
    },
    {
      id: 'count',
      label: 'Count',
      type: 'number',
      description: 'Number of times triggered',
    },
    {
      id: 'timestamp',
      label: 'Timestamp',
      type: 'number',
      description: 'Timestamp of the trigger',
    },
  ],

  /**
   * Validate inputs before execution
   *
   * Ensures:
   * - Delay is a positive number
   * - Interval is non-negative
   * - MaxTriggers is non-negative
   */
  validate: (inputs: Record<string, unknown>): string[] => {
    const errors: string[] = [];

    // Validate delay
    const delay = inputs.delay as number;
    if (typeof delay !== 'number' || delay <= 0) {
      errors.push('Delay must be a positive number');
    }

    // Validate interval
    const interval = inputs.interval as number;
    if (interval !== undefined && (typeof interval !== 'number' || interval < 0)) {
      errors.push('Interval must be a non-negative number');
    }

    // Validate maxTriggers
    const maxTriggers = inputs.maxTriggers as number;
    if (maxTriggers !== undefined && (typeof maxTriggers !== 'number' || maxTriggers < 0)) {
      errors.push('Max triggers must be a non-negative number');
    }

    return errors;
  },

  /**
   * Execute timer trigger
   *
   * Workflow:
   * 1. Extract timing parameters
   * 2. Emit 'running' state
   * 3. Wait for initial delay
   * 4. Emit first trigger
   * 5. If interval > 0, set up repeating triggers
   * 6. Emit 'complete' state when done
   *
   * Error handling:
   * - Logs errors to execution context
   * - Emits 'error' state for UI feedback
   * - Re-throws error to propagate to downstream nodes
   *
   * Note: This is a simplified implementation for demonstration.
   * In a real system, interval-based triggers would be managed by
   * the execution runtime, not within the node itself.
   */
  execute: async (
    inputs: Record<string, unknown>,
    context: ExecutionContext
  ): Promise<NodeExecutionResult> => {
    // Extract inputs
    const delay = (inputs.delay as number) || 1000;
    const interval = (inputs.interval as number) || 0;
    const maxTriggers = (inputs.maxTriggers as number) || 0;
    const data = inputs.data;

    // Log execution start
    context.log('info', 'Timer trigger started', {
      delay,
      interval,
      maxTriggers,
      mode: interval > 0 ? 'interval' : 'one-shot',
    });

    // Emit running state
    context.emitState('running');

    try {
      // Check for abort signal
      if (context.signal?.aborted) {
        throw new Error('Execution aborted');
      }

      // Wait for initial delay
      await new Promise<void>((resolve, reject) => {
        const timeout = setTimeout(() => {
          resolve();
        }, delay);

        // Handle abort signal
        if (context.signal) {
          context.signal.addEventListener('abort', () => {
            clearTimeout(timeout);
            reject(new Error('Execution aborted'));
          });
        }
      });

      // First trigger
      const timestamp = Date.now();
      let triggerCount = 1;

      context.log('info', 'Timer triggered', {
        count: triggerCount,
        timestamp,
      });

      // Note: Interval-based repeating triggers would require a different execution model
      // In a production system, this would be handled by the runtime scheduler
      // For now, we just emit the first trigger and complete

      if (interval > 0 && maxTriggers !== 1) {
        context.log('warn', 'Interval-based repeating triggers not yet implemented in runtime', {
          interval,
          maxTriggers,
        });
      }

      // Emit complete state
      context.emitState('complete');

      // Return outputs
      return {
        outputs: {
          trigger: data,
          count: triggerCount,
          timestamp,
        },
        meta: {
          executionTime: Date.now(),
          delay,
          interval,
          mode: interval > 0 ? 'interval' : 'one-shot',
        },
      };
    } catch (error) {
      // Log error
      const errorMessage = error instanceof Error ? error.message : String(error);
      context.log('error', 'Timer trigger execution failed', {
        error: errorMessage,
      });

      // Emit error state
      context.emitState('error');

      // Re-throw to propagate
      throw new Error(`Timer trigger execution failed: ${errorMessage}`);
    }
  },

  /**
   * Plugin metadata
   */
  metadata: {
    version: '1.0.0',
    author: 'Mascarade',
    tags: ['automation', 'timer', 'trigger', 'delay', 'interval', 'schedule'],
    experimental: false,
  },
};
