"""Pytest configuration for Mascarade core tests."""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to Python path so that deploy module can be imported
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
