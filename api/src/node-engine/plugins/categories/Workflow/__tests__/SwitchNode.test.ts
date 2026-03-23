/**
 * SwitchNode Tests
 *
 * Tests for the Switch node plugin, including:
 * - Input validation
 * - Multi-way branching logic
 * - Case matching (strict equality)
 * - Default case handling
 * - State emission
 * - Error handling
 */

import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import { SwitchNode } from '../SwitchNode.js';
import type { ExecutionContext } from '../../../NodePluginAPI.js';

describe('SwitchNode', () => {
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
      expect(SwitchNode.id).toBe('switch');
      expect(SwitchNode.category).toBe('Workflow');
    });

    it('should have correct label and description', () => {
      expect(SwitchNode.label).toBe('Switch');
      expect(SwitchNode.description).toContain('Multi-way branching');
    });

    it('should define required inputs', () => {
      expect(SwitchNode.inputs).toBeDefined();
      const valueInput = SwitchNode.inputs.find((i) => i.id === 'value');
      expect(valueInput).toBeDefined();
      expect(valueInput?.required).toBe(true);
    });

    it('should define case inputs', () => {
      const caseInputs = SwitchNode.inputs.filter((i) => i.id.startsWith('case'));
      expect(caseInputs.length).toBeGreaterThanOrEqual(4);
    });

    it('should define expected outputs', () => {
      expect(SwitchNode.outputs).toBeDefined();
      const outputIds = SwitchNode.outputs.map((o) => o.id);
      expect(outputIds).toContain('output0');
      expect(outputIds).toContain('output1');
      expect(outputIds).toContain('output2');
      expect(outputIds).toContain('output3');
      expect(outputIds).toContain('default');
      expect(outputIds).toContain('matched_index');
    });
  });

  describe('Input Validation', () => {
    it('should validate missing value', () => {
      const errors = SwitchNode.validate?.({ case0: 'a' });
      expect(errors).toBeDefined();
      expect(errors?.length).toBeGreaterThan(0);
      expect(errors?.[0]).toContain('Value must be provided');
    });

    it('should validate null value', () => {
      const errors = SwitchNode.validate?.({ value: null, case0: 'a' });
      expect(errors).toBeDefined();
      expect(errors?.length).toBeGreaterThan(0);
    });

    it('should validate missing cases', () => {
      const errors = SwitchNode.validate?.({ value: 'test' });
      expect(errors).toBeDefined();
      expect(errors?.some((e) => e.includes('At least one case'))).toBe(true);
    });

    it('should pass validation with value and at least one case', () => {
      const errors = SwitchNode.validate?.({ value: 'test', case0: 'a' });
      expect(errors).toBeDefined();
      expect(errors?.length).toBe(0);
    });
  });

  describe('Case Matching', () => {
    it('should match case0 and route to output0', async () => {
      const result = await SwitchNode.execute(
        {
          value: 'alpha',
          case0: 'alpha',
          case1: 'beta',
          data: 'test-data',
        },
        mockContext
      );

      // Verify state emissions
      expect(emitStateSpy).toHaveBeenCalledWith('running');
      expect(emitStateSpy).toHaveBeenCalledWith('complete');

      // Verify outputs
      if ('outputs' in result) {
        expect(result.outputs.output0).toBe('test-data');
        expect(result.outputs.output1).toBeUndefined();
        expect(result.outputs.output2).toBeUndefined();
        expect(result.outputs.output3).toBeUndefined();
        expect(result.outputs.default).toBeUndefined();
        expect(result.outputs.matched_index).toBe(0);
      }
    });

    it('should match case1 and route to output1', async () => {
      const result = await SwitchNode.execute(
        {
          value: 'beta',
          case0: 'alpha',
          case1: 'beta',
          case2: 'gamma',
          data: 'test-data',
        },
        mockContext
      );

      if ('outputs' in result) {
        expect(result.outputs.output1).toBe('test-data');
        expect(result.outputs.output0).toBeUndefined();
        expect(result.outputs.matched_index).toBe(1);
      }
    });

    it('should match case2 and route to output2', async () => {
      const result = await SwitchNode.execute(
        {
          value: 42,
          case0: 10,
          case1: 20,
          case2: 42,
          data: 'test-data',
        },
        mockContext
      );

      if ('outputs' in result) {
        expect(result.outputs.output2).toBe('test-data');
        expect(result.outputs.matched_index).toBe(2);
      }
    });

    it('should match case3 and route to output3', async () => {
      const result = await SwitchNode.execute(
        {
          value: true,
          case0: false,
          case1: 0,
          case2: '',
          case3: true,
          data: 'test-data',
        },
        mockContext
      );

      if ('outputs' in result) {
        expect(result.outputs.output3).toBe('test-data');
        expect(result.outputs.matched_index).toBe(3);
      }
    });
  });

  describe('Default Case', () => {
    it('should route to default when no case matches', async () => {
      const result = await SwitchNode.execute(
        {
          value: 'delta',
          case0: 'alpha',
          case1: 'beta',
          case2: 'gamma',
          data: 'test-data',
        },
        mockContext
      );

      if ('outputs' in result) {
        expect(result.outputs.default).toBe('test-data');
        expect(result.outputs.output0).toBeUndefined();
        expect(result.outputs.output1).toBeUndefined();
        expect(result.outputs.output2).toBeUndefined();
        expect(result.outputs.output3).toBeUndefined();
        expect(result.outputs.matched_index).toBe(-1);
      }
    });

    it('should route to default when value does not match any case', async () => {
      const result = await SwitchNode.execute(
        {
          value: 999,
          case0: 1,
          case1: 2,
          data: 'default-data',
        },
        mockContext
      );

      if ('outputs' in result) {
        expect(result.outputs.default).toBe('default-data');
        expect(result.outputs.matched_index).toBe(-1);
      }
    });
  });

  describe('Strict Equality', () => {
    it('should use strict equality for matching', async () => {
      // String '1' should not match number 1
      const result = await SwitchNode.execute(
        {
          value: '1',
          case0: 1,
          case1: '1',
          data: 'test',
        },
        mockContext
      );

      if ('outputs' in result) {
        expect(result.outputs.output1).toBe('test');
        expect(result.outputs.output0).toBeUndefined();
        expect(result.outputs.matched_index).toBe(1);
      }
    });

    it('should distinguish between false and 0', async () => {
      const result = await SwitchNode.execute(
        {
          value: false,
          case0: 0,
          case1: false,
          data: 'test',
        },
        mockContext
      );

      if ('outputs' in result) {
        expect(result.outputs.output1).toBe('test');
        expect(result.outputs.matched_index).toBe(1);
      }
    });
  });

  describe('Data Passing', () => {
    it('should pass complex data through matched output', async () => {
      const testData = { key: 'value', nested: { data: [1, 2, 3] } };
      const result = await SwitchNode.execute(
        {
          value: 'match',
          case0: 'match',
          data: testData,
        },
        mockContext
      );

      if ('outputs' in result) {
        expect(result.outputs.output0).toEqual(testData);
      }
    });

    it('should work without data parameter', async () => {
      const result = await SwitchNode.execute(
        {
          value: 'test',
          case0: 'test',
        },
        mockContext
      );

      if ('outputs' in result) {
        expect(result.outputs.output0).toBeUndefined();
        expect(result.outputs.matched_index).toBe(0);
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
        SwitchNode.execute({ value: 'test', case0: 'test' }, abortContext)
      ).rejects.toThrow('aborted');

      expect(emitStateSpy).toHaveBeenCalledWith('error');
    });
  });

  describe('Metadata', () => {
    it('should have metadata defined', () => {
      expect(SwitchNode.metadata).toBeDefined();
      expect(SwitchNode.metadata?.version).toBe('1.0.0');
      expect(SwitchNode.metadata?.author).toBe('Mascarade');
      expect(SwitchNode.metadata?.tags).toContain('workflow');
      expect(SwitchNode.metadata?.tags).toContain('switch');
      expect(SwitchNode.metadata?.experimental).toBe(false);
    });
  });
});
