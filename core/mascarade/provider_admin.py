"""Administration des cles providers LLM — status, update, .env persistence."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from mascarade.config import is_secret_configured, settings

logger = logging.getLogger("mascarade.provider_admin")

PROVIDER_REGISTRY: dict[str, dict] = {
    "claude": {
        "label": "Anthropic / Claude",
        "module": "mascarade.router.providers.claude",
        "class": "ClaudeProvider",
        "fields": [
            {
                "env": "ANTHROPIC_API_KEY",
                "attr": "anthropic_api_key",
                "label": "API Key",
                "secret": True,
            },
        ],
    },
    "openai": {
        "label": "OpenAI",
        "module": "mascarade.router.providers.openai",
        "class": "OpenAIProvider",
        "fields": [
            {"env": "OPENAI_API_KEY", "attr": "openai_api_key", "label": "API Key", "secret": True},
        ],
    },
    "mistral": {
        "label": "Mistral AI",
        "module": "mascarade.router.providers.mistral",
        "class": "MistralProvider",
        "fields": [
            {
                "env": "MISTRAL_API_KEY",
                "attr": "mistral_api_key",
                "label": "API Key",
                "secret": True,
            },
        ],
    },
    "google": {
        "label": "Google Gemini",
        "module": "mascarade.router.providers.google",
        "class": "GoogleProvider",
        "fields": [
            {"env": "GOOGLE_API_KEY", "attr": "google_api_key", "label": "API Key", "secret": True},
        ],
    },
    "bedrock": {
        "label": "AWS Bedrock",
        "module": "mascarade.router.providers.bedrock",
        "class": "BedrockProvider",
        "fields": [
            {
                "env": "AWS_ACCESS_KEY_ID",
                "attr": "aws_access_key_id",
                "label": "Access Key ID",
                "secret": True,
            },
            {
                "env": "AWS_SECRET_ACCESS_KEY",
                "attr": "aws_secret_access_key",
                "label": "Secret Access Key",
                "secret": True,
            },
        ],
    },
    "huggingface": {
        "label": "HuggingFace",
        "module": "mascarade.router.providers.huggingface",
        "class": "HuggingFaceProvider",
        "fields": [
            {
                "env": "HUGGINGFACE_API_KEY",
                "attr": "huggingface_api_key",
                "label": "API Key",
                "secret": True,
            },
        ],
    },
    "ollama": {
        "label": "Ollama (local)",
        "module": "mascarade.router.providers.ollama",
        "class": "OllamaProvider",
        "fields": [
            {
                "env": "OLLAMA_BASE_URL",
                "attr": "ollama_base_url",
                "label": "Base URL",
                "secret": False,
            },
        ],
        "toggle": {"env": "OLLAMA_ENABLED", "attr": "ollama_enabled"},
    },
}


def _mask(value: str) -> str:
    if not value or len(value) < 10:
        return "***" if value else ""
    return f"{value[:4]}...{value[-4:]}"


def get_providers_status(router) -> list[dict]:
    active_names = set(router.available_providers)
    result = []

    for name, meta in PROVIDER_REGISTRY.items():
        fields_status = []
        all_configured = True

        for field in meta["fields"]:
            value = getattr(settings, field["attr"], "")
            if field.get("secret"):
                configured = is_secret_configured(value)
                hint = _mask(value) if configured else ""
            else:
                configured = bool(value.strip())
                hint = value.strip() if configured else ""
            if not configured:
                all_configured = False
            fields_status.append(
                {
                    "env": field["env"],
                    "label": field["label"],
                    "configured": configured,
                    "hint": hint,
                    "secret": field.get("secret", False),
                }
            )

        toggle = meta.get("toggle")
        enabled = True
        if toggle:
            enabled = bool(getattr(settings, toggle["attr"], False))

        active = name in active_names
        provider_obj = router._providers.get(name)

        entry: dict = {
            "name": name,
            "label": meta["label"],
            "configured": all_configured and (enabled if toggle else True),
            "active": active,
            "fields": fields_status,
            "default_model": getattr(provider_obj, "default_model", None) if provider_obj else None,
            "models": provider_obj.available_models() if provider_obj else [],
        }

        if toggle:
            entry["enabled"] = enabled
            entry["toggle_env"] = toggle["env"]

        result.append(entry)

    return result


def update_provider_keys(name: str, keys: dict[str, str], router) -> dict:
    if name not in PROVIDER_REGISTRY:
        return {"error": f"Unknown provider: {name}"}

    meta = PROVIDER_REGISTRY[name]
    valid_envs = {f["env"] for f in meta["fields"]}
    if meta.get("toggle"):
        valid_envs.add(meta["toggle"]["env"])

    for env_key in keys:
        if env_key not in valid_envs:
            return {"error": f"Unknown field: {env_key}"}

    # Update settings in-memory
    for field in meta["fields"]:
        if field["env"] in keys:
            setattr(settings, field["attr"], keys[field["env"]])

    if meta.get("toggle") and meta["toggle"]["env"] in keys:
        val = keys[meta["toggle"]["env"]]
        setattr(settings, meta["toggle"]["attr"], val.lower() in ("true", "1", "yes"))

    # Persist to .env (best-effort)
    try:
        _persist_env(keys)
    except Exception as exc:
        logger.warning("Failed to persist to .env: %s", exc)

    # Re-initialize provider
    try:
        module = __import__(meta["module"], fromlist=[meta["class"]])
        provider_cls = getattr(module, meta["class"])
        provider = provider_cls()

        if provider.is_configured:
            router.register(provider)
            return {"status": "ok", "active": True}

        router._providers.pop(name, None)
        return {
            "status": "ok",
            "active": False,
            "message": "Saved but provider reports not configured",
        }
    except Exception as exc:
        logger.warning("Failed to re-initialize %s: %s", name, exc)
        return {"status": "ok", "active": False, "message": f"Saved but init failed: {exc}"}


def _persist_env(updates: dict[str, str]) -> None:
    env_path = Path(".env")
    lines: list[str] = []

    if env_path.exists():
        lines = env_path.read_text().splitlines(keepends=True)

    remaining = dict(updates)
    new_lines: list[str] = []

    for line in lines:
        matched = False
        for env_key in list(remaining):
            if re.match(rf"^{re.escape(env_key)}\s*=", line.lstrip()):
                value = remaining.pop(env_key)
                quoted = f'"{value}"' if " " in value or not value else value
                new_lines.append(f"{env_key}={quoted}\n")
                matched = True
                break
        if not matched:
            new_lines.append(line if line.endswith("\n") else line + "\n")

    for env_key, value in remaining.items():
        quoted = f'"{value}"' if " " in value or not value else value
        new_lines.append(f"{env_key}={quoted}\n")

    env_path.write_text("".join(new_lines))
    logger.info("Persisted %d key(s) to .env", len(updates))
