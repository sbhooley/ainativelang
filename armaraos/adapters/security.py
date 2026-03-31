"""
ArmaraOS Security Adapter

Provides hooks for WASM sandbox, Merkle trails, and taint tracking.

This module is an integration-layer helper (not AINL core). It encodes
portable policy *hints* into the compiled IR (`ir["_security"]`) so emitters
and host runtimes can enforce sandboxing, taint tracking, and audit trails.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass
import uuid


@dataclass
class WASMSandboxConfig:
    """Configuration for WASM sandbox execution."""
    max_memory_mb: int = 256
    max_instructions: int = 10_000_000
    allowed_imports: List[str] = None
    blocked_syscalls: List[str] = None
    fuel_limit: Optional[int] = None  # for fuel metering

    def __post_init__(self) -> None:
        if self.allowed_imports is None:
            self.allowed_imports = ["env.print", "env.log"]
        if self.blocked_syscalls is None:
            self.blocked_syscalls = ["filesystem", "network", "process"]


class ArmaraOSSecurityAdapter:
    """Inject WASM sandbox hints + taint tracking into compiled AINL IR."""

    def __init__(self):
        self._taint_sources: Dict[str, uuid.UUID] = {}
        self._merkle_hooks: List[Callable] = []

    def apply_sandbox_policy(self, ir: Dict[str, Any]) -> Dict[str, Any]:
        """Inject WASM sandbox configuration into the AINL IR."""
        ir["_security"] = {
            "sandbox": "wasm",
            "wasm_config": WASMSandboxConfig().__dict__,
            "taint": {
                "sources": list(self._taint_sources.keys()),
                "tracking_enabled": True,
            },
            "merkle": {
                "hooks_enabled": True,
                "incremental": True,
            },
        }
        return ir

    def mark_taint_source(self, node_id: str, source_type: str) -> uuid.UUID:
        """Mark a graph node as a taint source."""
        taint_id = uuid.uuid4()
        self._taint_sources[node_id] = taint_id
        return taint_id

    def register_merkle_hook(self, hook: Callable[[Dict[str, Any]], None]) -> None:
        """Register a callback to be invoked for Merkle trail updates."""
        self._merkle_hooks.append(hook)

    def generate_wasm_sandbox_code(self, ir: Dict[str, Any]) -> str:
        """Generate WASM wrapper code for the compiled graph."""
        # This would produce a .wat or precompiled .wasm module that enforces policy.
        # For now, return a placeholder.
        return f"(;; ArmaraOS WASM sandbox for IR {ir.get('ir_version', 'unknown')} ;;)"

    def validate_taint_propagation(self, execution_log: List[Dict[str, Any]]) -> bool:
        """Ensure taint does not leak to unmarked outputs."""
        # Simple check: any output node that isn't marked as sanitized should not contain tainted data.
        # Implementation would track taint bits through the execution trace.
        return True  # placeholder


# Backward compatibility for older bridge code.
OpenFangSecurityAdapter = ArmaraOSSecurityAdapter
