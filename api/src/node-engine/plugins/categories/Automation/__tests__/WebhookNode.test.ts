/**
 * WebhookNode Tests
 *
 * Tests for the Webhook node plugin, including:
 * - Input validation
 * - Payload processing
 * - Header extraction
 * - State emission
 * - Error handling
 */

import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import { WebhookNode } from '../WebhookNode.js';
import type { ExecutionContext } from '../../../NodePluginAPI.js';

describe('WebhookNode', () => {
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
      expect(WebhookNode.id).toBe('webhook');
      expect(WebhookNode.category).toBe('Automation');
    });

    it('should have correct label and description', () => {
      expect(WebhookNode.label).toBe('Webhook');
      expect(WebhookNode.description).toContain('webhook');
    });

    it('should define required inputs', () => {
      expect(WebhookNode.inputs).toBeDefined();
      const pathInput = WebhookNode.inputs.find((i) => i.id === 'path');
      expect(pathInput).toBeDefined();
      expect(pathInput?.required).toBe(true);
    });

    it('should define expected outputs', () => {
      expect(WebhookNode.outputs).toBeDefined();
      const outputIds = WebhookNode.outputs.map((o) => o.id);
      expect(outputIds).toContain('data');
      expect(outputIds).toContain('headers');
      expect(outputIds).toContain('meta');
    });
  });

  describe('Input Validation', () => {
    it('should validate missing path', () => {
      const errors = WebhookNode.validate?.({});
      expect(errors).toBeDefined();
      expect(errors?.length).toBeGreaterThan(0);
      expect(errors?.[0]).toContain('Webhook path must be provided');
    });

    it('should validate path without leading slash', () => {
      const errors = WebhookNode.validate?.({ path: 'webhook/test' });
      expect(errors).toBeDefined();
      expect(errors?.length).toBeGreaterThan(0);
      expect(errors?.some(e => e.includes('must start with /'))).toBe(true);
    });

    it('should validate invalid HTTP method', () => {
      const errors = WebhookNode.validate?.({ path: '/webhook', method: 'INVALID' });
      expect(errors).toBeDefined();
      expect(errors?.length).toBeGreaterThan(0);
      expect(errors?.some(e => e.includes('HTTP method'))).toBe(true);
    });

    it('should pass validation with valid path', () => {
      const errors = WebhookNode.validate?.({ path: '/webhook/test' });
      expect(errors).toBeDefined();
      expect(errors?.length).toBe(0);
    });

    it('should pass validation with valid path and method', () => {
      const errors = WebhookNode.validate?.({ path: '/webhook/test', method: 'POST' });
      expect(errors).toBeDefined();
      expect(errors?.length).toBe(0);
    });

    it('should accept all valid HTTP methods', () => {
      const validMethods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'];

      for (const method of validMethods) {
        const errors = WebhookNode.validate?.({ path: '/webhook', method });
        expect(errors?.length).toBe(0);
      }
    });

    it('should accept lowercase HTTP methods', () => {
      const errors = WebhookNode.validate?.({ path: '/webhook', method: 'post' });
      expect(errors?.length).toBe(0);
    });
  });

  describe('Execution - Basic Webhook Processing', () => {
    it('should process webhook with JSON payload', async () => {
      const payload = { event: 'test', data: { value: 42 } };

      const result = await WebhookNode.execute(
        { path: '/webhook/test', method: 'POST', payload },
        mockContext
      );

      // Verify state emissions
      expect(emitStateSpy).toHaveBeenCalledWith('running');
      expect(emitStateSpy).toHaveBeenCalledWith('complete');

      // Verify logs
      expect(logSpy).toHaveBeenCalledWith('info', 'Webhook processing started', expect.any(Object));
      expect(logSpy).toHaveBeenCalledWith('info', 'Webhook processed successfully', expect.any(Object));

      // Verify outputs
      expect(result).toBeDefined();
      if ('outputs' in result) {
        expect(result.outputs.data).toEqual(payload);
        expect(result.outputs.headers).toEqual({});
        expect(result.outputs.meta).toBeDefined();
        expect(result.outputs.meta).toHaveProperty('path', '/webhook/test');
        expect(result.outputs.meta).toHaveProperty('method', 'POST');
        expect(result.outputs.meta).toHaveProperty('timestamp');
      }
    });

    it('should process webhook with headers', async () => {
      const payload = { test: 'data' };
      const headers = {
        'content-type': 'application/json',
        'user-agent': 'test-agent',
        'x-custom-header': 'custom-value',
      };

      const result = await WebhookNode.execute(
        { path: '/webhook/test', payload, headers },
        mockContext
      );

      if ('outputs' in result) {
        expect(result.outputs.headers).toEqual(headers);
      }
    });

    it('should work without payload', async () => {
      const result = await WebhookNode.execute(
        { path: '/webhook/test' },
        mockContext
      );

      if ('outputs' in result) {
        expect(result.outputs.data).toBeUndefined();
        expect(result.outputs.meta).toBeDefined();
      }
    });

    it('should include execution metadata', async () => {
      const result = await WebhookNode.execute(
        { path: '/webhook/test', method: 'GET' },
        mockContext
      );

      if ('meta' in result) {
        expect(result.meta?.webhookPath).toBe('/webhook/test');
        expect(result.meta?.httpMethod).toBe('GET');
        expect(result.meta?.executionTime).toBeDefined();
      }
    });
  });

  describe('Execution - JSON Payload Parsing', () => {
    it('should parse JSON string payload', async () => {
      const jsonString = '{"event":"test","value":123}';
      const expectedObject = { event: 'test', value: 123 };

      const result = await WebhookNode.execute(
        { path: '/webhook/test', payload: jsonString },
        mockContext
      );

      if ('outputs' in result) {
        expect(result.outputs.data).toEqual(expectedObject);
      }

      // Verify JSON parsing was logged
      expect(logSpy).toHaveBeenCalledWith(
        'info',
        'Parsed JSON payload',
        expect.any(Object)
      );
    });

    it('should handle invalid JSON gracefully', async () => {
      const invalidJson = '{"invalid": json}';

      const result = await WebhookNode.execute(
        { path: '/webhook/test', payload: invalidJson },
        mockContext
      );

      if ('outputs' in result) {
        // Should use raw string when JSON parsing fails
        expect(result.outputs.data).toBe(invalidJson);
      }

      // Verify warning was logged
      expect(logSpy).toHaveBeenCalledWith(
        'warn',
        expect.stringContaining('Failed to parse payload as JSON'),
        expect.any(Object)
      );
    });

    it('should handle non-JSON string payload', async () => {
      const textPayload = 'plain text payload';

      const result = await WebhookNode.execute(
        { path: '/webhook/test', payload: textPayload },
        mockContext
      );

      if ('outputs' in result) {
        expect(result.outputs.data).toBe(textPayload);
      }
    });
  });

  describe('Execution - Signature Verification', () => {
    it('should log signature verification attempt when secret provided', async () => {
      const headers = {
        'x-webhook-signature': 'sha256=abc123def456',
      };

      await WebhookNode.execute(
        { path: '/webhook/test', secret: 'my-secret', payload: {}, headers },
        mockContext
      );

      // Should log that signature verification was requested
      expect(logSpy).toHaveBeenCalledWith(
        'info',
        'Webhook signature verification requested',
        expect.any(Object)
      );

      // Should log warning that it's not implemented
      expect(logSpy).toHaveBeenCalledWith(
        'warn',
        expect.stringContaining('Webhook signature verification not yet implemented'),
        expect.any(Object)
      );
    });

    it('should support GitHub-style signatures', async () => {
      const headers = {
        'x-hub-signature-256': 'sha256=github-signature',
      };

      await WebhookNode.execute(
        { path: '/webhook/github', secret: 'github-secret', payload: {}, headers },
        mockContext
      );

      expect(logSpy).toHaveBeenCalledWith(
        'info',
        'Webhook signature verification requested',
        expect.any(Object)
      );
    });

    it('should skip verification when no secret provided', async () => {
      await WebhookNode.execute(
        { path: '/webhook/test', payload: {} },
        mockContext
      );

      // Should not log signature verification
      expect(logSpy).not.toHaveBeenCalledWith(
        'info',
        'Webhook signature verification requested',
        expect.any(Object)
      );
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
        WebhookNode.execute({ path: '/webhook/test' }, abortContext)
      ).rejects.toThrow('aborted');

      expect(emitStateSpy).toHaveBeenCalledWith('error');
    });
  });

  describe('Lifecycle Hooks', () => {
    it('should have onInit hook', () => {
      expect(WebhookNode.onInit).toBeDefined();
    });

    it('should have onDestroy hook', () => {
      expect(WebhookNode.onDestroy).toBeDefined();
    });

    it('should log initialization', async () => {
      if (WebhookNode.onInit) {
        await WebhookNode.onInit(mockContext);

        expect(logSpy).toHaveBeenCalledWith(
          'info',
          'Webhook node initialized',
          expect.objectContaining({
            nodeId: mockContext.nodeId,
            graphId: mockContext.graphId,
          })
        );
      }
    });

    it('should log destruction', async () => {
      if (WebhookNode.onDestroy) {
        await WebhookNode.onDestroy(mockContext);

        expect(logSpy).toHaveBeenCalledWith(
          'info',
          'Webhook node destroyed',
          expect.objectContaining({
            nodeId: mockContext.nodeId,
            graphId: mockContext.graphId,
          })
        );
      }
    });
  });

  describe('Metadata', () => {
    it('should have metadata defined', () => {
      expect(WebhookNode.metadata).toBeDefined();
      expect(WebhookNode.metadata?.version).toBe('1.0.0');
      expect(WebhookNode.metadata?.author).toBe('Mascarade');
      expect(WebhookNode.metadata?.tags).toContain('automation');
      expect(WebhookNode.metadata?.tags).toContain('webhook');
      expect(WebhookNode.metadata?.experimental).toBe(false);
    });
  });
});
