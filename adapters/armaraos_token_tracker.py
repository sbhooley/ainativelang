"""ArmaraOS token tracker adapter.

This is a small bridge surface for writing token usage/audit entries to a JSONL log.
It is intentionally optional and file-based; no ArmaraOS CLI dependency.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List

from armaraos.env import resolve_armaraos_env
from runtime.adapters.base import RuntimeAdapter, AdapterError

logger = logging.getLogger(__name__)


class OpenFangTokenTrackerAdapter(RuntimeAdapter):
    """
    Adapter group: armaraos_token_tracker
    Verbs:
      - append_jsonl <obj>
      - append_usage <hand_id> <prompt_tokens> <completion_tokens> <model?>

    Note: class name kept for backward compatibility with earlier ArmaraOS/OpenFang bridge scripts.
    """

    def __init__(self, audit_log_path: str | None = None) -> None:
        env = resolve_armaraos_env()
        self.path = Path(
            audit_log_path
            or os.getenv("ARMARAOS_TOKEN_AUDIT")
            or os.getenv("OPENFANG_TOKEN_AUDIT")
            or str(env.token_audit_path)
        ).expanduser()

    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        verb = str(target or "").strip().lower()
        dry = context.get("dry_run") in (True, 1, "1", "true", "True", "yes") or os.getenv("AINL_DRY_RUN", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )

        if verb == "append_jsonl":
            if len(args) < 1:
                raise AdapterError("append_jsonl requires obj: dict|list|str")
            obj = args[0]
            if dry:
                logger.info("[dry_run] armaraos_token_tracker.append_jsonl — no write")
                return 1
            self._append_line(obj)
            return 1

        if verb == "append_usage":
            if len(args) < 3:
                raise AdapterError("append_usage requires hand_id, prompt_tokens, completion_tokens, [model]")
            hand_id = str(args[0])
            prompt_tokens = int(args[1])
            completion_tokens = int(args[2])
            model = str(args[3]) if len(args) >= 4 else ""
            entry = {
                "ts": time.time(),
                "hand_id": hand_id,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": int(prompt_tokens + completion_tokens),
                "model": model,
                "source": "ainl.armaraos_token_tracker",
            }
            if dry:
                logger.info("[dry_run] armaraos_token_tracker.append_usage — no write")
                return entry
            self._append_line(entry)
            return entry

        raise AdapterError(f"armaraos_token_tracker: unknown verb {verb!r}")

    def _append_line(self, obj: Any) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(obj, ensure_ascii=False)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


ArmaraOSTokenTrackerAdapter = OpenFangTokenTrackerAdapter

