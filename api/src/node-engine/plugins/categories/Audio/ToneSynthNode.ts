/**
 * Tone.js Synth Node - Browser-based audio synthesis with user gesture gating
 *
 * Triggers synthesized audio notes using Tone.js. Enforces Web Audio API
 * autoplay policy by requiring audio context to be started via user gesture.
 *
 * Features:
 * - Simple monophonic synthesis
 * - Configurable note pitch and duration
 * - Audio context state validation (prevents autoplay policy violations)
 * - Graceful error messaging for context not started
 *
 * Inspired by:
 * - Max/MSP: Audio synthesis and signal processing
 * - Tone.js: Browser-based audio synthesis with Web Audio API
 * - TouchDesigner: Real-time audio processing nodes
 *
 * CRITICAL CONSTRAINT:
 * Tone.js requires the audio context to be started after a user gesture (click, keypress, etc.)
 * due to browser autoplay policies. This node will throw an error if executed before
 * the context is started via Tone.start().
 */

import {
  NodeCategory,
  type NodePlugin,
  type ExecutionContext,
  type NodeExecutionResult,
} from '../../NodePluginAPI.js';
import * as Tone from 'tone';

/**
 * Tone.js Synth Node Plugin
 *
 * Synthesizes audio notes using Tone.js monophonic synth. Requires audio context
 * to be started before execution (user gesture required).
 *
 * Example usage in a graph:
 * 1. Trigger → ToneSynthNode → Audio Output
 * 2. MIDI Input → ToneSynthNode → Recorder
 * 3. Sequencer → ToneSynthNode → Effects Chain
 *
 * Configuration:
 * - note: Musical note (e.g., 'C4', 'A#3', 'F5') - supports scientific pitch notation
 * - duration: Note duration (e.g., '4n' = quarter note, '8n' = eighth note, '0.5' = 0.5 seconds)
 * - velocity: Note velocity/volume (0.0-1.0)
 *
 * Audio Context Gating:
 * Before using this node, the audio context must be started via user interaction:
 * ```typescript
 * // In UI button click handler:
 * await Tone.start();
 * ```
 */
