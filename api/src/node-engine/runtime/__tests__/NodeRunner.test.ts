/**
 * NodeRunner Tests
 *
 * Validates individual node execution with sync/async handling, timeouts,
 * validation, state emission, and error handling.
 */

import { describe, expect, it, beforeEach, vi } from 'vitest';
import { NodeRunner } from '../NodeRunner.js';
import { ExecutionContextManager } from '../ExecutionContext.js';
import type { NodePlugin, ExecutionContext } from '../../plugins/NodePluginAPI.js';
import { NodeCategory } from '../../plugins/NodePluginAPI.js';
import type { ExecutionEvent } from '../../types/ExecutionTypes.js';

describe('NodeRunner', () => {
  let contextManager: ExecutionContextManager;
  let events: ExecutionEvent[];

  beforeEach(() => {
    contextManager = new ExecutionContextManager();
    events = [];
  });

  // Helper to create a context with event tracking
  function createContext(runId: string, nodeId: string): ExecutionContext {
    return contextManager.createContext(runId, nodeId, 'graph-1', {
      pluginId: 'test-plugin',
      eventEmitter: (event) => events.push(event)
    });
  }

  describe('synchronous execution', () => {
    it('executes a synchronous node successfully', async () => {
      const plugin: NodePlugin = {
        id: 'sync-node',
        category: NodeCategory.Workflow,
        label: 'Sync Node',
        description: 'A synchronous test node',
        inputs: [
          { id: 'value', label: 'Value', type: 'number', required: true }
        ],
        outputs: [
          { id: 'result', label: 'Result', type: 'number' }
        ],
        execute: (inputs) => {
          return { result: (inputs.value as number) * 2 };
        }
      };

      const runner = new NodeRunner(plugin);
      const context = createContext('run-1', 'node-1');
      const inputs = { value: 21 };

      const record = await runner.execute(inputs, context);

      expect(record.state).toBe('complete');
      expect(record.outputs).toEqual({ result: 42 });
      expect(record.duration).toBeGreaterThanOrEqual(0);
      expect(record.error).toBeUndefined();
    });

    it('emits correct state transitions for sync execution', async () => {
      const plugin: NodePlugin = {
        id: 'sync-node',
        category: NodeCategory.Workflow,
        label: 'Sync Node',
        description: 'Test',
        inputs: [],
        outputs: [{ id: 'result', label: 'Result', type: 'number' }],
        execute: () => ({ result: 42 })
      };

      const runner = new NodeRunner(plugin);
      const context = createContext('run-1', 'node-1');

      await runner.execute({}, context);

      const stateEvents = events.filter(e => e.type === 'node.state');
      expect(stateEvents).toHaveLength(3);
      expect(stateEvents[0].state).toBe('pending');
      expect(stateEvents[1].state).toBe('running');
      expect(stateEvents[2].state).toBe('complete');
    });
  });

  describe('asynchronous execution', () => {
    it('executes an async node successfully', async () => {
      const plugin: NodePlugin = {
        id: 'async-node',
        category: NodeCategory.AI,
        label: 'Async Node',
        description: 'An async test node',
        inputs: [
          { id: 'prompt', label: 'Prompt', type: 'string', required: true }
        ],
        outputs: [
          { id: 'response', label: 'Response', type: 'string' }
        ],
        execute: async (inputs) => {
          // Simulate async work
          await new Promise(resolve => setTimeout(resolve, 10));
          return { response: `Echo: ${inputs.prompt}` };
        }
      };

      const runner = new NodeRunner(plugin);
      const context = createContext('run-1', 'node-1');
      const inputs = { prompt: 'Hello' };

      const record = await runner.execute(inputs, context);

      expect(record.state).toBe('complete');
      expect(record.outputs).toEqual({ response: 'Echo: Hello' });
      expect(record.duration).toBeGreaterThan(0);
    });

    it('handles NodeExecutionResult with meta', async () => {
      const plugin: NodePlugin = {
        id: 'meta-node',
        category: NodeCategory.Workflow,
        label: 'Meta Node',
        description: 'Returns result with metadata',
        inputs: [],
        outputs: [{ id: 'value', label: 'Value', type: 'number' }],
        execute: () => ({
          outputs: { value: 42 },
          meta: { executionTime: 123 }
        })
      };

      const runner = new NodeRunner(plugin);
      const context = createContext('run-1', 'node-1');

      const record = await runner.execute({}, context);

      expect(record.state).toBe('complete');
      expect(record.outputs).toEqual({ value: 42 });
    });
  });

  describe('input validation', () => {
    it('validates required inputs', async () => {
      const plugin: NodePlugin = {
        id: 'validation-node',
        category: NodeCategory.Workflow,
        label: 'Validation Node',
        description: 'Requires an input',
        inputs: [
          { id: 'required', label: 'Required', type: 'string', required: true }
        ],
        outputs: [
          { id: 'result', label: 'Result', type: 'string' }
        ],
        execute: (inputs) => ({ result: inputs.required })
      };

      const runner = new NodeRunner(plugin);
      const context = createContext('run-1', 'node-1');

      await expect(runner.execute({}, context)).rejects.toThrow(
        "Required input port 'required'"
      );
    });

    it('applies default values for missing inputs', async () => {
      const plugin: NodePlugin = {
        id: 'default-node',
        category: NodeCategory.Workflow,
        label: 'Default Node',
        description: 'Has default values',
        inputs: [
          { id: 'value', label: 'Value', type: 'number', defaultValue: 100 }
        ],
        outputs: [
          { id: 'result', label: 'Result', type: 'number' }
        ],
        execute: (inputs) => ({ result: inputs.value })
      };

      const runner = new NodeRunner(plugin);
      const context = createContext('run-1', 'node-1');

      const record = await runner.execute({}, context);

      expect(record.state).toBe('complete');
      expect(record.outputs).toEqual({ result: 100 });
    });

    it('uses default value for required port if missing', async () => {
      const plugin: NodePlugin = {
        id: 'required-default-node',
        category: NodeCategory.Workflow,
        label: 'Required Default Node',
        description: 'Required but has default',
        inputs: [
          {
            id: 'value',
            label: 'Value',
            type: 'number',
            required: true,
            defaultValue: 42
          }
        ],
        outputs: [
          { id: 'result', label: 'Result', type: 'number' }
        ],
        execute: (inputs) => ({ result: inputs.value })
      };

      const runner = new NodeRunner(plugin);
      const context = createContext('run-1', 'node-1');

      const record = await runner.execute({}, context);

      expect(record.state).toBe('complete');
      expect(record.outputs).toEqual({ result: 42 });
    });

    it('runs custom validation if defined', async () => {
      const plugin: NodePlugin = {
        id: 'custom-validation-node',
        category: NodeCategory.Workflow,
        label: 'Custom Validation',
        description: 'Has custom validation',
        inputs: [
          { id: 'value', label: 'Value', type: 'number' }
        ],
        outputs: [
          { id: 'result', label: 'Result', type: 'number' }
        ],
        execute: (inputs) => ({ result: inputs.value }),
        validate: (inputs) => {
          const errors: string[] = [];
          if (typeof inputs.value === 'number' && inputs.value < 0) {
            errors.push('Value must be non-negative');
          }
          return errors;
        }
      };

      const runner = new NodeRunner(plugin);
      const context = createContext('run-1', 'node-1');

      await expect(runner.execute({ value: -1 }, context)).rejects.toThrow(
        'Input validation failed: Value must be non-negative'
      );
    });

    it('skips validation when skipValidation is true', async () => {
      const plugin: NodePlugin = {
        id: 'skip-validation-node',
        category: NodeCategory.Workflow,
        label: 'Skip Validation',
        description: 'Validation can be skipped',
        inputs: [
          { id: 'required', label: 'Required', type: 'string', required: true }
        ],
        outputs: [
          { id: 'result', label: 'Result', type: 'string' }
        ],
        execute: (inputs) => ({ result: inputs.required || 'fallback' })
      };

      const runner = new NodeRunner(plugin);
      const context = createContext('run-1', 'node-1');

      // Should not throw even though required input is missing
      const record = await runner.execute({}, context, { skipValidation: true });

      expect(record.state).toBe('complete');
    });
  });

  describe('error handling', () => {
    it('handles execution errors correctly', async () => {
      const plugin: NodePlugin = {
        id: 'error-node',
        category: NodeCategory.Workflow,
        label: 'Error Node',
        description: 'Throws an error',
        inputs: [],
        outputs: [],
        execute: () => {
          throw new Error('Execution failed');
        }
      };

      const runner = new NodeRunner(plugin);
      const context = createContext('run-1', 'node-1');

      await expect(runner.execute({}, context)).rejects.toThrow('Execution failed');

      // Check that error state was emitted
      const stateEvents = events.filter(e => e.type === 'node.state');
      const lastState = stateEvents[stateEvents.length - 1];
      expect(lastState.state).toBe('error');
    });

    it('creates structured error with stack trace', async () => {
      const plugin: NodePlugin = {
        id: 'error-node',
        category: NodeCategory.Workflow,
        label: 'Error Node',
        description: 'Throws an error',
        inputs: [],
        outputs: [],
        execute: () => {
          throw new Error('Test error');
        }
      };

      const runner = new NodeRunner(plugin);
      const context = createContext('run-1', 'node-1');

      try {
        await runner.execute({}, context);
        expect.fail('Should have thrown');
      } catch (error) {
        // Error should be re-thrown
        expect(error).toBeInstanceOf(Error);
        expect((error as Error).message).toBe('Test error');
      }

      // Check error event logs
      const errorLogs = events.filter(e => e.type === 'execution.log' && e.log.level === 'error');
      expect(errorLogs.length).toBeGreaterThan(0);
    });

    it('handles non-Error throws', async () => {
      const plugin: NodePlugin = {
        id: 'string-throw-node',
        category: NodeCategory.Workflow,
        label: 'String Throw Node',
        description: 'Throws a string',
        inputs: [],
        outputs: [],
        execute: () => {
          throw 'String error'; // eslint-disable-line no-throw-literal
        }
      };

      const runner = new NodeRunner(plugin);
      const context = createContext('run-1', 'node-1');

      await expect(runner.execute({}, context)).rejects.toBe('String error');
    });
  });

  describe('timeout handling', () => {
    it('enforces execution timeout', async () => {
      const plugin: NodePlugin = {
        id: 'slow-node',
        category: NodeCategory.AI,
        label: 'Slow Node',
        description: 'Takes too long',
        inputs: [],
        outputs: [],
        execute: async () => {
          // Wait longer than timeout
          await new Promise(resolve => setTimeout(resolve, 200));
          return {};
        }
      };

      const runner = new NodeRunner(plugin);
      const context = createContext('run-1', 'node-1');

      await expect(
        runner.execute({}, context, { timeout: 50 })
      ).rejects.toThrow('timed out after 50ms');
    });

    it('completes successfully within timeout', async () => {
      const plugin: NodePlugin = {
        id: 'fast-node',
        category: NodeCategory.Workflow,
        label: 'Fast Node',
        description: 'Completes quickly',
        inputs: [],
        outputs: [{ id: 'result', label: 'Result', type: 'number' }],
        execute: async () => {
          await new Promise(resolve => setTimeout(resolve, 10));
          return { result: 42 };
        }
      };

      const runner = new NodeRunner(plugin);
      const context = createContext('run-1', 'node-1');

      const record = await runner.execute({}, context, { timeout: 1000 });

      expect(record.state).toBe('complete');
      expect(record.outputs).toEqual({ result: 42 });
    });
  });

  describe('abort signal handling', () => {
    it('aborts execution when signal is triggered', async () => {
      const plugin: NodePlugin = {
        id: 'abortable-node',
        category: NodeCategory.AI,
        label: 'Abortable Node',
        description: 'Can be aborted',
        inputs: [],
        outputs: [],
        execute: async (inputs, context) => {
          // Check signal periodically
          for (let i = 0; i < 10; i++) {
            if (context.signal?.aborted) {
              throw new Error('Execution aborted');
            }
            await new Promise(resolve => setTimeout(resolve, 10));
          }
          return {};
        }
      };

      const runner = new NodeRunner(plugin);
      const context = createContext('run-1', 'node-1');

      // Abort after 30ms using the context manager
      setTimeout(() => contextManager.abort('run-1'), 30);

      await expect(runner.execute({}, context)).rejects.toThrow();
    });

    it('rejects if aborted before execution starts', async () => {
      const plugin: NodePlugin = {
        id: 'never-runs',
        category: NodeCategory.Workflow,
        label: 'Never Runs',
        description: 'Aborted before start',
        inputs: [],
        outputs: [],
        execute: () => ({ result: 42 })
      };

      const runner = new NodeRunner(plugin);

      // Create context first, then abort it
      const context = createContext('run-1', 'node-1');
      contextManager.abort('run-1');

      await expect(runner.execute({}, context)).rejects.toThrow('aborted');
    });
  });

  describe('performance tracking', () => {
    it('tracks execution duration', async () => {
      const plugin: NodePlugin = {
        id: 'timed-node',
        category: NodeCategory.Workflow,
        label: 'Timed Node',
        description: 'Execution is timed',
        inputs: [],
        outputs: [],
        execute: async () => {
          await new Promise(resolve => setTimeout(resolve, 50));
          return {};
        }
      };

      const runner = new NodeRunner(plugin);
      const context = createContext('run-1', 'node-1');

      const record = await runner.execute({}, context);

      expect(record.duration).toBeGreaterThanOrEqual(50);
      expect(record.startedAt).toBeDefined();
      expect(record.completedAt).toBeDefined();
    });

    it('tracks duration even on error', async () => {
      const plugin: NodePlugin = {
        id: 'error-timed-node',
        category: NodeCategory.Workflow,
        label: 'Error Timed Node',
        description: 'Error is timed',
        inputs: [],
        outputs: [],
        execute: async () => {
          await new Promise(resolve => setTimeout(resolve, 20));
          throw new Error('Failed');
        }
      };

      const runner = new NodeRunner(plugin);
      const context = createContext('run-1', 'node-1');

      try {
        await runner.execute({}, context);
        expect.fail('Should have thrown');
      } catch (error) {
        // Error expected
      }

      // Should still have logged duration
      const errorLogs = events.filter(
        e => e.type === 'execution.log' && e.log.level === 'error'
      );
      expect(errorLogs.length).toBeGreaterThan(0);
    });
  });

  describe('lifecycle hooks', () => {
    it('calls onInit hook', async () => {
      const onInitMock = vi.fn();

      const plugin: NodePlugin = {
        id: 'lifecycle-node',
        category: NodeCategory.Workflow,
        label: 'Lifecycle Node',
        description: 'Has lifecycle hooks',
        inputs: [],
        outputs: [],
        execute: () => ({}),
        onInit: onInitMock
      };

      const runner = new NodeRunner(plugin);
      const context = createContext('run-1', 'node-1');

      await runner.init(context);

      expect(onInitMock).toHaveBeenCalledWith(context);
    });

    it('calls onDestroy hook', async () => {
      const onDestroyMock = vi.fn();

      const plugin: NodePlugin = {
        id: 'lifecycle-node',
        category: NodeCategory.Workflow,
        label: 'Lifecycle Node',
        description: 'Has lifecycle hooks',
        inputs: [],
        outputs: [],
        execute: () => ({}),
        onDestroy: onDestroyMock
      };

      const runner = new NodeRunner(plugin);
      const context = createContext('run-1', 'node-1');

      await runner.destroy(context);

      expect(onDestroyMock).toHaveBeenCalledWith(context);
    });

    it('handles async lifecycle hooks', async () => {
      const onInitMock = vi.fn(async () => {
        await new Promise(resolve => setTimeout(resolve, 10));
      });

      const plugin: NodePlugin = {
        id: 'async-lifecycle-node',
        category: NodeCategory.Hardware,
        label: 'Async Lifecycle Node',
        description: 'Has async lifecycle hooks',
        inputs: [],
        outputs: [],
        execute: () => ({}),
        onInit: onInitMock
      };

      const runner = new NodeRunner(plugin);
      const context = createContext('run-1', 'node-1');

      await runner.init(context);

      expect(onInitMock).toHaveBeenCalledWith(context);
    });

    it('does not fail if lifecycle hooks are not defined', async () => {
      const plugin: NodePlugin = {
        id: 'no-lifecycle-node',
        category: NodeCategory.Workflow,
        label: 'No Lifecycle Node',
        description: 'No lifecycle hooks',
        inputs: [],
        outputs: [],
        execute: () => ({})
      };

      const runner = new NodeRunner(plugin);
      const context = createContext('run-1', 'node-1');

      await expect(runner.init(context)).resolves.toBeUndefined();
      await expect(runner.destroy(context)).resolves.toBeUndefined();
    });
  });

  describe('getPlugin', () => {
    it('returns the plugin instance', () => {
      const plugin: NodePlugin = {
        id: 'test-plugin',
        category: NodeCategory.Workflow,
        label: 'Test Plugin',
        description: 'Test',
        inputs: [],
        outputs: [],
        execute: () => ({})
      };

      const runner = new NodeRunner(plugin);

      expect(runner.getPlugin()).toBe(plugin);
    });
  });
});
