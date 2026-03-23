#!/usr/bin/env python3
"""P2P bridge node — connects LAN mesh to Tailscale peers.

Runs on GrosMac which has visibility on both networks and hosts the
fine-tune research/archive capabilities that require local internet access.
"""

import asyncio
import json
import os
import signal
import sys

sys.path.insert(0, os.environ.get("PYTHONPATH", os.path.expanduser("~/mascarade/core")))

from mascarade.p2p.asyncio_node import MascaradeP2PNode
from mascarade.p2p.relay import P2PRelay

LISTEN_HOST = os.environ.get("P2P_LISTEN_HOST", "0.0.0.0")
LISTEN_PORT = int(os.environ.get("P2P_LISTEN_PORT", "4001"))
KEY_DIR = os.path.expanduser(os.environ.get("P2P_KEY_DIR", "~/.mascarade/p2p"))
BOOTSTRAP_ID = os.environ.get("P2P_BOOTSTRAP_ID", "QmTO5AYG6ZT3EU3UWVLNWU2FFFHWKUJR7S")
BOOTSTRAP_HOST = os.environ.get("P2P_BOOTSTRAP_HOST", "192.168.0.119")
BOOTSTRAP_PORT = int(os.environ.get("P2P_BOOTSTRAP_PORT", "4001"))
CAPABILITIES = os.environ.get(
    "P2P_CAPABILITIES",
    "p2p-relay,p2p-bridge,llm-inference,ft-research,ft-dataset,ft-teacher,ft-archive",
).split(",")
ROLE = os.environ.get("P2P_ROLE", "bridge")
LABEL = os.environ.get("P2P_LABEL", "GrosMac Bridge")
HTTP_BASE = os.environ.get("P2P_HTTP_BASE", "http://localhost:8100")


async def handle_task(payload: dict, capability: str) -> dict:
    """Bridge-local handler for fine-tune and simple diagnostic tasks."""
    action = payload.get("action", "unknown")
    if action == "ping":
        return {"status": "pong", "from": LABEL, "capability": capability}
    if action == "echo":
        return {
            "status": "echoed",
            "from": LABEL,
            "message": payload.get("message", ""),
        }

    if capability.startswith("ft-"):
        from mascarade.finetune.p2p.task_handlers import handle_ft_task

        result = await handle_ft_task(payload, capability)
        if isinstance(result, dict) and "from" not in result:
            result = {"from": LABEL, **result}
        return result

    return {
        "error": f"Unsupported capability on bridge: {capability}",
        "from": LABEL,
        "action": action,
    }


async def main():
    os.makedirs(KEY_DIR, exist_ok=True)
    node = MascaradeP2PNode(
        listen_host=LISTEN_HOST,
        listen_port=LISTEN_PORT,
        key_dir=KEY_DIR,
        bootstrap_peers=[(BOOTSTRAP_ID, BOOTSTRAP_HOST, BOOTSTRAP_PORT)],
    )
    await node.start()
    print(json.dumps({"peer_id": node.peer_id, "port": LISTEN_PORT}), flush=True)

    # Run relay so Tailscale peers can reach LAN peers through us
    relay = P2PRelay(local_peer_id=node.peer_id, transport=node.transport, dht=node.dht)
    await relay.announce()
    node.set_task_handler(handle_task)

    await asyncio.sleep(1)
    await node.advertise_capabilities(
        capabilities=CAPABILITIES,
        role=ROLE,
        label=LABEL,
        http_base_url=HTTP_BASE,
    )
    print(f"READY (bridge + relay, caps={CAPABILITIES})", flush=True)

    stop = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        asyncio.get_running_loop().add_signal_handler(sig, stop.set)
    await stop.wait()
    await node.stop()


asyncio.run(main())
