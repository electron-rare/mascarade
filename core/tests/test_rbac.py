"""Tests pour la logique RBAC (Role-Based Access Control)."""

import pytest

from mascarade.db.models import RoleName
from mascarade.rbac import (
    VALID_PERMISSIONS,
    check_permission,
    get_default_permissions,
    has_admin_permission,
    validate_permissions,
)


class TestCheckPermission:
    """Tests pour la fonction check_permission."""

    def test_valid_permission_granted(self):
        """Vérifie qu'une permission valide est accordée."""
        permissions = {"agents": ["read", "use"], "providers": ["read"]}
        assert check_permission(permissions, "agents", "read") is True
        assert check_permission(permissions, "agents", "use") is True
        assert check_permission(permissions, "providers", "read") is True

    def test_valid_permission_denied(self):
        """Vérifie qu'une permission non accordée est refusée."""
        permissions = {"agents": ["read", "use"], "providers": ["read"]}
        assert check_permission(permissions, "agents", "write") is False
        assert check_permission(permissions, "agents", "delete") is False
        assert check_permission(permissions, "providers", "write") is False

    def test_resource_not_in_permissions(self):
        """Vérifie le comportement quand la ressource n'est pas dans les permissions."""
        permissions = {"agents": ["read"]}
        assert check_permission(permissions, "users", "read") is False
        assert check_permission(permissions, "config", "write") is False

    def test_unknown_resource_type(self):
        """Vérifie qu'un type de ressource inconnu est rejeté."""
        permissions = {"unknown_resource": ["read"]}
        assert check_permission(permissions, "unknown_resource", "read") is False

    def test_invalid_action_for_resource(self):
        """Vérifie qu'une action invalide pour une ressource est rejetée."""
        permissions = {"agents": ["read", "invalid_action"]}
        assert check_permission(permissions, "agents", "invalid_action") is False

    def test_empty_permissions(self):
        """Vérifie le comportement avec des permissions vides."""
        assert check_permission({}, "agents", "read") is False
        assert check_permission({}, "users", "write") is False

    def test_none_permissions(self):
        """Vérifie le comportement avec des permissions None."""
        assert check_permission(None, "agents", "read") is False

    def test_invalid_permissions_type(self):
        """Vérifie le comportement avec un type de permissions invalide."""
        assert check_permission("not_a_dict", "agents", "read") is False
        assert check_permission([], "agents", "read") is False
        assert check_permission(123, "agents", "read") is False

    def test_invalid_resource_permissions_type(self):
        """Vérifie le comportement quand les permissions d'une ressource ne sont pas une liste."""
        permissions = {"agents": "not_a_list"}
        assert check_permission(permissions, "agents", "read") is False

        permissions = {"agents": {"read": True}}
        assert check_permission(permissions, "agents", "read") is False

    def test_all_valid_resources_and_actions(self):
        """Vérifie toutes les combinaisons valides de ressources et actions."""
        # Create full admin permissions
        permissions = {
            resource: actions.copy() for resource, actions in VALID_PERMISSIONS.items()
        }

        for resource, actions in VALID_PERMISSIONS.items():
            for action in actions:
                assert check_permission(permissions, resource, action) is True


