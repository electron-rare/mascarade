#!/usr/bin/env node
/**
 * MIDI Bridge Service — JZZ wrapper with HTTP API
 *
 * This Node.js service wraps the JZZ MIDI library and exposes
 * a simple HTTP API for the Python backend to communicate with MIDI devices.
 */

const http = require('http');
const url = require('url');

// Try to load JZZ, graceful fallback if not installed
let JZZ;
try {
  JZZ = require('jzz');
} catch (error) {
  console.error('JZZ not installed. Install with: npm install jzz');
  process.exit(1);
}

const PORT = process.env.MIDI_BRIDGE_PORT || 3333;
const HOST = process.env.MIDI_BRIDGE_HOST || 'localhost';

// Store open MIDI ports
const openPorts = new Map();

/**
 * Get list of MIDI devices
 */
async function getDevices(type = 'output') {
  try {
    const info = await JZZ().info();
    const devices = type === 'input' ? info.inputs : info.outputs;

    return devices.map((device, index) => ({
      id: `${type}-${index}`,
      name: device.name || `MIDI ${type} ${index}`,
      manufacturer: device.manufacturer || null,
    }));
  } catch (error) {
    console.error('Failed to enumerate MIDI devices:', error.message);
    return [];
  }
}

/**
 * Open MIDI port
 */
async function openPort(deviceId, type = 'output') {
  if (openPorts.has(deviceId)) {
    return openPorts.get(deviceId);
  }

  const index = parseInt(deviceId.split('-')[1]);

  try {
    const midi = JZZ();
    const port = type === 'input'
      ? await midi.openMidiIn(index)
      : await midi.openMidiOut(index);

    openPorts.set(deviceId, port);
    console.log(`Opened MIDI ${type} port: ${deviceId}`);
    return port;
  } catch (error) {
    console.error(`Failed to open MIDI port ${deviceId}:`, error.message);
    throw error;
  }
}

/**
 * Send MIDI message
 */
async function sendMessage(deviceId, message) {
  const port = await openPort(deviceId, 'output');
  const { type, channel, data } = message;

  // MIDI channels are 0-indexed in JZZ
  const ch = (channel || 1) - 1;

  try {
    switch (type) {
      case 'note_on':
        port.noteOn(ch, data.note, data.velocity || 64);
        break;

      case 'note_off':
        port.noteOff(ch, data.note);
        break;

      case 'cc':
        port.control(ch, data.controller, data.value);
        break;

      case 'program_change':
        port.program(ch, data.program);
        break;

      default:
        throw new Error(`Unknown MIDI message type: ${type}`);
    }

    console.log(`Sent ${type} to ${deviceId}:`, data);
    return { success: true, message: `Sent ${type}` };
  } catch (error) {
    console.error(`Failed to send MIDI message:`, error.message);
    throw error;
  }
}

/**
 * Parse JSON body from request
 */
function parseBody(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', () => {
      try {
        resolve(body ? JSON.parse(body) : {});
      } catch (error) {
        reject(error);
      }
    });
    req.on('error', reject);
  });
}

/**
 * Send JSON response
 */
function sendJSON(res, data, statusCode = 200) {
  res.writeHead(statusCode, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(data));
}

/**
 * HTTP request handler
 */
const server = http.createServer(async (req, res) => {
  const parsedUrl = url.parse(req.url, true);
  const pathname = parsedUrl.pathname;
  const method = req.method;

  // CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (method === 'OPTIONS') {
    res.writeHead(200);
    res.end();
    return;
  }

  try {
    // Health check
    if (pathname === '/health' && method === 'GET') {
      sendJSON(res, { status: 'ok', service: 'midi-bridge' });
      return;
    }

    // Get devices
    if (pathname === '/devices' && method === 'GET') {
      const type = parsedUrl.query.type || 'output';
      const devices = await getDevices(type);
      sendJSON(res, { devices });
      return;
    }

    // Send MIDI message
    if (pathname === '/send' && method === 'POST') {
      const body = await parseBody(req);
      const result = await sendMessage(body.device_id, {
        type: body.type,
        channel: body.channel,
        data: body.data,
      });
      sendJSON(res, result);
      return;
    }

    // 404 Not Found
    sendJSON(res, { error: 'Not Found' }, 404);
  } catch (error) {
    console.error('Request error:', error.message);
    sendJSON(res, { error: error.message }, 500);
  }
});

// Start server
server.listen(PORT, HOST, () => {
  console.log(`MIDI Bridge listening on http://${HOST}:${PORT}`);
  console.log('Endpoints:');
  console.log('  GET  /health - Health check');
  console.log('  GET  /devices?type=output - List MIDI devices');
  console.log('  POST /send - Send MIDI message');
});

// Cleanup on exit
process.on('SIGINT', () => {
  console.log('\nClosing MIDI ports...');
  for (const port of openPorts.values()) {
    try {
      port.close();
    } catch (error) {
      // Ignore errors during cleanup
    }
  }
  process.exit(0);
});
