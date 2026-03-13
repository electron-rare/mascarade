"""Version de l'API et métadonnées."""

from __future__ import annotations

from typing import Any

API_VERSION = "1.0.0"


def get_version_info() -> dict[str, Any]:
    """Retourne les métadonnées de version de l'API.

    Returns:
        dict contenant:
        - api_version: version de l'API (str)
        - stability: niveau de stabilité (str)
        - frozen_contracts: liste des contrats API gelés
    """
    return {
        "api_version": API_VERSION,
        "stability": "stable",
        "frozen_contracts": [
            "/v1/chat/completions"
        ],
    }