export const ToneSynthNode: NodePlugin = {
  id: 'tone-synth',
  category: NodeCategory.Audio,
  label: 'Tone.js Synth',
  description: 'Trigger synthesized audio notes (requires audio context started via user gesture)',

  inputs: [
    {
      id: 'note',
      label: 'Note',
      type: 'string',
      required: true,
      defaultValue: 'C4',
      description: 'Musical note in scientific pitch notation (e.g., C4, A#3, F5)',
    },
    {
      id: 'duration',
      label: 'Duration',
      type: 'string',
      required: false,
      defaultValue: '4n',
      description: 'Note duration (e.g., "4n" = quarter note, "8n" = eighth note, "0.5" = 0.5 seconds)',
    },
    {
      id: 'velocity',
      label: 'Velocity',
      type: 'number',
      required: false,
      defaultValue: 0.7,
      description: 'Note velocity/volume (0.0-1.0)',
    },
  ],

  outputs: [
    {
      id: 'triggered',
      label: 'Triggered',
      type: 'boolean',
      description: 'True when note was successfully triggered',
    },
    {
      id: 'note',
      label: 'Note',
      type: 'string',
      description: 'The note that was played',
    },
    {
      id: 'timestamp',
      label: 'Timestamp',
      type: 'number',
      description: 'Audio context time when note was triggered',
    },
  ],

  /**
   * Validate inputs before execution
   *
   * Ensures:
   * - Note is a non-empty string
   * - Duration is a non-empty string
   * - Velocity is in valid range (0.0-1.0)
   */
  validate: (inputs: Record<string, unknown>): string[] => {
    const errors: string[] = [];

    // Validate note
    const note = inputs.note;
    if (typeof note !== 'string' || note.trim().length === 0) {
      errors.push('Note must be a non-empty string (e.g., C4, A#3, F5)');
    }

    // Validate duration
    const duration = inputs.duration;
    if (duration !== undefined && (typeof duration !== 'string' || String(duration).trim().length === 0)) {
      errors.push('Duration must be a non-empty string (e.g., "4n", "8n", "0.5")');
    }

    // Validate velocity
    const velocity = inputs.velocity;
    if (velocity !== undefined) {
      if (typeof velocity !== 'number') {
        errors.push('Velocity must be a number');
      } else if (velocity < 0 || velocity > 1) {
        errors.push('Velocity must be between 0.0 and 1.0');
      }
    }

    return errors;
  },

  /**
   * Execute audio synthesis
   *
   * Workflow:
   * 1. Validate audio context state (must be 'running')
   * 2. Extract and validate inputs
   * 3. Emit 'running' state for UI feedback
   * 4. Create synth and trigger note
   * 5. Emit 'complete' state
   * 6. Return outputs
   *
   * Error handling:
   * - Throws error if audio context not started (user gesture required)
   * - Logs errors to execution context
   * - Emits 'error' state for UI feedback
   * - Re-throws error to propagate to downstream nodes
   *
   * CRITICAL: This node will fail if Tone.context.state is not 'running'.
   * The audio context must be started via user gesture before graph execution:
   * ```typescript
   * await Tone.start(); // Call this in a click handler or similar user event
   * ```
   */
  execute: async (
    inputs: Record<string, unknown>,
    context: ExecutionContext
  ): Promise<NodeExecutionResult> => {
    // Extract inputs with type safety
    const note = String(inputs.note || 'C4');
    const duration = inputs.duration ? String(inputs.duration) : '4n';
    const velocity = typeof inputs.velocity === 'number' ? inputs.velocity : 0.7;

    // Log execution start
    context.log('info', 'Starting Tone.js synth execution', {
      note,
      duration,
      velocity,
      contextState: Tone.context.state,
    });

    // Emit running state for UI feedback
    context.emitState('running');

    try {
      // CRITICAL: Validate audio context state
      // This enforces browser autoplay policy - audio context must be started
      // after user gesture (click, keypress, etc.)
      if (Tone.context.state !== 'running') {
        const errorMsg =
          'Audio context not started - user gesture required. ' +
          'Call Tone.start() in a button click handler before executing audio nodes. ' +
          `Current state: ${Tone.context.state}`;

        context.log('error', 'Audio context validation failed', {
          state: Tone.context.state,
          required: 'running',
        });

        throw new Error(errorMsg);
      }

      // Check for abort signal
      if (context.signal?.aborted) {
        throw new Error('Execution aborted');
      }

      // Create synth and trigger note
      // Note: We create a new synth instance for each execution to ensure clean state
      const synth = new Tone.Synth().toDestination();

      // Apply velocity to volume (convert 0-1 range to dB)
      // Velocity 0.7 ≈ -6dB, 1.0 = 0dB, 0.5 ≈ -12dB
      synth.volume.value = 20 * Math.log10(velocity);

      // Trigger note with attack-release envelope
      const now = Tone.now();
      synth.triggerAttackRelease(note, duration, now);

      // Get audio context timestamp
      const timestamp = Tone.context.currentTime;

      // Log success
      context.log('info', 'Tone.js synth note triggered', {
        note,
        duration,
        velocity,
        timestamp,
        volumeDb: synth.volume.value,
      });

      // Emit complete state
      context.emitState('complete');

      // Return outputs
      return {
        outputs: {
          triggered: true,
          note,
          timestamp,
        },
        meta: {
          executionTime: Date.now(),
          note,
          duration,
          velocity,
          audioContextTime: timestamp,
          audioContextState: Tone.context.state,
        },
      };
    } catch (error) {
      // Log error with details
      const errorMessage = error instanceof Error ? error.message : String(error);

      context.log('error', 'Tone.js synth execution failed', {
        error: errorMessage,
        note,
        duration,
        contextState: Tone.context.state,
      });

      // Emit error state
      context.emitState('error');

      // Re-throw to propagate to downstream nodes
      throw new Error(`Tone.js synth execution failed: ${errorMessage}`);
    }
  },

  /**
   * Plugin metadata
   */
  metadata: {
    version: '1.0.0',
    author: 'Mascarade',
    tags: ['audio', 'synthesis', 'tone.js', 'music', 'sound'],
    experimental: false,
  },
};
