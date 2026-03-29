import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// Multi-machine Ollama routing
export const OLLAMA_NODES: Record<string, string> = {
  tower: process.env.OLLAMA_TOWER || "http://mascarade-ollama:11434",
  kxkm: process.env.OLLAMA_KXKM || "http://mascarade-ollama:11434",
};
export const OLLAMA_DEFAULT = process.env.OLLAMA_URL || OLLAMA_NODES.tower;
export const MODEL_ROUTES: Record<string, string> = {
  "albert": OLLAMA_NODES.kxkm, "mistral:7b": OLLAMA_NODES.kxkm,
  "devstral": OLLAMA_NODES.kxkm, "qwen3:8b": OLLAMA_NODES.kxkm,
  "qwen3:4b": OLLAMA_NODES.tower, "bge-m3": OLLAMA_NODES.kxkm,
};
export function ollamaFor(model: string): string { return MODEL_ROUTES[model] || OLLAMA_DEFAULT; }

export const QDRANT_URL = process.env.QDRANT_URL || "http://mascarade-qdrant:6333";
export const SEARXNG_URL = process.env.SEARXNG_URL || "http://mascarade-searxng:8080";
export const RAG_COLLECTION = process.env.RAG_COLLECTION || "mascarade-rag";
export const EMBED_MODEL = process.env.EMBED_MODEL || "bge-m3";
export const TIMEOUT = 90000;

// Load agents
export let AGENTS: Array<Record<string, unknown>> = [];
try { AGENTS = JSON.parse(readFileSync(resolve(process.cwd(), "../core/data/agents.json"), "utf-8")); } catch {}
try { if (!AGENTS.length) AGENTS = JSON.parse(readFileSync("/app/core/data/agents.json", "utf-8")); } catch {}
