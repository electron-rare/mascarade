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
        "classification": "provider-credential",
        "criticality": "feature-required",
        "required_when": "Requis seulement si Claude est active comme provider.",
        "used_by": ["core", "playground", "orchestrate"],
        "module": "mascarade.router.providers.claude",
        "class": "ClaudeProvider",
        "fields": [
            {
                "env": "ANTHROPIC_API_KEY",
                "attr": "anthropic_api_key",
                "label": "API Key",
                "secret": True,
                "classification": "provider-credential",
            },
        ],
    },
    "openai": {
        "label": "OpenAI",
        "classification": "provider-credential",
        "criticality": "feature-required",
        "required_when": "Requis seulement si OpenAI est active comme provider.",
        "used_by": ["core", "playground", "orchestrate"],
        "module": "mascarade.router.providers.openai",
        "class": "OpenAIProvider",
        "fields": [
            {
                "env": "OPENAI_API_KEY",
                "attr": "openai_api_key",
                "label": "API Key",
                "secret": True,
                "classification": "provider-credential",
            },
        ],
    },
    "mistral": {
        "label": "Mistral AI",
        "classification": "provider-credential",
        "criticality": "feature-required",
        "required_when": "Requis seulement si Mistral est active comme provider.",
        "used_by": ["core", "playground", "orchestrate"],
        "module": "mascarade.router.providers.mistral",
        "class": "MistralProvider",
        "fields": [
            {
                "env": "MISTRAL_API_KEY",
                "attr": "mistral_api_key",
                "label": "API Key",
                "secret": True,
                "classification": "provider-credential",
            },
        ],
    },
    "codestral": {
        "label": "Mistral Codestral",
        "classification": "provider-credential",
        "criticality": "feature-required",
        "required_when": "Requis seulement si Codestral est active comme provider code/FIM.",
        "used_by": ["core", "cli-agents", "fim"],
        "module": "mascarade.router.providers.codestral",
        "class": "CodestralProvider",
        "fields": [
            {
                "env": "CODESTRAL_API_KEY",
                "attr": "codestral_api_key",
                "label": "API Key",
                "secret": True,
                "classification": "provider-credential",
            },
        ],
    },
    "google": {
        "label": "Google Gemini",
        "classification": "provider-credential",
        "criticality": "feature-required",
        "required_when": "Requis seulement si Google Gemini est active comme provider.",
        "used_by": ["core", "playground", "orchestrate"],
        "module": "mascarade.router.providers.google",
        "class": "GoogleProvider",
        "auth_mode": {
            "env": "GOOGLE_AUTH_MODE",
            "attr": "google_auth_mode",
            "default": "api_key",
            "options": ["api_key", "oauth_oidc", "adc"],
        },
        "fields": [
            {
                "env": "GOOGLE_API_KEY",
                "attr": "google_api_key",
                "label": "API Key",
                "secret": True,
                "auth_modes": ["api_key"],
                "classification": "provider-credential",
            },
            {
                "env": "GOOGLE_OAUTH_ACCESS_TOKEN",
                "attr": "google_oauth_access_token",
                "label": "OAuth access token",
                "secret": True,
                "auth_modes": ["oauth_oidc"],
                "classification": "provider-credential",
            },
            {
                "env": "GOOGLE_OAUTH_REFRESH_TOKEN",
                "attr": "google_oauth_refresh_token",
                "label": "OAuth refresh token",
                "secret": True,
                "auth_modes": ["oauth_oidc"],
                "classification": "provider-credential",
            },
            {
                "env": "GOOGLE_OAUTH_CLIENT_ID",
                "attr": "google_oauth_client_id",
                "label": "OAuth client ID",
                "secret": False,
                "auth_modes": ["oauth_oidc"],
                "classification": "oauth-config",
            },
            {
                "env": "GOOGLE_OAUTH_CLIENT_SECRET",
                "attr": "google_oauth_client_secret",
                "label": "OAuth client secret",
                "secret": True,
                "auth_modes": ["oauth_oidc"],
                "classification": "provider-credential",
            },
            {
                "env": "GOOGLE_OAUTH_TOKEN_ENDPOINT",
                "attr": "google_oauth_token_endpoint",
                "label": "OAuth token endpoint",
                "secret": False,
                "auth_modes": ["oauth_oidc"],
                "classification": "oauth-config",
                "criticality": "local-operator-context",
            },
            {
                "env": "GOOGLE_OAUTH_EXPIRES_AT",
                "attr": "google_oauth_expires_at",
                "label": "OAuth expires at",
                "secret": False,
                "auth_modes": ["oauth_oidc"],
                "classification": "oauth-config",
                "criticality": "local-operator-context",
            },
            {
                "env": "GOOGLE_CLOUD_PROJECT",
                "attr": "google_cloud_project",
                "label": "Google Cloud project",
                "secret": False,
                "auth_modes": ["oauth_oidc", "adc"],
                "classification": "operator-context",
            },
            {
                "env": "GOOGLE_CLOUD_LOCATION",
                "attr": "google_cloud_location",
                "label": "Google Cloud location",
                "secret": False,
                "auth_modes": ["oauth_oidc", "adc"],
                "classification": "operator-context",
            },
            {
                "env": "GOOGLE_APPLICATION_CREDENTIALS",
                "attr": "google_application_credentials",
                "label": "Application credentials path",
                "secret": False,
                "auth_modes": ["adc"],
                "classification": "operator-context",
            },
        ],
    },
    "bedrock": {
        "label": "AWS Bedrock",
        "classification": "provider-credential",
        "criticality": "feature-required",
        "required_when": "Requis seulement si AWS Bedrock est active comme provider.",
        "used_by": ["core", "playground", "orchestrate"],
        "module": "mascarade.router.providers.bedrock",
        "class": "BedrockProvider",
        "fields": [
            {
                "env": "AWS_ACCESS_KEY_ID",
                "attr": "aws_access_key_id",
                "label": "Access Key ID",
                "secret": True,
                "classification": "provider-credential",
            },
            {
                "env": "AWS_SECRET_ACCESS_KEY",
                "attr": "aws_secret_access_key",
                "label": "Secret Access Key",
                "secret": True,
                "classification": "provider-credential",
            },
        ],
    },
    "huggingface": {
        "label": "HuggingFace",
        "classification": "provider-credential",
        "criticality": "feature-required",
        "required_when": "Requis seulement si HuggingFace est active comme provider.",
        "used_by": ["core", "playground", "orchestrate", "ops-agent"],
        "module": "mascarade.router.providers.huggingface",
        "class": "HuggingFaceProvider",
        "auth_mode": {
            "env": "HUGGINGFACE_AUTH_MODE",
            "attr": "huggingface_auth_mode",
            "default": "api_key",
            "options": ["api_key", "oauth_oidc"],
        },
        "fields": [
            {
                "env": "HUGGINGFACE_API_KEY",
                "attr": "huggingface_api_key",
                "label": "API Key",
                "secret": True,
                "auth_modes": ["api_key"],
                "classification": "provider-credential",
            },
            {
                "env": "HUGGINGFACE_OAUTH_ACCESS_TOKEN",
                "attr": "huggingface_oauth_access_token",
                "label": "OAuth access token",
                "secret": True,
                "auth_modes": ["oauth_oidc"],
                "classification": "provider-credential",
            },
            {
                "env": "HUGGINGFACE_OAUTH_REFRESH_TOKEN",
                "attr": "huggingface_oauth_refresh_token",
                "label": "OAuth refresh token",
                "secret": True,
                "auth_modes": ["oauth_oidc"],
                "classification": "provider-credential",
            },
            {
                "env": "HUGGINGFACE_OAUTH_CLIENT_ID",
                "attr": "huggingface_oauth_client_id",
                "label": "OAuth client ID",
                "secret": False,
                "auth_modes": ["oauth_oidc"],
                "classification": "oauth-config",
            },
            {
                "env": "HUGGINGFACE_OAUTH_CLIENT_SECRET",
                "attr": "huggingface_oauth_client_secret",
                "label": "OAuth client secret",
                "secret": True,
                "auth_modes": ["oauth_oidc"],
                "classification": "provider-credential",
            },
            {
                "env": "HUGGINGFACE_OAUTH_TOKEN_ENDPOINT",
                "attr": "huggingface_oauth_token_endpoint",
                "label": "OAuth token endpoint",
                "secret": False,
                "auth_modes": ["oauth_oidc"],
                "classification": "oauth-config",
                "criticality": "local-operator-context",
            },
            {
                "env": "HUGGINGFACE_OAUTH_EXPIRES_AT",
                "attr": "huggingface_oauth_expires_at",
                "label": "OAuth expires at",
                "secret": False,
                "auth_modes": ["oauth_oidc"],
                "classification": "oauth-config",
                "criticality": "local-operator-context",
            },
        ],
    },
    "ollama": {
        "label": "Ollama (local)",
        "classification": "provider-credential",
        "criticality": "feature-required",
        "required_when": "Requis seulement si le provider local Ollama est active.",
        "used_by": ["core", "playground", "orchestrate"],
        "module": "mascarade.router.providers.ollama",
        "class": "OllamaProvider",
        "fields": [
            {
                "env": "OLLAMA_BASE_URL",
                "attr": "ollama_base_url",
                "label": "Base URL",
                "secret": False,
                "classification": "operator-context",
                "criticality": "local-operator-context",
            },
        ],
        "toggle": {"env": "OLLAMA_ENABLED", "attr": "ollama_enabled"},
    },
}


