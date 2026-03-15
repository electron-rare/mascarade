# Cluster / P2P / Remote Send - Sequence Diagram - 2026-03-11

## Scope

Ce document fixe le chemin d'execution du forwarding cluster pour un agent ou un appel direct:

- selection locale vs peer distant
- tentative P2P avant fallback HTTP
- execution distante sur `/cluster/node/send`
- metadata de routage remontee vers l'API operateur

References code:

- `core/mascarade/orchestrator/engine.py`
- `core/mascarade/cluster.py`
- `core/mascarade/server.py`
- `core/mascarade/p2p/asyncio_node.py`
- `core/mascarade/p2p/stream_forward.py`
- `core/mascarade/p2p/libp2p_node.py`

## Remote send sequence

```mermaid
sequenceDiagram
    autonumber
    participant U as Client / UI
    participant API as API Hono
    participant Core as Core FastAPI
    participant Orch as Orchestrator
    participant CM as ClusterManager
    participant RP as Remote peer probe
    participant P2P as P2P transport
    participant HTTP as HTTP cluster lane
    participant RCore as Remote Core
    participant Router as Remote Router

    alt Multi-agent path
        U->>API: POST /api/agents/orchestrate
        API->>Core: POST /orchestrate
        Core->>Orch: run(...)
        Orch->>CM: forward_send(peer_id=None, preferred_role, allow_local=true, payload)
    else Direct cluster path
        U->>API: POST /api/cluster/forward/send
        API->>Core: POST /cluster/forward/send
        Core->>CM: forward_send(peer_id?, preferred_role?, allow_local, payload)
    end

    CM->>CM: select_route(peer_id, preferred_role, provider, model, allow_local)
    CM->>RP: probe_peers() / _probe_peer(identity)

    alt selected_by=auto-local or explicit local match
        CM->>Router: _send_local(payload)
        Router-->>CM: LLMResponse
        CM-->>Orch: remote=false, selected_by=auto-local
        Orch-->>Core: TaskResult(remote=false, selected_by, node_id, role)
    else selected_by=explicit-peer or auto-peer
        CM->>P2P: _try_p2p_forward(peer_id, payload)
        alt asyncio P2P node can_forward(peer_id)
            P2P->>RCore: send:request
            RCore->>Router: _p2p_send_handler -> _send_local(payload)
            Router-->>RCore: LLMResponse
            RCore-->>P2P: send:response
            P2P-->>CM: response + _p2p_meta
            CM-->>Orch: remote=true, transport=p2p
        else libp2p node has discovered peer mapping
            P2P->>RCore: SEND_PROTOCOL stream
            RCore->>Router: _handle_send -> _p2p_local_send -> _send_local(payload)
            Router-->>RCore: LLMResponse
            RCore-->>P2P: response dict
            P2P-->>CM: response
            CM-->>Orch: remote=true, transport=p2p
        else P2P unavailable or failed
            CM->>HTTP: POST /cluster/node/send
            HTTP->>RCore: authenticated cluster request
            RCore->>Router: _send_local(payload)
            Router-->>RCore: LLMResponse
            RCore-->>HTTP: content + provider + model + usage + node_id
            HTTP-->>CM: remote response
            CM-->>Orch: remote=true, transport=http
        end
        Orch-->>Core: TaskResult(remote=true, selected_by, peer_id, node_id, role)
    end

    Core-->>API: per-step results
    API-->>U: 200 JSON
```

## Route selection notes

- `explicit-peer`: un `peer_id` est fourni, le cluster force ce noeud.
- `auto-local`: le noeud courant satisfait `role/provider/model`.
- `auto-peer`: un peer sain et compatible est choisi par latence.
- `auto-peer-fallback`: un peer sain est choisi meme sans filtre fort si rien d'autre ne matche.

## Transport notes

- Le chemin P2P `asyncio` passe par `P2PStreamForwarder` et ajoute `_p2p_meta` dans la reponse brute.
- Le chemin P2P `libp2p` passe par `P2PNode.forward_send()` et le stream `SEND_PROTOCOL`.
- Si aucun transport P2P operable n'est disponible, le cluster retombe sur `POST /cluster/node/send`.

## Observability notes

- `TaskResult` remonte deja `remote`, `selected_by`, `peer_id`, `node_id` et `role`.
- `ClusterManager.forward_send()` remonte aussi `transport` et `latency_ms`.
- le lot courant remonte aussi `routing_selected_by`, `routing_transport` et `routing_latency_ms` dans `AgentTraceBuffer` pour les evenements `agent_output`.
- les surfaces cockpit `web/src/pages/Logs.tsx` et `web/src/pages/Orchestrate.tsx` les affichent maintenant comme badges `route`, `transport` et `latence` pour raccourcir la lecture operateur.
