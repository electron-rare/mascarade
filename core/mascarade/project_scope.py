"""Project-aware scope helpers for multi-project execution paths."""

from __future__ import annotations

from collections.abc import Iterable

from mascarade.config import settings

VALID_KNOWLEDGE_SCOPES = frozenset({"project", "federated"})


def normalize_scope(
    project_id: str | None = None,
    federation_scope: Iterable[str] | None = None,
    knowledge_scope: str = "project",
    *,
    require_project_id: bool = False,
    default_project_id: str | None = None,
) -> tuple[str, tuple[str, ...], str]:
    """Normalize project scoping inputs and enforce federation rules."""
    explicit_project = str(project_id or "").strip()
    if require_project_id and not explicit_project:
        raise ValueError("project_id is required")

    fallback_project = str(
        default_project_id or settings.mascarade_project_id or ""
    ).strip()
    normalized_project = explicit_project or fallback_project or "default"

    normalized_scope = str(knowledge_scope or "project").strip().lower() or "project"
    if normalized_scope not in VALID_KNOWLEDGE_SCOPES:
        raise ValueError(f"Unsupported knowledge_scope: {knowledge_scope}")

    normalized_federation = tuple(
        dict.fromkeys(
            item.strip()
            for item in (federation_scope or [])
            if isinstance(item, str) and item.strip()
        )
    )
    if normalized_scope == "federated":
        if not normalized_federation:
            raise ValueError(
                "federation_scope is required when knowledge_scope is federated"
            )
    else:
        normalized_federation = ()

    return normalized_project, normalized_federation, normalized_scope


def scoped_resource_key(
    namespace: str,
    resource_id: str,
    *,
    project_id: str | None = None,
    logical_scope: str | None = None,
) -> str:
    """Build a Redis/cache-safe scoped key."""
    normalized_project, _, _ = normalize_scope(project_id=project_id)
    parts = [namespace, normalized_project]
    if logical_scope:
        scope = logical_scope.strip()
        if scope:
            parts.append(scope)
    parts.append(resource_id)
    return ":".join(parts)


def scoped_principal_id(project_id: str, principal_id: str) -> str:
    """Namespace an external principal by project to prevent cross-project reuse."""
    return f"{project_id}:{principal_id}"
