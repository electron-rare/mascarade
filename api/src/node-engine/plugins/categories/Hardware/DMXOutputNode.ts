/**
 * DMX Output Node - Set DMX512 channel values for lighting control
 *
 * Controls DMX512 lighting fixtures via USB DMX interfaces (Enttec, DMXKing, etc.).
 * Supports standard 512-channel DMX universes with optional fade transitions.
 *
 * Features:
 * - Set individual channel values (1-512, 0-255)
 * - Multiple universe support
 * - Fade/transition time control
 * - Common DMX driver support (Enttec USB DMX Pro, DMXKing Ultra DMX Pro, etc.)
 * - Graceful degradation when no DMX hardware available
 * - Blackout functionality
 *
 * Inspired by:
 * - TouchDesigner: DMX output operators for stage lighting
 * - QLC+: Open source lighting control
 * - Node-RED: DMX hardware control nodes
 *
 * CRITICAL CONSTRAINT:
 * DMX requires USB hardware interface. The node will gracefully handle missing
 * hardware by logging warnings and continuing execution without sending data.
 *
 * Common DMX Drivers:
 * - enttec-usb-dmx-pro: Enttec USB DMX Pro
 * - enttec-open-usb-dmx: Enttec Open DMX USB
 * - dmx-king-ultra-dmx-pro: DMXKing Ultra DMX Pro
 * - artnet: Art-Net DMX over Ethernet
 * - null: Null driver for testing (no hardware required)
 */

import {
  NodeCategory,
  type NodePlugin,
  type ExecutionContext,
  type NodeExecutionResult,
} from '../../NodePluginAPI.js';

// Import DMX library - note: this is a Node.js native module
// and requires USB DMX hardware to function properly
let DMX: any;
try {
  DMX = await import('dmx');
} catch (error) {
  console.warn('DMX library not available - DMX nodes will run in mock mode');
  DMX = null;
}

/**
 * DMX channel value range (0-255 per DMX512 spec)
 */
const DMX_MIN_VALUE = 0;
const DMX_MAX_VALUE = 255;

/**
 * DMX channel range (1-512 per DMX512 spec)
 */
const DMX_MIN_CHANNEL = 1;
const DMX_MAX_CHANNEL = 512;

/**
 * DMX Output Node Plugin
 *
 * Sets DMX channel values for controlling stage lighting, moving heads,
 * LED fixtures, fog machines, and other DMX512-compatible equipment.
 *
 * Example usage in a graph:
 * 1. Trigger → DMXOutputNode → (lighting fixture)
 * 2. Automation → DMXOutputNode → (stage effects)
 * 3. Audio Analyzer → DMXOutputNode → (reactive lighting)
 *
 * Configuration:
 * - universe: DMX universe name/ID (default: 'default')
 * - channel: DMX channel number (1-512)
 * - value: Channel value (0-255, where 0=off, 255=max)
 * - transition_time: Fade time in milliseconds (0=instant, default: 0)
 * - driver: DMX USB driver type (default: 'enttec-usb-dmx-pro')
 * - device_path: USB device path (optional, auto-detect if not specified)
 *
 * Channel Mapping Examples:
 * - Single RGB fixture (3 channels):
 *   - Channel 1: Red (0-255)
 *   - Channel 2: Green (0-255)
 *   - Channel 3: Blue (0-255)
 * - Moving head (8+ channels):
 *   - Channel 1: Pan
 *   - Channel 2: Tilt
 *   - Channel 3: Dimmer
 *   - Channel 4: Strobe
 *   - etc.
 */
