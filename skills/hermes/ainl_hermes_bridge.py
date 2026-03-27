from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


@dataclass(frozen=True)
class HermesBridgePaths:
    """
    Local filesystem bridge paths for Hermes Agent integration.

    Hermes Agent itself owns its internal memory/user-model storage.
    This helper stays file-based and host-agnostic:
    - ingest AINL trajectory/audit JSONL into a Hermes-readable file location
    - export an evolved skill stub back into .ainl for strict validation
    """

    hermes_root: Path

    @property
    def skills_dir(self) -> Path:
        return self.hermes_root / "skills"

    @property
    def memory_dir(self) -> Path:
        return self.hermes_root / "memory"

    @property
    def ainl_ingest_jsonl(self) -> Path:
        return self.memory_dir / "ainl_trajectories.jsonl"


def default_paths(home: Optional[Path] = None) -> HermesBridgePaths:
    h = home if home is not None else Path.home()
    return HermesBridgePaths(hermes_root=h / ".hermes")


def _iter_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    for raw in path.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if not s:
            continue
        obj = json.loads(s)
        if isinstance(obj, dict):
            yield obj


def ingest_ainl_trajectory_jsonl(
    trajectory_jsonl: Path,
    *,
    out_jsonl: Optional[Path] = None,
    home: Optional[Path] = None,
) -> Path:
    """
    Append AINL trajectory rows to a Hermes-friendly JSONL sink file.

    This intentionally preserves the original AINL event rows and only wraps them
    in a thin envelope so Hermes-side routines can key off `kind="ainl_trajectory"`.
    """
    paths = default_paths(home)
    out_path = out_jsonl if out_jsonl is not None else paths.ainl_ingest_jsonl
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for ev in _iter_jsonl(trajectory_jsonl):
        rows.append({"kind": "ainl_trajectory", "event": ev})

    with out_path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    return out_path


def export_hermes_skill_to_ainl(
    *,
    skill_name: str,
    out_ainl: Path,
    notes: str = "",
) -> Path:
    """
    Export a placeholder skill stub to `.ainl` so it can be validated with strict mode.

    Hermes "learning loop" artifacts are host-owned and may not be representable
    as a pure AINL graph automatically. This exporter provides the *bridge point*:
    Hermes can emit a concrete graph shape here when a deterministic workflow emerges.
    """
    header = f"# Hermes skill export stub: {skill_name}\n"
    if notes:
        header += f"# Notes: {notes}\n"

    body = """S app api /api
L1:
  R core.ECHO "hermes_export_stub" ->msg
  J msg
"""
    out_ainl.parent.mkdir(parents=True, exist_ok=True)
    out_ainl.write_text(header + "\n" + body, encoding="utf-8")
    return out_ainl

