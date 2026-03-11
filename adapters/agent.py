import json
import os
from pathlib import Path
from typing import Any, Dict, List

from runtime.adapters.base import RuntimeAdapter, AdapterError


class AgentAdapter(RuntimeAdapter):
  """Extension/OpenClaw agent coordination adapter (local, file-backed).

  This adapter is:
  - extension-level and noncanonical,
  - local-only and file-backed,
  - sandboxed under AINL_AGENT_ROOT (default: /tmp/ainl_agents).
  """

  def _root(self) -> Path:
    raw = os.getenv("AINL_AGENT_ROOT", "/tmp/ainl_agents")
    root = Path(raw).resolve()
    # Disallow using filesystem root as sandbox; that defeats the boundary.
    if root == root.root:
      raise AdapterError("AINL_AGENT_ROOT must not be filesystem root")
    root.mkdir(parents=True, exist_ok=True)
    return root

  def _safe_path(self, rel: str) -> Path:
    root = self._root()
    target = (root / str(rel)).resolve()
    if target != root and root not in target.parents:
      raise AdapterError("agent path escapes AINL_AGENT_ROOT sandbox")
    return target

  def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
    verb = (target or "").strip()

    if verb == "send_task":
      if not args:
        raise AdapterError("agent.send_task requires at least one argument (task envelope)")

      envelope = args[0]
      if not isinstance(envelope, dict):
        raise AdapterError("agent.send_task expects first argument to be a JSON object envelope")

      # Tasks file path is fixed by convention; callers should not control it.
      path = self._safe_path("tasks/openclaw_agent_tasks.jsonl")

      try:
        line = json.dumps(envelope, sort_keys=True)
      except Exception as e:
        raise AdapterError(f"agent.send_task could not serialize envelope: {e}") from e

      path.parent.mkdir(parents=True, exist_ok=True)
      with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")

      task_id = str(envelope.get("task_id") or "")
      return task_id

    if verb == "read_result":
      if not args:
        raise AdapterError("agent.read_result requires task_id")
      task_id = str(args[0])
      # Treat task_id as an identifier, not a path fragment.
      if "/" in task_id or ".." in task_id:
        raise AdapterError("agent.read_result task_id must not contain path separators")
      rel_path = f"results/{task_id}.json"
      path = self._safe_path(rel_path)
      if not path.exists() or not path.is_file():
        raise AdapterError("agent.read_result target does not exist")
      try:
        data = json.loads(path.read_text(encoding="utf-8"))
      except Exception as e:
        raise AdapterError(f"agent.read_result failed to parse JSON: {e}") from e
      if not isinstance(data, dict):
        raise AdapterError("agent.read_result expects JSON object result")
      return data

    raise AdapterError(f"agent supports only send_task/read_result (got {target!r})")
