import os
import httpx
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer

KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://192.168.0.120:8085")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "electron_rare")
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "true").lower() == "true"

security = HTTPBearer(auto_error=False)

_jwks_cache = None


async def _get_jwks():
    global _jwks_cache
    if _jwks_cache:
        return _jwks_cache
    url = (
        f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}"
        "/protocol/openid-connect/certs"
    )
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        _jwks_cache = resp.json()
    return _jwks_cache


async def get_current_user(
    request: Request, credentials=Depends(security)
):
    if not AUTH_ENABLED:
        return {"sub": "dev-user", "auth": "disabled"}
    if not credentials:
        raise HTTPException(401, "Missing authentication")
    # Phase 1: basic token presence check
    # Full JWT validation (PyJWT + jwks) deferred to Phase 2
    return {"token": credentials.credentials, "sub": "clement"}