def resolve_provider_meta(name: str) -> dict:
    meta = PROVIDER_REGISTRY.get(name)
    if not meta:
        raise KeyError(name)
    return meta


def valid_provider_envs(meta: dict) -> set[str]:
    envs = {str(field["env"]) for field in meta["fields"]}
    auth_mode = meta.get("auth_mode")
    if auth_mode:
        envs.add(str(auth_mode["env"]))
    toggle = meta.get("toggle")
    if toggle:
        envs.add(str(toggle["env"]))
    return envs


def _mask(value: str) -> str:
    if not value or len(value) < 10:
        return "***" if value else ""
    return f"{value[:4]}...{value[-4:]}"


def _provider_auth_mode(meta: dict) -> str | None:
    auth_mode_meta = meta.get("auth_mode")
    if not auth_mode_meta:
        return None
    options = [str(option) for option in auth_mode_meta.get("options", [])]
    default = str(auth_mode_meta.get("default", options[0] if options else ""))
    raw_value = str(getattr(settings, auth_mode_meta["attr"], default)).strip()
    return raw_value if raw_value in options else default


def _field_is_active(field: dict, auth_mode: str | None) -> bool:
    auth_modes = [str(mode) for mode in field.get("auth_modes", [])]
    return not auth_modes or auth_mode is None or auth_mode in auth_modes


