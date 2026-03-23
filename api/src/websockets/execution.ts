/**
 * WebSocket endpoint for real-time execution state updates
 *
 * Broadcasts execution events to connected clients:
 * - Graph lifecycle events (started, completed, failed)
 * - Node state changes (idle → pending → running → completed/error)
 * - Node outputs and errors
 * - Execution logs
 *
 * Usage:
 * ```typescript
 * import { createExecutionWebSocketServer } from './websockets/execution.js';
 *
 * const server = http.createServer(app);
 * createExecutionWebSocketServer(server, '/ws/execution');
 * ```
 */

import { WebSocketServer, WebSocket } from 'ws';
import type { Server as HTTPServer } from 'node:http';
import { EventEmitter } from 'node:events';
import type { ExecutionEvent } from '../node-engine/types/ExecutionTypes.js';
import { emitStructuredLog } from '../lib/otel.js';

/**
 * WebSocket message types
 */
type WebSocketMessage =
  | { type: 'ping' }
  | { type: 'subscribe'; runId: string }
  | { type: 'unsubscribe'; runId: string }
  | { type: 'subscribe_all' }
  | { type: 'execution_event'; event: ExecutionEvent };

/**
 * Client connection state
 */
interface ClientConnection {
  /** WebSocket instance */
  ws: WebSocket;
  /** Client ID */
  id: string;
  /** Subscribed run IDs (empty = all runs) */
  subscriptions: Set<string>;
  /** Connection timestamp */
  connectedAt: Date;
  /** Last activity timestamp */
  lastActivity: Date;
}

/**
 * Global event emitter for execution events
 *
 * ExecutionContext instances emit events here, and the WebSocket
 * server broadcasts them to connected clients.
 */
export const executionEventEmitter = new EventEmitter();

// Increase max listeners to support many concurrent executions
executionEventEmitter.setMaxListeners(1000);

/**
 * Active WebSocket clients
 */
const clients = new Map<string, ClientConnection>();

/**
 * Generate unique client ID
 */
