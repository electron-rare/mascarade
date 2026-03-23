#!/usr/bin/env node
/**
 * MCP HTTP Bridge — exposes an MCP stdio server over HTTP.
 *
 * Env:
 *   MCP_TRANSPORT   "stdio" (default) | "http"
 *   MCP_HTTP_PORT   Port to listen on (default: 8300)
 *   MCP_CMD         Command to spawn the MCP server (default: "node dist/index.js")
 *
 * When MCP_TRANSPORT=http, starts an HTTP server that:
 *   POST /mcp   → sends JSON-RPC request to MCP stdin, returns stdout response
 *   GET  /health → basic health check
 *   GET  /tools  → calls tools/list via MCP and returns the result
 *
 * When MCP_TRANSPORT=stdio, just exec the MCP command directly (passthrough).
 */

const http = require("http");
const { spawn } = require("child_process");

const TRANSPORT = (process.env.MCP_TRANSPORT || "stdio").toLowerCase();
const PORT = parseInt(process.env.MCP_HTTP_PORT || "8300", 10);
const MCP_CMD = process.env.MCP_CMD || "node dist/index.js";

if (TRANSPORT === "stdio") {
  // Passthrough — just exec the MCP server
  const [cmd, ...args] = MCP_CMD.split(" ");
  const child = spawn(cmd, args, { stdio: "inherit", cwd: process.cwd() });
  child.on("exit", (code) => process.exit(code || 0));
  process.on("SIGTERM", () => child.kill("SIGTERM"));
  process.on("SIGINT", () => child.kill("SIGINT"));
} else {
  // HTTP bridge
  let mcpProcess = null;
  let requestId = 1;
  let pending = new Map();
  let buffer = "";

  function startMcp() {
    const [cmd, ...args] = MCP_CMD.split(" ");
    mcpProcess = spawn(cmd, args, {
      stdio: ["pipe", "pipe", "inherit"],
      cwd: process.cwd(),
    });

    mcpProcess.stdout.on("data", (chunk) => {
      buffer += chunk.toString();
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (!line.trim()) continue;
        try {
          const msg = JSON.parse(line);
          const id = msg.id;
          if (id != null && pending.has(id)) {
            pending.get(id)(msg);
            pending.delete(id);
          }
        } catch {
          // ignore non-JSON lines
        }
      }
    });

    mcpProcess.on("exit", (code) => {
      console.error(`[mcp-bridge] MCP process exited with code ${code}`);
      // Reject all pending requests
      for (const [, reject] of pending) {
        reject({ error: { code: -1, message: "MCP process exited" } });
      }
      pending.clear();
      // Restart after delay
      setTimeout(startMcp, 2000);
    });
  }

  function sendRequest(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = requestId++;
      const msg = JSON.stringify({ jsonrpc: "2.0", id, method, params });
      pending.set(id, resolve);
      setTimeout(() => {
        if (pending.has(id)) {
          pending.delete(id);
          reject(new Error("MCP request timeout"));
        }
      }, 30000);
      mcpProcess.stdin.write(msg + "\n");
    });
  }

  startMcp();

  const server = http.createServer(async (req, res) => {
    const url = new URL(req.url, `http://127.0.0.1:${PORT}`);

    if (url.pathname === "/health") {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ ok: true, transport: "http", pid: mcpProcess?.pid }));
      return;
    }

    if (url.pathname === "/tools" && req.method === "GET") {
      try {
        const result = await sendRequest("tools/list");
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify(result));
      } catch (err) {
        res.writeHead(502, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: err.message }));
      }
      return;
    }

    if (url.pathname === "/mcp" && req.method === "POST") {
      let body = "";
      req.on("data", (chunk) => (body += chunk));
      req.on("end", async () => {
        try {
          const rpc = JSON.parse(body);
          const result = await sendRequest(rpc.method, rpc.params || {});
          res.writeHead(200, { "Content-Type": "application/json" });
          res.end(JSON.stringify(result));
        } catch (err) {
          res.writeHead(502, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ error: err.message }));
        }
      });
      return;
    }

    res.writeHead(404, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: "Not found" }));
  });

  server.listen(PORT, "0.0.0.0", () => {
    console.log(`[mcp-bridge] MCP HTTP bridge listening on :${PORT}`);
  });

  process.on("SIGTERM", () => {
    mcpProcess?.kill("SIGTERM");
    server.close();
  });
}
