/**
 * G-Code Generator Node - CAD category example node
 *
 * Generates simple G-code toolpaths for basic shapes (line, rectangle, circle).
 * This is a lightweight CAD node focused on G-code export rather than full CAD kernel.
 *
 * Features:
 * - Multiple toolpath patterns (line, rectangle, circle)
 * - Configurable feed rate and spindle speed
 * - Standard G-code output (G0, G1, G2, G3)
 * - Tool radius compensation support
 *
 * Inspired by:
 * - CNC toolpath generators
 * - CAM software workflow
 * - G-code standards (NIST RS274NGC)
 */

import {
  NodeCategory,
  type NodePlugin,
  type ExecutionContext,
  type NodeExecutionResult,
} from '../../NodePluginAPI.js';

/**
 * G-Code Generator Node Plugin
 *
 * Generates G-code for simple toolpaths. Useful for CNC machining, 3D printing
 * setup, laser cutting, and other CAD/CAM workflows.
 *
 * Example usage in a graph:
 * 1. Design Parameters → GCodeGeneratorNode → File Export
 * 2. User Input → GCodeGeneratorNode → CNC Controller
 *
 * Configuration:
 * - pattern: Toolpath pattern type (line, rectangle, circle)
 * - width: Width of the pattern (mm, for line and rectangle)
 * - height: Height of the pattern (mm, for rectangle)
 * - radius: Radius of the pattern (mm, for circle)
 * - feedRate: Feed rate (mm/min)
 * - spindleSpeed: Spindle speed (RPM)
 * - toolDiameter: Tool diameter (mm) for radius compensation
 * - safeHeight: Safe Z height for rapid moves (mm)
 * - cutDepth: Cutting depth (mm, negative for cutting)
 */
