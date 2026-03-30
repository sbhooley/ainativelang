"""OpenClaw Token Tracker Adapter for AINL.

Provides token usage statistics for the main direct session (agent:main:main).
"""
from __future__ import annotations
import os
import json
import subprocess
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from runtime.adapters.base import RuntimeAdapter

class OpenClawTokenTrackerAdapter(RuntimeAdapter):
    """Adapter for querying OpenClaw session token usage."""

    NAMESPACE = "openclaw_token_tracker"

    def __init__(self):
        self.openclaw_bin = os.getenv(
            "OPENCLAW_BIN",
            "/Users/clawdbot/.nvm/versions/node/v22.22.0/bin/openclaw"
        )
        self.cache_namespace = os.getenv("TOKEN_TRACKER_CACHE_NS", "workflow")
        self.cache_key = os.getenv("TOKEN_TRACKER_CACHE_KEY", "main_session_tokens")
        self.default_window_minutes = int(os.getenv("TOKEN_TRACKER_WINDOW_MINUTES", "60"))
        self.cache_ttl_seconds = int(os.getenv("TOKEN_TRACKER_CACHE_TTL", "300"))

    def run(self, method: str, *args, **kwargs) -> Any:
        if method == "RUN":
            return self.run_tracker()
        elif method == "ReadTokenStats":
            return self.read_token_stats()
        else:
            raise ValueError(f"Unknown method {method}")

    def run_tracker(self) -> Dict:
        """Main entry: compute token stats and update cache. Returns stats dict."""
        stats = self.compute_stats()
        if stats:
            self.write_cache(stats)
        return stats or {}

    def read_token_stats(self) -> Dict:
        """Read token stats from cache if fresh, else compute."""
        cached = self.read_cache()
        if cached:
            try:
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(cached["ts"].rstrip("Z"))).total_seconds()
                if age < self.cache_ttl_seconds:
                    return cached
            except Exception:
                pass
        # Cache miss or stale; compute and update
        stats = self.compute_stats()
        if stats:
            self.write_cache(stats)
        return stats or {}

    def compute_stats(self) -> Dict | None:
        """Query OpenClaw sessions CLI for main session token count."""
        try:
            result = subprocess.run(
                [self.openclaw_bin, "sessions", "--json", "--active", str(self.default_window_minutes)],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode != 0:
                return None
            data = json.loads(result.stdout)
            total_tokens = 0
            session_count = 0
            for s in data.get("sessions", []):
                key = s.get("key", "")
                parts = key.split(":")
                if len(parts) == 3 and parts[0] == "agent" and parts[1] == "main" and parts[2] == "main":
                    total_tokens += s.get("inputTokens", 0) or 0
                    session_count += 1
            return {
                "tokens": total_tokens,
                "sessions": session_count,
                "ts": datetime.now(timezone.utc).isoformat(),
                "source": "openclaw_sessions_cli",
            }
        except Exception:
            return None

    def read_cache(self) -> Optional[Dict]:
        try:
            result = subprocess.run(
                [self.openclaw_bin, "cache", "get", self.cache_namespace, self.cache_key],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                return None
            raw = result.stdout.strip()
            if not raw:
                return None
            return json.loads(raw)
        except Exception:
            return None

    def write_cache(self, stats: Dict) -> None:
        """Write stats to OpenClaw cache."""
        try:
            payload = {"tokens": stats["tokens"], "sessions": stats["sessions"], "ts": stats["ts"]}
            subprocess.run(
                [self.openclaw_bin, "cache", "set", self.cache_namespace, self.cache_key, json.dumps(payload)],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except Exception:
            pass

    def capabilities(self) -> Dict[str, Any]:
        return {"description": "Token tracking for OpenClaw main session"}
