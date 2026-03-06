import { Hono } from "hono";
import { coreClient } from "../client/core.js";
import { handleCoreError } from "../middleware/error.js";

const comfyui = new Hono();

const SAFE_PATH_RE = /^[a-zA-Z0-9._-]+$/;

function validatePathParam(value: string | undefined, name: string): boolean {
  if (!value) return true;
  return SAFE_PATH_RE.test(value) && !value.includes("..");
}

/** Statut systeme ComfyUI */
comfyui.get("/status", async (c) => {
  try {
    const result = await coreClient.comfyuiStatus();
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Statut de la queue */
comfyui.get("/queue", async (c) => {
  try {
    const result = await coreClient.comfyuiQueue();
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Lister les modeles */
comfyui.get("/models/:modelType", async (c) => {
  try {
    const modelType = c.req.param("modelType");
    if (!validatePathParam(modelType, "modelType")) {
      return c.json({ error: "Invalid model type parameter" }, 400);
    }
    const result = await coreClient.comfyuiModels(modelType);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Generer une image (txt2img) */
comfyui.post("/generate", async (c) => {
  try {
    const body = await c.req.json();
    const result = await coreClient.comfyuiGenerate(body);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Soumettre un workflow brut */
comfyui.post("/workflow", async (c) => {
  try {
    const { workflow } = await c.req.json();
    const result = await coreClient.comfyuiQueueWorkflow(workflow);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Historique d'un prompt */
comfyui.get("/history/:promptId", async (c) => {
  try {
    const promptId = c.req.param("promptId");
    if (!validatePathParam(promptId, "promptId")) {
      return c.json({ error: "Invalid prompt ID parameter" }, 400);
    }
    const result = await coreClient.comfyuiHistory(promptId);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Interrompre l'execution */
comfyui.post("/interrupt", async (c) => {
  try {
    const result = await coreClient.comfyuiInterrupt();
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Recuperer une image generee */
comfyui.get("/image", async (c) => {
  try {
    const filename = c.req.query("filename");
    if (!filename) {
      return c.json({ error: "filename query parameter is required" }, 400);
    }
    const subfolder = c.req.query("subfolder");
    const type = c.req.query("type");

    if (!validatePathParam(filename, "filename") ||
        !validatePathParam(subfolder, "subfolder") ||
        !validatePathParam(type, "type")) {
      return c.json({ error: "Invalid path parameter" }, 400);
    }

    const res = await coreClient.comfyuiImage(filename, subfolder || undefined, type || undefined);
    if (!res.ok) {
      return c.json({ error: `Core returned ${res.status}` }, 502);
    }
    const data = await res.arrayBuffer();
    return new Response(data, {
      headers: { "Content-Type": res.headers.get("Content-Type") || "image/png" },
    });
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

export { comfyui };
