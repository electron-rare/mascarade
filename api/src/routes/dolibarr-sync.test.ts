import { Hono } from "hono";
import { describe, expect, it } from "vitest";
import { dolibarrSync } from "./dolibarr-sync.js";

function makeApp() {
  const app = new Hono();
  app.route("/dolibarr/sync", dolibarrSync);
  return app;
}

describe("dolibarr sync routes", () => {
  it("returns a customer folder mapping", async () => {
    const res = await makeApp().request("/dolibarr/sync/customer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ entity_id: 42, client_ref: "CLI-0042" }),
    });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.entity_type).toBe("customer");
    expect(body.nextcloud_path).toBe("/clients/CLI-0042/");
  });

  it("returns an invoice mapping with drive and open urls", async () => {
    const res = await makeApp().request("/dolibarr/sync/invoice", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ entity_id: 123, client_ref: "CLI-0042", invoice_ref: "FA-2026-0015" }),
    });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.object).toBe("invoice");
    expect(body.nextcloud_path).toContain("/clients/CLI-0042/factures/FA-2026-0015");
    expect(body.drive_url).toContain("drive.saillant.cc");
    expect(body.open_url).toBeTruthy();
  });

  it("returns a proposal mapping that prefers editing", async () => {
    const res = await makeApp().request("/dolibarr/sync/proposal", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ entity_id: 77, client_ref: "CLI-0042", proposal_ref: "PR-2026-0042" }),
    });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.object).toBe("proposal");
    expect(body.mode).toBe("edit");
    expect(body.target).toBe("docs");
  });
});
