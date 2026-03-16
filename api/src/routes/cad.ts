import { Hono } from "hono";
import { coreClient } from "../client/core.js";
import { handleCoreError } from "../middleware/error.js";

const cad = new Hono();

cad.get("/freecad/runtime", async (c) => {
  try {
    const runId = c.req.query("run_id") || undefined;
    return c.json(await coreClient.freecadRuntimeInfo(runId));
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

cad.post("/freecad/documents", async (c) => {
  try {
    return c.json(await coreClient.freecadCreateDocument(await c.req.json()));
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

cad.post("/freecad/export", async (c) => {
  try {
    return c.json(await coreClient.freecadExportDocument(await c.req.json()));
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

cad.post("/freecad/script", async (c) => {
  try {
    return c.json(await coreClient.freecadRunScript(await c.req.json()));
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

cad.get("/openscad/runtime", async (c) => {
  try {
    const runId = c.req.query("run_id") || undefined;
    return c.json(await coreClient.openscadRuntimeInfo(runId));
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

cad.post("/openscad/validate", async (c) => {
  try {
    return c.json(await coreClient.openscadValidateModel(await c.req.json()));
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

cad.post("/openscad/render", async (c) => {
  try {
    return c.json(await coreClient.openscadRenderModel(await c.req.json()));
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

cad.post("/openscad/export", async (c) => {
  try {
    return c.json(await coreClient.openscadExportModel(await c.req.json()));
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

cad.post("/kicad/schematic", async (c) => {
  try {
    return c.json(await coreClient.kicadGenerateSchematic(await c.req.json()));
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

cad.post("/kicad/layout", async (c) => {
  try {
    return c.json(await coreClient.kicadOptimizeLayout(await c.req.json()));
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

cad.post("/kicad/footprint", async (c) => {
  try {
    return c.json(await coreClient.kicadCreateFootprint(await c.req.json()));
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

cad.post("/kicad/drc", async (c) => {
  try {
    return c.json(await coreClient.kicadCheckDRC(await c.req.json()));
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

cad.post("/kicad/manufacturing", async (c) => {
  try {
    return c.json(await coreClient.kicadExportManufacturing(await c.req.json()));
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

export { cad };
