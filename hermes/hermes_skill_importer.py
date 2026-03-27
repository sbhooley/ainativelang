from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional


@dataclass(frozen=True)
class HermesSkillBundle:
    """In-memory representation of a Hermes skill bundle (dir -> files)."""

    # Relative path (POSIX) -> file contents
    files: Mapping[str, str]


def _slugify(name: str) -> str:
    s = (name or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "ainl-skill"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# agentskills.io-friendly bundle metadata (emitter version, not graph IR version).
SKILL_BUNDLE_VERSION = "1.0.0"
DEFAULT_SKILL_CATEGORY = "ainl"
DEFAULT_SKILL_TAGS = ("ainl", "deterministic", "mcp")


def _yaml_double_quote(s: str) -> str:
    """Escape for a double-quoted YAML scalar."""
    return (s or "").replace("\\", "\\\\").replace('"', '\\"')


def render_hermes_skill_markdown(
    ir: Dict[str, Any],
    *,
    ainl_source: str,
    skill_name: str,
    source_stem: str,
) -> str:
    """Render a Hermes-friendly Markdown skill (agentskills-style frontmatter).

    The skill is designed to run deterministically by calling the AINL MCP tool
    `ainl_run` and to support a closed loop by producing replayable AINL source
    + canonical IR artifacts inside the bundle directory.
    """

    slug = _slugify(skill_name)
    ts = _utc_now_iso()
    checksum = (ir.get("graph_semantic_checksum") or "").strip()
    entry = ""
    try:
        labels = ir.get("labels") or {}
        if isinstance(labels, dict) and labels:
            entry = sorted(labels.keys(), key=lambda x: (len(str(x)), str(x)))[0]
    except Exception:
        entry = ""

    desc = (
        f"AINL-compiled Hermes skill ({source_stem}). Deterministic execution via AINL MCP `ainl_run`."
    )
    if checksum:
        desc += f" Graph checksum: {checksum}."

    tags_lines = "\n".join(f"  - {t}" for t in DEFAULT_SKILL_TAGS)

    # Note: Hermes Agent can invoke MCP tools directly; the SKILL.md instructs the host
    # to call the AINL MCP server tool `ainl_run` with the embedded source.
    frontmatter = "\n".join(
        [
            "---",
            f'name: "{skill_name}"',
            f'slug: "{slug}"',
            f'description: "{_yaml_double_quote(desc)}"',
            f'version: "{SKILL_BUNDLE_VERSION}"',
            f'category: "{DEFAULT_SKILL_CATEGORY}"',
            "tags:",
            tags_lines,
            'kind: "skill"',
            'format: "markdown"',
            f'generated_at_utc: "{ts}"',
            'compat: "agentskills.io"',
            "---",
            "",
        ]
    )

    body = []
    body.append(f"# {skill_name}")
    body.append("")
    body.append(desc)
    body.append("")
    body.append("## Deterministic runtime contract")
    body.append("")
    body.append(
        "- This skill **must** execute by calling the AINL MCP tool `ainl_run` (no ad-hoc reasoning steps that change control-flow)."
    )
    body.append(
        "- The canonical IR (`ir.json`) and source (`workflow.ainl`) are bundled to support strict replay + validation."
    )
    body.append("")
    body.append("## Run")
    body.append("")
    body.append("Call the MCP tool with the exact embedded source:")
    body.append("")
    body.append("```json")
    payload = {
        "code": ainl_source,
        "strict": True,
    }
    if entry:
        payload["label"] = entry
    body.append(json.dumps(payload, indent=2))
    body.append("```")
    body.append("")
    body.append("## Closed learning loop hooks")
    body.append("")
    body.append(
        "- **AINL audit tapes → Hermes memory**: run with `AINL_LOG_TRAJECTORY=1` (when using `ainl-run`) and ingest the produced JSONL via `skills/hermes/ainl_hermes_bridge.py`."
    )
    body.append(
        "- **Hermes-evolved trajectories → strict .ainl export**: export candidate improvements as `.ainl`, then validate with `ainl check --strict` before promotion."
    )
    body.append("")
    body.append("## Bundled artifacts")
    body.append("")
    body.append("- `workflow.ainl` — exact source used for compilation")
    body.append("- `ir.json` — canonical IR JSON (stable for deterministic execution)")
    body.append("- `SKILL.md` — this skill file")
    body.append("")
    body.append("## Bridge (optional)")
    body.append("")
    body.append(
        "For audit-tape → memory ingest, use the AINL Hermes skill pack bridge installed under "
        "`~/.hermes/skills/ainl/ainl_hermes_bridge.py` (via `skills/hermes/install.sh`). "
        "You can also copy bridge helpers into a `references/` subfolder inside this bundle if your host expects that layout."
    )
    body.append("")

    return frontmatter + "\n".join(body).rstrip() + "\n"


def build_hermes_skill_bundle(
    ir: Dict[str, Any],
    *,
    ainl_source: str,
    skill_name: str,
    source_stem: str,
) -> HermesSkillBundle:
    """Build a drop-in Hermes skill bundle directory payload."""

    skill_md = render_hermes_skill_markdown(
        ir,
        ainl_source=ainl_source,
        skill_name=skill_name,
        source_stem=source_stem,
    )

    files = {
        "SKILL.md": skill_md,
        "workflow.ainl": (ainl_source or "").rstrip() + "\n",
        "ir.json": json.dumps(ir, indent=2, ensure_ascii=False).rstrip() + "\n",
    }
    return HermesSkillBundle(files=files)

