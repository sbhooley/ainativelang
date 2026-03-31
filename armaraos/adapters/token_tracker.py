"""
ArmaraOS Token Tracker Adapter

Integrates ArmaraOS token metering with AINL's token budget system.
Provides Merkle audit trails for token consumption.
"""

from __future__ import annotations
import os
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
import time
import hashlib
import json
from pathlib import Path


@dataclass
class TokenUsage:
    """Record of token consumption for an ArmaraOS hand."""
    hand_id: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model: str
    timestamp: float
    merkle_proof: Optional[str] = None


class OpenFangTokenTracker:
    """Tracks token usage and produces Merkle audit trails."""

    def __init__(self, audit_log_path: str = None):
        self.audit_log_path = (
            audit_log_path
            or os.getenv("ARMARAOS_TOKEN_AUDIT")
            or os.getenv("OPENFANG_TOKEN_AUDIT")
            or "/var/log/armaraos/token_audit.jsonl"
        )
        self._ensure_log_dir()
        self._pending: List[TokenUsage] = []
        self._merkle_tree: List[str] = []  # simplified Merkle chain

    def _ensure_log_dir(self) -> None:
        log_dir = Path(self.audit_log_path).parent
        log_dir.mkdir(parents=True, exist_ok=True)

    def record_usage(self, usage: TokenUsage) -> None:
        """Record token consumption for a hand execution."""
        self._pending.append(usage)

    def flush(self) -> None:
        """Write pending usage records to audit log and compute Merkle trail."""
        if not self._pending:
            return

        with open(self.audit_log_path, 'a') as f:
            for usage in self._pending:
                entry = asdict(usage)
                # Compute simple Merkle proof (hash chain)
                prev_hash = self._merkle_tree[-1] if self._merkle_tree else ""
                data = json.dumps(entry, sort_keys=True)
                entry_hash = hashlib.sha256((prev_hash + data).encode()).hexdigest()
                entry["merkle_proof"] = entry_hash
                self._merkle_tree.append(entry_hash)
                f.write(json.dumps(entry) + "\n")
        self._pending.clear()

    def get_total_usage(self, hand_id: Optional[str] = None) -> Dict[str, int]:
        """Aggregate token usage from audit log."""
        totals = {"prompt": 0, "completion": 0, "total": 0}
        if not os.path.exists(self.audit_log_path):
            return totals
        with open(self.audit_log_path, 'r') as f:
            for line in f:
                entry = json.loads(line)
                if hand_id is None or entry.get("hand_id") == hand_id:
                    totals["prompt"] += entry.get("prompt_tokens", 0)
                    totals["completion"] += entry.get("completion_tokens", 0)
                    totals["total"] += entry.get("total_tokens", 0)
        return totals

    def verify_merkle_chain(self) -> bool:
        """Verify the integrity of the Merkle trail."""
        if not os.path.exists(self.audit_log_path):
            return True
        entries = []
        with open(self.audit_log_path, 'r') as f:
            for line in f:
                entries.append(json.loads(line))
        expected_prev = ""
        for entry in entries:
            proof = entry.get("merkle_proof", "")
            data = json.dumps({k: v for k, v in entry.items() if k != "merkle_proof"}, sort_keys=True)
            expected = hashlib.sha256((expected_prev + data).encode()).hexdigest()
            if proof != expected:
                return False
            expected_prev = proof
        return True
