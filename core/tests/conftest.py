"""Pytest configuration for Mascarade core tests."""

from __future__ import annotations

import sys
import types
from pathlib import Path

# Add project root to Python path so that deploy module can be imported
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


if "asyncpg" not in sys.modules:
    asyncpg_stub = types.ModuleType("asyncpg")
    asyncpg_stub.Pool = object
    asyncpg_stub.Record = dict

    async def _create_pool(*args, **kwargs):
        raise RuntimeError("asyncpg is not installed in the test environment")

    asyncpg_stub.create_pool = _create_pool
    sys.modules["asyncpg"] = asyncpg_stub
