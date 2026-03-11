import { Hono } from "hono";
import { coreClient } from "../client/core.js";
import { handleCoreError } from "../middleware/error.js";

const p2p = new Hono();

/** Full mesh topology: all peers with capabilities, roles, status. */
p2p.get("/topology", async (c) => {
  try {
    const result = await coreClient.clusterPeers();
    // Enrich with P2P-specific fields
    return c.json({
      node: result.node,
      peers: result.peers,
      mesh: {
        total_peers: result.peers.length,
        online: result.peers.filter((p) => p.ok).length,
        offline: result.peers.filter((p) => !p.ok).length,
      },
    });
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Capabilities across all peers. */
p2p.get("/capabilities", async (c) => {
  try {
    const result = await coreClient.clusterPeers();
    const capMap: Record<string, string[]> = {};
    for (const peer of result.peers) {
      const caps = peer.providers || [];
      for (const cap of caps) {
        if (!capMap[cap]) capMap[cap] = [];
        capMap[cap].push(peer.peer_id);
      }
    }
    return c.json({ capabilities: capMap });
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Distribute a task to a capable peer. */
p2p.post("/task", async (c) => {
  try {
    const body = await c.req.json();
    const result = await coreClient.clusterForwardSend({
      ...body,
      messages: body.messages || [{ role: "user", content: body.prompt || "ping" }],
    });
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

export { p2p };
