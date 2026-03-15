/**
 * GCodeGeneratorNode Tests
 *
 * Tests for the G-Code Generator node plugin, including:
 * - Input validation
 * - G-code generation for different patterns
 * - Output format verification
 * - State emission
 * - Error handling
 */

import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import { GCodeGeneratorNode } from '../GCodeGeneratorNode.js';
import type { ExecutionContext } from '../../../NodePluginAPI.js';

describe('GCodeGeneratorNode', () => {
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
      expect(GCodeGeneratorNode.id).toBe('gcode-generator');
      expect(GCodeGeneratorNode.category).toBe('CAD');
    });

    it('should have correct label and description', () => {
      expect(GCodeGeneratorNode.label).toBe('G-Code Generator');
      expect(GCodeGeneratorNode.description).toContain('G-code');
    });

    it('should define required inputs', () => {
      expect(GCodeGeneratorNode.inputs).toBeDefined();
      const patternInput = GCodeGeneratorNode.inputs.find((i) => i.id === 'pattern');
      expect(patternInput).toBeDefined();
      expect(patternInput?.required).toBe(true);
    });

    it('should define expected outputs', () => {
      expect(GCodeGeneratorNode.outputs).toBeDefined();
      const outputIds = GCodeGeneratorNode.outputs.map((o) => o.id);
      expect(outputIds).toContain('gcode');
      expect(outputIds).toContain('line_count');
      expect(outputIds).toContain('pattern_type');
    });
  });

  describe('Input Validation', () => {
    it('should validate invalid pattern type', () => {
      const errors = GCodeGeneratorNode.validate?.({ pattern: 'invalid' });
      expect(errors).toBeDefined();
      expect(errors?.length).toBeGreaterThan(0);
      expect(errors?.[0]).toContain('Pattern must be one of');
    });

    it('should validate negative width', () => {
      const errors = GCodeGeneratorNode.validate?.({
        pattern: 'line',
        width: -10,
      });
      expect(errors).toBeDefined();
      expect(errors?.some((e) => e.includes('Width'))).toBe(true);
    });

    it('should validate negative height', () => {
      const errors = GCodeGeneratorNode.validate?.({
        pattern: 'rectangle',
        height: -10,
      });
      expect(errors).toBeDefined();
      expect(errors?.some((e) => e.includes('Height'))).toBe(true);
    });

    it('should validate negative radius', () => {
      const errors = GCodeGeneratorNode.validate?.({
        pattern: 'circle',
        radius: -10,
      });
      expect(errors).toBeDefined();
      expect(errors?.some((e) => e.includes('Radius'))).toBe(true);
    });

    it('should validate negative feed rate', () => {
      const errors = GCodeGeneratorNode.validate?.({
        pattern: 'line',
        feedRate: -100,
      });
      expect(errors).toBeDefined();
      expect(errors?.some((e) => e.includes('Feed rate'))).toBe(true);
    });

    it('should pass validation with valid inputs', () => {
      const errors = GCodeGeneratorNode.validate?.({
        pattern: 'rectangle',
        width: 100,
        height: 50,
        feedRate: 1000,
        spindleSpeed: 12000,
      });
      expect(errors).toBeDefined();
      expect(errors?.length).toBe(0);
    });
  });

  describe('Execution - Line Pattern', () => {
    it('should generate valid G-code for line pattern', async () => {
      const result = await GCodeGeneratorNode.execute(
        {
          pattern: 'line',
          width: 100,
          feedRate: 1000,
          spindleSpeed: 12000,
        },
        mockContext
      );

      // Verify state emissions
      expect(emitStateSpy).toHaveBeenCalledWith('running');
      expect(emitStateSpy).toHaveBeenCalledWith('complete');

      // Verify logs
      expect(logSpy).toHaveBeenCalledWith('info', 'Starting G-code generation', expect.any(Object));
      expect(logSpy).toHaveBeenCalledWith('info', 'G-code generation completed', expect.any(Object));

      // Verify outputs
      expect(result).toBeDefined();
      if ('outputs' in result) {
        expect(result.outputs.gcode).toBeDefined();
        expect(typeof result.outputs.gcode).toBe('string');
        expect(result.outputs.pattern_type).toBe('line');
        expect(typeof result.outputs.line_count).toBe('number');
        expect(result.outputs.line_count).toBeGreaterThan(0);

        // Verify G-code content
        const gcode = String(result.outputs.gcode);
        expect(gcode).toContain('G21'); // Units to mm
        expect(gcode).toContain('G90'); // Absolute positioning
        expect(gcode).toContain('M3 S12000'); // Spindle start
        expect(gcode).toContain('M5'); // Spindle stop
        expect(gcode).toContain('M2'); // End program
        expect(gcode).toContain('Line toolpath');
      }
    });
  });

  describe('Execution - Rectangle Pattern', () => {
    it('should generate valid G-code for rectangle pattern', async () => {
      const result = await GCodeGeneratorNode.execute(
        {
          pattern: 'rectangle',
          width: 100,
          height: 50,
          feedRate: 1000,
          spindleSpeed: 12000,
        },
        mockContext
      );

      // Verify state emissions
      expect(emitStateSpy).toHaveBeenCalledWith('running');
      expect(emitStateSpy).toHaveBeenCalledWith('complete');

      // Verify outputs
      expect(result).toBeDefined();
      if ('outputs' in result) {
        expect(result.outputs.gcode).toBeDefined();
        expect(typeof result.outputs.gcode).toBe('string');
        expect(result.outputs.pattern_type).toBe('rectangle');

        // Verify G-code content
        const gcode = String(result.outputs.gcode);
        expect(gcode).toContain('Rectangle toolpath');
        expect(gcode).toContain('G1 X100 Y0'); // Right edge
        expect(gcode).toContain('G1 X100 Y50'); // Top edge
        expect(gcode).toContain('G1 X0 Y50'); // Left edge
        expect(gcode).toContain('G1 X0 Y0'); // Bottom edge (close)
      }
    });
  });

  describe('Execution - Circle Pattern', () => {
    it('should generate valid G-code for circle pattern', async () => {
      const result = await GCodeGeneratorNode.execute(
        {
          pattern: 'circle',
          radius: 50,
          feedRate: 1000,
          spindleSpeed: 12000,
        },
        mockContext
      );

      // Verify state emissions
      expect(emitStateSpy).toHaveBeenCalledWith('running');
      expect(emitStateSpy).toHaveBeenCalledWith('complete');

      // Verify outputs
      expect(result).toBeDefined();
      if ('outputs' in result) {
        expect(result.outputs.gcode).toBeDefined();
        expect(typeof result.outputs.gcode).toBe('string');
        expect(result.outputs.pattern_type).toBe('circle');

        // Verify G-code content
        const gcode = String(result.outputs.gcode);
        expect(gcode).toContain('Circle toolpath');
        expect(gcode).toContain('G2'); // Circular interpolation
        expect(gcode).toContain('I-50'); // I offset for circle center
      }
    });
  });

  describe('G-Code Format', () => {
    it('should output valid G-code string', async () => {
      const result = await GCodeGeneratorNode.execute(
        { pattern: 'line', width: 50 },
        mockContext
      );

      if ('outputs' in result) {
        const gcode = String(result.outputs.gcode);

        // Verify standard G-code commands present
        expect(gcode).toContain('G21'); // Units
        expect(gcode).toContain('G90'); // Absolute mode
        expect(gcode).toContain('M3'); // Spindle on
        expect(gcode).toContain('M5'); // Spindle off
        expect(gcode).toContain('M2'); // Program end

        // Verify proper line structure
        const lines = gcode.split('\n');
        expect(lines.length).toBeGreaterThan(5);
      }
    });

    it('should include proper header comments', async () => {
      const result = await GCodeGeneratorNode.execute(
        { pattern: 'rectangle', width: 100, height: 50 },
        mockContext
      );

      if ('outputs' in result) {
        const gcode = String(result.outputs.gcode);
        expect(gcode).toContain('(G-code generated by Mascarade Node Engine)');
        expect(gcode).toContain('(Pattern: rectangle)');
        expect(gcode).toContain('(Feed Rate:');
        expect(gcode).toContain('(Spindle Speed:');
      }
    });
  });

  describe('Default Values', () => {
    it('should use default values when inputs not provided', async () => {
      const result = await GCodeGeneratorNode.execute(
        { pattern: 'rectangle' },
        mockContext
      );

      expect(result).toBeDefined();
      if ('outputs' in result) {
        expect(result.outputs.gcode).toBeDefined();
        expect(result.outputs.pattern_type).toBe('rectangle');

        // Should use defaults from input definitions
        const gcode = String(result.outputs.gcode);
        expect(gcode).toBeDefined();
      }
    });
  });

  describe('Error Handling', () => {
    it('should handle invalid pattern gracefully', async () => {
      await expect(
        GCodeGeneratorNode.execute(
          { pattern: 'invalid-pattern' },
          mockContext
        )
      ).rejects.toThrow('Unknown pattern type');

      expect(emitStateSpy).toHaveBeenCalledWith('error');
    });

    it('should handle abort signal', async () => {
      const abortController = new AbortController();
      abortController.abort();

      const abortContext = {
        ...mockContext,
        signal: abortController.signal,
      };

      await expect(
        GCodeGeneratorNode.execute({ pattern: 'line' }, abortContext)
      ).rejects.toThrow('aborted');

      expect(emitStateSpy).toHaveBeenCalledWith('error');
    });
  });

  describe('Metadata', () => {
    it('should have metadata defined', () => {
      expect(GCodeGeneratorNode.metadata).toBeDefined();
      expect(GCodeGeneratorNode.metadata?.version).toBe('1.0.0');
      expect(GCodeGeneratorNode.metadata?.author).toBe('Mascarade');
      expect(GCodeGeneratorNode.metadata?.tags).toContain('cad');
      expect(GCodeGeneratorNode.metadata?.tags).toContain('gcode');
      expect(GCodeGeneratorNode.metadata?.experimental).toBe(false);
    });
  });

  describe('Output Metadata', () => {
    it('should include execution metadata', async () => {
      const result = await GCodeGeneratorNode.execute(
        {
          pattern: 'line',
          width: 100,
          feedRate: 1000,
        },
        mockContext
      );

      if ('meta' in result && result.meta) {
        expect(result.meta.pattern).toBe('line');
        expect(result.meta.lineCount).toBeGreaterThan(0);
        expect(result.meta.gcodeLength).toBeGreaterThan(0);
        expect(result.meta.parameters).toBeDefined();
      }
    });
  });
});
