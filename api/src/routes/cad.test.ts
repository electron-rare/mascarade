import { Hono } from "hono";
import { describe, expect, it, vi } from "vitest";
import { coreClient } from "../client/core.js";
import { cad } from "./cad.js";

function makeApp() {
  const app = new Hono();
  app.route("/api/cad", cad);
  return app;
}

describe("cad routes", () => {
  it("proxies FreeCAD create document requests to the core MCP facade", async () => {
    vi.spyOn(coreClient, "freecadCreateDocument").mockResolvedValue({
      ok: true,
      document_path: ".cad-home/freecad/test.FCStd",
      document_name: "TraceDoc",
      run_id: "run-freecad-001",
    });

    const res = await makeApp().request("/api/cad/freecad/documents", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        output_path: ".cad-home/freecad/test.FCStd",
        name: "TraceDoc",
      }),
    });

    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({
      ok: true,
      document_path: ".cad-home/freecad/test.FCStd",
      document_name: "TraceDoc",
      run_id: "run-freecad-001",
    });
    expect(coreClient.freecadCreateDocument).toHaveBeenCalledWith({
      output_path: ".cad-home/freecad/test.FCStd",
      name: "TraceDoc",
    });
  });

  it("proxies OpenSCAD render requests to the core MCP facade", async () => {
    vi.spyOn(coreClient, "openscadRenderModel").mockResolvedValue({
      ok: true,
      output_path: ".cad-home/openscad/test.stl",
      size_bytes: 256,
      run_id: "run-openscad-001",
    });

    const res = await makeApp().request("/api/cad/openscad/render", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source: "cube([10, 8, 6]);",
        output_path: ".cad-home/openscad/test.stl",
      }),
    });

    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({
      ok: true,
      output_path: ".cad-home/openscad/test.stl",
      size_bytes: 256,
      run_id: "run-openscad-001",
    });
    expect(coreClient.openscadRenderModel).toHaveBeenCalledWith({
      source: "cube([10, 8, 6]);",
      output_path: ".cad-home/openscad/test.stl",
    });
  });
});
