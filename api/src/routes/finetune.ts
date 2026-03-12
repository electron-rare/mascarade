import { Hono } from "hono";
import { coreClient } from "../client/core.js";
import { handleCoreError } from "../middleware/error.js";

const finetune = new Hono();
const FALLBACK_STACK = {
  stack: ["Unsloth", "SimPO", "GRPO", "Qwen2.5-Coder"],
  recommended: "Unsloth + SimPO + GRPO + Qwen2.5-Coder",
};
type FinetunePipelinePayload = {
  task: string;
  domain?: string;
  max_model_size_gb?: number;
};

function sanitizeLogName(raw: string): string | null {
  let decoded: string;
  try {
    decoded = decodeURIComponent(raw).trim();
  } catch {
    return null;
  }

  if (!decoded || decoded.length === 0 || decoded.length > 256) {
    return null;
  }

  if (decoded.includes("..") || decoded.includes("/") || decoded.includes("\\")) {
    return null;
  }

  return decoded;
}

function sanitizePipelinePayload(raw: unknown): FinetunePipelinePayload | null {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    return null;
  }

  const payload = raw as Record<string, unknown>;
  const task = typeof payload.task === "string" ? payload.task.trim() : "";
  if (!task) {
    return null;
  }

  const domain = typeof payload.domain === "string" && payload.domain.trim().length > 0
    ? payload.domain.trim()
    : undefined;

  const maxModel = payload.max_model_size_gb;
  const max_model_size_gb = typeof maxModel === "number" && Number.isFinite(maxModel)
    ? maxModel
    : typeof maxModel === "string"
      ? (/^\d+(\.\d+)?$/.test(maxModel.trim()) ? Number.parseFloat(maxModel.trim()) : Number.NaN)
      : undefined;

  if (max_model_size_gb !== undefined && (!Number.isFinite(max_model_size_gb) || max_model_size_gb <= 0)) {
    return null;
  }

  return {
    task,
    ...(domain ? { domain } : {}),
    ...(max_model_size_gb !== undefined ? { max_model_size_gb } : {}),
  };
}

/** Lancer un pipeline finetune via le core */
finetune.post("/pipeline", async (c) => {
  try {
    const rawBody = await c.req.json().catch(() => null);
    if (rawBody === null) {
      return c.json({ error: "Invalid JSON payload" }, 400);
    }

    const body = sanitizePipelinePayload(rawBody);
    if (!body) {
      return c.json({ error: "Invalid payload. Required: task, optional: domain, max_model_size_gb" }, 400);
    }
    const result = await coreClient.finetunePipeline(body);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Stack finetune recommandee */
finetune.get("/stack", async (c) => {
  try {
    const stack = await coreClient.finetuneStack();
    return c.json(stack);
  } catch {
    return c.json(FALLBACK_STACK);
  }
});

/** Supprimer un log finetune */
finetune.delete("/logs/:name", async (c) => {
  try {
    const rawName = c.req.param("name");
    const name = sanitizeLogName(rawName);
    if (!name) {
      return c.json({ error: "Missing log name" }, 400);
    }
    const result = await coreClient.deleteFinetuneLog(name);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

export { finetune };
