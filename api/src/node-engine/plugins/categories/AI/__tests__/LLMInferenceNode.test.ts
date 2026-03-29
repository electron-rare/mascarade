/**
 * LLMInferenceNode Tests
 *
 * Tests for the LLM Inference node plugin, including:
 * - Input validation
 * - Execution flow
 * - Error handling
 * - State emission
 * - Mascarade router integration
 */

import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import { LLMInferenceNode } from '../LLMInferenceNode.js';
import type { ExecutionContext } from '../../../NodePluginAPI.js';
import * as coreClient from '../../../../../client/core.js';

// Mock the core client
vi.mock('../../../../../client/core.js', () => ({
  coreClient: {
    send: vi.fn(),
  },
  CoreApiError: class CoreApiError extends Error {
    constructor(message: string, public status: number, public coreBody?: unknown) {
      super(message);
      this.name = 'CoreApiError';
    }
  },
  getCoreAuthHeaders: vi.fn(() => ({})),
}));

describe('LLMInferenceNode', () => {
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
      expect(LLMInferenceNode.id).toBe('llm-inference');
      expect(LLMInferenceNode.category).toBe('AI');
    });

    it('should have correct label and description', () => {
      expect(LLMInferenceNode.label).toBe('LLM Inference');
      expect(LLMInferenceNode.description).toContain('Mascarade router');
    });

    it('should define required inputs', () => {
      expect(LLMInferenceNode.inputs).toBeDefined();
      const promptInput = LLMInferenceNode.inputs.find((i) => i.id === 'prompt');
      expect(promptInput).toBeDefined();
      expect(promptInput?.required).toBe(true);
    });

    it('should define expected outputs', () => {
      expect(LLMInferenceNode.outputs).toBeDefined();
      const outputIds = LLMInferenceNode.outputs.map((o) => o.id);
      expect(outputIds).toContain('response');
      expect(outputIds).toContain('model');
      expect(outputIds).toContain('provider');
      expect(outputIds).toContain('input_tokens');
      expect(outputIds).toContain('output_tokens');
    });
  });

  describe('Input Validation', () => {
    it('should validate empty prompt', () => {
      const errors = LLMInferenceNode.validate?.({
        prompt: '',
      });
      expect(errors).toBeDefined();
      expect(errors?.length).toBeGreaterThan(0);
      expect(errors?.[0]).toContain('Prompt must be a non-empty string');
    });

    it('should validate missing prompt', () => {
      const errors = LLMInferenceNode.validate?.({});
      expect(errors).toBeDefined();
      expect(errors?.length).toBeGreaterThan(0);
    });

    it('should validate temperature range', () => {
      const errors = LLMInferenceNode.validate?.({
        prompt: 'test',
        temperature: 3.0,
      });
      expect(errors).toBeDefined();
      expect(errors?.some((e) => e.includes('Temperature'))).toBe(true);
    });

    it('should validate negative temperature', () => {
      const errors = LLMInferenceNode.validate?.({
        prompt: 'test',
        temperature: -0.5,
      });
      expect(errors).toBeDefined();
      expect(errors?.some((e) => e.includes('Temperature'))).toBe(true);
    });

    it('should validate positive max_tokens', () => {
      const errors = LLMInferenceNode.validate?.({
        prompt: 'test',
        max_tokens: -100,
      });
      expect(errors).toBeDefined();
      expect(errors?.some((e) => e.includes('Max tokens'))).toBe(true);
    });

    it('should validate strategy options', () => {
      const errors = LLMInferenceNode.validate?.({
        prompt: 'test',
        strategy: 'invalid-strategy',
      });
      expect(errors).toBeDefined();
      expect(errors?.some((e) => e.includes('Strategy'))).toBe(true);
    });

    it('should require provider when strategy is specific', () => {
      const errors = LLMInferenceNode.validate?.({
        prompt: 'test',
        strategy: 'specific',
      });
      expect(errors).toBeDefined();
      expect(errors?.some((e) => e.includes('Provider'))).toBe(true);
    });

    it('should pass validation with valid inputs', () => {
      const errors = LLMInferenceNode.validate?.({
        prompt: 'Hello, world!',
        project_id: 'demo-project',
        temperature: 0.7,
        max_tokens: 1024,
        strategy: 'best',
      });
      expect(errors).toBeDefined();
      expect(errors?.length).toBe(0);
    });
  });

  describe('Execution', () => {
    it('should execute successfully with minimal inputs', async () => {
      // Mock successful response from core client
      const mockResponse = {
        content: 'Hello! How can I help you?',
        model: 'gpt-4',
        provider: 'openai',
        usage: { input_tokens: 10, output_tokens: 20 },
      };
      (coreClient.coreClient.send as Mock).mockResolvedValue(mockResponse);

      const result = await LLMInferenceNode.execute(
        { prompt: 'Hello', project_id: 'demo-project' },
        mockContext
      );

      // Verify core client was called
      expect(coreClient.coreClient.send).toHaveBeenCalledWith({
        messages: [{ role: 'user', content: 'Hello' }],
        project_id: 'demo-project',
        system: undefined,
        strategy: undefined,
        provider: undefined,
        model: undefined,
        temperature: undefined,
        max_tokens: undefined,
      });

      // Verify state emissions
      expect(emitStateSpy).toHaveBeenCalledWith('running');
      expect(emitStateSpy).toHaveBeenCalledWith('complete');

      // Verify logs
      expect(logSpy).toHaveBeenCalledWith('info', 'Starting LLM inference', expect.any(Object));
      expect(logSpy).toHaveBeenCalledWith('info', 'LLM inference completed', expect.any(Object));

      // Verify outputs
      expect(result).toBeDefined();
      if ('outputs' in result) {
        expect(result.outputs.response).toBe('Hello! How can I help you?');
        expect(result.outputs.model).toBe('gpt-4');
        expect(result.outputs.provider).toBe('openai');
        expect(result.outputs.input_tokens).toBe(10);
        expect(result.outputs.output_tokens).toBe(20);
      }
    });

    it('should execute with full configuration', async () => {
      const mockResponse = {
        content: 'Response from Claude',
        model: 'claude-3-sonnet',
        provider: 'anthropic',
        usage: { input_tokens: 50, output_tokens: 100 },
      };
      (coreClient.coreClient.send as Mock).mockResolvedValue(mockResponse);

      const result = await LLMInferenceNode.execute(
        {
          prompt: 'Explain AI',
          project_id: 'demo-project',
          system: 'You are an AI expert',
          strategy: 'specific',
          provider: 'anthropic',
          model: 'claude-3-sonnet',
          temperature: 0.5,
          max_tokens: 2048,
        },
        mockContext
      );

      // Verify core client was called with all parameters
      expect(coreClient.coreClient.send).toHaveBeenCalledWith({
        messages: [{ role: 'user', content: 'Explain AI' }],
        project_id: 'demo-project',
        system: 'You are an AI expert',
        strategy: 'specific',
        provider: 'anthropic',
        model: 'claude-3-sonnet',
        temperature: 0.5,
        max_tokens: 2048,
      });

      // Verify outputs
      if ('outputs' in result) {
        expect(result.outputs.response).toBe('Response from Claude');
        expect(result.outputs.model).toBe('claude-3-sonnet');
        expect(result.outputs.provider).toBe('anthropic');
      }
    });

    it('should handle errors from core client', async () => {
      // Mock error from core client
      const mockError = new coreClient.CoreApiError('Provider unavailable', 503);
      (coreClient.coreClient.send as Mock).mockRejectedValue(mockError);

      // Expect execution to throw
      await expect(
        LLMInferenceNode.execute({ prompt: 'Hello' }, mockContext)
      ).rejects.toThrow('LLM inference failed');

      // Verify error state and logging
      expect(emitStateSpy).toHaveBeenCalledWith('running');
      expect(emitStateSpy).toHaveBeenCalledWith('error');
      expect(logSpy).toHaveBeenCalledWith('error', 'LLM inference failed', expect.any(Object));
    });

    it('should handle abort signal', async () => {
      // Create abort controller
      const abortController = new AbortController();
      abortController.abort();

      const abortContext = {
        ...mockContext,
        signal: abortController.signal,
      };

      // Expect execution to throw abort error
      await expect(
        LLMInferenceNode.execute({ prompt: 'Hello' }, abortContext)
      ).rejects.toThrow('aborted');

      // Verify error state was emitted
      expect(emitStateSpy).toHaveBeenCalledWith('error');
    });

    it('should handle missing response fields gracefully', async () => {
      // Mock response with missing fields
      const mockResponse = {
        content: 'Response',
        model: '',
        provider: '',
        usage: {},
      };
      (coreClient.coreClient.send as Mock).mockResolvedValue(mockResponse);

      const result = await LLMInferenceNode.execute(
        { prompt: 'Hello' },
        mockContext
      );

      // Verify defaults are used for missing fields
      if ('outputs' in result) {
        expect(result.outputs.response).toBe('Response');
        expect(result.outputs.model).toBe('unknown');
        expect(result.outputs.provider).toBe('unknown');
        expect(result.outputs.input_tokens).toBe(0);
        expect(result.outputs.output_tokens).toBe(0);
      }
    });
  });

  describe('Metadata', () => {
    it('should have metadata defined', () => {
      expect(LLMInferenceNode.metadata).toBeDefined();
      expect(LLMInferenceNode.metadata?.version).toBe('1.0.0');
      expect(LLMInferenceNode.metadata?.author).toBe('Mascarade');
      expect(LLMInferenceNode.metadata?.tags).toContain('ai');
      expect(LLMInferenceNode.metadata?.experimental).toBe(false);
    });
  });
});
