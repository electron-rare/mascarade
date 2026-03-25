#!/usr/bin/env python3
"""Quick test for AgentRegistry metrics tracking."""

import sys

sys.path.insert(0, "./core")

from mascarade.agents.registry import AgentRegistry

registry = AgentRegistry()
print("OK")