class TestHasAdminPermission:
    """Tests pour la fonction has_admin_permission."""

    def test_admin_permissions_valid(self):
        """Vérifie qu'un ensemble de permissions admin valide est reconnu."""
        admin_perms = {
            "agents": ["read", "write", "delete", "use"],
            "providers": ["read", "write"],
            "users": ["read", "write", "delete"],
            "config": ["read", "write"],
            "usage": ["read"],
        }
        assert has_admin_permission(admin_perms) is True

    def test_admin_permissions_minimal(self):
        """Vérifie qu'un ensemble minimal de permissions admin est reconnu."""
        # Minimal admin: just the required user and config permissions
        minimal_admin = {
            "users": ["write", "delete"],
            "config": ["write"],
        }
        assert has_admin_permission(minimal_admin) is True

    def test_missing_user_write_permission(self):
        """Vérifie qu'un admin sans permission write sur users est rejeté."""
        perms = {
            "users": ["delete"],  # Missing "write"
            "config": ["write"],
        }
        assert has_admin_permission(perms) is False

    def test_missing_user_delete_permission(self):
        """Vérifie qu'un admin sans permission delete sur users est rejeté."""
        perms = {
            "users": ["write"],  # Missing "delete"
            "config": ["write"],
        }
        assert has_admin_permission(perms) is False

    def test_missing_config_write_permission(self):
        """Vérifie qu'un admin sans permission write sur config est rejeté."""
        perms = {
            "users": ["write", "delete"],
            "config": ["read"],  # Missing "write"
        }
        assert has_admin_permission(perms) is False

    def test_user_permissions_not_admin(self):
        """Vérifie que les permissions user ne sont pas reconnues comme admin."""
        user_perms = {
            "agents": ["read", "use"],
            "providers": ["read"],
        }
        assert has_admin_permission(user_perms) is False

    def test_read_only_permissions_not_admin(self):
        """Vérifie que les permissions read_only ne sont pas reconnues comme admin."""
        read_only_perms = {
            "agents": ["read"],
            "providers": ["read"],
            "usage": ["read"],
        }
        assert has_admin_permission(read_only_perms) is False

    def test_empty_permissions_not_admin(self):
        """Vérifie que des permissions vides ne sont pas admin."""
        assert has_admin_permission({}) is False

    def test_none_permissions_not_admin(self):
        """Vérifie que None n'est pas considéré comme admin."""
        assert has_admin_permission(None) is False

    def test_invalid_type_not_admin(self):
        """Vérifie qu'un type invalide n'est pas considéré comme admin."""
        assert has_admin_permission("not_a_dict") is False
        assert has_admin_permission([]) is False


class TestValidatePermissions:
    """Tests pour la fonction validate_permissions."""

    def test_valid_admin_permissions(self):
        """Vérifie que les permissions admin sont valides."""
        admin_perms = {
            "agents": ["read", "write", "delete", "use"],
            "providers": ["read", "write"],
            "users": ["read", "write", "delete"],
            "config": ["read", "write"],
            "usage": ["read"],
        }
        is_valid, error = validate_permissions(admin_perms)
        assert is_valid is True
        assert error is None

    def test_valid_user_permissions(self):
        """Vérifie que les permissions user sont valides."""
        user_perms = {
            "agents": ["read", "use"],
            "providers": ["read"],
        }
        is_valid, error = validate_permissions(user_perms)
        assert is_valid is True
        assert error is None

    def test_valid_empty_permissions(self):
        """Vérifie que des permissions vides sont valides."""
        is_valid, error = validate_permissions({})
        assert is_valid is True
        assert error is None

    def test_invalid_permissions_not_dict(self):
        """Vérifie qu'un type non-dict est invalide."""
        is_valid, error = validate_permissions("not_a_dict")
        assert is_valid is False
        assert "must be a dict" in error

        is_valid, error = validate_permissions([])
        assert is_valid is False
        assert "must be a dict" in error

        is_valid, error = validate_permissions(None)
        assert is_valid is False
        assert "must be a dict" in error

    def test_invalid_unknown_resource(self):
        """Vérifie qu'une ressource inconnue est invalide."""
        perms = {"unknown_resource": ["read"]}
        is_valid, error = validate_permissions(perms)
        assert is_valid is False
        assert "Unknown resource" in error
        assert "unknown_resource" in error

    def test_invalid_actions_not_list(self):
        """Vérifie que des actions non-liste sont invalides."""
        perms = {"agents": "read"}
        is_valid, error = validate_permissions(perms)
        assert is_valid is False
        assert "must be a list" in error
        assert "agents" in error

        perms = {"agents": {"read": True}}
        is_valid, error = validate_permissions(perms)
        assert is_valid is False
        assert "must be a list" in error

    def test_invalid_action_for_resource(self):
        """Vérifie qu'une action invalide pour une ressource est rejetée."""
        perms = {"agents": ["read", "invalid_action"]}
        is_valid, error = validate_permissions(perms)
        assert is_valid is False
        assert "Invalid action" in error
        assert "invalid_action" in error
        assert "agents" in error

    def test_valid_single_resource_single_action(self):
        """Vérifie qu'une seule ressource avec une seule action est valide."""
        perms = {"agents": ["read"]}
        is_valid, error = validate_permissions(perms)
        assert is_valid is True
        assert error is None

    def test_all_valid_permissions(self):
        """Vérifie que toutes les permissions valides sont acceptées."""
        # Build a permissions dict with all valid combinations
        all_perms = {
            resource: actions.copy() for resource, actions in VALID_PERMISSIONS.items()
        }
        is_valid, error = validate_permissions(all_perms)
        assert is_valid is True
        assert error is None


