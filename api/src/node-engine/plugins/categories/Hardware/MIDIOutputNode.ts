/**
 * MIDI Output Node - Send MIDI messages to external devices/software
 *
 * Sends MIDI messages (note on/off, CC, program change) using JZZ library.
 * Supports standard MIDI output ports and virtual MIDI devices.
 *
 * Features:
 * - Note on/off messages with velocity control
 * - Control Change (CC) messages for parameter automation
 * - Program Change messages for instrument selection
 * - Configurable MIDI channel (1-16)
 * - Port enumeration and selection
 * - Graceful degradation when no MIDI devices available
 *
 * Inspired by:
 * - Max/MSP: MIDI output objects for hardware control
 * - Node-RED: MIDI device communication nodes
 * - Ableton Live: MIDI routing and mapping
 *
 * CRITICAL CONSTRAINT:
 * JZZ requires MIDI output devices to be available. The node will gracefully
 * handle missing hardware by logging warnings and continuing execution.
 */

import {
  NodeCategory,
  type NodePlugin,
  type ExecutionContext,
  type NodeExecutionResult,
} from '../../NodePluginAPI.js';
// Lazy-loaded: jzz is optional (hardware nodes only)
let JZZ: typeof import('jzz') | null = null;
try {
  JZZ = await import('jzz');
} catch {
  // jzz not available — MIDI features disabled
}

/**
 * MIDI message type
 */
export type MidiMessageType = 'note_on' | 'note_off' | 'cc' | 'program_change';

/**
 * MIDI Output Node Plugin
 *
 * Sends MIDI messages to external devices or virtual MIDI software.
 * Supports note on/off, control change, and program change messages.
 *
 * Example usage in a graph:
 * 1. Sequencer → MIDIOutputNode → (external synth)
 * 2. Trigger → MIDIOutputNode → (DAW input)
 * 3. Automation → MIDIOutputNode → (hardware controller)
 *
 * Configuration:
 * - message_type: Type of MIDI message ('note_on', 'note_off', 'cc', 'program_change')
 * - channel: MIDI channel (1-16, default: 1)
 * - port_name: MIDI output port name (default: first available port)
 * - note: MIDI note number (0-127, for note_on/note_off)
 * - velocity: Note velocity (0-127, for note_on/note_off)
 * - cc_number: Control change number (0-127, for cc messages)
 * - cc_value: Control change value (0-127, for cc messages)
 * - program: Program/patch number (0-127, for program_change)
 *
 * Message Types:
 * - note_on: Trigger a note (requires note, velocity, channel)
 * - note_off: Release a note (requires note, channel)
 * - cc: Send control change (requires cc_number, cc_value, channel)
 * - program_change: Change program/patch (requires program, channel)
 */
