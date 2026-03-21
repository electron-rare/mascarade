/**
 * ExecutionContext Tests
 *
 * Validates execution context creation, state isolation, logging, and event emission.
 */

import { describe, expect, it, beforeEach } from 'vitest';
import { ExecutionContextManager } from '../ExecutionContext.js';
import type { ExecutionEvent } from '../../types/ExecutionTypes.js';

describe('ExecutionContext', () => {
  let manager: ExecutionContextManager;

  beforeEach(() => {
    manager = new ExecutionContextManager();
  });

  describe('createContext', () => {
    it('creates a new execution context', () => {
      const context = manager.createContext('run-1', 'node-a', 'graph-1');

      expect(context).toBeDefined();
      expect(context.runId).toBe('run-1');
      expect(context.nodeId).toBe('node-a');
      expect(context.graphId).toBe('graph-1');
      expect(context.state).toBeInstanceOf(Map);
      expect(context.signal).toBeDefined();
    });

    it('creates contexts with isolated node IDs but shared state within same run', () => {
      const context1 = manager.createContext('run-1', 'node-a', 'graph-1');
      const context2 = manager.createContext('run-1', 'node-b', 'graph-1');

      expect(context1.nodeId).toBe('node-a');
      expect(context2.nodeId).toBe('node-b');

      // State should be shared within the same run
      expect(context1.state).toBe(context2.state);
    });

    it('creates completely isolated state for different runs', () => {
      const context1 = manager.createContext('run-1', 'node-a', 'graph-1');
      const context2 = manager.createContext('run-2', 'node-a', 'graph-1');

      // State should be different for different runs
      expect(context1.state).not.toBe(context2.state);

      // Verify isolation by setting values
      context1.state.set('key', 'value1');
      context2.state.set('key', 'value2');

      expect(context1.state.get('key')).toBe('value1');
      expect(context2.state.get('key')).toBe('value2');
    });
  });

  describe('state management', () => {
    it('allows message passing between nodes via shared state', () => {
      const context1 = manager.createContext('run-1', 'node-a', 'graph-1');
      const context2 = manager.createContext('run-1', 'node-b', 'graph-1');

      // Node A sets a value
      context1.state.set('result', 42);

      // Node B can read the value
      expect(context2.state.get('result')).toBe(42);
    });

    it('supports complex data types in state', () => {
      const context = manager.createContext('run-1', 'node-a', 'graph-1');

      const complexData = {
        nested: { value: 123 },
        array: [1, 2, 3],
        fn: () => 'test'
      };

      context.state.set('complex', complexData);

      expect(context.state.get('complex')).toBe(complexData);
      expect((context.state.get('complex') as any).nested.value).toBe(123);
    });

    it('retrieves state for a specific run', () => {
      const context = manager.createContext('run-1', 'node-a', 'graph-1');
      context.state.set('key', 'value');

      const state = manager.getState('run-1');

      expect(state).toBeDefined();
      expect(state?.get('key')).toBe('value');
    });

    it('returns undefined for non-existent run state', () => {
      const state = manager.getState('non-existent');

      expect(state).toBeUndefined();
    });
  });

  describe('logging', () => {
    it('captures logs from execution context', () => {
      const context = manager.createContext('run-1', 'node-a', 'graph-1');

      context.log('info', 'Test message');
      context.log('error', 'Error message', { code: 'ERR001' });

      const logs = manager.getLogs('run-1');

      expect(logs).toHaveLength(2);
      expect(logs[0].level).toBe('info');
      expect(logs[0].message).toBe('Test message');
      expect(logs[0].nodeId).toBe('node-a');
      expect(logs[1].level).toBe('error');
      expect(logs[1].message).toBe('Error message');
      expect(logs[1].meta?.code).toBe('ERR001');
    });

    it('aggregates logs from multiple nodes in same run', () => {
      const context1 = manager.createContext('run-1', 'node-a', 'graph-1');
      const context2 = manager.createContext('run-1', 'node-b', 'graph-1');

      context1.log('info', 'Node A log');
      context2.log('warn', 'Node B log');

      const logs = manager.getLogs('run-1');

      expect(logs).toHaveLength(2);
      expect(logs[0].nodeId).toBe('node-a');
      expect(logs[1].nodeId).toBe('node-b');
    });

    it('supports all log levels', () => {
      const context = manager.createContext('run-1', 'node-a', 'graph-1');

      context.log('debug', 'Debug message');
      context.log('info', 'Info message');
      context.log('warn', 'Warning message');
      context.log('error', 'Error message');

      const logs = manager.getLogs('run-1');

      expect(logs).toHaveLength(4);
      expect(logs.map(l => l.level)).toEqual(['debug', 'info', 'warn', 'error']);
    });

    it('returns empty array for non-existent run logs', () => {
      const logs = manager.getLogs('non-existent');

      expect(logs).toEqual([]);
    });
  });

  describe('event emission', () => {
    it('emits state change events', () => {
      const events: ExecutionEvent[] = [];
      const eventEmitter = (event: ExecutionEvent) => events.push(event);

      const context = manager.createContext('run-1', 'node-a', 'graph-1', {
        pluginId: 'test-plugin',
        eventEmitter
      });

      context.emitState('running');
      context.emitState('complete');

      expect(events).toHaveLength(2);
      expect(events[0].type).toBe('node.state');
      expect(events[0].runId).toBe('run-1');
      expect(events[0].nodeId).toBe('node-a');
      expect((events[0] as any).state).toBe('running');
      expect((events[1] as any).state).toBe('complete');
    });

    it('emits log events', () => {
      const events: ExecutionEvent[] = [];
      const eventEmitter = (event: ExecutionEvent) => events.push(event);

      const context = manager.createContext('run-1', 'node-a', 'graph-1', {
        eventEmitter
      });

      context.log('info', 'Test log');

      expect(events).toHaveLength(1);
      expect(events[0].type).toBe('execution.log');
      expect(events[0].runId).toBe('run-1');
      expect((events[0] as any).log.message).toBe('Test log');
    });

    it('does not emit events when no emitter is provided', () => {
      // Should not throw even without event emitter
      const context = manager.createContext('run-1', 'node-a', 'graph-1');

      expect(() => {
        context.emitState('running');
        context.log('info', 'Test');
      }).not.toThrow();
    });
  });

  describe('abort signal', () => {
    it('provides abort signal in context', () => {
      const context = manager.createContext('run-1', 'node-a', 'graph-1');

      expect(context.signal).toBeDefined();
      expect(context.signal?.aborted).toBe(false);
    });

    it('aborts execution and triggers signal', () => {
      const context = manager.createContext('run-1', 'node-a', 'graph-1');

      const aborted = manager.abort('run-1');

      expect(aborted).toBe(true);
      expect(context.signal?.aborted).toBe(true);
    });

    it('shares abort signal across nodes in same run', () => {
      const context1 = manager.createContext('run-1', 'node-a', 'graph-1');
      const context2 = manager.createContext('run-1', 'node-b', 'graph-1');

      manager.abort('run-1');

      // Both contexts should see the abort
      expect(context1.signal?.aborted).toBe(true);
      expect(context2.signal?.aborted).toBe(true);
    });

    it('isolates abort signals across different runs', () => {
      const context1 = manager.createContext('run-1', 'node-a', 'graph-1');
      const context2 = manager.createContext('run-2', 'node-a', 'graph-1');

      manager.abort('run-1');

      expect(context1.signal?.aborted).toBe(true);
      expect(context2.signal?.aborted).toBe(false);
    });

    it('returns false when aborting non-existent run', () => {
      const aborted = manager.abort('non-existent');

      expect(aborted).toBe(false);
    });

    it('checks if execution is aborted', () => {
      manager.createContext('run-1', 'node-a', 'graph-1');

      expect(manager.isAborted('run-1')).toBe(false);

      manager.abort('run-1');

      expect(manager.isAborted('run-1')).toBe(true);
    });

    it('returns false for non-existent run abort check', () => {
      expect(manager.isAborted('non-existent')).toBe(false);
    });
  });

  describe('cleanup', () => {
    it('cleans up execution context', () => {
      const context = manager.createContext('run-1', 'node-a', 'graph-1');
      context.state.set('key', 'value');
      context.log('info', 'Test');

      const cleaned = manager.cleanup('run-1');

      expect(cleaned).toBe(true);
      expect(manager.getState('run-1')).toBeUndefined();
      expect(manager.getLogs('run-1')).toEqual([]);
    });

    it('returns false when cleaning up non-existent run', () => {
      const cleaned = manager.cleanup('non-existent');

      expect(cleaned).toBe(false);
    });

    it('cleans up all contexts', () => {
      manager.createContext('run-1', 'node-a', 'graph-1');
      manager.createContext('run-2', 'node-b', 'graph-1');
      manager.createContext('run-3', 'node-c', 'graph-1');

      expect(manager.getActiveCount()).toBe(3);

      manager.cleanupAll();

      expect(manager.getActiveCount()).toBe(0);
      expect(manager.getState('run-1')).toBeUndefined();
      expect(manager.getState('run-2')).toBeUndefined();
      expect(manager.getState('run-3')).toBeUndefined();
    });
  });

  describe('active runs tracking', () => {
    it('tracks active run IDs', () => {
      manager.createContext('run-1', 'node-a', 'graph-1');
      manager.createContext('run-2', 'node-b', 'graph-1');

      const activeRuns = manager.getActiveRuns();

      expect(activeRuns).toHaveLength(2);
      expect(activeRuns).toContain('run-1');
      expect(activeRuns).toContain('run-2');
    });

    it('counts active executions', () => {
      expect(manager.getActiveCount()).toBe(0);

      manager.createContext('run-1', 'node-a', 'graph-1');
      expect(manager.getActiveCount()).toBe(1);

      manager.createContext('run-2', 'node-b', 'graph-1');
      expect(manager.getActiveCount()).toBe(2);

      manager.cleanup('run-1');
      expect(manager.getActiveCount()).toBe(1);
    });
  });

  describe('concurrent execution isolation', () => {
    it('maintains complete isolation between concurrent executions', () => {
      // Create two concurrent graph executions
      const run1Context1 = manager.createContext('run-1', 'node-a', 'graph-1');
      const run1Context2 = manager.createContext('run-1', 'node-b', 'graph-1');
      const run2Context1 = manager.createContext('run-2', 'node-a', 'graph-1');
      const run2Context2 = manager.createContext('run-2', 'node-b', 'graph-1');

      // Run 1 sets state
      run1Context1.state.set('result', 'run1-value');
      run1Context1.log('info', 'Run 1 log');

      // Run 2 sets state
      run2Context1.state.set('result', 'run2-value');
      run2Context1.log('info', 'Run 2 log');

      // Verify state isolation
      expect(run1Context2.state.get('result')).toBe('run1-value');
      expect(run2Context2.state.get('result')).toBe('run2-value');

      // Verify log isolation
      expect(manager.getLogs('run-1')).toHaveLength(1);
      expect(manager.getLogs('run-2')).toHaveLength(1);
      expect(manager.getLogs('run-1')[0].message).toBe('Run 1 log');
      expect(manager.getLogs('run-2')[0].message).toBe('Run 2 log');

      // Verify abort isolation
      manager.abort('run-1');
      expect(run1Context1.signal?.aborted).toBe(true);
      expect(run2Context1.signal?.aborted).toBe(false);
    });

    it('supports many concurrent executions without interference', () => {
      const runCount = 100;

      // Create many concurrent executions
      for (let i = 0; i < runCount; i++) {
        const context = manager.createContext(`run-${i}`, 'node-a', 'graph-1');
        context.state.set('value', i);
        context.log('info', `Run ${i}`);
      }

      expect(manager.getActiveCount()).toBe(runCount);

      // Verify each run has correct isolated state
      for (let i = 0; i < runCount; i++) {
        const state = manager.getState(`run-${i}`);
        expect(state?.get('value')).toBe(i);

        const logs = manager.getLogs(`run-${i}`);
        expect(logs).toHaveLength(1);
        expect(logs[0].message).toBe(`Run ${i}`);
      }
    });
  });
});
