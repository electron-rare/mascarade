import { Hono } from "hono";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { homedir } from "node:os";
import path from "node:path";

const finetune = new Hono();

const REGISTRY_PATH = path.join(homedir(), ".mascarade", "finetune", "registry.json");
const LOGS_DIR = path.join(homedir(), ".mascarade", "finetune", "logs");

function readRegistry() {
  if (!existsSync(REGISTRY_PATH)) return { models: {}, datasets: {}, runs: {} };
  try {
    return JSON.parse(readFileSync(REGISTRY_PATH, "utf-8"));
  } catch {
    return { models: {}, datasets: {}, runs: {} };
  }
}

/** Get the local fine-tuning registry. */
finetune.get("/registry", (c) => {
  const data = readRegistry();
  return c.json(data);
});

/** Get fine-tuning capabilities map. */
finetune.get("/capabilities", (c) => {
  return c.json({
    capabilities: {
      "ft-research": { description: "Search models and papers (HF Hub)", nodes: ["GrosMac"] },
      "ft-dataset": { description: "Search and curate datasets", nodes: ["GrosMac"] },
      "ft-archive": { description: "Version on HuggingFace Hub", nodes: ["GrosMac"] },
      "ft-analysis": { description: "Benchmarks and metrics", nodes: ["KXKM-AI"] },
      "ft-teacher": { description: "Generate teacher data (LLM Router)", nodes: ["GrosMac"] },
      "ft-student": { description: "LoRA/QLoRA fine-tuning (Unsloth/trl)", nodes: ["KXKM-AI"] },
      "ft-reinforcement": { description: "SimPO/GRPO/DPO alignment", nodes: ["KXKM-AI"] },
      "ft-validation": { description: "E2E tests + red-teaming", nodes: ["CILS"] },
    },
    agents: [
      { name: "Chercheur", capability: "ft-research", status: "ready" },
      { name: "Documentaliste", capability: "ft-dataset", status: "ready" },
      { name: "Doctor", capability: "ft-teacher", status: "ready" },
      { name: "Archiviste", capability: "ft-archive", status: "ready" },
      { name: "Student", capability: "ft-student", status: "ready", backend: "unsloth" },
      { name: "Analyste", capability: "ft-analysis", status: "ready" },
      { name: "Renforceur", capability: "ft-reinforcement", status: "ready", methods: ["simpo", "grpo", "dpo"] },
      { name: "Validateur", capability: "ft-validation", status: "ready" },
    ],
    stack: {
      framework: "Unsloth 2026.3.4",
      alignment: ["SimPO", "GRPO", "DPO"],
      export: "GGUF Dynamic 2.0",
      gpu: "RTX 4090 (KXKM-AI)",
      recommended_model: "Qwen2.5-Coder-1.5B-Instruct",
      recommended_dataset: "Magicoder-OSS-Instruct-75K",
    },
  });
});

/** Get pipeline status (runs in progress, completed, etc.). */
finetune.get("/runs", (c) => {
  const data = readRegistry();
  const runs = Object.values(data.runs || {});
  return c.json({ runs });
});

/** Get pipeline logs. */
finetune.get("/logs", (c) => {
  if (!existsSync(LOGS_DIR)) return c.json({ logs: [] });
  try {
    const files = readdirSync(LOGS_DIR)
      .filter((f: string) => f.endsWith(".log"))
      .sort()
      .reverse()
      .slice(0, 20);
    const logs = files.map((f: string) => {
      const content = readFileSync(path.join(LOGS_DIR, f), "utf-8");
      const lines = content.split("\n").filter(Boolean);
      return {
        name: f,
        lines: lines.length,
        preview: lines.slice(-5).join("\n"),
        size_kb: Math.round(Buffer.byteLength(content) / 1024),
      };
    });
    return c.json({ logs });
  } catch {
    return c.json({ logs: [] });
  }
});

export { finetune };
