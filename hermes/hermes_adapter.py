from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class HermesPaths:
    """Hermes host filesystem layout used by AINL emitters and shims."""

    hermes_root: Path

    @property
    def skills_root(self) -> Path:
        return self.hermes_root / "skills"

    @property
    def ainl_imports_root(self) -> Path:
        # Separate from the AINL pack installed by skills/hermes/install.sh (skills/ainl/).
        return self.skills_root / "ainl-imports"


def resolve_hermes_paths(*, hermes_root: Optional[Path] = None) -> HermesPaths:
    root = hermes_root or (Path.home() / ".hermes")
    return HermesPaths(hermes_root=root)


def default_emit_dir_for_skill_name(
    skill_name: str,
    *,
    hermes_root: Optional[Path] = None,
) -> Path:
    """Default drop-in install location for a compiled Hermes skill bundle."""

    safe = (skill_name or "ainl-skill").strip().replace("\\", "-").replace("/", "-")
    return resolve_hermes_paths(hermes_root=hermes_root).ainl_imports_root / safe

