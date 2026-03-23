/**
 * LLM Inference Node - AI category example node using Mascarade router
 *
 * Performs LLM inference using the Mascarade core router, which automatically
 * selects the best available provider based on routing policy.
 *
 * Features:
 * - Supports multiple routing strategies (cheapest, fastest, best, specific)
 * - Automatic provider selection via Mascarade router
 * - Configurable temperature and max tokens
 * - Error handling with graceful fallback
 *
 * Inspired by:
 * - ComfyUI: Typed inputs with explicit schemas
 * - Node-RED: Message passing pattern
 * - Mascarade: LLM router abstraction
 */

import {
  NodeCategory,
  type NodePlugin,
  type ExecutionContext,
  type NodeExecutionResult,
} from '../../NodePluginAPI.js';
import { coreClient, CoreApiError } from '../../../../client/core.js';

/**
 * LLM Inference Node Plugin
 *
 * Executes LLM inference using the Mascarade router. Accepts a prompt and
 * system message, returns the AI-generated response.
 *
 * Example usage in a graph:
 * 1. Input node → LLMInferenceNode → Output node
 * 2. Trigger → LLMInferenceNode → Text-to-Speech node
 *
 * Configuration:
 * - prompt: User prompt for the LLM
 * - system: System prompt (optional, sets behavior/personality)
 * - strategy: Routing strategy (cheapest, fastest, best, specific)
 * - provider: Specific provider to use (optional, requires strategy: specific)
 * - model: Specific model to use (optional)
 * - temperature: Sampling temperature (0.0-2.0, default: 0.7)
 * - max_tokens: Maximum tokens to generate (default: 1024)
 */
