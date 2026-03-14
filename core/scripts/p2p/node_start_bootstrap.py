#!/usr/bin/env python3
"""P2P bootstrap node with relay service."""
import asyncio, os, sys, json, signal
sys.path.insert(0, os.environ.get('PYTHONPATH', '/mascarade/core'))

from mascarade.p2p.asyncio_node import MascaradeP2PNode
from mascarade.p2p.relay import P2PRelay

LISTEN_HOST = os.environ.get('P2P_LISTEN_HOST', '0.0.0.0')
LISTEN_PORT = int(os.environ.get('P2P_LISTEN_PORT', '4001'))
KEY_DIR = os.path.expanduser(os.environ.get('P2P_KEY_DIR', '~/.mascarade/p2p'))
CAPABILITIES = os.environ.get('P2P_CAPABILITIES', 'llm-inference,gpu,docker,p2p-relay').split(',')
ROLE = os.environ.get('P2P_ROLE', 'gpu')
LABEL = os.environ.get('P2P_LABEL', 'Photon VM')
HTTP_BASE = os.environ.get('P2P_HTTP_BASE', 'http://192.168.0.119:8100')

async def main():
    os.makedirs(KEY_DIR, exist_ok=True)
    node = MascaradeP2PNode(listen_host=LISTEN_HOST, listen_port=LISTEN_PORT, key_dir=KEY_DIR)
    await node.start()
    print(json.dumps({'peer_id': node.peer_id, 'port': LISTEN_PORT}), flush=True)

    relay = P2PRelay(local_peer_id=node.peer_id, transport=node.transport, dht=node.dht)
    await relay.announce()

    await node.advertise_capabilities(
        capabilities=CAPABILITIES, role=ROLE, label=LABEL, http_base_url=HTTP_BASE,
    )
    print('READY', flush=True)

    stop = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        asyncio.get_running_loop().add_signal_handler(sig, stop.set)
    await stop.wait()
    await node.stop()

asyncio.run(main())
