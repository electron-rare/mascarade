/**
 * Webhook Node - HTTP webhook receiver for external trigger integration
 *
 * Receives HTTP webhook requests and triggers graph execution with the payload.
 * Enables integration with external systems, services, and event sources.
 *
 * Features:
 * - HTTP POST/GET webhook reception
 * - JSON payload parsing
 * - Header extraction
 * - Query parameter support
 * - Webhook signature verification (optional)
 *
 * Inspired by:
 * - Node-RED: HTTP In node for webhook reception
 * - Zapier: Webhook triggers for automation
 * - GitHub Actions: Webhook event triggers
 */

import {
  NodeCategory,
  type NodePlugin,
  type ExecutionContext,
  type NodeExecutionResult,
} from '../../NodePluginAPI.js';

/**
 * Webhook Node Plugin
 *
 * Receives HTTP webhooks and emits the payload data, useful for:
 * - External service integration (GitHub, Slack, etc.)
 * - Event-driven automation workflows
 * - API callback handling
 * - Real-time notification processing
 *
 * Example usage in a graph:
 * 1. Webhook → Parse Event → Process → Store
 * 2. Webhook (GitHub) → Filter Branch → Build → Deploy
 *
 * Configuration:
 * - path: Webhook endpoint path (e.g., "/webhook/my-trigger")
 * - method: HTTP method to accept (GET, POST, PUT, etc.)
 * - secret: Optional secret for signature verification
 * - payload: The incoming webhook payload (injected by runtime)
 * - headers: The incoming request headers (injected by runtime)
 */