export const DMXOutputNode: NodePlugin = {
  id: 'dmx-output',
  category: NodeCategory.Hardware,
  label: 'DMX Output',
  description: 'Set DMX512 channel values (1-512) for lighting control via USB interface',

  inputs: [
    {
      id: 'universe',
      label: 'Universe',
      type: 'string',
      required: false,
      defaultValue: 'default',
      description: 'DMX universe name/ID (supports multiple isolated universes)',
    },
    {
      id: 'channel',
      label: 'Channel',
      type: 'number',
      required: true,
      defaultValue: 1,
      description: 'DMX channel number (1-512)',
    },
    {
      id: 'value',
      label: 'Value',
      type: 'number',
      required: true,
      defaultValue: 0,
      description: 'Channel value (0-255, where 0=off, 255=max intensity)',
    },
    {
      id: 'transition_time',
      label: 'Transition Time (ms)',
      type: 'number',
      required: false,
      defaultValue: 0,
      description: 'Fade transition time in milliseconds (0=instant)',
    },
    {
      id: 'driver',
      label: 'Driver',
      type: 'string',
      required: false,
      defaultValue: 'enttec-usb-dmx-pro',
      description: 'DMX USB driver: enttec-usb-dmx-pro, enttec-open-usb-dmx, dmx-king-ultra-dmx-pro, artnet, null',
    },
    {
      id: 'device_path',
      label: 'Device Path',
      type: 'string',
      required: false,
      description: 'USB device path (optional, auto-detect if not specified)',
    },
  ],

  outputs: [
    {
      id: 'sent',
      label: 'Sent',
      type: 'boolean',
      description: 'True when DMX value was successfully set',
    },
    {
      id: 'universe',
      label: 'Universe',
      type: 'string',
      description: 'DMX universe that was updated',
    },
    {
      id: 'channel',
      label: 'Channel',
      type: 'number',
      description: 'DMX channel that was set',
    },
    {
      id: 'value',
      label: 'Value',
      type: 'number',
      description: 'Value that was set',
    },
    {
      id: 'timestamp',
      label: 'Timestamp',
      type: 'number',
      description: 'Unix timestamp when value was set',
    },
  ],

  /**
   * Validate inputs before execution
   *
   * Ensures:
   * - Channel is in valid range (1-512)
   * - Value is in valid range (0-255)
   * - Transition time is non-negative
   * - Driver is a supported type
   */
  validate: (inputs: Record<string, unknown>): string[] => {
    const errors: string[] = [];

    // Validate channel (1-512)
    const channel = inputs.channel;
    if (channel !== undefined) {
      if (typeof channel !== 'number') {
        errors.push('Channel must be a number');
      } else if (!Number.isInteger(channel)) {
        errors.push('Channel must be an integer');
      } else if (channel < DMX_MIN_CHANNEL || channel > DMX_MAX_CHANNEL) {
        errors.push(`Channel must be between ${DMX_MIN_CHANNEL} and ${DMX_MAX_CHANNEL}`);
      }
    } else {
      errors.push('Channel is required');
    }

    // Validate value (0-255)
    const value = inputs.value;
    if (value !== undefined) {
      if (typeof value !== 'number') {
        errors.push('Value must be a number');
      } else if (!Number.isInteger(value)) {
        errors.push('Value must be an integer');
      } else if (value < DMX_MIN_VALUE || value > DMX_MAX_VALUE) {
        errors.push(`Value must be between ${DMX_MIN_VALUE} and ${DMX_MAX_VALUE}`);
      }
    } else {
      errors.push('Value is required');
    }

    // Validate transition time (non-negative)
    const transitionTime = inputs.transition_time;
    if (transitionTime !== undefined) {
      if (typeof transitionTime !== 'number') {
        errors.push('Transition time must be a number');
      } else if (!Number.isInteger(transitionTime)) {
        errors.push('Transition time must be an integer');
      } else if (transitionTime < 0) {
        errors.push('Transition time must be non-negative');
      }
    }

    // Validate driver (informational only - library will handle unknown drivers)
    const driver = inputs.driver;
    if (driver !== undefined && typeof driver !== 'string') {
      errors.push('Driver must be a string');
    }

    // Validate universe (must be string if provided)
    const universe = inputs.universe;
    if (universe !== undefined && typeof universe !== 'string') {
      errors.push('Universe must be a string');
    }

    return errors;
  },

  /**
   * Execute DMX output
   *
   * Workflow:
   * 1. Extract and validate inputs
   * 2. Initialize DMX library and universe (if not already initialized)
   * 3. Set channel value with optional transition
   * 4. Emit 'running' state for UI feedback
   * 5. Update DMX output
   * 6. Emit 'complete' state
   * 7. Return outputs
   *
   * Error handling:
   * - Gracefully handles missing DMX hardware (logs warning, continues)
   * - Logs errors to execution context
   * - Emits 'error' state for UI feedback
   * - Re-throws error to propagate to downstream nodes
   *
   * CRITICAL: This node requires DMX USB hardware. If no hardware is available,
   * it will log a warning and return without sending (sent = false).
   *
   * Note: The DMX library maintains persistent universe state across executions.
   * Each universe is initialized once and reused.
   */
  execute: async (
    inputs: Record<string, unknown>,
    context: ExecutionContext
  ): Promise<NodeExecutionResult> => {
    // Extract inputs with type safety
    const universe = String(inputs.universe || 'default');
    const channel = typeof inputs.channel === 'number' ? inputs.channel : 1;
    const value = typeof inputs.value === 'number' ? inputs.value : 0;
    const transitionTime = typeof inputs.transition_time === 'number' ? inputs.transition_time : 0;
    const driver = String(inputs.driver || 'enttec-usb-dmx-pro');
    const devicePath = inputs.device_path ? String(inputs.device_path) : undefined;

    // Log execution start
    context.log('info', 'Starting DMX output execution', {
      universe,
      channel,
      value,
      transitionTime,
      driver,
      devicePath,
    });

    // Emit running state for UI feedback
    context.emitState('running');

    try {
      // Check for abort signal
      if (context.signal?.aborted) {
        throw new Error('Execution aborted');
      }

      // Check if DMX library is available
      if (!DMX) {
        const warningMsg =
          'DMX library not available. DMX output will not be sent. ' +
          'Please install the dmx package and connect a DMX USB interface.';

        context.log('warn', 'DMX library not available', {
          universe,
          channel,
          value,
        });

        // Emit complete state (graceful degradation)
        context.emitState('complete');

        return {
          outputs: {
            sent: false,
            universe,
            channel,
            value,
            timestamp: Date.now(),
          },
          meta: {
            executionTime: Date.now(),
            warning: warningMsg,
            dmxAvailable: false,
          },
        };
      }

      // Get or create DMX instance from context state
      // This persists across node executions within the same graph run
      let dmxInstance = context.state.get('dmx_instance') as any;

      if (!dmxInstance) {
        try {
          // Initialize DMX library
          dmxInstance = new DMX.default();
          context.state.set('dmx_instance', dmxInstance);

          context.log('info', 'Initialized DMX library', {
            driver,
          });
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : String(error);

          context.log('warn', 'Failed to initialize DMX library - running in mock mode', {
            error: errorMessage,
          });

          // Emit complete state (graceful degradation)
          context.emitState('complete');

          return {
            outputs: {
              sent: false,
              universe,
              channel,
              value,
              timestamp: Date.now(),
            },
            meta: {
              executionTime: Date.now(),
              warning: `DMX initialization failed: ${errorMessage}`,
              dmxAvailable: false,
            },
          };
        }
      }

      // Get or create universe
      // Check if universe already exists in the DMX instance
      const existingUniverses = context.state.get('dmx_universes') as Set<string> || new Set<string>();

      if (!existingUniverses.has(universe)) {
        try {
          // Add universe with specified driver
          const universeConfig: any = {
            driver: driver,
          };

          // Add device path if specified
          if (devicePath) {
            universeConfig.device_path = devicePath;
          }

          dmxInstance.addUniverse(universe, driver, devicePath || 'auto');

          existingUniverses.add(universe);
          context.state.set('dmx_universes', existingUniverses);

          context.log('info', 'Added DMX universe', {
            universe,
            driver,
            devicePath: devicePath || 'auto-detect',
          });
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : String(error);

          context.log('warn', 'Failed to add DMX universe - may already exist or hardware unavailable', {
            error: errorMessage,
            universe,
            driver,
          });

          // Continue execution - universe may already exist
        }
      }

      // Set channel value
      const timestamp = Date.now();
      let sent = false;

      try {
        if (transitionTime > 0) {
          // Use transition for smooth fading
          dmxInstance.update(universe, { [channel]: value }, transitionTime);
        } else {
          // Instant update
          dmxInstance.update(universe, { [channel]: value });
        }

        sent = true;

        context.log('info', 'DMX channel value set', {
          universe,
          channel,
          value,
          transitionTime,
          timestamp,
        });
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);

        context.log('warn', 'Failed to set DMX channel - hardware may be unavailable', {
          error: errorMessage,
          universe,
          channel,
          value,
        });

        // Don't throw - graceful degradation
        sent = false;
      }

      // Emit complete state
      context.emitState('complete');

      // Return outputs
      return {
        outputs: {
          sent,
          universe,
          channel,
          value,
          timestamp,
        },
        meta: {
          executionTime: timestamp,
          universe,
          channel,
          value,
          transitionTime,
          driver,
          dmxAvailable: true,
        },
      };
    } catch (error) {
      // Log error with details
      const errorMessage = error instanceof Error ? error.message : String(error);

      context.log('error', 'DMX output execution failed', {
        error: errorMessage,
        universe,
        channel,
        value,
      });

      // Emit error state
      context.emitState('error');

      // Re-throw to propagate to downstream nodes
      throw new Error(`DMX output execution failed: ${errorMessage}`);
    }
  },

  /**
   * Lifecycle: Cleanup DMX instance when node is destroyed
   */
  onDestroy: async (context: ExecutionContext) => {
    const dmxInstance = context.state.get('dmx_instance') as any;

    if (dmxInstance) {
      try {
        // Close all universes
        const universes = context.state.get('dmx_universes') as Set<string>;
        if (universes) {
          for (const universe of universes) {
            try {
              // Set all channels to 0 (blackout) before closing
              const blackout: Record<number, number> = {};
              for (let ch = 1; ch <= 512; ch++) {
                blackout[ch] = 0;
              }
              dmxInstance.update(universe, blackout);
            } catch (error) {
              // Ignore errors during cleanup
            }
          }
        }

        context.log('info', 'DMX instance cleaned up');
        context.state.delete('dmx_instance');
        context.state.delete('dmx_universes');
      } catch (error) {
        context.log('warn', 'Error during DMX cleanup', {
          error: error instanceof Error ? error.message : String(error),
        });
      }
    }
  },

  /**
   * Plugin metadata
   */
  metadata: {
    version: '1.0.0',
    author: 'Mascarade',
    tags: ['dmx', 'dmx512', 'lighting', 'hardware', 'stage', 'control', 'output'],
    experimental: false,
  },
};
