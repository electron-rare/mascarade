# Audit securite Mascarade

Date: 2026-03-11

Scope cible:
- P2P auth (`core/mascarade/p2p/`)
- Transmission de cle cluster (`core/mascarade/cluster.py`)
- Contournements CORS et rate limiting
- Cookie sans `HttpOnly`
- Surface d'execution CAD/MCP

## Resume executif

Les cinq sujets demandes sont tous valides, avec une nuance importante sur le point P2P: la base cryptographique existe deja, mais elle n'est pas imposee sur les flux actifs. Le risque dominant est donc un systeme "authentifiable en theorie, non authentifie en pratique".

Priorisation recommande:

1. Bloquer l'execution arbitraire FreeCAD/MCP.
2. Supprimer le secret cluster en clair sur HTTP et passer a des requetes signees avec anti-rejeu.
3. Rendre l'authentification P2P obligatoire et lier l'identite applicative au peer libp2p.
4. Sortir la cle API du JavaScript et des cookies lisibles.
5. Remplacer le rate limiting memoire par un limiteur base proxy/Redis et durcir la politique CORS.

## 1. P2P auth: messages non signes

### Constat

La brique de signature Ed25519 existe deja dans [`core/mascarade/p2p/auth.py`](/Users/cils/mascarade/core/mascarade/p2p/auth.py#L15), mais:

- `verify_message()` accepte explicitement les messages non signes ([`core/mascarade/p2p/auth.py`](/Users/cils/mascarade/core/mascarade/p2p/auth.py#L27)).
- Les flux libp2p actifs echangeant l'identite, les `send` et les heartbeats utilisent du JSON brut sans signature applicative ([`core/mascarade/p2p/node.py`](/Users/cils/mascarade/core/mascarade/p2p/node.py#L280), [`core/mascarade/p2p/node.py`](/Users/cils/mascarade/core/mascarade/p2p/node.py#L311), [`core/mascarade/p2p/node.py`](/Users/cils/mascarade/core/mascarade/p2p/node.py#L322), [`core/mascarade/p2p/node.py`](/Users/cils/mascarade/core/mascarade/p2p/node.py#L378)).
- La decouverte par heartbeat accepte `node_id`, `role` et `base_url` fournis par le message sans verifier qu'ils sont lies au peer libp2p emetteur ([`core/mascarade/p2p/node.py`](/Users/cils/mascarade/core/mascarade/p2p/node.py#L414)).

### Impact

- Usurpation de `node_id` / `role`.
- Injection de faux peers et empoisonnement de routage.
- Rejeu de messages `send` si un attaquant peut observer le trafic applicatif.
- Pivot SSRF indirect via `base_url` falsifie, ensuite consomme par le cluster manager.

### Scenario d'abus

Un pair libp2p quelconque ou un acteur capable de publier sur le topic heartbeat peut annoncer:

- `node_id = prod-router`
- `role = orchestrator`
- `base_url = http://169.254.169.254:80`

Le cluster fusionne ensuite cette identite dans les peers connus ([`core/mascarade/cluster.py`](/Users/cils/mascarade/core/mascarade/cluster.py#L397)), puis sonde cette URL ([`core/mascarade/cluster.py`](/Users/cils/mascarade/core/mascarade/cluster.py#L731)).

### Patch minimal recommande

1. Rendre la signature obligatoire sur tous les messages applicatifs P2P.
2. Ajouter `ts` + `nonce` + cache anti-rejeu.
3. Verifier que la cle publique signee correspond bien au peer libp2p connecte.
4. Refuser tout heartbeat non signe.

### Patch concret

Introduire une enveloppe signee commune pour `identity`, `send` et `heartbeat`:

```python
# core/mascarade/p2p/signed_envelope.py
from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass

from mascarade.p2p.identity import PeerIdentity


@dataclass(slots=True)
class SignedEnvelope:
    body: dict
    ts: int
    nonce: str
    pubkey: str
    sig: str

    @staticmethod
    def canonical_payload(body: dict, ts: int, nonce: str) -> bytes:
        return json.dumps(
            {"body": body, "ts": ts, "nonce": nonce},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    @classmethod
    def sign(cls, identity: PeerIdentity, body: dict, nonce: str) -> dict:
        ts = int(time.time())
        payload = cls.canonical_payload(body, ts, nonce)
        sig = identity.sign(payload)
        return {
            "body": body,
            "ts": ts,
            "nonce": nonce,
            "pubkey": base64.b64encode(identity.public_key_bytes()).decode("ascii"),
            "sig": base64.b64encode(sig).decode("ascii"),
        }
```

Puis, dans `P2PNode`:

```python
# core/mascarade/p2p/node.py
self._seen_nonces: dict[str, float] = {}

def _verify_envelope(self, envelope: dict, *, expected_peer_id: str | None = None) -> dict:
    body = envelope["body"]
    ts = int(envelope["ts"])
    nonce = str(envelope["nonce"])
    pub = base64.b64decode(envelope["pubkey"])
    sig = base64.b64decode(envelope["sig"])

    if abs(time.time() - ts) > 30:
        raise ValueError("stale message")
    if nonce in self._seen_nonces:
        raise ValueError("replayed message")

    payload = SignedEnvelope.canonical_payload(body, ts, nonce)
    if not PeerIdentity.verify(pub, sig, payload):
        raise ValueError("invalid signature")

    derived_peer_id = PeerIdentity.from_public_key_bytes(pub).peer_id
    if expected_peer_id and derived_peer_id != expected_peer_id:
        raise ValueError("peer identity mismatch")

    self._seen_nonces[nonce] = time.monotonic()
    return body
```

### Durcissement supplementaire

- Remplacer l'acceptation implicite des messages non signes par `reject_unsigned=True` par defaut.
- Signer aussi les publications GossipSub.
- Lier `node_id` a une liste d'autorisations ou a un mapping persistant `node_id -> public_key`.

## 2. Transmission de la cle cluster en clair

### Constat

Le cluster utilise un bearer statique partage:

- validation cote serveur dans [`core/mascarade/cluster.py`](/Users/cils/mascarade/core/mascarade/cluster.py#L293)
- emission brute dans l'en-tete `Authorization: Bearer <cluster_shared_key>` dans [`core/mascarade/cluster.py`](/Users/cils/mascarade/core/mascarade/cluster.py#L837)

Le transport accepte `http` ou `https` aussi bien dans la configuration statique que dans la decouverte mDNS ([`core/mascarade/cluster.py`](/Users/cils/mascarade/core/mascarade/cluster.py#L273), [`core/mascarade/cluster.py`](/Users/cils/mascarade/core/mascarade/cluster.py#L553)). En pratique, si `mesh_scheme=http`, la cle traverse le reseau local en clair.

### Impact

- Compromission immediate de tout le plan de controle cluster en sniffing reseau.
- Rejeu trivial des requetes cluster.
- Escalade laterale: une seule capture permet d'appeler `/cluster/node/send`.

### Patch minimal recommande

1. Interdire `http` en production quand `cluster_enabled=true`.
2. Remplacer le bearer statique par des en-tetes signes HMAC avec timestamp court et nonce.
3. Rejeter tout message hors fenetre temporelle et tout nonce rejoue.

### Patch concret

```python
# core/mascarade/cluster.py
import hashlib
import secrets

_CLUSTER_SIGNATURE_TTL_SECONDS = 30
_seen_cluster_nonces: dict[str, float] = {}


def _cluster_sign(method: str, path: str, body: bytes) -> dict[str, str]:
    ts = str(int(time.time()))
    nonce = secrets.token_hex(16)
    payload = b"\n".join([
        method.upper().encode(),
        path.encode(),
        ts.encode(),
        nonce.encode(),
        hashlib.sha256(body).hexdigest().encode(),
    ])
    secret = settings.cluster_shared_key.strip().encode()
    sig = hmac.new(secret, payload, hashlib.sha256).hexdigest()
    return {
        "X-Mascarade-Node-ID": settings.node_id,
        "X-Mascarade-Timestamp": ts,
        "X-Mascarade-Nonce": nonce,
        "X-Mascarade-Signature": sig,
    }
```

Verification cote recepteur:

```python
async def require_cluster_auth(request: Request) -> None:
    secret = settings.cluster_shared_key.strip().encode()
    ts = request.headers.get("X-Mascarade-Timestamp", "")
    nonce = request.headers.get("X-Mascarade-Nonce", "")
    sig = request.headers.get("X-Mascarade-Signature", "")

    now = int(time.time())
    if not ts.isdigit() or abs(now - int(ts)) > _CLUSTER_SIGNATURE_TTL_SECONDS:
        raise HTTPException(status_code=401, detail="Stale cluster request")
    if nonce in _seen_cluster_nonces:
        raise HTTPException(status_code=401, detail="Replay detected")

    body = await request.body()
    payload = b"\n".join([
        request.method.upper().encode(),
        request.url.path.encode(),
        ts.encode(),
        nonce.encode(),
        hashlib.sha256(body).hexdigest().encode(),
    ])
    expected = hmac.new(secret, payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        raise HTTPException(status_code=401, detail="Invalid cluster signature")
```

Et cote emission:

```python
body = json.dumps(json or {}, separators=(",", ":")).encode("utf-8") if json else b""
headers = _cluster_sign(method, path, body)
response = await client.request(
    method,
    url,
    content=body if body else None,
    headers={**headers, "Content-Type": "application/json"} if body else headers,
)
```

### Durcissement supplementaire

- Mutual TLS entre noeuds.
- Refuser le boot si `mesh_scheme != "https"` hors mode dev.
- Ne jamais reutiliser le meme secret pour mDNS et API cluster.

## 3. CORS et rate limiting contournables

### Constat CORS

La config CORS met `credentials: true` dans tous les cas ([`api/src/middleware/cors.ts`](/Users/cils/mascarade/api/src/middleware/cors.ts#L10)). La liste d'origines vient d'une variable d'environnement simple ([`api/src/middleware/cors.ts`](/Users/cils/mascarade/api/src/middleware/cors.ts#L3)).

La faiblesse la plus concrete n'est pas un bypass navigateur "magique", mais une configuration fragile:

- `CORS_ORIGINS=*` est explicitement prevu.
- l'API accepte l'auth par cookie ([`api/src/middleware/auth.ts`](/Users/cils/mascarade/api/src/middleware/auth.ts#L56)).
- l'API front stocke cette cle dans un cookie lisible JS ([`web/src/api/client.ts`](/Users/cils/mascarade/web/src/api/client.ts#L7)).

Le combo "cookie de secret + credentials + CORS permissif" augmente fortement le blast radius d'une erreur de config.

### Constat rate limiting

Le limiteur se base sur `x-forwarded-for` ou `x-real-ip` fournis par le client ([`api/src/middleware/rate-limit.ts`](/Users/cils/mascarade/api/src/middleware/rate-limit.ts#L14)).

Faiblesses:

- contournement trivial par rotation de `X-Forwarded-For`
- pas de prise en compte d'un proxy de confiance
- store purement memoire par process
- bypass horizontal si plusieurs replicas
- l'ordre middleware actuel laisse des tentatives d'auth invalides hors quota ([`api/src/index.ts`](/Users/cils/mascarade/api/src/index.ts#L34))

### Impact

- brute force / enumeration a cout quasi nul
- DoS distribue leger via inflation de cles memoire
- contourner les quotas via changement d'header ou changement de replica

### Patch minimal recommande

1. CORS:
   - interdire `*` si `credentials=true`
   - normaliser strictement les origins
   - desactiver `credentials` si aucune auth cookie n'est necessaire
2. Rate limit:
   - utiliser `req.raw.socket.remoteAddress` si la requete ne vient pas d'un proxy de confiance
   - introduire `TRUSTED_PROXY_CIDRS`
   - ajouter une dimension par API key
   - deplacer le stockage vers Redis
   - compter aussi les 401/403

### Patch concret CORS

```ts
// api/src/middleware/cors.ts
const configured = (process.env.CORS_ORIGINS || "")
  .split(",")
  .map((o) => o.trim())
  .filter(Boolean);

if (configured.includes("*")) {
  throw new Error("CORS_ORIGINS=* interdit quand l'API utilise des credentials");
}

export const corsMiddleware = cors({
  origin: (origin) => {
    if (!origin) return null;
    return configured.includes(origin) ? origin : null;
  },
  credentials: false,
  allowMethods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
  allowHeaders: ["Content-Type", "Authorization"],
  maxAge: 600,
});
```

### Patch concret rate limiting

```ts
// api/src/middleware/rate-limit.ts
function clientIp(c: Context): string {
  const remote = c.env?.incoming?.socket?.remoteAddress || c.req.raw.headers.get("x-real-ip");
  return remote || "unknown";
}

function subjectKey(c: Context): string {
  const auth = c.req.header("authorization") || "";
  const apiKeyHash = auth.startsWith("Bearer ")
    ? createHash("sha256").update(auth.slice(7)).digest("hex").slice(0, 16)
    : "anonymous";
  return `${clientIp(c)}:${apiKeyHash}`;
}
```

Et brancher le limiteur avant l'auth, avec deux seuils:

```ts
app.use("/api/*", rateLimitMiddleware);
app.use("/api/*", authMiddleware);
```

Puis:

- quota faible pour anonymes / 401
- quota normal pour identites valides

## 4. Cookie `HttpOnly` manquant

### Constat

Le front ecrit directement la cle API dans `document.cookie` sans `HttpOnly` ([`web/src/api/client.ts`](/Users/cils/mascarade/web/src/api/client.ts#L7)). Le middleware API lit ensuite cette cle depuis le cookie `mascarade_key` ([`api/src/middleware/auth.ts`](/Users/cils/mascarade/api/src/middleware/auth.ts#L29)).

`HttpOnly` est impossible a poser depuis JavaScript. Donc ici, ce n'est pas seulement "un attribut oublie", c'est un design qui impose l'absence de `HttpOnly`.

### Impact

- toute XSS devient vol direct de la cle API persistante
- exfiltration simple vers un domaine tiers
- persistance possible 30 jours si `persist=true`

### Patch recommande

Supprimer completement le modele "API key en cookie lisible JS".

Deux options saines:

1. Option minimale:
   - ne plus accepter la cle depuis un cookie
   - ne l'accepter que via header `Authorization`
   - garder la cle uniquement en memoire front
2. Option robuste:
   - remplacer la cle API utilisateur par une vraie session serveur
   - emettre un cookie `HttpOnly; Secure; SameSite=Strict`

### Patch concret minimal

Retirer la lecture du cookie:

```ts
// api/src/middleware/auth.ts
export const authMiddleware: MiddlewareHandler = async (c, next) => {
  const apiKeys = configuredApiKeys();
  if (apiKeys.length === 0) return next();

  const authHeader = c.req.header("Authorization");
  const token =
    authHeader && authHeader.startsWith("Bearer ")
      ? authHeader.slice(7)
      : null;

  if (!token) {
    return c.json({ error: "Token invalide ou manquant" }, 401);
  }
  ...
}
```

Et cesser d'utiliser `document.cookie`:

```ts
// web/src/api/client.ts
let inMemoryApiKey = "";

export function getApiKey(): string {
  return inMemoryApiKey;
}

export function setApiKey(key: string) {
  inMemoryApiKey = key.trim();
}

export function clearApiKey() {
  inMemoryApiKey = "";
}
```

### Patch concret robuste

Creer une route de login qui pose un cookie de session:

```ts
return c.body(null, 204, {
  "Set-Cookie": `mascarade_session=${sessionId}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=28800`,
});
```

Puis:

- le navigateur envoie automatiquement le cookie
- le front ne voit jamais le secret
- CORS peut rester `credentials=false` si meme origin uniquement

## 5. Surface d'execution CAD / MCP

### Constat

La route [`/mcp/freecad/script`](/Users/cils/mascarade/core/mascarade/server.py#L983) accepte un script Python arbitraire et le transmet tel quel a `run_python_script` ([`core/mascarade/mcp/client.py`](/Users/cils/mascarade/core/mascarade/mcp/client.py#L974)).

Le client MCP peut lancer des serveurs externes definis par scripts shell ou commandes locales ([`core/mascarade/mcp/client.py`](/Users/cils/mascarade/core/mascarade/mcp/client.py#L132)).

Le probleme principal n'est pas `create_subprocess_exec` en soi, mais l'exposition d'une primitive "execute du Python FreeCAD arbitraire" derriere une simple cle API.

### Impact

- execution de code arbitraire dans le contexte du runtime CAD
- lecture/ecriture de fichiers accessibles par le process
- mouvements lateraux si le runtime dispose de secrets, acces reseau ou montages

### Scenario d'abus

Un utilisateur disposant d'une cle API valide peut envoyer un script FreeCAD contenant:

- `import os, pathlib`
- lecture de fichiers d'environnement
- ecriture sur un chemin arbitraire
- appels reseau si le runtime les autorise

Le risque est equivalent a exposer un mini endpoint RCE, meme si le but fonctionnel est "CAD scripting".

### Patch minimal recommande

1. Desactiver par defaut `/mcp/freecad/script` en production.
2. Ajouter un allowlist de capabilities CAD.
3. Limiter les chemins de sortie a un workspace dedie.
4. Passer d'un modele "script libre" a un modele "operations parametrees".

### Patch concret

Ajouter un flag de securite:

```python
# core/mascarade/server.py
if not settings.enable_unsafe_cad_scripts:
    raise HTTPException(status_code=403, detail="FreeCAD scripting disabled")
```

Normaliser et borner les chemins:

```python
from pathlib import Path

CAD_ROOT = Path(settings.cad_workspace_root).resolve()

def _safe_cad_path(raw: str) -> str:
    candidate = (CAD_ROOT / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
    if CAD_ROOT not in candidate.parents and candidate != CAD_ROOT:
        raise HTTPException(status_code=400, detail="Path outside CAD workspace")
    return str(candidate)
```

Remplacer le script libre par des templates:

```python
class FreeCADOp(BaseModel):
    op: Literal["create_box", "export_step", "export_stl"]
    document_path: str | None = None
    output_path: str
    params: dict[str, float | str | int] = Field(default_factory=dict)
```

Puis ne conserver `run_python_script` que pour un mode admin explicite:

- route separee
- role admin
- environnement isole
- audit log obligatoire

### Durcissement supplementaire

- lancer le MCP CAD dans un conteneur sans reseau
- root filesystem en lecture seule
- volume de sortie dedie
- seccomp/AppArmor
- uid non privilegie
- timeouts plus courts et quotas CPU/memoire

## Plan d'application recommande

### Phase 1: reduire l'exposition immediate

- desactiver `/mcp/freecad/script` en prod
- retirer l'auth par cookie cote API
- ne plus stocker la cle en `document.cookie`
- interdire `CORS_ORIGINS=*`

### Phase 2: authentifier les flux internes

- signer les messages P2P
- ajouter anti-rejeu P2P
- signer les requetes cluster
- interdire `mesh_scheme=http` hors dev

### Phase 3: robustesse operationnelle

- limiteur Redis
- prise en charge de proxies de confiance
- isolation systeme des runtimes MCP/CAD
- journalisation securite dediee

## Conclusion

Le point le plus critique est la surface CAD/MCP, car elle donne une capacite d'execution proche d'une RCE applicative. Le second point est l'auth cluster en bearer statique sur un transport pouvant etre HTTP. Le point P2P est structurellement faible parce que l'auth existe mais reste optionnelle, ce qui cree une fausse impression de securite.

Si vous voulez, je peux maintenant transformer ce rapport en patches applicables directement sur le depot, en commencant par:

1. suppression du cookie API lisible JS
2. durcissement CORS/rate limit
3. kill switch sur `freecad/script`
