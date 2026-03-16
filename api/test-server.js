/**
 * Simple test server for Node Engine component verification
 *
 * This serves the standalone HTML file to verify the NodeEditor component works.
 */

import { createServer } from 'node:http';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const PORT = 3001;

const server = createServer((req, res) => {
  console.log(`${req.method} ${req.url}`);

  if (req.url === '/' || req.url === '/node-engine') {
    res.writeHead(200, { 'Content-Type': 'text/html' });
    res.end(readFileSync(join(process.cwd(), 'public/node-engine-standalone.html')));
  } else if (req.url === '/node-engine-bundle.js') {
    res.writeHead(200, { 'Content-Type': 'application/javascript' });
    res.end(readFileSync(join(process.cwd(), 'public/node-engine-bundle.js')));
  } else if (req.url === '/node-engine-bundle.js.map') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(readFileSync(join(process.cwd(), 'public/node-engine-bundle.js.map')));
  } else {
    res.writeHead(404);
    res.end('Not found');
  }
});

server.listen(PORT, () => {
  console.log(`✓ Test server running at http://localhost:${PORT}/node-engine`);
  console.log('  Press Ctrl+C to stop');
});