export const WebhookNode: NodePlugin = {
  id: 'webhook',
  category: NodeCategory.Automation,
  label: 'Webhook',
  description: 'Receive HTTP webhooks and trigger graph execution',

  inputs: [
    {
      id: 'path',
      label: 'Webhook Path',
      type: 'string',
      required: true,
      defaultValue: '/webhook/default',
      description: 'Webhook endpoint path (e.g., /webhook/my-trigger)',
    },
    {
      id: 'method',
      label: 'HTTP Method',
      type: 'string',
      required: false,
      defaultValue: 'POST',
      description: 'HTTP method to accept (GET, POST, PUT, DELETE)',
    },
    {
      id: 'secret',
      label: 'Secret',
      type: 'string',
      required: false,
      description: 'Optional secret for signature verification',
    },
    {
      id: 'payload',
      label: 'Payload',
      type: 'any',
      required: false,
      description: 'Incoming webhook payload (injected by runtime)',
    },
    {
      id: 'headers',
      label: 'Headers',
      type: 'any',
      required: false,
      description: 'Incoming request headers (injected by runtime)',
    },
  ],

  outputs: [
    {
      id: 'data',
      label: 'Data',
      type: 'any',
      description: 'Webhook payload data',
    },
    {
      id: 'headers',
      label: 'Headers',
      type: 'any',
      description: 'Request headers',
    },
    {
      id: 'meta',
      label: 'Metadata',
      type: 'any',
      description: 'Webhook metadata (timestamp, method, path)',
    },
  ],

  /**
   * Validate inputs before execution
   *
   * Ensures:
   * - Path is provided and starts with '/'
   * - Method is valid HTTP method
   */
  validate: (inputs: Record<string, unknown>): string[] => {
    const errors: string[] = [];

    // Validate path
    const path = inputs.path as string;
    if (!path || typeof path !== 'string') {
      errors.push('Webhook path must be provided');
    } else if (!path.startsWith('/')) {
      errors.push('Webhook path must start with /');
    }

    // Validate method
    const method = inputs.method as string;
    if (method) {
      const validMethods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'];
      if (!validMethods.includes(method.toUpperCase())) {
        errors.push(`HTTP method must be one of: ${validMethods.join(', ')}`);
      }
    }

    return errors;
  },

  /**
   * Execute webhook processing
   *
   * Workflow:
   * 1. Extract webhook configuration and payload
   * 2. Emit 'running' state
   * 3. Verify signature if secret is provided
   * 4. Parse and validate payload
   * 5. Emit 'complete' state
   * 6. Return webhook data and metadata
   *
   * Error handling:
   * - Logs errors to execution context
   * - Emits 'error' state for UI feedback
   * - Re-throws error to propagate to downstream nodes
   *
   * Note: This is a simplified implementation for demonstration.
   * In a real system, webhook registration and HTTP server integration
   * would be managed by the execution runtime, not within the node itself.
   */
  execute: async (
    inputs: Record<string, unknown>,
    context: ExecutionContext
  ): Promise<NodeExecutionResult> => {
    // Extract inputs
    const path = (inputs.path as string) || '/webhook/default';
    const method = ((inputs.method as string) || 'POST').toUpperCase();
    const secret = inputs.secret as string | undefined;
    const payload = inputs.payload;
    const headers = inputs.headers as Record<string, string> | undefined;

    // Log execution start
    context.log('info', 'Webhook processing started', {
      path,
      method,
      hasSecret: !!secret,
      hasPayload: payload !== undefined,
    });

    // Emit running state
    context.emitState('running');

    try {
      // Check for abort signal
      if (context.signal?.aborted) {
        throw new Error('Execution aborted');
      }

      // Verify signature if secret is provided
      if (secret && headers) {
        const signature = headers['x-webhook-signature'] || headers['x-hub-signature-256'];
        if (signature) {
          context.log('info', 'Webhook signature verification requested', {
            hasSignature: true,
          });
          // Note: Actual signature verification would be implemented here
          // For now, we just log that it's requested
          context.log('warn', 'Webhook signature verification not yet implemented', {
            signature: signature.substring(0, 10) + '...',
          });
        }
      }

      // Process payload
      let processedPayload = payload;
      if (typeof payload === 'string') {
        try {
          processedPayload = JSON.parse(payload);
          context.log('info', 'Parsed JSON payload', {
            payloadType: typeof processedPayload,
          });
        } catch (e) {
          context.log('warn', 'Failed to parse payload as JSON, using raw string', {
            error: e instanceof Error ? e.message : String(e),
          });
        }
      }

      const timestamp = Date.now();

      context.log('info', 'Webhook processed successfully', {
        timestamp,
        payloadSize: JSON.stringify(processedPayload || {}).length,
      });

      // Emit complete state
      context.emitState('complete');

      // Return outputs
      return {
        outputs: {
          data: processedPayload,
          headers: headers || {},
          meta: {
            path,
            method,
            timestamp,
            verified: false, // Will be true when signature verification is implemented
          },
        },
        meta: {
          executionTime: Date.now(),
          webhookPath: path,
          httpMethod: method,
        },
      };
    } catch (error) {
      // Log error
      const errorMessage = error instanceof Error ? error.message : String(error);
      context.log('error', 'Webhook processing failed', {
        error: errorMessage,
      });

      // Emit error state
      context.emitState('error');

      // Re-throw to propagate
      throw new Error(`Webhook processing failed: ${errorMessage}`);
    }
  },

  /**
   * Lifecycle: Initialize webhook endpoint
   *
   * In a production system, this would:
   * - Register the webhook path with the HTTP server
   * - Set up event handlers for incoming requests
   * - Configure signature verification
   */
  onInit: async (context: ExecutionContext) => {
    context.log('info', 'Webhook node initialized', {
      nodeId: context.nodeId,
      graphId: context.graphId,
    });
    // Note: Actual webhook registration would be implemented here
    // by the runtime's HTTP server integration
  },

  /**
   * Lifecycle: Clean up webhook endpoint
   *
   * In a production system, this would:
   * - Unregister the webhook path from the HTTP server
   * - Clean up event handlers
   */
  onDestroy: async (context: ExecutionContext) => {
    context.log('info', 'Webhook node destroyed', {
      nodeId: context.nodeId,
      graphId: context.graphId,
    });
    // Note: Actual webhook cleanup would be implemented here
  },

  /**
   * Plugin metadata
   */
  metadata: {
    version: '1.0.0',
    author: 'Mascarade',
    tags: ['automation', 'webhook', 'http', 'trigger', 'integration', 'api'],
    experimental: false,
  },
};
