#!/usr/bin/env python3
"""P2P worker node. Configure via environment variables."""

import asyncio
import json
import os
import signal
import sys

sys.path.insert(0, os.environ.get("PYTHONPATH", os.path.expanduser("~/mascarade/core")))

from mascarade.p2p.asyncio_node import MascaradeP2PNode

LISTEN_HOST = os.environ.get("P2P_LISTEN_HOST", "0.0.0.0")
LISTEN_PORT = int(os.environ.get("P2P_LISTEN_PORT", "4001"))
KEY_DIR = os.path.expanduser(os.environ.get("P2P_KEY_DIR", "~/.mascarade/p2p"))
BOOTSTRAP_ID = os.environ.get("P2P_BOOTSTRAP_ID", "QmTO5AYG6ZT3EU3UWVLNWU2FFFHWKUJR7S")
BOOTSTRAP_HOST = os.environ.get("P2P_BOOTSTRAP_HOST", "192.168.0.119")
BOOTSTRAP_PORT = int(os.environ.get("P2P_BOOTSTRAP_PORT", "4001"))
CAPABILITIES = os.environ.get("P2P_CAPABILITIES", "compute").split(",")
ROLE = os.environ.get("P2P_ROLE", "worker")
LABEL = os.environ.get("P2P_LABEL", "Worker")
HTTP_BASE = os.environ.get("P2P_HTTP_BASE", "")
USE_RELAY = os.environ.get("P2P_USE_RELAY", "false").lower() == "true"


async def main():
    os.makedirs(KEY_DIR, exist_ok=True)
    node = MascaradeP2PNode(
        listen_host=LISTEN_HOST,
        listen_port=LISTEN_PORT,
        key_dir=KEY_DIR,
        bootstrap_peers=[(BOOTSTRAP_ID, BOOTSTRAP_HOST, BOOTSTRAP_PORT)],
    )
    await node.start()
    print(json.dumps({"peer_id": node.peer_id}), flush=True)

    if USE_RELAY:
        from mascarade.p2p.relay import RelayClient

        rc = RelayClient(local_peer_id=node.peer_id, transport=node.transport, dht=node.dht)
        rc.add_known_relay(BOOTSTRAP_ID)
        node.transport.set_relay_client(rc)

    await asyncio.sleep(1)
    await node.advertise_capabilities(
        capabilities=CAPABILITIES,
        role=ROLE,
        label=LABEL,
        http_base_url=HTTP_BASE,
    )
    print("READY", flush=True)

    stop = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        asyncio.get_running_loop().add_signal_handler(sig, stop.set)
    await stop.wait()
    await node.stop()


asyncio.run(main())
