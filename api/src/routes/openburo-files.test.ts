import { Hono } from "hono";
import { describe, expect, it } from "vitest";
import { openburoFiles, resolveBusinessObjectFile, resolveOpenTarget } from "./openburo-files.js";

function makeApp() {
  const app = new Hono();
  app.route("/openburo/files", openburoFiles);
  return app;
}

describe("openburo file opening", () => {
  it("routes office-like files to the suite editor", () => {
    const result = resolveOpenTarget({
      url: "https://drive.saillant.cc/files/report.docx",
      filename: "report.docx",
      mime_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    });

    expect(result.target).toBe("docs");
    expect(result.mode).toBe("edit");
    expect(result.editor).toBe("docs");
    expect(result.reason).toBe("suite_editor_available");
    expect(result.open_url).toContain("docs.saillant.cc");
    expect(result.drive_url).toContain("drive.saillant.cc");
    expect(result.download_url).toBeNull();
  });

  it("falls back to drive for non-editable files", () => {
    const result = resolveOpenTarget({
      url: "https://drive.saillant.cc/files/archive.zip",
      filename: "archive.zip",
      mime_type: "application/zip",
    });

    expect(result.target).toBe("drive");
    expect(result.mode).toBe("browse");
    expect(result.editor).toBe("drive");
    expect(result.reason).toBe("fallback_file_manager");
    expect(result.open_url).toContain("drive.saillant.cc");
  });

  it("builds business-object metadata for invoices", () => {
    const result = resolveBusinessObjectFile({
      type: "invoice",
      id: "123",
      client_ref: "CLI-0042",
      invoice_ref: "FA-2026-0015.pdf",
      filename: "FA-2026-0015.pdf",
      mime_type: "application/pdf",
    });

    expect(result.object).toBe("invoice");
    expect(result.object_id).toBe("123");
    expect(result.nextcloud_path).toContain("/clients/CLI-0042/factures/FA-2026-0015.pdf");
    expect(result.target).toBe("drive");
    expect(result.editor).toBe("drive");
    expect(result.drive_url).toContain("drive.saillant.cc");
  });

  it("exposes GET /resolve-open", async () => {
    const res = await makeApp().request("/openburo/files/resolve-open?url=https%3A%2F%2Fdrive.saillant.cc%2Ffiles%2Fnotes.md&filename=notes.md");
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.target).toBe("docs");
    expect(body.editor).toBe("docs");
    expect(body.mode).toBe("edit");
    expect(body.open_url).toContain("docs.saillant.cc");
  });

  it("exposes GET /by-business-object", async () => {
    const res = await makeApp().request("/openburo/files/by-business-object?type=invoice&id=123&client_ref=CLI-0042&invoice_ref=FA-2026-0015.pdf&filename=FA-2026-0015.pdf");
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.object).toBe("invoice");
    expect(body.object_id).toBe("123");
    expect(body.nextcloud_path).toContain("/clients/CLI-0042/factures/FA-2026-0015.pdf");
  });

  it("supports the /files alias shape used by Dolibarr", async () => {
    const app = new Hono();
    app.route("/files", openburoFiles);

    const res = await app.request("/files/by-business-object?type=proposal&id=77&client_ref=CLI-0042&proposal_ref=PR-2026-0042&filename=PR-2026-0042.odt");
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.editor).toBe("docs");
    expect(body.mode).toBe("edit");
    expect(body.open_url).toContain("docs.saillant.cc");
  });
});
