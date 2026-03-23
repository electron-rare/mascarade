#!/usr/bin/env python3
"""Test P2P mesh connectivity from the local machine.

Usage:
    PYTHONPATH=. python scripts/p2p/test_mesh.py <bootstrap_peer_id>
    PYTHONPATH=. python scripts/p2p/test_mesh.py  # auto-detect from VM log
"""

import asyncio
import subprocess
import sys
import tempfile

from mascarade.p2p.asyncio_node import MascaradeP2PNode


def get_bootstrap_peer_id() -> str:
    """Get bootstrap peer ID from CLI arg or VM log."""
    if len(sys.argv) > 1:
        return sys.argv[1]

    try:
        result = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=3", "root@192.168.0.119",
             "head -1 /tmp/p2p_node.log"],
            capture_output=True, text=True, timeout=5,
        )
        import json
        info = json.loads(result.stdout.strip())
        return info["peer_id"]
    except Exception:
        pass

    # Try plain text format
    try:
        line = result.stdout.strip()
        if line.startswith("PEER_ID="):
            return line.split("=", 1)[1]
    except Exception:
        pass

    print("ERROR: Cannot determine bootstrap peer ID")
    print("Usage: python test_mesh.py <bootstrap_peer_id>")
    sys.exit(1)


async def main():
    bootstrap_id = get_bootstrap_peer_id()
    print(f"Bootstrap: {bootstrap_id} @ 192.168.0.119:4001")
    print()

    with tempfile.TemporaryDirectory() as d:
        node = MascaradeP2PNode(
            listen_host="0.0.0.0",
            listen_port=0,  # random port
            key_dir=d,
            bootstrap_peers=[(bootstrap_id, "192.168.0.119", 4001)],
        )
        await node.start()
        print(f"Local PeerID: {node.peer_id}")
        print(f"Listening on port {node.transport.listen_port}")

        await asyncio.sleep(3)

        # Check what we can see
        caps = node.capabilities.all_capabilities()
        dht = node.dht.routing_table.all_entries()
        transport = node.transport.peers

        print(f"\n{'='*50}")
        print(f"Transport peers: {len(transport)}")
        for pid, pc in transport.items():
            print(f"  {pid[:25]}: {pc.host}:{pc.port} connected={pc.connected}")

        print(f"\nDHT entries: {len(dht)}")
        for e in dht:
            print(f"  {e.peer_id[:25]}: {e.host}:{e.port} caps={e.capabilities}")

        print(f"\nCapabilities: {len(caps)} peer(s)")
        for pid, c in caps.items():
            print(f"  {c.label or pid[:20]}: {c.capabilities} role={c.role}")
            if c.http_base_url:
                print(f"    http={c.http_base_url}")

        # Search tests
        print(f"\n{'='*50}")
        for cap in ["llm-inference", "kicad-validation", "compute", "training"]:
            peers = await node.find_capable_peers(cap)
            if peers:
                names = [p.label or p.peer_id[:15] for p in peers]
                print(f"  {cap}: {names}")

        print(f"\n{'='*50}")
        total_caps = len(caps)
        if total_caps >= 3:
            print("RESULT: FULL MESH (all nodes visible)")
        elif total_caps >= 1:
            print(f"RESULT: PARTIAL ({total_caps} of 3+ nodes visible)")
        else:
            print("RESULT: FAIL (no peers visible)")

        await node.stop()

    return 0 if total_caps >= 1 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
