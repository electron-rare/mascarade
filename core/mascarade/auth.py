"""Authentification — Bearer token simple."""

from __future__ import annotations

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from mascarade.config import settings

_bearer_scheme = HTTPBearer(auto_error=False)


async def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> None:
    """Vérifie le Bearer token si MASCARADE_API_KEY est configuré."""
    if not settings.mascarade_api_key:
        return
    if credentials is None or credentials.credentials != settings.mascarade_api_key:
        raise HTTPException(status_code=401, detail="Token invalide ou manquant")
