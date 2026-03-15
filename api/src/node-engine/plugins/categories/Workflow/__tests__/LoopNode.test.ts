/**
 * LoopNode Tests
 *
 * Tests for the Loop node plugin, including:
 * - Input validation
 * - Array iteration
 * - Numeric range iteration
 * - Step handling (positive/negative)
 * - State emission
 * - Error handling
 */

import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import { LoopNode } from '../LoopNode.js';
import type { ExecutionContext } from '../../../NodePluginAPI.js';

describe('LoopNode', () => {
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
      expect(LoopNode.id).toBe('loop');
      expect(LoopNode.category).toBe('Workflow');
    });

    it('should have correct label and description', () => {
      expect(LoopNode.label).toBe('Loop');
      expect(LoopNode.description).toContain('Iterate over array or numeric range');
    });

    it('should define inputs for both array and range modes', () => {
      expect(LoopNode.inputs).toBeDefined();
      const inputIds = LoopNode.inputs.map((i) => i.id);
      expect(inputIds).toContain('items');
      expect(inputIds).toContain('start');
      expect(inputIds).toContain('end');
      expect(inputIds).toContain('step');
    });

    it('should define expected outputs', () => {
      expect(LoopNode.outputs).toBeDefined();
      const outputIds = LoopNode.outputs.map((o) => o.id);
      expect(outputIds).toContain('items');
      expect(outputIds).toContain('count');
      expect(outputIds).toContain('first');
      expect(outputIds).toContain('last');
    });
  });

  describe('Input Validation', () => {
    it('should validate missing items and range', () => {
      const errors = LoopNode.validate?.({});
      expect(errors).toBeDefined();
      expect(errors?.some((e) => e.includes('Either items array or range'))).toBe(true);
    });

    it('should validate zero step', () => {
      const errors = LoopNode.validate?.({ end: 10, step: 0 });
      expect(errors).toBeDefined();
      expect(errors?.some((e) => e.includes('Step cannot be zero'))).toBe(true);
    });

    it('should validate invalid range with positive step', () => {
      const errors = LoopNode.validate?.({ start: 10, end: 5, step: 1 });
      expect(errors).toBeDefined();
      expect(errors?.some((e) => e.includes('End must be greater than start'))).toBe(true);
    });

    it('should validate invalid range with negative step', () => {
      const errors = LoopNode.validate?.({ start: 5, end: 10, step: -1 });
      expect(errors).toBeDefined();
      expect(errors?.some((e) => e.includes('End must be less than start'))).toBe(true);
    });

    it('should pass validation with items array', () => {
      const errors = LoopNode.validate?.({ items: [1, 2, 3] });
      expect(errors).toBeDefined();
      expect(errors?.length).toBe(0);
    });

    it('should pass validation with valid range', () => {
      const errors = LoopNode.validate?.({ start: 0, end: 10, step: 1 });
      expect(errors).toBeDefined();
      expect(errors?.length).toBe(0);
    });
  });

  describe('Array Mode', () => {
    it('should iterate over array of items', async () => {
      const items = ['a', 'b', 'c', 'd'];
      const result = await LoopNode.execute({ items }, mockContext);

      // Verify state emissions
      expect(emitStateSpy).toHaveBeenCalledWith('running');
      expect(emitStateSpy).toHaveBeenCalledWith('complete');

      // Verify logs
      expect(logSpy).toHaveBeenCalledWith('info', 'Starting loop iteration', expect.objectContaining({
        mode: 'array',
        arrayLength: 4,
      }));

      // Verify outputs
      if ('outputs' in result) {
        expect(result.outputs.items).toEqual(items);
        expect(result.outputs.count).toBe(4);
        expect(result.outputs.first).toBe('a');
        expect(result.outputs.last).toBe('d');
      }
    });

    it('should handle array of numbers', async () => {
      const items = [10, 20, 30, 40, 50];
      const result = await LoopNode.execute({ items }, mockContext);

      if ('outputs' in result) {
        expect(result.outputs.items).toEqual(items);
        expect(result.outputs.count).toBe(5);
        expect(result.outputs.first).toBe(10);
        expect(result.outputs.last).toBe(50);
      }
    });

    it('should handle array of objects', async () => {
      const items = [
        { id: 1, name: 'Alice' },
        { id: 2, name: 'Bob' },
      ];
      const result = await LoopNode.execute({ items }, mockContext);

      if ('outputs' in result) {
        expect(result.outputs.items).toEqual(items);
        expect(result.outputs.count).toBe(2);
        expect(result.outputs.first).toEqual({ id: 1, name: 'Alice' });
        expect(result.outputs.last).toEqual({ id: 2, name: 'Bob' });
      }
    });

    it('should handle single item as array', async () => {
      const result = await LoopNode.execute({ items: 'single' }, mockContext);

      if ('outputs' in result) {
        expect(result.outputs.items).toEqual(['single']);
        expect(result.outputs.count).toBe(1);
        expect(result.outputs.first).toBe('single');
        expect(result.outputs.last).toBe('single');
      }
    });

    it('should handle empty array', async () => {
      const result = await LoopNode.execute({ items: [] }, mockContext);

      if ('outputs' in result) {
        expect(result.outputs.items).toEqual([]);
        expect(result.outputs.count).toBe(0);
        expect(result.outputs.first).toBeUndefined();
        expect(result.outputs.last).toBeUndefined();
      }
    });
  });

  describe('Range Mode - Positive Step', () => {
    it('should generate range from 0 to 10 with step 1', async () => {
      const result = await LoopNode.execute(
        { start: 0, end: 10, step: 1 },
        mockContext
      );

      if ('outputs' in result) {
        expect(result.outputs.items).toEqual([0, 1, 2, 3, 4, 5, 6, 7, 8, 9]);
        expect(result.outputs.count).toBe(10);
        expect(result.outputs.first).toBe(0);
        expect(result.outputs.last).toBe(9);
      }
    });

    it('should generate range with step 2', async () => {
      const result = await LoopNode.execute(
        { start: 0, end: 10, step: 2 },
        mockContext
      );

      if ('outputs' in result) {
        expect(result.outputs.items).toEqual([0, 2, 4, 6, 8]);
        expect(result.outputs.count).toBe(5);
      }
    });

    it('should generate range with step 5', async () => {
      const result = await LoopNode.execute(
        { start: 0, end: 20, step: 5 },
        mockContext
      );

      if ('outputs' in result) {
        expect(result.outputs.items).toEqual([0, 5, 10, 15]);
        expect(result.outputs.count).toBe(4);
      }
    });

    it('should use default start value of 0', async () => {
      const result = await LoopNode.execute(
        { end: 5, step: 1 },
        mockContext
      );

      if ('outputs' in result) {
        expect(result.outputs.items).toEqual([0, 1, 2, 3, 4]);
        expect(result.outputs.first).toBe(0);
      }
    });

    it('should use default step value of 1', async () => {
      const result = await LoopNode.execute(
        { start: 0, end: 5 },
        mockContext
      );

      if ('outputs' in result) {
        expect(result.outputs.items).toEqual([0, 1, 2, 3, 4]);
      }
    });
  });

  describe('Range Mode - Negative Step', () => {
    it('should generate range from 10 to 0 with step -1', async () => {
      const result = await LoopNode.execute(
        { start: 10, end: 0, step: -1 },
        mockContext
      );

      if ('outputs' in result) {
        expect(result.outputs.items).toEqual([10, 9, 8, 7, 6, 5, 4, 3, 2, 1]);
        expect(result.outputs.count).toBe(10);
        expect(result.outputs.first).toBe(10);
        expect(result.outputs.last).toBe(1);
      }
    });

    it('should generate range with step -2', async () => {
      const result = await LoopNode.execute(
        { start: 10, end: 0, step: -2 },
        mockContext
      );

      if ('outputs' in result) {
        expect(result.outputs.items).toEqual([10, 8, 6, 4, 2]);
        expect(result.outputs.count).toBe(5);
      }
    });
  });

  describe('Edge Cases', () => {
    it('should handle range where start equals end', async () => {
      const result = await LoopNode.execute(
        { start: 5, end: 5, step: 1 },
        mockContext
      );

      if ('outputs' in result) {
        expect(result.outputs.items).toEqual([]);
        expect(result.outputs.count).toBe(0);
      }
    });

    it('should handle fractional steps', async () => {
      const result = await LoopNode.execute(
        { start: 0, end: 2, step: 0.5 },
        mockContext
      );

      if ('outputs' in result) {
        expect(result.outputs.items).toEqual([0, 0.5, 1, 1.5]);
        expect(result.outputs.count).toBe(4);
      }
    });
  });

  describe('Error Handling', () => {
    it('should handle abort signal', async () => {
      const abortController = new AbortController();
      abortController.abort();

      const abortContext = {
        ...mockContext,
        signal: abortController.signal,
      };

      await expect(
        LoopNode.execute({ items: [1, 2, 3] }, abortContext)
      ).rejects.toThrow('aborted');

      expect(emitStateSpy).toHaveBeenCalledWith('error');
    });
  });

  describe('Metadata', () => {
    it('should have metadata defined', () => {
      expect(LoopNode.metadata).toBeDefined();
      expect(LoopNode.metadata?.version).toBe('1.0.0');
      expect(LoopNode.metadata?.author).toBe('Mascarade');
      expect(LoopNode.metadata?.tags).toContain('workflow');
      expect(LoopNode.metadata?.tags).toContain('loop');
      expect(LoopNode.metadata?.tags).toContain('iteration');
      expect(LoopNode.metadata?.experimental).toBe(false);
    });
  });
});