export const GCodeGeneratorNode: NodePlugin = {
  id: 'gcode-generator',
  category: NodeCategory.CAD,
  label: 'G-Code Generator',
  description: 'Generate G-code toolpaths for simple shapes (line, rectangle, circle)',

  inputs: [
    {
      id: 'pattern',
      label: 'Pattern',
      type: 'string',
      required: true,
      defaultValue: 'rectangle',
      description: 'Toolpath pattern: line, rectangle, or circle',
    },
    {
      id: 'width',
      label: 'Width (mm)',
      type: 'number',
      required: false,
      defaultValue: 100,
      description: 'Width of the pattern (for line and rectangle)',
    },
    {
      id: 'height',
      label: 'Height (mm)',
      type: 'number',
      required: false,
      defaultValue: 50,
      description: 'Height of the pattern (for rectangle)',
    },
    {
      id: 'radius',
      label: 'Radius (mm)',
      type: 'number',
      required: false,
      defaultValue: 50,
      description: 'Radius of the pattern (for circle)',
    },
    {
      id: 'feedRate',
      label: 'Feed Rate (mm/min)',
      type: 'number',
      required: false,
      defaultValue: 1000,
      description: 'Feed rate for cutting moves',
    },
    {
      id: 'spindleSpeed',
      label: 'Spindle Speed (RPM)',
      type: 'number',
      required: false,
      defaultValue: 12000,
      description: 'Spindle rotation speed',
    },
    {
      id: 'toolDiameter',
      label: 'Tool Diameter (mm)',
      type: 'number',
      required: false,
      defaultValue: 6,
      description: 'Tool diameter for radius compensation',
    },
    {
      id: 'safeHeight',
      label: 'Safe Z Height (mm)',
      type: 'number',
      required: false,
      defaultValue: 5,
      description: 'Safe Z height for rapid moves',
    },
    {
      id: 'cutDepth',
      label: 'Cut Depth (mm)',
      type: 'number',
      required: false,
      defaultValue: -2,
      description: 'Cutting depth (negative for cutting)',
    },
  ],

  outputs: [
    {
      id: 'gcode',
      label: 'G-Code',
      type: 'string',
      description: 'Generated G-code program',
    },
    {
      id: 'line_count',
      label: 'Line Count',
      type: 'number',
      description: 'Number of lines in generated G-code',
    },
    {
      id: 'pattern_type',
      label: 'Pattern Type',
      type: 'string',
      description: 'The pattern type that was generated',
    },
  ],

  /**
   * Validate inputs before execution
   *
   * Ensures:
   * - Pattern type is valid
   * - Dimensions are positive
   * - Feed rate is positive
   * - Spindle speed is positive
   * - Tool diameter is positive
   * - Safe height is positive
   */
  validate: (inputs: Record<string, unknown>): string[] => {
    const errors: string[] = [];

    // Validate pattern
    const pattern = inputs.pattern;
    const validPatterns = ['line', 'rectangle', 'circle'];
    if (typeof pattern !== 'string' || !validPatterns.includes(pattern)) {
      errors.push(`Pattern must be one of: ${validPatterns.join(', ')}`);
    }

    // Validate dimensions
    const width = inputs.width;
    if (width !== undefined && (typeof width !== 'number' || width <= 0)) {
      errors.push('Width must be a positive number');
    }

    const height = inputs.height;
    if (height !== undefined && (typeof height !== 'number' || height <= 0)) {
      errors.push('Height must be a positive number');
    }

    const radius = inputs.radius;
    if (radius !== undefined && (typeof radius !== 'number' || radius <= 0)) {
      errors.push('Radius must be a positive number');
    }

    // Validate feed rate
    const feedRate = inputs.feedRate;
    if (feedRate !== undefined && (typeof feedRate !== 'number' || feedRate <= 0)) {
      errors.push('Feed rate must be a positive number');
    }

    // Validate spindle speed
    const spindleSpeed = inputs.spindleSpeed;
    if (spindleSpeed !== undefined && (typeof spindleSpeed !== 'number' || spindleSpeed < 0)) {
      errors.push('Spindle speed must be a non-negative number');
    }

    // Validate tool diameter
    const toolDiameter = inputs.toolDiameter;
    if (toolDiameter !== undefined && (typeof toolDiameter !== 'number' || toolDiameter <= 0)) {
      errors.push('Tool diameter must be a positive number');
    }

    // Validate safe height
    const safeHeight = inputs.safeHeight;
    if (safeHeight !== undefined && (typeof safeHeight !== 'number' || safeHeight <= 0)) {
      errors.push('Safe height must be a positive number');
    }

    return errors;
  },

  /**
   * Execute G-code generation
   *
   * Workflow:
   * 1. Extract and validate inputs
   * 2. Emit 'running' state for UI feedback
   * 3. Generate G-code based on pattern type
   * 4. Emit 'complete' state
   * 5. Return G-code and metadata
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
    // Extract inputs with type safety
    const pattern = String(inputs.pattern || 'rectangle');
    const width = typeof inputs.width === 'number' ? inputs.width : 100;
    const height = typeof inputs.height === 'number' ? inputs.height : 50;
    const radius = typeof inputs.radius === 'number' ? inputs.radius : 50;
    const feedRate = typeof inputs.feedRate === 'number' ? inputs.feedRate : 1000;
    const spindleSpeed = typeof inputs.spindleSpeed === 'number' ? inputs.spindleSpeed : 12000;
    const toolDiameter = typeof inputs.toolDiameter === 'number' ? inputs.toolDiameter : 6;
    const safeHeight = typeof inputs.safeHeight === 'number' ? inputs.safeHeight : 5;
    const cutDepth = typeof inputs.cutDepth === 'number' ? inputs.cutDepth : -2;

    // Log execution start
    context.log('info', 'Starting G-code generation', {
      pattern,
      width,
      height,
      radius,
      feedRate,
      spindleSpeed,
    });

    // Emit running state
    context.emitState('running');

    try {
      // Check for abort signal
      if (context.signal?.aborted) {
        throw new Error('Execution aborted');
      }

      // Generate G-code header
      const lines: string[] = [];
      lines.push('(G-code generated by Mascarade Node Engine)');
      lines.push(`(Pattern: ${pattern})`);
      lines.push(`(Feed Rate: ${feedRate} mm/min)`);
      lines.push(`(Spindle Speed: ${spindleSpeed} RPM)`);
      lines.push(`(Tool Diameter: ${toolDiameter} mm)`);
      lines.push('');
      lines.push('G21 ; Set units to millimeters');
      lines.push('G90 ; Absolute positioning');
      lines.push('G17 ; XY plane selection');
      lines.push(`M3 S${spindleSpeed} ; Start spindle`);
      lines.push(`G0 Z${safeHeight} ; Move to safe height`);
      lines.push('');

      // Generate toolpath based on pattern
      switch (pattern) {
        case 'line':
          generateLineToolpath(lines, width, feedRate, safeHeight, cutDepth);
          break;
        case 'rectangle':
          generateRectangleToolpath(lines, width, height, feedRate, safeHeight, cutDepth);
          break;
        case 'circle':
          generateCircleToolpath(lines, radius, feedRate, safeHeight, cutDepth);
          break;
        default:
          throw new Error(`Unknown pattern type: ${pattern}`);
      }

      // Generate G-code footer
      lines.push('');
      lines.push(`G0 Z${safeHeight} ; Return to safe height`);
      lines.push('M5 ; Stop spindle');
      lines.push('G0 X0 Y0 ; Return to origin');
      lines.push('M2 ; End program');

      // Combine lines into G-code string
      const gcode = lines.join('\n');
      const lineCount = lines.length;

      // Log success
      context.log('info', 'G-code generation completed', {
        pattern,
        lineCount,
        gcodeLength: gcode.length,
      });

      // Emit complete state
      context.emitState('complete');

      // Return outputs
      return {
        outputs: {
          gcode,
          line_count: lineCount,
          pattern_type: pattern,
        },
        meta: {
          executionTime: Date.now(),
          pattern,
          lineCount,
          gcodeLength: gcode.length,
          parameters: {
            width,
            height,
            radius,
            feedRate,
            spindleSpeed,
            toolDiameter,
            safeHeight,
            cutDepth,
          },
        },
      };
    } catch (error) {
      // Log error
      const errorMessage = error instanceof Error ? error.message : String(error);
      context.log('error', 'G-code generation failed', {
        error: errorMessage,
        pattern,
      });

      // Emit error state
      context.emitState('error');

      // Re-throw to propagate
      throw new Error(`G-code generation failed: ${errorMessage}`);
    }
  },

  /**
   * Plugin metadata
   */
  metadata: {
    version: '1.0.0',
    author: 'Mascarade',
    tags: ['cad', 'cnc', 'gcode', 'toolpath', 'machining'],
    experimental: false,
  },
};

