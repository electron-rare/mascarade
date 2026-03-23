"""Mascarade P2P layer — auto-selects backend.

Priority:
  1. libp2p (trio-based) — if libp2p + trio + multiaddr are installed
  2. asyncio native       — pure-Python fallback (always available)

Both backends expose the same interface to ClusterManager.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("mascarade.p2p")

# Detect available backend
_LIBP2P_AVAILABLE = False
try:
    import libp2p  # noqa: F401
    import multiaddr  # noqa: F401
    import trio  # noqa: F401

    _LIBP2P_AVAILABLE = True
except ImportError:
    pass

if _LIBP2P_AVAILABLE:
    from mascarade.p2p.libp2p_node import P2PNode, P2PPeer  # noqa: F401

    BACKEND = "libp2p"
    logger.info("P2P backend: libp2p (trio)")
else:
    logger.info("P2P backend: asyncio (libp2p not available)")

# Always export the asyncio node for direct use
from mascarade.p2p.asyncio_node import MascaradeP2PNode  # noqa: F401
from mascarade.p2p.identity import PeerIdentity  # noqa: F401

if not _LIBP2P_AVAILABLE:
    BACKEND = "asyncio"

__all__ = [
    "BACKEND",
    "MascaradeP2PNode",
    "PeerIdentity",
]
if _LIBP2P_AVAILABLE:
    __all__ += ["P2PNode", "P2PPeer"]