def _field_status(
    field: dict,
    auth_mode: str | None,
    default_criticality: str,
    default_classification: str,
) -> dict:
    value = str(getattr(settings, field["attr"], ""))
    configured = is_secret_configured(value) if field.get("secret") else bool(value.strip())
    return {
        "env": field["env"],
        "label": field["label"],
        "configured": configured,
        "hint": (
            _mask(value)
            if field.get("secret") and configured
            else value.strip() if configured else ""
        ),
        "secret": field.get("secret", False),
        "classification": str(field.get("classification", default_classification)),
        "criticality": str(field.get("criticality", default_criticality)),
        "auth_modes": [str(mode) for mode in field.get("auth_modes", [])],
        "active": _field_is_active(field, auth_mode),
    }


def _provider_is_configured(
    name: str,
    meta: dict,
    auth_mode: str | None,
    fields_status: list[dict],
) -> bool:
    active_fields = [field for field in fields_status if field["active"]]
    if meta.get("auth_mode") and not active_fields:
        return False

    if name == "huggingface":
        if auth_mode == "api_key":
            return is_secret_configured(settings.huggingface_api_key)
        return bool(
            settings.huggingface_oauth_client_id.strip()
            and is_secret_configured(settings.huggingface_oauth_client_secret)
            and (
                is_secret_configured(settings.huggingface_oauth_access_token)
                or is_secret_configured(settings.huggingface_oauth_refresh_token)
            )
        )

    if name == "google":
        if auth_mode == "api_key":
            return is_secret_configured(settings.google_api_key)
        if auth_mode == "oauth_oidc":
            return bool(
                settings.google_oauth_client_id.strip()
                and is_secret_configured(settings.google_oauth_client_secret)
                and (
                    is_secret_configured(settings.google_oauth_access_token)
                    or is_secret_configured(settings.google_oauth_refresh_token)
                )
            )
        return bool(
            settings.google_cloud_project.strip()
            and settings.google_application_credentials.strip()
        )

    return all(field["configured"] for field in active_fields)