class TestGetDefaultPermissions:
    """Tests pour la fonction get_default_permissions."""

    def test_admin_default_permissions(self):
        """Vérifie les permissions par défaut pour le rôle admin."""
        perms = get_default_permissions(RoleName.ADMIN)

        assert perms["agents"] == ["read", "write", "delete", "use"]
        assert perms["providers"] == ["read", "write"]
        assert perms["users"] == ["read", "write", "delete"]
        assert perms["config"] == ["read", "write"]
        assert perms["usage"] == ["read"]

        # Verify it's admin
        assert has_admin_permission(perms) is True

    def test_user_default_permissions(self):
        """Vérifie les permissions par défaut pour le rôle user."""
        perms = get_default_permissions(RoleName.USER)

        assert perms["agents"] == ["read", "use"]
        assert perms["providers"] == ["read"]
        assert perms["users"] == []
        assert perms["config"] == []
        assert perms["usage"] == []

        # Verify it's not admin
        assert has_admin_permission(perms) is False

    def test_read_only_default_permissions(self):
        """Vérifie les permissions par défaut pour le rôle read_only."""
        perms = get_default_permissions(RoleName.READ_ONLY)

        assert perms["agents"] == ["read"]
        assert perms["providers"] == ["read"]
        assert perms["users"] == []
        assert perms["config"] == []
        assert perms["usage"] == ["read"]

        # Verify it's not admin
        assert has_admin_permission(perms) is False

    def test_admin_string_role_name(self):
        """Vérifie qu'un nom de rôle string 'admin' fonctionne."""
        perms = get_default_permissions("admin")
        assert perms["users"] == ["read", "write", "delete"]
        assert has_admin_permission(perms) is True

    def test_user_string_role_name(self):
        """Vérifie qu'un nom de rôle string 'user' fonctionne."""
        perms = get_default_permissions("user")
        assert perms["agents"] == ["read", "use"]
        assert has_admin_permission(perms) is False

    def test_read_only_string_role_name(self):
        """Vérifie qu'un nom de rôle string 'read_only' fonctionne."""
        perms = get_default_permissions("read_only")
        assert perms["agents"] == ["read"]
        assert has_admin_permission(perms) is False

    def test_invalid_string_role_name(self):
        """Vérifie qu'un nom de rôle invalide lève une ValueError."""
        with pytest.raises(ValueError, match="Invalid role name"):
            get_default_permissions("invalid_role")

        with pytest.raises(ValueError, match="Invalid role name"):
            get_default_permissions("superuser")

    def test_default_permissions_are_valid(self):
        """Vérifie que toutes les permissions par défaut sont valides."""
        for role in RoleName:
            perms = get_default_permissions(role)
            is_valid, error = validate_permissions(perms)
            assert (
                is_valid is True
            ), f"Default permissions for {role.value} are invalid: {error}"


class TestValidPermissionsConstant:
    """Tests pour la constante VALID_PERMISSIONS."""

    def test_all_resources_defined(self):
        """Vérifie que toutes les ressources attendues sont définies."""
        expected_resources = {"agents", "providers", "users", "config", "usage"}
        assert set(VALID_PERMISSIONS.keys()) == expected_resources

    def test_agents_actions(self):
        """Vérifie les actions valides pour agents."""
        assert VALID_PERMISSIONS["agents"] == ["read", "write", "delete", "use"]

    def test_providers_actions(self):
        """Vérifie les actions valides pour providers."""
        assert VALID_PERMISSIONS["providers"] == ["read", "write"]

    def test_users_actions(self):
        """Vérifie les actions valides pour users."""
        assert VALID_PERMISSIONS["users"] == ["read", "write", "delete"]

    def test_config_actions(self):
        """Vérifie les actions valides pour config."""
        assert VALID_PERMISSIONS["config"] == ["read", "write"]

    def test_usage_actions(self):
        """Vérifie les actions valides pour usage."""
        assert VALID_PERMISSIONS["usage"] == ["read"]
