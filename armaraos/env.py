from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _first_nonempty(*values: str | None) -> str | None:
    for v in values:
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return None


def _getenv_any(*names: str) -> str | None:
    return _first_nonempty(*[os.getenv(n) for n in names])


def _truthy(v: str | None) -> bool:
    if v is None:
        return False
    return str(v).strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class ArmaraOSEnv:
    workspace: Path
    memory_dir: Path
    memory_db: Path
    ir_cache_dir: Path
    monitor_cache_json: Path
    fs_root: Path
    token_audit_path: Path
    prefer_session_context: bool


def resolve_armaraos_env() -> ArmaraOSEnv:
    """
    Resolve ArmaraOS + AINL integration paths.

    Canonical vars are ARMARAOS_*, with AINL_* and OPENFANG_* supported as aliases
    for compatibility with older docs and forks.
    """
    ws_raw = _getenv_any("ARMARAOS_WORKSPACE", "OPENFANG_WORKSPACE")
    workspace = Path(ws_raw).expanduser() if ws_raw else (Path.home() / ".armaraos" / "workspace")

    mem_dir_raw = _getenv_any("ARMARAOS_MEMORY_DIR")
    memory_dir = Path(mem_dir_raw).expanduser() if mem_dir_raw else (workspace / "memory")

    db_raw = _getenv_any("ARMARAOS_MEMORY_DB", "AINL_MEMORY_DB", "OPENFANG_MEMORY_DB")
    memory_db = Path(db_raw).expanduser() if db_raw else (workspace / ".ainl" / "ainl_memory.sqlite3")

    ir_cache_raw = _getenv_any("AINL_IR_CACHE_DIR")
    ir_cache_dir = Path(ir_cache_raw).expanduser() if ir_cache_raw else (workspace / ".ainl" / "ir_cache")

    monitor_cache_raw = _getenv_any("MONITOR_CACHE_JSON")
    monitor_cache_json = (
        Path(monitor_cache_raw).expanduser()
        if monitor_cache_raw
        else (workspace / ".ainl" / "monitor_cache.json")
    )

    fs_root_raw = _getenv_any("AINL_FS_ROOT")
    fs_root = Path(fs_root_raw).expanduser() if fs_root_raw else workspace

    token_audit_raw = _getenv_any("ARMARAOS_TOKEN_AUDIT", "OPENFANG_TOKEN_AUDIT")
    token_audit_path = Path(token_audit_raw).expanduser() if token_audit_raw else Path("/var/log/armaraos/token_audit.jsonl")

    prefer_session_context = _truthy(
        _getenv_any("ARMARAOS_BOOTSTRAP_PREFER_SESSION_CONTEXT", "OPENFANG_BOOTSTRAP_PREFER_SESSION_CONTEXT")
    )

    return ArmaraOSEnv(
        workspace=workspace,
        memory_dir=memory_dir,
        memory_db=memory_db,
        ir_cache_dir=ir_cache_dir,
        monitor_cache_json=monitor_cache_json,
        fs_root=fs_root,
        token_audit_path=token_audit_path,
        prefer_session_context=prefer_session_context,
    )

