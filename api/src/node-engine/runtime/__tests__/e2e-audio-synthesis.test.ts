/**
 * End-to-End Test: Audio Synthesis Node Plays Sound After User Gesture
 *
 * Verifies the complete audio synthesis pipeline:
 * 1. ToneSynthNode is registered in PluginRegistry
 * 2. Node can be placed in a graph and executed via NodeRunner
 * 3. Audio context state gating works (rejects when not started)
 * 4. Node produces correct outputs when audio context is running
 *
 * NOTE: Tone.js is browser-only. These tests mock the Tone.js module
 * to verify wiring and integration. Manual browser verification is
 * required to confirm actual audio output (see node-engine-audio-e2e.html).
 */

import { describe, expect, it, beforeEach, vi } from 'vitest';

// Mock Tone.js before importing modules that use it
vi.mock('tone', () => {
  let contextState = 'suspended';

  const mockSynth = {
    toDestination: vi.fn().mockReturnThis(),
    triggerAttackRelease: vi.fn(),
    volume: { value: 0 },
  };

  // Synth must be a constructor (called with `new`)
  function Synth() {
    return mockSynth;
  }

  return {
    start: vi.fn(async () => {
      contextState = 'running';
    }),
    context: {
      get state() {
        return contextState;
      },
      currentTime: 1.234,
    },
    Synth,
    now: vi.fn(() => 1.234),
    __resetMock: () => {
      contextState = 'suspended';
      mockSynth.triggerAttackRelease.mockClear();
    },
    __setContextState: (state: string) => {
      contextState = state;
    },
    __getMockSynth: () => mockSynth,
  };
});

import * as Tone from 'tone';
import { GraphExecutor } from '../GraphExecutor.js';
import { NodeRunner } from '../NodeRunner.js';
import { ExecutionContextManager } from '../ExecutionContext.js';
import { ToneSynthNode } from '../../plugins/categories/Audio/ToneSynthNode.js';
import { PluginRegistry } from '../../plugins/PluginRegistry.js';
import { NodeCategory } from '../../plugins/NodePluginAPI.js';
import type { NodeGraph, GraphNode, GraphEdge } from '../../types/NodeTypes.js';
import type { ExecutionEvent } from '../../types/ExecutionTypes.js';

// Access mock helpers
const ToneMock = Tone as unknown as typeof Tone & {
  __resetMock: () => void;
  __setContextState: (state: string) => void;
  __getMockSynth: () => { toDestination: ReturnType<typeof vi.fn>; triggerAttackRelease: ReturnType<typeof vi.fn>; volume: { value: number } };
};

function createAudioNode(id: string, note = 'C4', duration = '4n', velocity = 0.7): GraphNode {
  return {
    id,
    type: 'tone-synth',
    position: { x: 0, y: 0 },
    data: {
      pluginId: 'tone-synth',
      label: 'Tone.js Synth',
      category: NodeCategory.Audio,
      inputValues: { note, duration, velocity },
      executionState: 'idle',
    },
  };
}

