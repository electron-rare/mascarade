#!/usr/bin/env python3
"""Test P2P live — lance 2 nœuds sur localhost et vérifie la connexion."""

import asyncio
import tempfile

from mascarade.p2p.asyncio_node import MascaradeP2PNode


async def main():
    print("=" * 60)
    print("  Mascarade P2P — Test 2 nœuds localhost")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as dir_a, tempfile.TemporaryDirectory() as dir_b:
        # --- Node A : GPU / LLM ---
        node_a = MascaradeP2PNode(
            listen_host="127.0.0.1",
            listen_port=4001,
            key_dir=dir_a,
        )
        await node_a.start()
        print(f"\n[A] PeerID:  {node_a.peer_id}")
        print(f"[A] Listen:  127.0.0.1:{node_a.transport.listen_port}")

        # --- Node B : Worker / MCP ---
        node_b = MascaradeP2PNode(
            listen_host="127.0.0.1",
            listen_port=4002,
            key_dir=dir_b,
            bootstrap_peers=[
                (node_a.peer_id, "127.0.0.1", node_a.transport.listen_port)
            ],
        )
        await node_b.start()
        print(f"\n[B] PeerID:  {node_b.peer_id}")
        print(f"[B] Listen:  127.0.0.1:{node_b.transport.listen_port}")

        # Attendre le bootstrap
        print("\n--- Bootstrap + DHT discovery ---")
        await asyncio.sleep(2.0)

        # Advertise capabilities
        print("\n--- Capability exchange ---")
        await node_a.advertise_capabilities(
            capabilities=["llm-inference", "gpu", "agent-orchestration"],
            providers=["claude", "ollama"],
            provider_models={
                "claude": ["claude-sonnet-4-6", "claude-haiku-4-5-20251001"],
                "ollama": ["mistral-7b", "llama-3.1-8b"],
            },
            role="gpu",
            label="Photon GPU Node",
            http_base_url="http://192.168.0.119:8100",
        )
        print("[A] Advertised: llm-inference, gpu, agent-orchestration")

        await node_b.advertise_capabilities(
            capabilities=["mcp-host", "kicad-validation", "firmware-build"],
            role="worker",
            label="Worker Node",
            http_base_url="http://192.168.0.120:8100",
        )
        print("[B] Advertised: mcp-host, kicad-validation, firmware-build")

        await asyncio.sleep(1.0)

        # Vérifier la découverte
        print("\n--- Discovery results ---")
        peers_a = await node_a.discover_peers()
        peers_b = await node_b.discover_peers()
        print(f"[A] Voit {len(peers_a)} peer(s): {[p.peer_id[:15] for p in peers_a]}")
        print(f"[B] Voit {len(peers_b)} peer(s): {[p.peer_id[:15] for p in peers_b]}")

        # Vérifier les capabilities
        print("\n--- Capability view ---")
        caps_a = node_a.capabilities.all_capabilities()
        caps_b = node_b.capabilities.all_capabilities()

        print(f"[A] Voit {len(caps_a)} peer(s) avec capabilities:")
        for pid, c in caps_a.items():
            print(f"    {pid[:15]}: {c.capabilities} (role={c.role})")

        print(f"[B] Voit {len(caps_b)} peer(s) avec capabilities:")
        for pid, c in caps_b.items():
            print(f"    {pid[:15]}: {c.capabilities} (role={c.role})")
            print(f"    providers: {c.providers}")
            print(f"    models:    {c.provider_models}")

        # Recherche par capability
        print("\n--- Capability search ---")
        llm_peers = await node_b.find_capable_peers("llm-inference")
        print(f"[B] Cherche 'llm-inference': {len(llm_peers)} peer(s)")
        for p in llm_peers:
            print(f"    {p.peer_id[:15]} (role={p.role}, http={p.http_base_url})")

        kicad_peers = await node_a.find_capable_peers("kicad-validation")
        print(f"[A] Cherche 'kicad-validation': {len(kicad_peers)} peer(s)")
        for p in kicad_peers:
            print(f"    {p.peer_id[:15]} (role={p.role})")

        # Status réseau
        print("\n--- Network status ---")
        print(f"[A] DHT entries: {len(node_a.dht.routing_table)}")
        print(f"[B] DHT entries: {len(node_b.dht.routing_table)}")
        print(f"[A] Transport peers: {len(node_a.transport.peers)}")
        print(f"[B] Transport peers: {len(node_b.transport.peers)}")

        # Vérifications
        print("\n--- Checks ---")
        ok = True
        if len(caps_b) >= 1 and node_a.peer_id in caps_b:
            print("[OK] B voit les capabilities de A")
        else:
            print("[FAIL] B ne voit pas les capabilities de A")
            ok = False

        if len(caps_a) >= 1 and node_b.peer_id in caps_a:
            print("[OK] A voit les capabilities de B")
        else:
            print("[FAIL] A ne voit pas les capabilities de B")
            ok = False

        if llm_peers and any(p.peer_id == node_a.peer_id for p in llm_peers):
            print("[OK] Recherche llm-inference trouve A")
        else:
            print("[FAIL] Recherche llm-inference ne trouve pas A")
            ok = False

        if kicad_peers and any(p.peer_id == node_b.peer_id for p in kicad_peers):
            print("[OK] Recherche kicad-validation trouve B")
        else:
            print("[FAIL] Recherche kicad-validation ne trouve pas B")
            ok = False

        print("\n" + "=" * 60)
        if ok:
            print("  TOUS LES CHECKS PASSENT")
        else:
            print("  CERTAINS CHECKS ECHOUENT")
        print("=" * 60)

        await node_a.stop()
        await node_b.stop()


if __name__ == "__main__":
    asyncio.run(main())