/**
 * Generate G-code for a line toolpath
 */
function generateLineToolpath(
  lines: string[],
  width: number,
  feedRate: number,
  safeHeight: number,
  cutDepth: number
): void {
  lines.push('(Line toolpath)');
  lines.push('G0 X0 Y0 ; Move to start position');
  lines.push(`G0 Z${cutDepth} ; Move to cut depth`);
  lines.push(`G1 X${width} Y0 F${feedRate} ; Cut line`);
}

/**
 * Generate G-code for a rectangle toolpath
 */
function generateRectangleToolpath(
  lines: string[],
  width: number,
  height: number,
  feedRate: number,
  safeHeight: number,
  cutDepth: number
): void {
  lines.push('(Rectangle toolpath)');
  lines.push('G0 X0 Y0 ; Move to start position');
  lines.push(`G0 Z${cutDepth} ; Move to cut depth`);
  lines.push(`G1 X${width} Y0 F${feedRate} ; Cut right edge`);
  lines.push(`G1 X${width} Y${height} ; Cut top edge`);
  lines.push(`G1 X0 Y${height} ; Cut left edge`);
  lines.push('G1 X0 Y0 ; Cut bottom edge (close rectangle)');
}

/**
 * Generate G-code for a circle toolpath
 */
function generateCircleToolpath(
  lines: string[],
  radius: number,
  feedRate: number,
  safeHeight: number,
  cutDepth: number
): void {
  lines.push('(Circle toolpath)');
  lines.push(`G0 X${radius} Y0 ; Move to start position (right side of circle)`);
  lines.push(`G0 Z${cutDepth} ; Move to cut depth`);
  lines.push(`G2 X${radius} Y0 I${-radius} J0 F${feedRate} ; Cut full circle (clockwise)`);
}