function generateClientId(): string {
  return `client-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

/**
 * Send message to WebSocket client
 *
 * @param client - Client connection
 * @param message - Message to send
 */
function sendToClient(client: ClientConnection, message: WebSocketMessage): void {
  if (client.ws.readyState === WebSocket.OPEN) {
    try {
      client.ws.send(JSON.stringify(message));
      client.lastActivity = new Date();
    } catch (err: unknown) {
      emitStructuredLog({
        service: 'api',
        severity: 'error',
        message: 'Failed to send WebSocket message',
        client_id: client.id,
        error: err instanceof Error ? err.message : String(err),
      });
    }
  }
}

/**
 * Broadcast execution event to subscribed clients
 *
 * @param event - Execution event to broadcast
 */
function broadcastExecutionEvent(event: ExecutionEvent): void {
  const message: WebSocketMessage = {
    type: 'execution_event',
    event,
  };

  // Extract runId from event (all event types have runId)
  const runId = event.runId;

  let broadcastCount = 0;

  for (const client of clients.values()) {
    // Send to clients subscribed to this runId or subscribed to all runs
    if (client.subscriptions.size === 0 || client.subscriptions.has(runId)) {
      sendToClient(client, message);
      broadcastCount++;
    }
  }

  if (broadcastCount > 0) {
    emitStructuredLog({
      service: 'api',
      severity: 'debug',
      message: 'Broadcasted execution event',
      event_type: event.type,
      run_id: runId,
      client_count: broadcastCount,
    });
  }
}

/**
 * Handle incoming WebSocket message
 *
 * @param client - Client connection
 * @param data - Raw message data
 */
function handleClientMessage(client: ClientConnection, data: Buffer | string): void {
  try {
    const message = JSON.parse(data.toString()) as WebSocketMessage;

    switch (message.type) {
      case 'ping':
        // Respond with pong (keep-alive)
        client.ws.send(JSON.stringify({ type: 'pong' }));
        client.lastActivity = new Date();
        break;

      case 'subscribe':
        // Subscribe to specific run ID
        client.subscriptions.add(message.runId);
        emitStructuredLog({
          service: 'api',
          severity: 'debug',
          message: 'Client subscribed to run',
          client_id: client.id,
          run_id: message.runId,
        });
        client.ws.send(
          JSON.stringify({
            type: 'subscribed',
            runId: message.runId,
          })
        );
        break;

      case 'unsubscribe':
        // Unsubscribe from specific run ID
        client.subscriptions.delete(message.runId);
        emitStructuredLog({
          service: 'api',
          severity: 'debug',
          message: 'Client unsubscribed from run',
          client_id: client.id,
          run_id: message.runId,
        });
        client.ws.send(
          JSON.stringify({
            type: 'unsubscribed',
            runId: message.runId,
          })
        );
        break;

      case 'subscribe_all':
        // Subscribe to all execution events (clear specific subscriptions)
        client.subscriptions.clear();
        emitStructuredLog({
          service: 'api',
          severity: 'debug',
          message: 'Client subscribed to all runs',
          client_id: client.id,
        });
        client.ws.send(
          JSON.stringify({
            type: 'subscribed_all',
          })
        );
        break;

      default:
        emitStructuredLog({
          service: 'api',
          severity: 'warn',
          message: 'Unknown WebSocket message type',
          client_id: client.id,
          message_type: (message as { type: string }).type,
        });
    }
  } catch (err: unknown) {
    emitStructuredLog({
      service: 'api',
      severity: 'error',
      message: 'Failed to parse WebSocket message',
      client_id: client.id,
      error: err instanceof Error ? err.message : String(err),
    });
  }
}

/**
 * Remove client connection
 *
 * @param clientId - Client ID to remove
 */
function removeClient(clientId: string): void {
  const client = clients.get(clientId);
  if (client) {
    clients.delete(clientId);
    emitStructuredLog({
      service: 'api',
      severity: 'info',
      message: 'WebSocket client disconnected',
      client_id: clientId,
      connected_duration_ms: Date.now() - client.connectedAt.getTime(),
      total_clients: clients.size,
    });
  }
}

/**
 * Create WebSocket server for execution events
 *
 * @param httpServer - HTTP server instance
 * @param path - WebSocket endpoint path (default: /ws/execution)
 * @returns WebSocket server instance
 */
export function createExecutionWebSocketServer(
  httpServer: HTTPServer,
  path = '/ws/execution'
): WebSocketServer {
  const wss = new WebSocketServer({
    server: httpServer,
    path,
  });

  // Listen for execution events and broadcast to clients
  executionEventEmitter.on('execution_event', (event: ExecutionEvent) => {
    broadcastExecutionEvent(event);
  });

  // Handle new WebSocket connections
  wss.on('connection', (ws: WebSocket) => {
    const clientId = generateClientId();
    const client: ClientConnection = {
      ws,
      id: clientId,
      subscriptions: new Set(), // Empty = subscribed to all
      connectedAt: new Date(),
      lastActivity: new Date(),
    };

    clients.set(clientId, client);

    emitStructuredLog({
      service: 'api',
      severity: 'info',
      message: 'WebSocket client connected',
      client_id: clientId,
      total_clients: clients.size,
    });

    // Send welcome message
    ws.send(
      JSON.stringify({
        type: 'connected',
        clientId,
        message: 'Connected to node engine execution updates',
      })
    );

    // Handle incoming messages
    ws.on('message', (data: Buffer) => {
      handleClientMessage(client, data);
    });

    // Handle connection close
    ws.on('close', () => {
      removeClient(clientId);
    });

    // Handle errors
    ws.on('error', (err: Error) => {
      emitStructuredLog({
        service: 'api',
        severity: 'error',
        message: 'WebSocket error',
        client_id: clientId,
        error: err.message,
      });
      removeClient(clientId);
    });
  });

  // Handle server errors
  wss.on('error', (err: Error) => {
    emitStructuredLog({
      service: 'api',
      severity: 'error',
      message: 'WebSocket server error',
      error: err.message,
    });
  });

  emitStructuredLog({
    service: 'api',
    severity: 'info',
    message: 'WebSocket server initialized',
    path,
  });

  return wss;
}

/**
 * Get connected client count
 *
 * @returns Number of connected clients
 */
export function getConnectedClientCount(): number {
  return clients.size;
}

/**
 * Get client information
 *
 * @returns Array of client connection info
 */
export function getConnectedClients(): Array<{
  id: string;
  subscriptions: string[];
  connectedAt: string;
  lastActivity: string;
}> {
  return Array.from(clients.values()).map((client) => ({
    id: client.id,
    subscriptions: Array.from(client.subscriptions),
    connectedAt: client.connectedAt.toISOString(),
    lastActivity: client.lastActivity.toISOString(),
  }));
}

/**
 * Emit execution event to WebSocket clients
 *
 * Helper function for ExecutionContext to emit events.
 * Events are broadcasted to all subscribed clients.
 *
 * @param event - Execution event to emit
 */
export function emitExecutionEvent(event: ExecutionEvent): void {
  executionEventEmitter.emit('execution_event', event);
}
