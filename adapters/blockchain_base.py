"""
Abstract base for chain-specific runtime adapters.

Concrete adapters (e.g. ``SolanaAdapter``) subclass :class:`BlockchainAdapterBase`
and implement :meth:`RuntimeAdapter.call` with lazy imports for optional
third-party RPC/SDK packages.

**Future EVM sketch (no implementation here):**

.. code-block:: python

    # class EVMAdapter(BlockchainAdapterBase):
    #     @property
    #     def chain_family(self) -> str:
    #         return \"evm\"
    #
    #     def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
    #         # Verbs: ETH_CALL, SEND_RAW_TX, GET_BALANCE, CALL (contract), QUERY (read-only batch)
    #         # — lazy-import web3/eth_account; same RuntimeAdapter.call / call_async pattern.
    #         raise NotImplementedError
    #
    # Register in AdapterRegistry as \"evm\" so strict DSL can use R evm.CALL / R evm.QUERY
    # (first-dot split) alongside other adapters.

Register as ``evm`` in :class:`runtime.adapters.base.AdapterRegistry` when implemented.
"""

from __future__ import annotations

from abc import ABC
from typing import Any, Dict, List

from runtime.adapters.base import RuntimeAdapter


class BlockchainAdapterBase(RuntimeAdapter, ABC):
    """Marker base for blockchain RPC adapters; keeps a stable extension point for EVM and others."""

    @property
    def chain_family(self) -> str:
        """Short identifier (e.g. ``solana``, ``evm``) for logging and policy hints."""
        return "unknown"

    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        raise NotImplementedError
