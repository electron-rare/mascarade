/**
 * IfNode Tests
 *
 * Tests for the If node plugin, including:
 * - Input validation
 * - Conditional branching logic
 * - Truthy/falsy value handling
 * - State emission
 * - Error handling
 */

import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import { IfNode } from '../IfNode.js';
import type { ExecutionContext } from '../../../NodePluginAPI.js';

describe('IfNode', () => {
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
      expect(IfNode.id).toBe('if');
      expect(IfNode.category).toBe('Workflow');
    });

    it('should have correct label and description', () => {
      expect(IfNode.label).toBe('If');
      expect(IfNode.description).toContain('Conditional branching');
    });

    it('should define required inputs', () => {
      expect(IfNode.inputs).toBeDefined();
      const conditionInput = IfNode.inputs.find((i) => i.id === 'condition');
      expect(conditionInput).toBeDefined();
      expect(conditionInput?.required).toBe(true);
    });

    it('should define expected outputs', () => {
      expect(IfNode.outputs).toBeDefined();
      const outputIds = IfNode.outputs.map((o) => o.id);
      expect(outputIds).toContain('then');
      expect(outputIds).toContain('else');
      expect(outputIds).toContain('result');
    });
  });

  describe('Input Validation', () => {
    it('should validate missing condition', () => {
      const errors = IfNode.validate?.({});
      expect(errors).toBeDefined();
      expect(errors?.length).toBeGreaterThan(0);
      expect(errors?.[0]).toContain('Condition must be provided');
    });

    it('should validate null condition', () => {
      const errors = IfNode.validate?.({ condition: null });
      expect(errors).toBeDefined();
      expect(errors?.length).toBeGreaterThan(0);
    });

    it('should pass validation with boolean condition', () => {
      const errors = IfNode.validate?.({ condition: true });
      expect(errors).toBeDefined();
      expect(errors?.length).toBe(0);
    });

    it('should pass validation with truthy condition', () => {
      const errors = IfNode.validate?.({ condition: 'yes' });
      expect(errors).toBeDefined();
      expect(errors?.length).toBe(0);
    });

    it('should pass validation with falsy condition', () => {
      const errors = IfNode.validate?.({ condition: 0 });
      expect(errors).toBeDefined();
      expect(errors?.length).toBe(0);
    });
  });

  describe('Execution - True Condition', () => {
    it('should route to then branch when condition is true', async () => {
      const result = await IfNode.execute(
        { condition: true, data: 'test-data' },
        mockContext
      );

      // Verify state emissions
      expect(emitStateSpy).toHaveBeenCalledWith('running');
      expect(emitStateSpy).toHaveBeenCalledWith('complete');

      // Verify logs
      expect(logSpy).toHaveBeenCalledWith('info', 'Evaluating condition', expect.any(Object));
      expect(logSpy).toHaveBeenCalledWith('info', 'Condition evaluated', expect.objectContaining({
        result: true,
        branch: 'then',
      }));

      // Verify outputs
      expect(result).toBeDefined();
      if ('outputs' in result) {
        expect(result.outputs.then).toBe('test-data');
        expect(result.outputs.else).toBeUndefined();
        expect(result.outputs.result).toBe(true);
      }
    });

    it('should handle truthy values as true', async () => {
      const truthyValues = [1, 'yes', 'true', [], {}, -1];

      for (const value of truthyValues) {
        const result = await IfNode.execute(
          { condition: value },
          mockContext
        );

        if ('outputs' in result) {
          expect(result.outputs.result).toBe(true);
        }
      }
    });
  });

  describe('Execution - False Condition', () => {
    it('should route to else branch when condition is false', async () => {
      const result = await IfNode.execute(
        { condition: false, data: 'test-data' },
        mockContext
      );

      // Verify state emissions
      expect(emitStateSpy).toHaveBeenCalledWith('running');
      expect(emitStateSpy).toHaveBeenCalledWith('complete');

      // Verify logs
      expect(logSpy).toHaveBeenCalledWith('info', 'Condition evaluated', expect.objectContaining({
        result: false,
        branch: 'else',
      }));

      // Verify outputs
      expect(result).toBeDefined();
      if ('outputs' in result) {
        expect(result.outputs.then).toBeUndefined();
        expect(result.outputs.else).toBe('test-data');
        expect(result.outputs.result).toBe(false);
      }
    });

    it('should handle falsy values as false', async () => {
      const falsyValues = [0, '', false, undefined];

      for (const value of falsyValues) {
        // Skip undefined for condition as it's invalid
        if (value === undefined) continue;

        const result = await IfNode.execute(
          { condition: value },
          mockContext
        );

        if ('outputs' in result) {
          expect(result.outputs.result).toBe(false);
        }
      }
    });
  });

  describe('Data Passing', () => {
    it('should pass data through then branch when true', async () => {
      const testData = { key: 'value', number: 42 };
      const result = await IfNode.execute(
        { condition: true, data: testData },
        mockContext
      );

      if ('outputs' in result) {
        expect(result.outputs.then).toEqual(testData);
      }
    });

    it('should pass data through else branch when false', async () => {
      const testData = { key: 'value', number: 42 };
      const result = await IfNode.execute(
        { condition: false, data: testData },
        mockContext
      );

      if ('outputs' in result) {
        expect(result.outputs.else).toEqual(testData);
      }
    });

    it('should work without data parameter', async () => {
      const result = await IfNode.execute(
        { condition: true },
        mockContext
      );

      if ('outputs' in result) {
        expect(result.outputs.then).toBeUndefined();
        expect(result.outputs.result).toBe(true);
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
        IfNode.execute({ condition: true }, abortContext)
      ).rejects.toThrow('aborted');

      expect(emitStateSpy).toHaveBeenCalledWith('error');
    });
  });

  describe('Metadata', () => {
    it('should have metadata defined', () => {
      expect(IfNode.metadata).toBeDefined();
      expect(IfNode.metadata?.version).toBe('1.0.0');
      expect(IfNode.metadata?.author).toBe('Mascarade');
      expect(IfNode.metadata?.tags).toContain('workflow');
      expect(IfNode.metadata?.tags).toContain('conditional');
      expect(IfNode.metadata?.experimental).toBe(false);
    });
  });
});
