"""Tests for enhanced config security (SecretStr, AWS Secrets Manager integration)."""

import os
from unittest.mock import patch

from pydantic import SecretStr

from mascarade.config import Settings, is_secret_configured


def test_secret_str_repr_does_not_leak():
    """SecretStr fields should not leak values in repr()."""
    settings = Settings(
        anthropic_api_key=SecretStr("sk-ant-secret-key-12345"),
        openai_api_key=SecretStr("sk-openai-secret-67890"),
    )

    repr_str = repr(settings)

    # Verify secrets are not in the repr output
    assert "sk-ant-secret-key-12345" not in repr_str
    assert "sk-openai-secret-67890" not in repr_str

    # Fields with repr=False should not appear in repr at all
    # (This is the desired behavior - complete omission from repr)
    assert "anthropic_api_key" not in repr_str
    assert "openai_api_key" not in repr_str


def test_secret_str_get_secret_value():
    """SecretStr.get_secret_value() should return the actual secret."""
    settings = Settings(
        anthropic_api_key=SecretStr("sk-ant-test-key"),
    )

    # Should be able to get the actual value when needed
    actual_value = settings.anthropic_api_key.get_secret_value()
    assert actual_value == "sk-ant-test-key"


def test_secret_str_field_repr_false():
    """Fields with repr=False should not appear in repr at all."""
    settings = Settings(
        anthropic_api_key=SecretStr("sk-ant-secret"),
        openai_api_key=SecretStr("sk-openai-secret"),
        database_url=SecretStr("postgresql://user:pass@localhost/db"),
    )

    repr_str = repr(settings)

    # Verify actual secret values don't leak
    assert "sk-ant-secret" not in repr_str
    assert "sk-openai-secret" not in repr_str
    assert "postgresql://user:pass@localhost/db" not in repr_str


def test_is_secret_configured_with_valid_secret():
    """is_secret_configured should return True for valid secrets."""
    assert is_secret_configured("sk-ant-valid-key-12345")
    assert is_secret_configured("actual-api-key-value")
    assert is_secret_configured("non-placeholder-secret")


def test_is_secret_configured_with_placeholder():
    """is_secret_configured should return False for placeholder values."""
    assert not is_secret_configured("")
    assert not is_secret_configured("sk-...")
    assert not is_secret_configured("sk-ant-...")
    assert not is_secret_configured("placeholder...")
    assert not is_secret_configured("   ")  # whitespace only


def test_is_secret_configured_with_secretstr():
    """is_secret_configured should handle SecretStr type."""
    valid_secret = SecretStr("sk-ant-real-key")
    placeholder_secret = SecretStr("sk-...")
    empty_secret = SecretStr("")

    assert is_secret_configured(valid_secret)
    assert not is_secret_configured(placeholder_secret)
    assert not is_secret_configured(empty_secret)


def test_aws_secrets_manager_config_fields():
    """AWS Secrets Manager configuration fields should be present."""
    settings = Settings()

    # Verify AWS Secrets Manager config fields exist
    assert hasattr(settings, "use_aws_secrets")
    assert hasattr(settings, "aws_secret_name")
    assert hasattr(settings, "aws_secrets_region")

    # Verify defaults
    assert settings.use_aws_secrets is False
    assert settings.aws_secret_name == ""
    assert settings.aws_secrets_region == "eu-west-1"


def test_aws_secrets_manager_config_from_env():
    """AWS Secrets Manager config can be loaded from environment."""
    with patch.dict(
        os.environ,
        {
            "USE_AWS_SECRETS": "true",
            "AWS_SECRET_NAME": "mascarade/prod/secrets",
            "AWS_SECRETS_REGION": "us-east-1",
        },
        clear=False,
    ):
        settings = Settings()

        assert settings.use_aws_secrets is True
        assert settings.aws_secret_name == "mascarade/prod/secrets"
        assert settings.aws_secrets_region == "us-east-1"


def test_all_sensitive_fields_use_secretstr():
    """All sensitive configuration fields should use SecretStr type."""
    settings = Settings()

    # Define fields that should be SecretStr
    sensitive_fields = [
        "anthropic_api_key",
        "openai_api_key",
        "mistral_api_key",
        "google_api_key",
        "huggingface_api_key",
        "huggingface_oauth_access_token",
        "huggingface_oauth_refresh_token",
        "huggingface_oauth_client_id",
        "huggingface_oauth_client_secret",
        "aws_access_key_id",
        "aws_secret_access_key",
        "aws_session_token",
        "google_oauth_access_token",
        "google_oauth_refresh_token",
        "google_oauth_client_id",
        "google_oauth_client_secret",
        "google_application_credentials",
        "memos_access_token",
        "docmost_password",
        "github_app_private_key",
        "database_url",
        "mascarade_api_key",
        "cluster_shared_key",
        "clickhouse_password",
        "litellm_master_key",
    ]

    # Verify each field is a SecretStr
    for field_name in sensitive_fields:
        field_value = getattr(settings, field_name)
        assert isinstance(
            field_value, SecretStr
        ), f"{field_name} should be SecretStr type"


def test_config_does_not_expose_secrets_in_str():
    """String representation should not expose secrets."""
    settings = Settings(
        anthropic_api_key=SecretStr("sk-ant-test-secret-123"),
        openai_api_key=SecretStr("sk-openai-test-secret-456"),
    )

    str_repr = str(settings)

    # Verify secrets don't leak in str()
    assert "sk-ant-test-secret-123" not in str_repr
    assert "sk-openai-test-secret-456" not in str_repr


