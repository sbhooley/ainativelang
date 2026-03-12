import re
import datetime as _dt
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from tooling.memory_bridge import DEFAULT_DB_PATH, ImportResult, import_records


JsonObject = Dict[str, Any]


def _now_iso() -> str:
    return _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _slugify_heading(text: str) -> str:
    slug = re.sub(r"[^\w]+", "_", text.strip().lower())
    slug = slug.strip("_")
    return slug or "section"


def _parse_memory_md_sections(text: str) -> List[Tuple[str, str]]:
    """
    Parse MEMORY.md-style file into (heading, body) sections.

    We treat '## ' headings as section delimiters and ignore the initial '# ' title.
    """
    lines = text.splitlines()
    sections: List[Tuple[str, List[str]]] = []
    current_heading: Optional[str] = None
    current_body: List[str] = []

    for line in lines:
        if line.startswith("## "):
            # Flush previous
            if current_heading is not None:
                sections.append((current_heading, current_body))
            current_heading = line[3:].strip()
            current_body = []
        else:
            if current_heading is not None:
                current_body.append(line)

    if current_heading is not None:
        sections.append((current_heading, current_body))

    result: List[Tuple[str, str]] = []
    for heading, body_lines in sections:
        body = "\n".join(body_lines).strip()
        if body:
            result.append((heading, body))
    return result


def _memory_md_to_envelopes(path: Path) -> List[JsonObject]:
    """
    Convert MEMORY.md into long_term.project_fact envelopes.

    Each '## ' section with non-empty body becomes one record. This is intentionally
    conservative and does not attempt semantic classification.
    """
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    sections = _parse_memory_md_sections(text)
    if not sections:
        return []

    now = _now_iso()
    envs: List[JsonObject] = []
    for heading, body in sections:
        rid = _slugify_heading(heading)
        payload: JsonObject = {"text": body}
        provenance: JsonObject = {
            "source_system": "legacy_markdown",
            "origin_uri": str(path),
            "authored_by": "human",
            "confidence": None,
        }
        flags: JsonObject = {
            "authoritative": False,
            "ephemeral": False,
            "curated": False,
        }
        envs.append(
            {
                "namespace": "long_term",
                "record_kind": "long_term.project_fact",
                "record_id": f"memory_md.{rid}",
                "created_at": now,
                "updated_at": now,
                "ttl_seconds": None,
                "payload": payload,
                "provenance": provenance,
                "flags": flags,
            }
        )
    return envs


_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})\.md$")


def _parse_legacy_daily_log_file(path: Path) -> Optional[JsonObject]:
    """
    Convert a legacy memory/YYYY-MM-DD.md file into a daily_log.note envelope.
    """
    m = _DATE_RE.match(path.name)
    if not m:
        return None
    record_id = path.name[:-3]
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    entries: List[JsonObject] = []
    for line in lines:
        raw = line.strip()
        if not raw or raw == "---":
            continue
        ts: Optional[str] = None
        content = raw
        # Simple pattern: "- [timestamp] text" or "[timestamp] text"
        if raw.startswith("- [") and "]" in raw:
            prefix, rest = raw[2:].split("]", 1)
            ts = prefix.lstrip("[").strip()
            content = rest.strip()
        elif raw.startswith("[") and "]" in raw:
            prefix, rest = raw.split("]", 1)
            ts = prefix.lstrip("[").strip()
            content = rest.strip()
        elif raw.startswith("- "):
            content = raw[2:].strip()

        entries.append(
            {
                "ts": ts,
                "text": content,
            }
        )

    now = _now_iso()
    payload: JsonObject = {"entries": entries} if entries else {"entries": []}
    provenance: JsonObject = {
        "source_system": "legacy_markdown",
        "origin_uri": str(path),
        "authored_by": "human",
        "confidence": None,
    }
    flags: JsonObject = {
        "authoritative": False,
        "ephemeral": False,
        "curated": False,
    }
    return {
        "namespace": "daily_log",
        "record_kind": "daily_log.note",
        "record_id": record_id,
        "created_at": now,
        "updated_at": now,
        "ttl_seconds": None,
        "payload": payload,
        "provenance": provenance,
        "flags": flags,
    }


def _daily_logs_to_envelopes(root: Path) -> List[JsonObject]:
    """
    Collect envelopes from legacy memory/YYYY-MM-DD.md files under a directory.
    """
    if not root.is_dir():
        return []
    envs: List[JsonObject] = []
    for p in root.iterdir():
        if p.is_file() and _DATE_RE.match(p.name):
            env = _parse_legacy_daily_log_file(p)
            if env is not None:
                envs.append(env)
    return envs


def migrate_legacy_memory(
    db_path: Optional[str],
    memory_md: Optional[Path],
    daily_log_dir: Optional[Path],
) -> ImportResult:
    """
    Migrate legacy MEMORY.md and memory/YYYY-MM-DD.md files into the SQLite-backed
    memory store, using the existing JSON envelope import path.
    """
    envs: List[JsonObject] = []
    if memory_md is not None:
        envs.extend(_memory_md_to_envelopes(memory_md))
    if daily_log_dir is not None:
        envs.extend(_daily_logs_to_envelopes(daily_log_dir))

    if not envs:
        # No-op migration; return a successful, empty result
        return ImportResult(ok=True, inserted=0, updated=0, errors=[])

    return import_records(db_path or DEFAULT_DB_PATH, envs)

