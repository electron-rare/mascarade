import { Hono } from "hono";
import { CoreApiError, coreClient } from "../client/core.js";

const comfyui = new Hono();

function handleCoreError(error: unknown) {
  if (error instanceof CoreApiError) {
    const status = error.status >= 400 && error.status < 500 ? (400 as const) : (502 as const);
    return { status, body: { error: error.message, core_status: error.status } };
  }
  return { status: 502 as const, body: { error: "Core service unreachable" } };
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
    const result = await coreClient.comfyuiModels(c.req.param("modelType"));
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
    const result = await coreClient.comfyuiHistory(c.req.param("promptId"));
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

export { comfyui };
