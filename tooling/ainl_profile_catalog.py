"""Named AINL environment profiles (caps + host defaults).

Profiles are loaded from ``tooling/ainl_profiles.json`` next to this module.
"""
from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Any, Dict, List

_CATALOG_PATH = Path(__file__).resolve().parent / "ainl_profiles.json"


def _load_raw() -> Dict[str, Any]:
    if not _CATALOG_PATH.is_file():
        raise FileNotFoundError(f"missing profile catalog: {_CATALOG_PATH}")
    with open(_CATALOG_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_catalog() -> Dict[str, Any]:
    """Return full catalog including ``version`` and ``profiles``."""
    return _load_raw()


def list_profile_ids() -> List[str]:
    data = load_catalog()
    prof = data.get("profiles") or {}
    return sorted(prof.keys())


def get_profile(profile_id: str) -> Dict[str, Any]:
    """Return one profile dict (title, description, env, notes). Raises KeyError if unknown."""
    data = load_catalog()
    prof = data.get("profiles") or {}
    if profile_id not in prof:
        raise KeyError(profile_id)
    out = dict(prof[profile_id])
    out["id"] = profile_id
    return out


def emit_shell_exports(profile_id: str) -> str:
    """Bash/zsh ``export`` lines for profile env (values shell-quoted)."""
    p = get_profile(profile_id)
    env = p.get("env") or {}
    lines: List[str] = []
    for key in sorted(env.keys()):
        val = env[key]
        if val is None:
            continue
        lines.append(f"export {key}={shlex.quote(str(val))}")
    return "\n".join(lines) + ("\n" if lines else "")


def format_profile_text(profile_id: str) -> str:
    p = get_profile(profile_id)
    lines = [
        f"id: {profile_id}",
        f"title: {p.get('title', '')}",
        f"description: {p.get('description', '')}",
        "env:",
    ]
    env = p.get("env") or {}
    for k in sorted(env.keys()):
        lines.append(f"  {k}={env[k]}")
    notes = p.get("notes") or []
    if notes:
        lines.append("notes:")
        for n in notes:
            lines.append(f"  - {n}")
    return "\n".join(lines) + "\n"