describe('End-to-End: Audio Synthesis Node', () => {
  let contextManager: ExecutionContextManager;
  let events: ExecutionEvent[];

  beforeEach(() => {
    contextManager = new ExecutionContextManager();
    events = [];
    ToneMock.__resetMock();
  });

  describe('Plugin Registration', () => {
    it('ToneSynthNode can be registered in PluginRegistry', () => {
      const registry = new PluginRegistry();
      registry.register(ToneSynthNode, { builtin: true });
      const plugin = registry.get('tone-synth');
      expect(plugin).toBeDefined();
      expect(plugin.id).toBe('tone-synth');
      expect(plugin.category).toBe(NodeCategory.Audio);
    });

    it('ToneSynthNode appears in Audio category', () => {
      const registry = new PluginRegistry();
      registry.register(ToneSynthNode, { builtin: true });
      const audioPlugins = registry.listByCategory(NodeCategory.Audio);
      const ids = audioPlugins.map((p) => p.id);
      expect(ids).toContain('tone-synth');
    });
  });

  describe('Audio Context Gating', () => {
    it('rejects execution when audio context is suspended', async () => {
      ToneMock.__setContextState('suspended');

      const runner = new NodeRunner(ToneSynthNode);
      const context = contextManager.createContext('run-audio-1', 'synth-1', 'graph-1', {
        pluginId: 'tone-synth',
      });

      await expect(
        runner.execute({ note: 'C4', duration: '4n', velocity: 0.7 }, context, {
          skipValidation: true,
        })
      ).rejects.toThrow(/[Aa]udio context/);
    });

    it('succeeds when audio context is running (after user gesture)', async () => {
      // Simulate user gesture: Tone.start()
      await Tone.start();
      expect(Tone.context.state).toBe('running');

      const runner = new NodeRunner(ToneSynthNode);
      const context = contextManager.createContext('run-audio-2', 'synth-1', 'graph-1', {
        pluginId: 'tone-synth',
      });

      const record = await runner.execute(
        { note: 'C4', duration: '4n', velocity: 0.7 },
        context,
        { skipValidation: true }
      );

      expect(record.state).toBe('complete');
      expect(record.outputs).toBeDefined();
      expect(record.outputs!.triggered).toBe(true);
      expect(record.outputs!.note).toBe('C4');
    });
  });

  describe('Full Graph Execution with Audio Node', () => {
    it('executes a graph containing a ToneSynthNode', async () => {
      // Start audio context (simulating user gesture)
      await Tone.start();

      const graph: NodeGraph = {
        id: 'audio-test-graph',
        name: 'Audio E2E Test',
        nodes: [createAudioNode('synth-1', 'A4', '8n', 0.8)],
        edges: [],
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      };

      const executor = new GraphExecutor();
      const order = executor.getExecutionOrder(graph);
      expect(order).toEqual(['synth-1']);

      const eventEmitter = (event: ExecutionEvent) => events.push(event);

      // Execute the graph
      const node = graph.nodes[0];
      const runner = new NodeRunner(ToneSynthNode);
      const context = contextManager.createContext('run-audio-3', node.id, graph.id, {
        pluginId: node.data.pluginId,
        eventEmitter,
      });

      const record = await runner.execute(node.data.inputValues, context, {
        skipValidation: true,
      });

      // Verify execution succeeded
      expect(record.state).toBe('complete');
      expect(record.outputs!.triggered).toBe(true);
      expect(record.outputs!.note).toBe('A4');
      expect(typeof record.outputs!.timestamp).toBe('number');

      // Verify synth was used correctly
      const mockSynth = ToneMock.__getMockSynth();
      expect(mockSynth.toDestination).toHaveBeenCalled();
      expect(mockSynth.triggerAttackRelease).toHaveBeenCalledWith('A4', '8n', 1.234);

      // Verify state events emitted
      const stateEvents = events.filter(
        (e): e is Extract<ExecutionEvent, { type: 'node.state' }> => e.type === 'node.state'
      );
      const states = stateEvents.map((e) => e.state);
      expect(states).toContain('pending');
      expect(states).toContain('running');
      expect(states).toContain('complete');
    });

    it('executes a chain: Trigger → ToneSynth', async () => {
      await Tone.start();

      // Simple trigger node that outputs a note
      const triggerPlugin = {
        id: 'trigger',
        category: NodeCategory.Workflow,
        label: 'Note Trigger',
        description: 'Outputs a note value',
        inputs: [],
        outputs: [
          { id: 'note', label: 'Note', type: 'string' as const },
          { id: 'duration', label: 'Duration', type: 'string' as const },
          { id: 'velocity', label: 'Velocity', type: 'number' as const },
        ],
        execute: () => ({
          outputs: { note: 'E4', duration: '4n', velocity: 0.6 },
        }),
      };

      const graph: NodeGraph = {
        id: 'chain-audio-graph',
        name: 'Trigger → Synth',
        nodes: [
          {
            id: 'trigger-1',
            type: 'trigger',
            position: { x: 0, y: 0 },
            data: {
              pluginId: 'trigger',
              label: 'Note Trigger',
              category: NodeCategory.Workflow,
              inputValues: {},
              executionState: 'idle',
            },
          },
          createAudioNode('synth-1'),
        ],
        edges: [
          {
            id: 'e1',
            source: 'trigger-1',
            sourceHandle: 'note',
            target: 'synth-1',
            targetHandle: 'note',
          },
        ],
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      };

      const executor = new GraphExecutor();
      const order = executor.getExecutionOrder(graph);
      expect(order).toEqual(['trigger-1', 'synth-1']);

      // Execute trigger node
      const triggerRunner = new NodeRunner(triggerPlugin as any);
      const triggerCtx = contextManager.createContext('run-chain-1', 'trigger-1', graph.id, {
        pluginId: 'trigger',
      });
      const triggerResult = await triggerRunner.execute({}, triggerCtx, { skipValidation: true });

      // Pass trigger output to synth node
      const synthInputs: Record<string, unknown> = {};
      for (const edge of graph.edges) {
        if (edge.target === 'synth-1' && triggerResult.outputs) {
          synthInputs[edge.targetHandle || 'note'] =
            triggerResult.outputs[edge.sourceHandle || 'note'];
        }
      }

      const synthRunner = new NodeRunner(ToneSynthNode);
      const synthCtx = contextManager.createContext('run-chain-1', 'synth-1', graph.id, {
        pluginId: 'tone-synth',
      });
      const synthResult = await synthRunner.execute(synthInputs, synthCtx, {
        skipValidation: true,
      });

      expect(synthResult.state).toBe('complete');
      expect(synthResult.outputs!.triggered).toBe(true);
      // The trigger sends 'E4' through the edge
      expect(synthResult.outputs!.note).toBe('E4');
    });
  });

  describe('Input Validation', () => {
    it('validates note input', () => {
      const errors = ToneSynthNode.validate!({ note: '', duration: '4n', velocity: 0.7 });
      expect(errors.length).toBeGreaterThan(0);
    });

    it('validates velocity range', () => {
      const errors = ToneSynthNode.validate!({ note: 'C4', velocity: 1.5 });
      expect(errors.length).toBeGreaterThan(0);
    });

    it('accepts valid inputs', () => {
      const errors = ToneSynthNode.validate!({ note: 'C4', duration: '4n', velocity: 0.7 });
      expect(errors).toHaveLength(0);
    });
  });
});