export const MIDIOutputNode: NodePlugin = {
  id: 'midi-output',
  category: NodeCategory.Hardware,
  label: 'MIDI Output',
  description: 'Send MIDI messages (note on/off, CC, program change) to external devices',

  inputs: [
    {
      id: 'message_type',
      label: 'Message Type',
      type: 'string',
      required: true,
      defaultValue: 'note_on',
      description: 'Type of MIDI message: note_on, note_off, cc, program_change',
    },
    {
      id: 'channel',
      label: 'MIDI Channel',
      type: 'number',
      required: false,
      defaultValue: 1,
      description: 'MIDI channel (1-16)',
    },
    {
      id: 'port_name',
      label: 'Port Name',
      type: 'string',
      required: false,
      description: 'MIDI output port name (defaults to first available port)',
    },
    {
      id: 'note',
      label: 'Note Number',
      type: 'number',
      required: false,
      defaultValue: 60,
      description: 'MIDI note number (0-127, middle C = 60) - for note_on/note_off',
    },
    {
      id: 'velocity',
      label: 'Velocity',
      type: 'number',
      required: false,
      defaultValue: 100,
      description: 'Note velocity (0-127) - for note_on/note_off',
    },
    {
      id: 'cc_number',
      label: 'CC Number',
      type: 'number',
      required: false,
      defaultValue: 1,
      description: 'Control change number (0-127) - for cc messages',
    },
    {
      id: 'cc_value',
      label: 'CC Value',
      type: 'number',
      required: false,
      defaultValue: 64,
      description: 'Control change value (0-127) - for cc messages',
    },
    {
      id: 'program',
      label: 'Program Number',
      type: 'number',
      required: false,
      defaultValue: 0,
      description: 'Program/patch number (0-127) - for program_change',
    },
  ],

  outputs: [
    {
      id: 'sent',
      label: 'Sent',
      type: 'boolean',
      description: 'True when MIDI message was successfully sent',
    },
    {
      id: 'message_type',
      label: 'Message Type',
      type: 'string',
      description: 'Type of MIDI message that was sent',
    },
    {
      id: 'channel',
      label: 'Channel',
      type: 'number',
      description: 'MIDI channel used',
    },
    {
      id: 'port',
      label: 'Port',
      type: 'string',
      description: 'MIDI output port name used',
    },
    {
      id: 'timestamp',
      label: 'Timestamp',
      type: 'number',
      description: 'Unix timestamp when message was sent',
    },
  ],

  /**
   * Validate inputs before execution
   *
   * Ensures:
   * - Message type is valid
   * - Channel is in valid range (1-16)
   * - Note, velocity, CC values are in valid MIDI range (0-127)
   * - Required parameters for each message type are present
   */
  validate: (inputs: Record<string, unknown>): string[] => {
    const errors: string[] = [];

    // Validate message type
    const messageType = inputs.message_type;
    const validTypes: MidiMessageType[] = ['note_on', 'note_off', 'cc', 'program_change'];
    if (typeof messageType !== 'string' || !validTypes.includes(messageType as MidiMessageType)) {
      errors.push(`Message type must be one of: ${validTypes.join(', ')}`);
    }

    // Validate channel (1-16)
    const channel = inputs.channel;
    if (channel !== undefined) {
      if (typeof channel !== 'number') {
        errors.push('Channel must be a number');
      } else if (channel < 1 || channel > 16) {
        errors.push('Channel must be between 1 and 16');
      }
    }

    // Validate note-specific parameters
    if (messageType === 'note_on' || messageType === 'note_off') {
      const note = inputs.note;
      if (note !== undefined) {
        if (typeof note !== 'number') {
          errors.push('Note must be a number');
        } else if (note < 0 || note > 127) {
          errors.push('Note must be between 0 and 127');
        }
      }

      if (messageType === 'note_on') {
        const velocity = inputs.velocity;
        if (velocity !== undefined) {
          if (typeof velocity !== 'number') {
            errors.push('Velocity must be a number');
          } else if (velocity < 0 || velocity > 127) {
            errors.push('Velocity must be between 0 and 127');
          }
        }
      }
    }

    // Validate CC-specific parameters
    if (messageType === 'cc') {
      const ccNumber = inputs.cc_number;
      if (ccNumber !== undefined) {
        if (typeof ccNumber !== 'number') {
          errors.push('CC number must be a number');
        } else if (ccNumber < 0 || ccNumber > 127) {
          errors.push('CC number must be between 0 and 127');
        }
      }

      const ccValue = inputs.cc_value;
      if (ccValue !== undefined) {
        if (typeof ccValue !== 'number') {
          errors.push('CC value must be a number');
        } else if (ccValue < 0 || ccValue > 127) {
          errors.push('CC value must be between 0 and 127');
        }
      }
    }

    // Validate program change parameters
    if (messageType === 'program_change') {
      const program = inputs.program;
      if (program !== undefined) {
        if (typeof program !== 'number') {
          errors.push('Program number must be a number');
        } else if (program < 0 || program > 127) {
          errors.push('Program number must be between 0 and 127');
        }
      }
    }

    return errors;
  },

  /**
   * Execute MIDI output
   *
   * Workflow:
   * 1. Extract and validate inputs
   * 2. Enumerate MIDI output ports
   * 3. Select target port (by name or first available)
   * 4. Emit 'running' state for UI feedback
   * 5. Send MIDI message based on type
   * 6. Emit 'complete' state
   * 7. Return outputs
   *
   * Error handling:
   * - Gracefully handles missing MIDI devices (logs warning, continues)
   * - Logs errors to execution context
   * - Emits 'error' state for UI feedback
   * - Re-throws error to propagate to downstream nodes
   *
   * CRITICAL: This node requires MIDI output devices. If no devices are available,
   * it will log a warning and return without sending (sent = false).
   */
  execute: async (
    inputs: Record<string, unknown>,
    context: ExecutionContext
  ): Promise<NodeExecutionResult> => {
    // Extract inputs with type safety
    const messageType = String(inputs.message_type || 'note_on') as MidiMessageType;
    const channel = typeof inputs.channel === 'number' ? inputs.channel : 1;
    const portName = inputs.port_name ? String(inputs.port_name) : undefined;
    const note = typeof inputs.note === 'number' ? inputs.note : 60;
    const velocity = typeof inputs.velocity === 'number' ? inputs.velocity : 100;
    const ccNumber = typeof inputs.cc_number === 'number' ? inputs.cc_number : 1;
    const ccValue = typeof inputs.cc_value === 'number' ? inputs.cc_value : 64;
    const program = typeof inputs.program === 'number' ? inputs.program : 0;

    // Convert MIDI channel to 0-indexed (JZZ uses 0-15 internally)
    const channelIndex = channel - 1;

    // Log execution start
    context.log('info', 'Starting MIDI output execution', {
      messageType,
      channel,
      portName,
      note,
      velocity,
      ccNumber,
      ccValue,
      program,
    });

    // Emit running state for UI feedback
    context.emitState('running');

    try {
      // Check for abort signal
      if (context.signal?.aborted) {
        throw new Error('Execution aborted');
      }

      // Get available MIDI output ports
      const midiEngine = JZZ();
      const outputs = midiEngine.info().outputs || [];

      // Check if any MIDI outputs are available
      if (outputs.length === 0) {
        const warningMsg =
          'No MIDI output devices found. MIDI message will not be sent. ' +
          'Please connect a MIDI device or enable a virtual MIDI port.';

        context.log('warn', 'No MIDI outputs available', {
          messageType,
          channel,
        });

        // Emit complete state (graceful degradation)
        context.emitState('complete');

        return {
          outputs: {
            sent: false,
            message_type: messageType,
            channel,
            port: 'none',
            timestamp: Date.now(),
          },
          meta: {
            executionTime: Date.now(),
            warning: warningMsg,
            availablePorts: 0,
          },
        };
      }

      // Select MIDI output port
      let selectedPort: string;
      if (portName) {
        // Try to find port by name
        const matchingPort = outputs.find(
          (port) => port.name === portName || port.id === portName
        );
        if (!matchingPort) {
          context.log('warn', 'Requested MIDI port not found, using first available', {
            requested: portName,
            available: outputs.map((p) => p.name || p.id),
          });
          selectedPort = outputs[0].name || outputs[0].id || '0';
        } else {
          selectedPort = matchingPort.name || matchingPort.id || '0';
        }
      } else {
        // Use first available port
        selectedPort = outputs[0].name || outputs[0].id || '0';
      }

      // Open MIDI output port
      const port = midiEngine.openMidiOut(selectedPort);

      // Send MIDI message based on type
      let messageSent = false;
      const timestamp = Date.now();

      switch (messageType) {
        case 'note_on':
          // Send note on message
          port.noteOn(channelIndex, note, velocity);
          messageSent = true;
          context.log('info', 'MIDI note on sent', {
            channel,
            note,
            velocity,
            port: selectedPort,
          });
          break;

        case 'note_off':
          // Send note off message (velocity typically ignored, set to 0)
          port.noteOff(channelIndex, note);
          messageSent = true;
          context.log('info', 'MIDI note off sent', {
            channel,
            note,
            port: selectedPort,
          });
          break;

        case 'cc':
          // Send control change message
          port.control(channelIndex, ccNumber, ccValue);
          messageSent = true;
          context.log('info', 'MIDI CC sent', {
            channel,
            ccNumber,
            ccValue,
            port: selectedPort,
          });
          break;

        case 'program_change':
          // Send program change message
          port.program(channelIndex, program);
          messageSent = true;
          context.log('info', 'MIDI program change sent', {
            channel,
            program,
            port: selectedPort,
          });
          break;

        default:
          throw new Error(`Unsupported MIDI message type: ${messageType}`);
      }

      // Close MIDI port
      port.close();

      // Emit complete state
      context.emitState('complete');

      // Return outputs
      return {
        outputs: {
          sent: messageSent,
          message_type: messageType,
          channel,
          port: selectedPort,
          timestamp,
        },
        meta: {
          executionTime: timestamp,
          messageType,
          channel,
          port: selectedPort,
          availablePorts: outputs.length,
          portList: outputs.map((p) => p.name || p.id),
        },
      };
    } catch (error) {
      // Log error with details
      const errorMessage = error instanceof Error ? error.message : String(error);

      context.log('error', 'MIDI output execution failed', {
        error: errorMessage,
        messageType,
        channel,
        portName,
      });

      // Emit error state
      context.emitState('error');

      // Re-throw to propagate to downstream nodes
      throw new Error(`MIDI output execution failed: ${errorMessage}`);
    }
  },

  /**
   * Plugin metadata
   */
  metadata: {
    version: '1.0.0',
    author: 'Mascarade',
    tags: ['midi', 'hardware', 'music', 'control', 'output'],
    experimental: false,
  },
};