export const LLMInferenceNode: NodePlugin = {
  id: 'llm-inference',
  category: NodeCategory.AI,
  label: 'LLM Inference',
  description: 'Execute LLM inference using Mascarade router with automatic provider selection',

  inputs: [
    {
      id: 'prompt',
      label: 'Prompt',
      type: 'string',
      required: true,
      description: 'User prompt for the LLM',
    },
    {
      id: 'project_id',
      label: 'Project ID',
      type: 'string',
      required: true,
      description: 'Logical project scope used for cache, memory, and retrieval isolation',
    },
    {
      id: 'system',
      label: 'System Prompt',
      type: 'string',
      required: false,
      defaultValue: 'You are a helpful assistant.',
      description: 'System prompt that sets the behavior of the LLM',
    },
    {
      id: 'strategy',
      label: 'Routing Strategy',
      type: 'string',
      required: false,
      defaultValue: 'best',
      description: 'Routing strategy: cheapest, fastest, best, or specific',
    },
    {
      id: 'provider',
      label: 'Provider',
      type: 'string',
      required: false,
      description: 'Specific provider (e.g., openai, anthropic) - requires strategy: specific',
    },
    {
      id: 'model',
      label: 'Model',
      type: 'string',
      required: false,
      description: 'Specific model to use (e.g., gpt-4, claude-3-sonnet)',
    },
    {
      id: 'temperature',
      label: 'Temperature',
      type: 'number',
      required: false,
      defaultValue: 0.7,
      description: 'Sampling temperature (0.0-2.0)',
    },
    {
      id: 'max_tokens',
      label: 'Max Tokens',
      type: 'number',
      required: false,
      defaultValue: 1024,
      description: 'Maximum tokens to generate',
    },
  ],

  outputs: [
    {
      id: 'response',
      label: 'Response',
      type: 'string',
      description: 'LLM-generated response text',
    },
    {
      id: 'model',
      label: 'Model Used',
      type: 'string',
      description: 'Model that was used for inference',
    },
    {
      id: 'provider',
      label: 'Provider Used',
      type: 'string',
      description: 'Provider that was used for inference',
    },
    {
      id: 'input_tokens',
      label: 'Input Tokens',
      type: 'number',
      description: 'Number of input tokens consumed',
    },
    {
      id: 'output_tokens',
      label: 'Output Tokens',
      type: 'number',
      description: 'Number of output tokens generated',
    },
  ],

  /**
   * Validate inputs before execution
   *
   * Ensures:
   * - Prompt is not empty
   * - Temperature is in valid range (0.0-2.0)
   * - Max tokens is positive
   * - Strategy is valid
   * - Provider is specified when strategy is 'specific'
   */
  validate: (inputs: Record<string, unknown>): string[] => {
    const errors: string[] = [];

    // Validate prompt
    const prompt = inputs.prompt;
    if (typeof prompt !== 'string' || prompt.trim().length === 0) {
      errors.push('Prompt must be a non-empty string');
    }

    const projectId = inputs.project_id;
    if (typeof projectId !== 'string' || projectId.trim().length === 0) {
      errors.push('Project ID must be a non-empty string');
    }

    // Validate temperature
    const temperature = inputs.temperature;
    if (temperature !== undefined) {
      if (typeof temperature !== 'number') {
        errors.push('Temperature must be a number');
      } else if (temperature < 0 || temperature > 2) {
        errors.push('Temperature must be between 0.0 and 2.0');
      }
    }

    // Validate max_tokens
    const maxTokens = inputs.max_tokens;
    if (maxTokens !== undefined) {
      if (typeof maxTokens !== 'number') {
        errors.push('Max tokens must be a number');
      } else if (maxTokens <= 0) {
        errors.push('Max tokens must be positive');
      }
    }

    // Validate strategy
    const strategy = inputs.strategy;
    if (strategy !== undefined) {
      const validStrategies = ['cheapest', 'fastest', 'best', 'specific'];
      if (typeof strategy !== 'string' || !validStrategies.includes(strategy)) {
        errors.push(`Strategy must be one of: ${validStrategies.join(', ')}`);
      }

      // Validate provider when strategy is 'specific'
      if (strategy === 'specific' && !inputs.provider) {
        errors.push('Provider must be specified when strategy is "specific"');
      }
    }

    return errors;
  },

  /**
   * Execute LLM inference
   *
   * Workflow:
   * 1. Extract and validate inputs
   * 2. Emit 'running' state for UI feedback
   * 3. Call Mascarade router with configured parameters
   * 4. Extract response and metadata
   * 5. Emit 'complete' state
   * 6. Return outputs
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
    const prompt = String(inputs.prompt || '');
    const projectId = String(inputs.project_id || '').trim();
    const system = inputs.system ? String(inputs.system) : undefined;
    const strategy = inputs.strategy ? String(inputs.strategy) : undefined;
    const provider = inputs.provider ? String(inputs.provider) : undefined;
    const model = inputs.model ? String(inputs.model) : undefined;
    const temperature = typeof inputs.temperature === 'number' ? inputs.temperature : undefined;
    const maxTokens = typeof inputs.max_tokens === 'number' ? inputs.max_tokens : undefined;

    // Log execution start
    context.log('info', 'Starting LLM inference', {
      promptLength: prompt.length,
      strategy,
      provider,
      model,
    });

    // Emit running state for UI feedback
    context.emitState('running');

    try {
      // Check for abort signal
      if (context.signal?.aborted) {
        throw new Error('Execution aborted');
      }

      // Call Mascarade router
      const response = await coreClient.send({
        messages: [{ role: 'user', content: prompt }],
        project_id: projectId,
        system,
        strategy,
        provider,
        model,
        temperature,
        max_tokens: maxTokens,
      });

      // Extract response data
      const responseText = response.content || '';
      const usedModel = response.model || 'unknown';
      const usedProvider = response.provider || 'unknown';
      const inputTokens = response.usage?.input_tokens || 0;
      const outputTokens = response.usage?.output_tokens || 0;

      // Log success
      context.log('info', 'LLM inference completed', {
        model: usedModel,
        provider: usedProvider,
        inputTokens,
        outputTokens,
        responseLength: responseText.length,
      });

      // Emit complete state
      context.emitState('complete');

      // Return outputs
      return {
        outputs: {
          response: responseText,
          model: usedModel,
          provider: usedProvider,
          input_tokens: inputTokens,
          output_tokens: outputTokens,
        },
        meta: {
          executionTime: Date.now(),
          model: usedModel,
          provider: usedProvider,
          usage: {
            input_tokens: inputTokens,
            output_tokens: outputTokens,
          },
        },
      };
    } catch (error) {
      // Log error with details
      const errorMessage = error instanceof Error ? error.message : String(error);
      const errorStatus = error instanceof CoreApiError ? error.status : undefined;

      context.log('error', 'LLM inference failed', {
        error: errorMessage,
        status: errorStatus,
      });

      // Emit error state
      context.emitState('error');

      // Re-throw to propagate to downstream nodes
      throw new Error(`LLM inference failed: ${errorMessage}`);
    }
  },

  /**
   * Plugin metadata
   */
  metadata: {
    version: '1.0.0',
    author: 'Mascarade',
    tags: ['ai', 'llm', 'inference', 'text-generation'],
    experimental: false,
  },
};
