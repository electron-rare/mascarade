"""Database models for RBAC multi-user authentication."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TypedDict

from pydantic import BaseModel, Field


# --- Enums ---


class RoleName(str, Enum):
    """User role types."""

    ADMIN = "admin"
    USER = "user"
    READ_ONLY = "read_only"


# --- Database Record Types (TypedDict for asyncpg records) ---


class UserRecord(TypedDict):
    """Database record for users table."""

    id: int
    username: str
    email: str
    role_id: int
    is_active: bool
    rate_limits: dict | None
    created_at: datetime
    updated_at: datetime


class RoleRecord(TypedDict):
    """Database record for roles table."""

    id: int
    name: str
    description: str
    permissions: dict
    rate_limits: dict
    created_at: datetime


class ApiKeyRecord(TypedDict):
    """Database record for api_keys table."""

    id: int
    user_id: int
    key_hash: str
    key_prefix: str
    name: str
    is_active: bool
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None


# --- Pydantic Models (API validation & serialization) ---


class Role(BaseModel):
    """Role model for API responses."""

    id: int
    name: str = Field(min_length=1, max_length=50)
    description: str = Field(max_length=500)
    permissions: dict = Field(default_factory=dict)
    rate_limits: dict = Field(default_factory=dict)
    created_at: datetime

    @classmethod
    def from_record(cls, record: RoleRecord) -> Role:
        """Create Role from database record."""
        return cls(
            id=record["id"],
            name=record["name"],
            description=record["description"],
            permissions=record["permissions"],
            rate_limits=record["rate_limits"],
            created_at=record["created_at"],
        )


class User(BaseModel):
    """User model for API responses."""

    id: int
    username: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=1, max_length=255)
    role_id: int
    is_active: bool = True
    rate_limits: dict | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, record: UserRecord) -> User:
        """Create User from database record."""
        return cls(
            id=record["id"],
            username=record["username"],
            email=record["email"],
            role_id=record["role_id"],
            is_active=record["is_active"],
            rate_limits=record["rate_limits"],
            created_at=record["created_at"],
            updated_at=record["updated_at"],
        )


class ApiKey(BaseModel):
    """API key model for API responses (excludes key_hash for security)."""

    id: int
    user_id: int
    key_prefix: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=200)
    is_active: bool = True
    created_at: datetime
    expires_at: datetime | None = None
    last_used_at: datetime | None = None

    @classmethod
    def from_record(cls, record: ApiKeyRecord) -> ApiKey:
        """Create ApiKey from database record (excludes sensitive key_hash)."""
        return cls(
            id=record["id"],
            user_id=record["user_id"],
            key_prefix=record["key_prefix"],
            name=record["name"],
            is_active=record["is_active"],
            created_at=record["created_at"],
            expires_at=record["expires_at"],
            last_used_at=record["last_used_at"],
        )


# --- Request Models ---


class UserCreate(BaseModel):
    """Request model for creating a new user."""

    username: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=1, max_length=255)
    role_id: int
    is_active: bool = True
    rate_limits: dict | None = None


class UserUpdate(BaseModel):
    """Request model for updating a user."""

    username: str | None = Field(default=None, min_length=1, max_length=100)
    email: str | None = Field(default=None, min_length=1, max_length=255)
    role_id: int | None = None
    is_active: bool | None = None
    rate_limits: dict | None = None


class ApiKeyCreate(BaseModel):
    """Request model for creating a new API key."""

    name: str = Field(min_length=1, max_length=200)
    expires_at: datetime | None = None


class ApiKeyCreateResponse(BaseModel):
    """Response model when creating an API key (includes the actual key once)."""

    api_key: ApiKey
    key: str = Field(
        description="The actual API key. This is only shown once and cannot be retrieved again."
    )
