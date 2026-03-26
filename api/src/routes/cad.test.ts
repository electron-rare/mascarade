import { Hono } from "hono";
import { afterEach, describe, expect, it, vi } from "vitest";
import { coreClient } from "../client/core.js";
import { cad } from "./cad.js";

function makeApp() {
  const app = new Hono();
  app.route("/v1/api/cad", cad);
  return app;
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("cad routes", () => {
  describe("FreeCAD", () => {
    it("proxies create document requests to the core MCP facade", async () => {
      vi.spyOn(coreClient, "freecadCreateDocument").mockResolvedValue({
        ok: true,
        document_path: ".cad-home/freecad/test.FCStd",
        document_name: "TraceDoc",
        run_id: "run-freecad-001",
      });

      const res = await makeApp().request("/v1/api/cad/freecad/documents", {
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

    it("proxies runtime info requests", async () => {
      vi.spyOn(coreClient, "freecadRuntimeInfo").mockResolvedValue({
        ok: true,
        version: "0.21",
        status: "running",
      } as any);

      const res = await makeApp().request("/v1/api/cad/freecad/runtime?run_id=run-001");

      expect(res.status).toBe(200);
      const body = await res.json();
      expect(body.status).toBe("running");
      expect(coreClient.freecadRuntimeInfo).toHaveBeenCalledWith("run-001");
    });

    it("proxies export document requests", async () => {
      vi.spyOn(coreClient, "freecadExportDocument").mockResolvedValue({
        ok: true,
        output_path: "export.step",
      } as any);

      const res = await makeApp().request("/v1/api/cad/freecad/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ document_path: "test.FCStd", format: "step" }),
      });

      expect(res.status).toBe(200);
      expect(coreClient.freecadExportDocument).toHaveBeenCalledWith({
        document_path: "test.FCStd",
        format: "step",
      });
    });

    it("proxies script execution requests", async () => {
      vi.spyOn(coreClient, "freecadRunScript").mockResolvedValue({
        ok: true,
        output: "Script completed",
      } as any);

      const res = await makeApp().request("/v1/api/cad/freecad/script", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ script: "FreeCAD.newDocument()" }),
      });

      expect(res.status).toBe(200);
      expect(coreClient.freecadRunScript).toHaveBeenCalledWith({
        script: "FreeCAD.newDocument()",
      });
    });

    it("returns 502 when core is unreachable for create document", async () => {
      vi.spyOn(coreClient, "freecadCreateDocument").mockRejectedValue(new Error("ECONNREFUSED"));

      const res = await makeApp().request("/v1/api/cad/freecad/documents", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ output_path: "test.FCStd", name: "Doc" }),
      });

      expect(res.status).toBe(502);
      const body = await res.json();
      expect(body.error).toBe("Core service unreachable");
    });
  });

  describe("OpenSCAD", () => {
    it("proxies render requests to the core MCP facade", async () => {
      vi.spyOn(coreClient, "openscadRenderModel").mockResolvedValue({
        ok: true,
        output_path: ".cad-home/openscad/test.stl",
        size_bytes: 256,
        run_id: "run-openscad-001",
      });

      const res = await makeApp().request("/v1/api/cad/openscad/render", {
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
    });

    it("proxies runtime info requests", async () => {
      vi.spyOn(coreClient, "openscadRuntimeInfo").mockResolvedValue({
        ok: true,
        version: "2024.01",
      } as any);

      const res = await makeApp().request("/v1/api/cad/openscad/runtime");

      expect(res.status).toBe(200);
      expect(coreClient.openscadRuntimeInfo).toHaveBeenCalledWith(undefined);
    });

    it("proxies validate requests", async () => {
      vi.spyOn(coreClient, "openscadValidateModel").mockResolvedValue({
        ok: true,
        valid: true,
      } as any);

      const res = await makeApp().request("/v1/api/cad/openscad/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source: "sphere(5);" }),
      });

      expect(res.status).toBe(200);
      const body = await res.json();
      expect(body.valid).toBe(true);
    });

    it("proxies export requests", async () => {
      vi.spyOn(coreClient, "openscadExportModel").mockResolvedValue({
        ok: true,
        output_path: "model.3mf",
      } as any);

      const res = await makeApp().request("/v1/api/cad/openscad/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source: "cube(10);", format: "3mf" }),
      });

      expect(res.status).toBe(200);
      expect(coreClient.openscadExportModel).toHaveBeenCalledWith({
        source: "cube(10);",
        format: "3mf",
      });
    });
  });

  describe("KiCad", () => {
    it("proxies schematic generation", async () => {
      vi.spyOn(coreClient, "kicadGenerateSchematic").mockResolvedValue({
        ok: true,
        schematic_path: "circuit.kicad_sch",
      } as any);

      const res = await makeApp().request("/v1/api/cad/kicad/schematic", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ components: ["R1", "C1"], net: "VCC" }),
      });

      expect(res.status).toBe(200);
      const body = await res.json();
      expect(body.ok).toBe(true);
    });

    it("proxies layout optimization", async () => {
      vi.spyOn(coreClient, "kicadOptimizeLayout").mockResolvedValue({
        ok: true,
        optimized: true,
      } as any);

      const res = await makeApp().request("/v1/api/cad/kicad/layout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ board_path: "board.kicad_pcb" }),
      });

      expect(res.status).toBe(200);
    });

    it("proxies DRC check", async () => {
      vi.spyOn(coreClient, "kicadCheckDRC").mockResolvedValue({
        ok: true,
        violations: 0,
      } as any);

      const res = await makeApp().request("/v1/api/cad/kicad/drc", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ board_path: "board.kicad_pcb" }),
      });

      expect(res.status).toBe(200);
      const body = await res.json();
      expect(body.violations).toBe(0);
    });

    it("proxies manufacturing export", async () => {
      vi.spyOn(coreClient, "kicadExportManufacturing").mockResolvedValue({
        ok: true,
        gerber_path: "gerbers.zip",
      } as any);

      const res = await makeApp().request("/v1/api/cad/kicad/manufacturing", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ board_path: "board.kicad_pcb" }),
      });

      expect(res.status).toBe(200);
      expect(coreClient.kicadExportManufacturing).toHaveBeenCalled();
    });

    it("returns 502 when core is unreachable for KiCad DRC", async () => {
      vi.spyOn(coreClient, "kicadCheckDRC").mockRejectedValue(new Error("ECONNREFUSED"));

      const res = await makeApp().request("/v1/api/cad/kicad/drc", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ board_path: "test.kicad_pcb" }),
      });

      expect(res.status).toBe(502);
    });
  });

  describe("Mesh operations", () => {
    it("proxies mesh import", async () => {
      vi.spyOn(coreClient, "meshImport").mockResolvedValue({
        ok: true,
        vertices: 1024,
        faces: 2048,
      } as any);

      const res = await makeApp().request("/v1/api/cad/mesh/import", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: "model.stl" }),
      });

      expect(res.status).toBe(200);
      const body = await res.json();
      expect(body.vertices).toBe(1024);
    });

    it("proxies mesh simplify", async () => {
      vi.spyOn(coreClient, "meshSimplify").mockResolvedValue({
        ok: true,
        reduced_faces: 512,
      } as any);

      const res = await makeApp().request("/v1/api/cad/mesh/simplify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: "model.stl", target_ratio: 0.5 }),
      });

      expect(res.status).toBe(200);
      const body = await res.json();
      expect(body.reduced_faces).toBe(512);
    });

    it("proxies mesh boolean operations", async () => {
      vi.spyOn(coreClient, "meshBoolean").mockResolvedValue({
        ok: true,
        operation: "union",
      } as any);

      const res = await makeApp().request("/v1/api/cad/mesh/boolean", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ a: "a.stl", b: "b.stl", operation: "union" }),
      });

      expect(res.status).toBe(200);
    });
  });

  describe("Toolpath", () => {
    it("proxies toolpath generation", async () => {
      vi.spyOn(coreClient, "toolpathGenerate").mockResolvedValue({
        ok: true,
        gcode_path: "output.gcode",
      } as any);

      const res = await makeApp().request("/v1/api/cad/toolpath/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model_path: "part.stl", tool_diameter: 3 }),
      });

      expect(res.status).toBe(200);
      const body = await res.json();
      expect(body.gcode_path).toBe("output.gcode");
    });

    it("proxies toolpath optimization", async () => {
      vi.spyOn(coreClient, "toolpathOptimize").mockResolvedValue({
        ok: true,
        time_saved_pct: 15,
      } as any);

      const res = await makeApp().request("/v1/api/cad/toolpath/optimize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ gcode_path: "output.gcode" }),
      });

      expect(res.status).toBe(200);
      const body = await res.json();
      expect(body.time_saved_pct).toBe(15);
    });
  });
});
