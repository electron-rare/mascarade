"""OpenLLMetry integration — automatic OTel instrumentation of LLM provider calls.

Uses traceloop-sdk to auto-instrument supported LLM libraries (openai, anthropic,
mistralai, google-generativeai, litellm) and export traces to the existing OTel
collector configured via OTEL_EXPORTER_OTLP_ENDPOINT / OTEL_COLLECTOR_HTTP_ENDPOINT.

Falls back gracefully when traceloop-sdk is not installed — callers should guard
behind ``settings.openllmetry_enabled``.
"""

from __future__ import annotations

import logging
import os

from mascarade.config import settings

logger = logging.getLogger("mascarade.observability.openllmetry")

_INSTRUMENTED_LIBS = [
    "openai",
    "anthropic",
    "mistralai",
    "google_generativeai",
    "litellm",
]


def init_openllmetry() -> bool:
    """Initialize OpenLLMetry tracing via traceloop-sdk.

    Returns ``True`` if initialization succeeded, ``False`` otherwise.
    """
    try:
        from traceloop.sdk import Traceloop  # type: ignore[import-untyped]
    except ImportError:
        logger.warning(
            "traceloop-sdk not installed — skipping OpenLLMetry init. "
            "Install with: pip install mascarade-core[observability]"
        )
        return False

    # Resolve the OTLP endpoint: prefer the standard env var, fall back to config.
    endpoint = os.environ.get(
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        settings.otel_collector_http_endpoint,
    )

    # Traceloop reads standard OTel env vars; ensure they are set so the SDK
    # picks them up regardless of how mascarade was configured.
    if endpoint:
        os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", endpoint)

    os.environ.setdefault("OTEL_SERVICE_NAME", settings.otel_service_name)

    if settings.otel_resource_attributes:
        os.environ.setdefault("OTEL_RESOURCE_ATTRIBUTES", settings.otel_resource_attributes)

    if settings.otel_exporter_headers:
        # Convert "Key=Value,Key2=Value2" → "Key=Value,Key2=Value2" (already compatible)
        os.environ.setdefault("OTEL_EXPORTER_OTLP_HEADERS", settings.otel_exporter_headers)

    try:
        Traceloop.init(
            app_name=settings.otel_service_name,
            disable_batch=False,
        )
    except Exception:
        logger.exception("Failed to initialize OpenLLMetry")
        return False

    logger.info(
        "OpenLLMetry initialized — exporting to %s (service=%s)",
        endpoint,
        settings.otel_service_name,
    )
    return True