def test_config_loads_from_env_file():
    """Configuration should load from .env file with SecretStr protection."""
    with patch.dict(
        os.environ,
        {
            "ANTHROPIC_API_KEY": "sk-ant-env-key",
            "OPENAI_API_KEY": "sk-openai-env-key",
            "DATABASE_URL": "postgresql://user:secret@host/db",
        },
        clear=False,
    ):
        settings = Settings()

        # Verify values are loaded
        assert settings.anthropic_api_key.get_secret_value() == "sk-ant-env-key"
        assert settings.openai_api_key.get_secret_value() == "sk-openai-env-key"
        assert (
            settings.database_url.get_secret_value()
            == "postgresql://user:secret@host/db"
        )

        # Verify they don't leak in repr
        repr_str = repr(settings)
        assert "sk-ant-env-key" not in repr_str
        assert "sk-openai-env-key" not in repr_str
        assert "user:secret" not in repr_str


def test_empty_secrets_are_handled_gracefully():
    """Empty or unset secrets should not cause errors."""
    settings = Settings(
        anthropic_api_key=SecretStr(""),
        openai_api_key=SecretStr(""),
    )

    # All secret fields should default to empty SecretStr
    assert isinstance(settings.anthropic_api_key, SecretStr)
    assert isinstance(settings.openai_api_key, SecretStr)

    # Should not raise errors
    assert settings.anthropic_api_key.get_secret_value() == ""
    assert settings.openai_api_key.get_secret_value() == ""


def test_aws_bedrock_credentials_use_secretstr():
    """AWS Bedrock credentials should use SecretStr."""
    settings = Settings(
        aws_access_key_id=SecretStr("AKIA..."),
        aws_secret_access_key=SecretStr("secret-access-key"),
        aws_session_token=SecretStr("session-token"),
    )

    # Verify types
    assert isinstance(settings.aws_access_key_id, SecretStr)
    assert isinstance(settings.aws_secret_access_key, SecretStr)
    assert isinstance(settings.aws_session_token, SecretStr)

    # Verify no leakage
    repr_str = repr(settings)
    assert "AKIA..." not in repr_str
    assert "secret-access-key" not in repr_str
    assert "session-token" not in repr_str


def test_oauth_tokens_use_secretstr():
    """OAuth tokens should use SecretStr for all providers."""
    settings = Settings(
        huggingface_oauth_access_token=SecretStr("hf-access-token"),
        huggingface_oauth_refresh_token=SecretStr("hf-refresh-token"),
        huggingface_oauth_client_secret=SecretStr("hf-client-secret"),
        google_oauth_access_token=SecretStr("google-access-token"),
        google_oauth_refresh_token=SecretStr("google-refresh-token"),
        google_oauth_client_secret=SecretStr("google-client-secret"),
    )

    repr_str = repr(settings)

    # Verify no OAuth secrets leak
    assert "hf-access-token" not in repr_str
    assert "hf-refresh-token" not in repr_str
    assert "hf-client-secret" not in repr_str
    assert "google-access-token" not in repr_str
    assert "google-refresh-token" not in repr_str
    assert "google-client-secret" not in repr_str


def test_cluster_shared_key_uses_secretstr():
    """Cluster shared key should use SecretStr."""
    settings = Settings(
        cluster_enabled=True,
        cluster_shared_key=SecretStr("cluster-secret-key-123"),
    )

    assert isinstance(settings.cluster_shared_key, SecretStr)
    repr_str = repr(settings)
    assert "cluster-secret-key-123" not in repr_str


def test_database_url_uses_secretstr():
    """Database URL should use SecretStr to protect credentials."""
    settings = Settings(
        database_url=SecretStr("postgresql://user:password@host:5432/dbname"),
    )

    assert isinstance(settings.database_url, SecretStr)

    repr_str = repr(settings)
    # Verify password doesn't leak
    assert "password" not in repr_str
    assert "postgresql://user:password@host" not in repr_str


def test_github_app_private_key_uses_secretstr():
    """GitHub App private key should use SecretStr."""
    settings = Settings(
        github_app_private_key=SecretStr("-----BEGIN RSA PRIVATE KEY-----\n..."),
    )

    assert isinstance(settings.github_app_private_key, SecretStr)

    repr_str = repr(settings)
    assert "BEGIN RSA PRIVATE KEY" not in repr_str


def test_litellm_master_key_uses_secretstr():
    """LiteLLM master key should use SecretStr."""
    settings = Settings(
        litellm_master_key=SecretStr("sk-litellm-master-key"),
    )

    assert isinstance(settings.litellm_master_key, SecretStr)

    repr_str = repr(settings)
    assert "sk-litellm-master-key" not in repr_str


def test_memos_access_token_uses_secretstr():
    """Memos access token should use SecretStr."""
    settings = Settings(
        memos_access_token=SecretStr("memos-token-12345"),
    )

    assert isinstance(settings.memos_access_token, SecretStr)

    repr_str = repr(settings)
    assert "memos-token-12345" not in repr_str


def test_config_extra_ignore():
    """Configuration should ignore extra fields without error."""
    # This tests the model_config extra='ignore'
    settings = Settings(
        unknown_field="should-be-ignored",
        another_unknown="also-ignored",
    )

    # Should not raise errors, and unknown fields should not be set
    assert not hasattr(settings, "unknown_field")
    assert not hasattr(settings, "another_unknown")
