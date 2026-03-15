/**
 * TimerTriggerNode Tests
 *
 * Tests for the Timer Trigger node plugin, including:
 * - Input validation
 * - Delay triggering
 * - Timing accuracy
 * - State emission
 * - Error handling
 */

import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import { TimerTriggerNode } from '../TimerTriggerNode.js';
import type { ExecutionContext } from '../../../NodePluginAPI.js';

describe('TimerTriggerNode', () => {
  let mockContext: ExecutionContext;
  let emitStateSpy: Mock;
  let logSpy: Mock;

  beforeEach(() => {
    // Reset mocks
    vi.clearAllMocks();

    // Create mock context
    emitStateSpy = vi.fn();
    logSpy = vi.fn();

    mockContext = {
      runId: 'test-run-123',
      nodeId: 'test-node-abc',
      graphId: 'test-graph-xyz',
      emitState: emitStateSpy,
      log: logSpy,
      state: new Map(),
    };
  });

  describe('Plugin Metadata', () => {
    it('should have correct plugin ID and category', () => {
      expect(TimerTriggerNode.id).toBe('timer-trigger');
      expect(TimerTriggerNode.category).toBe('Automation');
    });

    it('should have correct label and description', () => {
      expect(TimerTriggerNode.label).toBe('Timer Trigger');
      expect(TimerTriggerNode.description).toContain('Trigger execution');
    });

    it('should define required inputs', () => {
      expect(TimerTriggerNode.inputs).toBeDefined();
      const delayInput = TimerTriggerNode.inputs.find((i) => i.id === 'delay');
      expect(delayInput).toBeDefined();
      expect(delayInput?.required).toBe(true);
    });

    it('should define expected outputs', () => {
      expect(TimerTriggerNode.outputs).toBeDefined();
      const outputIds = TimerTriggerNode.outputs.map((o) => o.id);
      expect(outputIds).toContain('trigger');
      expect(outputIds).toContain('count');
      expect(outputIds).toContain('timestamp');
    });
  });

  describe('Input Validation', () => {
    it('should validate missing delay', () => {
      const errors = TimerTriggerNode.validate?.({});
      expect(errors).toBeDefined();
      expect(errors?.length).toBeGreaterThan(0);
      expect(errors?.[0]).toContain('Delay must be a positive number');
    });

    it('should validate negative delay', () => {
      const errors = TimerTriggerNode.validate?.({ delay: -100 });
      expect(errors).toBeDefined();
      expect(errors?.length).toBeGreaterThan(0);
      expect(errors?.[0]).toContain('Delay must be a positive number');
    });

    it('should validate zero delay', () => {
      const errors = TimerTriggerNode.validate?.({ delay: 0 });
      expect(errors).toBeDefined();
      expect(errors?.length).toBeGreaterThan(0);
      expect(errors?.[0]).toContain('Delay must be a positive number');
    });

    it('should validate negative interval', () => {
      const errors = TimerTriggerNode.validate?.({ delay: 100, interval: -50 });
      expect(errors).toBeDefined();
      expect(errors?.length).toBeGreaterThan(0);
      expect(errors?.some(e => e.includes('Interval'))).toBe(true);
    });

    it('should validate negative maxTriggers', () => {
      const errors = TimerTriggerNode.validate?.({ delay: 100, maxTriggers: -5 });
      expect(errors).toBeDefined();
      expect(errors?.length).toBeGreaterThan(0);
      expect(errors?.some(e => e.includes('Max triggers'))).toBe(true);
    });

    it('should pass validation with valid delay', () => {
      const errors = TimerTriggerNode.validate?.({ delay: 1000 });
      expect(errors).toBeDefined();
      expect(errors?.length).toBe(0);
    });

    it('should pass validation with valid delay and interval', () => {
      const errors = TimerTriggerNode.validate?.({ delay: 1000, interval: 500 });
      expect(errors).toBeDefined();
      expect(errors?.length).toBe(0);
    });

    it('should pass validation with zero interval (one-shot mode)', () => {
      const errors = TimerTriggerNode.validate?.({ delay: 1000, interval: 0 });
      expect(errors).toBeDefined();
      expect(errors?.length).toBe(0);
    });
  });

  describe('Execution - One-shot Trigger', () => {
    it('should trigger after delay', async () => {
      const startTime = Date.now();
      const delay = 100;

      const result = await TimerTriggerNode.execute(
        { delay, interval: 0, data: 'test-data' },
        mockContext
      );

      const endTime = Date.now();
      const elapsed = endTime - startTime;

      // Verify timing (allow 50ms tolerance)
      expect(elapsed).toBeGreaterThanOrEqual(delay - 50);

      // Verify state emissions
      expect(emitStateSpy).toHaveBeenCalledWith('running');
      expect(emitStateSpy).toHaveBeenCalledWith('complete');

      // Verify logs
      expect(logSpy).toHaveBeenCalledWith('info', 'Timer trigger started', expect.any(Object));
      expect(logSpy).toHaveBeenCalledWith('info', 'Timer triggered', expect.any(Object));

      // Verify outputs
      expect(result).toBeDefined();
      if ('outputs' in result) {
        expect(result.outputs.trigger).toBe('test-data');
        expect(result.outputs.count).toBe(1);
        expect(result.outputs.timestamp).toBeDefined();
        expect(typeof result.outputs.timestamp).toBe('number');
      }
    });

    it('should work without data parameter', async () => {
      const result = await TimerTriggerNode.execute(
        { delay: 50 },
        mockContext
      );

      if ('outputs' in result) {
        expect(result.outputs.trigger).toBeUndefined();
        expect(result.outputs.count).toBe(1);
      }
    });

    it('should include execution metadata', async () => {
      const result = await TimerTriggerNode.execute(
        { delay: 50, interval: 0 },
        mockContext
      );

      if ('meta' in result) {
        expect(result.meta?.mode).toBe('one-shot');
        expect(result.meta?.delay).toBe(50);
        expect(result.meta?.interval).toBe(0);
      }
    });
  });

  describe('Execution - Interval Mode', () => {
    it('should log warning for interval mode (not yet implemented)', async () => {
      await TimerTriggerNode.execute(
        { delay: 50, interval: 100, maxTriggers: 5 },
        mockContext
      );

      // Should log warning about interval mode not being implemented
      expect(logSpy).toHaveBeenCalledWith(
        'warn',
        expect.stringContaining('Interval-based repeating triggers not yet implemented'),
        expect.any(Object)
      );
    });

    it('should set correct mode in metadata for interval', async () => {
      const result = await TimerTriggerNode.execute(
        { delay: 50, interval: 100 },
        mockContext
      );

      if ('meta' in result) {
        expect(result.meta?.mode).toBe('interval');
      }
    });
  });

  describe('Error Handling', () => {
    it('should handle abort signal', async () => {
      const abortController = new AbortController();

      // Abort immediately
      abortController.abort();

      const abortContext = {
        ...mockContext,
        signal: abortController.signal,
      };

      await expect(
        TimerTriggerNode.execute({ delay: 1000 }, abortContext)
      ).rejects.toThrow('aborted');

      expect(emitStateSpy).toHaveBeenCalledWith('error');
    });

    it('should handle abort signal during delay', async () => {
      const abortController = new AbortController();

      const abortContext = {
        ...mockContext,
        signal: abortController.signal,
      };

      // Start execution and abort after 50ms
      const executePromise = TimerTriggerNode.execute(
        { delay: 500 },
        abortContext
      );

      setTimeout(() => abortController.abort(), 50);

      await expect(executePromise).rejects.toThrow('aborted');
      expect(emitStateSpy).toHaveBeenCalledWith('error');
    });
  });

  describe('Data Passing', () => {
    it('should pass through simple data types', async () => {
      const testData = 'hello';
      const result = await TimerTriggerNode.execute(
        { delay: 50, data: testData },
        mockContext
      );

      if ('outputs' in result) {
        expect(result.outputs.trigger).toBe(testData);
      }
    });

    it('should pass through complex objects', async () => {
      const testData = { key: 'value', number: 42, nested: { data: true } };
      const result = await TimerTriggerNode.execute(
        { delay: 50, data: testData },
        mockContext
      );

      if ('outputs' in result) {
        expect(result.outputs.trigger).toEqual(testData);
      }
    });

    it('should pass through arrays', async () => {
      const testData = [1, 2, 3, 'four', { five: 5 }];
      const result = await TimerTriggerNode.execute(
        { delay: 50, data: testData },
        mockContext
      );

      if ('outputs' in result) {
        expect(result.outputs.trigger).toEqual(testData);
      }
    });
  });

  describe('Metadata', () => {
    it('should have metadata defined', () => {
      expect(TimerTriggerNode.metadata).toBeDefined();
      expect(TimerTriggerNode.metadata?.version).toBe('1.0.0');
      expect(TimerTriggerNode.metadata?.author).toBe('Mascarade');
      expect(TimerTriggerNode.metadata?.tags).toContain('automation');
      expect(TimerTriggerNode.metadata?.tags).toContain('timer');
      expect(TimerTriggerNode.metadata?.experimental).toBe(false);
    });
  });
});