def get_providers_status(router) -> list[dict]:
    active_names = set(router.available_providers)
    result = []

    for name, meta in PROVIDER_REGISTRY.items():
        auth_mode_meta = meta.get("auth_mode")
        auth_mode = _provider_auth_mode(meta)
        default_criticality = str(meta.get("criticality", "feature-required"))
        default_classification = str(meta.get("classification", "provider-credential"))
        fields_status = [
            _field_status(field, auth_mode, default_criticality, default_classification)
            for field in meta["fields"]
        ]
        all_configured = _provider_is_configured(name, meta, auth_mode, fields_status)

        toggle = meta.get("toggle")
        enabled = True
        if toggle:
            enabled = bool(getattr(settings, toggle["attr"], False))

        active = name in active_names
        provider_obj = router._providers.get(name)

        entry: dict = {
            "name": name,
            "label": meta["label"],
            "classification": default_classification,
            "criticality": default_criticality,
            "required_when": str(meta.get("required_when", "")),
            "used_by": [str(item) for item in meta.get("used_by", [])],
            "configured": all_configured and (enabled if toggle else True),
            "active": active,
            "fields": fields_status,
            "default_model": (
                getattr(provider_obj, "default_model", None) if provider_obj else None
            ),
            "models": provider_obj.available_models() if provider_obj else [],
        }

        if auth_mode_meta:
            entry["auth_mode"] = auth_mode
            entry["auth_mode_env"] = auth_mode_meta["env"]
            entry["auth_modes"] = list(auth_mode_meta.get("options", []))

        if toggle:
            entry["enabled"] = enabled
            entry["toggle_env"] = toggle["env"]

        result.append(entry)

    return result


def update_provider_keys(
    name: str,
    keys: dict[str, str],
    router,
    *,
    persist_env: bool = True,
) -> dict:
    try:
        meta = resolve_provider_meta(name)
    except KeyError:
        return {"error": f"Unknown provider: {name}"}

    valid_envs = valid_provider_envs(meta)
    for env_key in keys:
        if env_key not in valid_envs:
            return {"error": f"Unknown field: {env_key}"}

    auth_mode_meta = meta.get("auth_mode")
    if auth_mode_meta and auth_mode_meta["env"] in keys:
        auth_mode_value = keys[auth_mode_meta["env"]].strip()
        if auth_mode_value not in auth_mode_meta.get("options", []):
            return {"error": f"Invalid auth mode: {auth_mode_value}"}
        setattr(settings, auth_mode_meta["attr"], auth_mode_value)

    for field in meta["fields"]:
        if field["env"] in keys:
            setattr(settings, field["attr"], keys[field["env"]])

    if meta.get("toggle") and meta["toggle"]["env"] in keys:
        val = keys[meta["toggle"]["env"]]
        setattr(settings, meta["toggle"]["attr"], val.lower() in ("true", "1", "yes"))

    if persist_env:
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
            result = {"status": "ok", "active": True}
            if not persist_env:
                result["message"] = (
                    "Core runtime updated only; use the API facade for durable .env persistence"
                )
            return result

        router._providers.pop(name, None)
        result = {
            "status": "ok",
            "active": False,
            "message": "Saved but provider reports not configured",
        }
        if not persist_env:
            result["message"] = (
                "Core runtime updated only; use the API facade for durable .env persistence"
            )
        return result
    except Exception as exc:
        logger.warning("Failed to re-initialize %s: %s", name, exc)
        return {
            "status": "ok",
            "active": False,
            "message": f"Saved but init failed: {exc}",
        }


def _persist_env(updates: dict[str, str]) -> None:
    # SEC-02: Re-validate each key against the global provider allowlist
    # to prevent .env writes of arbitrary env vars via crafted payloads.
    all_valid_envs: set[str] = set()
    for meta in PROVIDER_REGISTRY.values():
        all_valid_envs |= valid_provider_envs(meta)
    for key in updates:
        if key not in all_valid_envs:
            raise ValueError(f"Refusing to persist unknown env key: {key}")

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
