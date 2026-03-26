import { Hono } from "hono";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("node:fs", () => ({
  existsSync: vi.fn(() => true),
}));

vi.mock("node:fs/promises", () => ({
  readFile: vi.fn(),
}));

import { readFile } from "node:fs/promises";
import { p2p } from "./p2p.js";

const ORIGINAL_FETCH = global.fetch;

function makeApp() {
  const app = new Hono();
  app.route("/api/p2p", p2p);
  return app;
}

const SAMPLE_YAML = `
bootstrap:
  host: 192.168.0.119
  port: 8100
  role: control-plane
  name: Photon
nodes:
  gpu-worker:
    host: 192.168.0.120
    port: 8100
    role: gpu-primary
    name: KXKM
    capabilities:
      - ft-train
      - ft-eval
`;

afterEach(() => {
  vi.restoreAllMocks();
  if (ORIGINAL_FETCH === undefined) {
    // @ts-expect-error test cleanup
    delete global.fetch;
  } else {
    global.fetch = ORIGINAL_FETCH;
  }
});

describe("p2p routes", () => {
  it("GET /nodes lists parsed nodes from YAML", async () => {
    vi.mocked(readFile).mockResolvedValue(SAMPLE_YAML as any);

    const res = await makeApp().request("/api/p2p/nodes");

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(Array.isArray(body)).toBe(true);
    expect(body.length).toBeGreaterThanOrEqual(2);
    expect(body[0].node_id).toBe("bootstrap");
  });

  it("GET /health probes each node and returns health summary", async () => {
    vi.mocked(readFile).mockResolvedValue(SAMPLE_YAML as any);
    const fetchMock = vi.fn().mockRejectedValue(new Error("ECONNREFUSED"));
    vi.stubGlobal("fetch", fetchMock);

    const res = await makeApp().request("/api/p2p/health");

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.total_nodes).toBeGreaterThanOrEqual(2);
    expect(typeof body.healthy_nodes).toBe("number");
    expect(typeof body.unhealthy_nodes).toBe("number");
  });

  it("GET /nodes returns 404 when YAML file is missing", async () => {
    const err = new Error("ENOENT") as NodeJS.ErrnoException;
    err.code = "ENOENT";
    vi.mocked(readFile).mockRejectedValue(err);

    const res = await makeApp().request("/api/p2p/nodes");

    expect(res.status).toBe(404);
    const body = await res.json();
    expect(body.error).toContain("not found");
  });

  it("GET /topology returns mesh topology", async () => {
    vi.mocked(readFile).mockResolvedValue(SAMPLE_YAML as any);
    const fetchMock = vi.fn().mockRejectedValue(new Error("ECONNREFUSED"));
    vi.stubGlobal("fetch", fetchMock);

    const res = await makeApp().request("/api/p2p/topology");

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.node).toBeDefined();
    expect(body.peers).toBeDefined();
    expect(body.mesh).toBeDefined();
  });

  it("GET /capabilities returns aggregated capabilities", async () => {
    vi.mocked(readFile).mockResolvedValue(SAMPLE_YAML as any);

    const res = await makeApp().request("/api/p2p/capabilities");

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.capabilities).toBeDefined();
  });
});
