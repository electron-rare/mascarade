#!/usr/bin/env node

import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..", "..");
const coreDir = path.join(repoRoot, "core");

function joinPathList(parts) {
  return parts.filter(Boolean).join(path.delimiter);
}

function pickPythonCommand() {
  const candidates = [
    process.env.MASCARADE_MCP_PYTHON,
    path.join(coreDir, ".venv", "bin", "python"),
    path.join(repoRoot, ".venv", "bin", "python"),
    "python3",
    "python",
  ].filter(Boolean);

  for (const candidate of candidates) {
    if (candidate.includes(path.sep)) {
      if (existsSync(candidate)) {
        return candidate;
      }
      continue;
    }
    return candidate;
  }

  return "python3";
}

const python = pickPythonCommand();
const args = ["-m", "mascarade.mcp.server"];
const env = {
  ...process.env,
  PYTHONPATH: joinPathList([coreDir, process.env.PYTHONPATH]),
};

if (process.env.MASCARADE_MCP_PRINT_ONLY === "1") {
  process.stdout.write(
    `${JSON.stringify({ python, args, cwd: coreDir, env: { PYTHONPATH: env.PYTHONPATH } }, null, 2)}\n`,
  );
  process.exit(0);
}

const child = spawn(python, args, {
  cwd: coreDir,
  env,
  stdio: "inherit",
});

const forwardSignal = (signal) => {
  if (!child.killed) {
    child.kill(signal);
  }
};

process.on("SIGINT", () => forwardSignal("SIGINT"));
process.on("SIGTERM", () => forwardSignal("SIGTERM"));

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 0);
});

child.on("error", (error) => {
  process.stderr.write(`[mascarade-mcp] failed to launch ${python}: ${String(error)}\n`);
  process.exit(1);
});
