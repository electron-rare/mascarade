"""Role-Based Access Control (RBAC) — Permission checking and validation."""

from __future__ import annotations

import logging
from typing import Any

from mascarade.db.models import Role, RoleName

logger = logging.getLogger("mascarade.rbac")

# Permission definitions for each resource type
# Structure: {"resource": ["action1", "action2", ...]}
VALID_PERMISSIONS = {
    "agents": ["read", "write", "delete", "use"],
    "providers": ["read", "write"],
    "users": ["read", "write", "delete"],
    "config": ["read", "write"],
    "usage": ["read"],
}


def check_permission(permissions: dict[str, list[str]], resource: str, action: str) -> bool:
    """
    Check if a permission set allows a specific action on a resource.

    Args:
        permissions: Permission dictionary from role (e.g., {"agents": ["read", "write"]})
        resource: Resource type to check (e.g., "agents", "users", "config")
        action: Action to perform (e.g., "read", "write", "delete", "use")

    Returns:
        True if the action is permitted, False otherwise

    Examples:
        >>> perms = {"agents": ["read", "use"], "providers": ["read"]}
        >>> check_permission(perms, "agents", "read")
        True
        >>> check_permission(perms, "agents", "write")
        False
        >>> check_permission(perms, "providers", "write")
        False
    """
    if not permissions or not isinstance(permissions, dict):
        logger.debug("Invalid permissions format: %s", type(permissions))
        return False

    if resource not in VALID_PERMISSIONS:
        logger.warning("Unknown resource type: %s", resource)
        return False

    if action not in VALID_PERMISSIONS[resource]:
        logger.warning("Invalid action '%s' for resource '%s'", action, resource)
        return False

    resource_permissions = permissions.get(resource, [])
    if not isinstance(resource_permissions, list):
        logger.debug("Invalid permissions for resource '%s': %s", resource, type(resource_permissions))
        return False

    has_permission = action in resource_permissions
    if not has_permission:
        logger.debug(
            "Permission denied: resource=%s, action=%s, allowed_actions=%s",
            resource,
            action,
            resource_permissions,
        )

    return has_permission


def has_admin_permission(permissions: dict[str, list[str]]) -> bool:
    """
    Check if permissions represent admin-level access.

    Admin role should have write/delete access to users and config.

    Args:
        permissions: Permission dictionary from role

    Returns:
        True if permissions represent admin access
    """
    if not permissions or not isinstance(permissions, dict):
        return False

    # Admin must have user management permissions
    user_perms = permissions.get("users", [])
    if "write" not in user_perms or "delete" not in user_perms:
        return False

    # Admin must have config write permissions
    config_perms = permissions.get("config", [])
    if "write" not in config_perms:
        return False

    return True


def validate_permissions(permissions: dict[str, list[str]]) -> tuple[bool, str | None]:
    """
    Validate that a permissions dictionary is well-formed.

    Args:
        permissions: Permission dictionary to validate

    Returns:
        Tuple of (is_valid, error_message)
        error_message is None if valid
    """
    if not isinstance(permissions, dict):
        return False, f"Permissions must be a dict, got {type(permissions).__name__}"

    for resource, actions in permissions.items():
        if resource not in VALID_PERMISSIONS:
            return False, f"Unknown resource: {resource}"

        if not isinstance(actions, list):
            return False, f"Actions for {resource} must be a list, got {type(actions).__name__}"

        for action in actions:
            if action not in VALID_PERMISSIONS[resource]:
                return False, f"Invalid action '{action}' for resource '{resource}'. Valid actions: {VALID_PERMISSIONS[resource]}"

    return True, None


def get_default_permissions(role_name: str | RoleName) -> dict[str, list[str]]:
    """
    Get default permissions for a role name.

    Args:
        role_name: Role name (admin, user, or read_only)

    Returns:
        Default permissions dictionary for the role

    Raises:
        ValueError: If role_name is not a valid role
    """
    if isinstance(role_name, str):
        try:
            role_name = RoleName(role_name)
        except ValueError:
            raise ValueError(f"Invalid role name: {role_name}. Valid roles: {[r.value for r in RoleName]}")

    if role_name == RoleName.ADMIN:
        return {
            "agents": ["read", "write", "delete", "use"],
            "providers": ["read", "write"],
            "users": ["read", "write", "delete"],
            "config": ["read", "write"],
            "usage": ["read"],
        }
    elif role_name == RoleName.USER:
        return {
            "agents": ["read", "use"],
            "providers": ["read"],
            "users": [],
            "config": [],
            "usage": [],
        }
    elif role_name == RoleName.READ_ONLY:
        return {
            "agents": ["read"],
            "providers": ["read"],
            "users": [],
            "config": [],
            "usage": ["read"],
        }
    else:
        raise ValueError(f"Unknown role: {role_name}")
