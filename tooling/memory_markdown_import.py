import datetime as _dt
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from tooling.memory_bridge import DEFAULT_DB_PATH, ImportResult, import_records


SUPPORTED_KINDS: Tuple[Tuple[str, str], ...] = (
    ("long_term", "long_term.project_fact"),
    ("long_term", "long_term.user_preference"),
)


def _parse_frontmatter_and_body(text: str) -> Tuple[Dict[str, str], str]:
    """
    Very small frontmatter parser.

    Expects:
    ---
    key: value
    ...
    ---
    <markdown body>
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text

    fm: Dict[str, str] = {}
    i = 1
    while i < len(lines):
        line = lines[i]
        if line.strip() == "---":
            i += 1
            break
        if ":" in line:
            key, val = line.split(":", 1)
            fm[key.strip()] = val.strip()
        i += 1

    body = "\n".join(lines[i:])
    return fm, body


def _bool_from_frontmatter(val: Optional[str]) -> Optional[bool]:
    if val is None:
        return None
    v = val.strip().lower()
    if v in {"true", "yes", "1"}:
        return True
    if v in {"false", "no", "0"}:
        return False
    return None


def _now_iso() -> str:
    return _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _frontmatter_to_envelope(
    fm: Dict[str, str], body: str, origin_path: Path
) -> Optional[Dict[str, Any]]:
    ns = fm.get("ainl_namespace")
    rk = fm.get("ainl_record_kind")
    rid = fm.get("ainl_record_id")

    if not ns or not rk or not rid:
        return None

    if (ns, rk) not in SUPPORTED_KINDS:
        return None

    now = _now_iso()

    # Base payload mapping
    payload: Dict[str, Any] = {"text": body.strip()}

    if rk == "long_term.user_preference":
        key = fm.get("preference_key") or fm.get("key")
        value = fm.get("preference_value") or fm.get("value")
        if key:
            payload["key"] = key
        if value is not None:
            payload["value"] = value

    provenance: Dict[str, Any] = {
        "source_system": fm.get("ainl_source_system") or "markdown",
        "origin_uri": str(origin_path),
        "authored_by": fm.get("ainl_authored_by") or "human",
        "confidence": None,
    }

    flags: Dict[str, Any] = {
        "authoritative": _bool_from_frontmatter(fm.get("ainl_authoritative")) or False,
        "ephemeral": _bool_from_frontmatter(fm.get("ainl_ephemeral")) or False,
        "curated": _bool_from_frontmatter(fm.get("ainl_curated")) or True,
    }

    return {
        "namespace": ns,
        "record_kind": rk,
        "record_id": rid,
        "created_at": now,
        "updated_at": now,
        "ttl_seconds": None,
        "payload": payload,
        "provenance": provenance,
        "flags": flags,
    }


def collect_markdown_envelopes(paths: Iterable[Path]) -> List[Dict[str, Any]]:
    """
    Collect canonical memory envelopes from a set of markdown files.

    Only files with explicit AINL frontmatter and supported kinds are imported.
    """
    envelopes: List[Dict[str, Any]] = []
    for p in paths:
        if not p.is_file() or p.suffix.lower() not in {".md", ".markdown"}:
            continue
        text = p.read_text(encoding="utf-8")
        fm, body = _parse_frontmatter_and_body(text)
        env = _frontmatter_to_envelope(fm, body, p)
        if env is not None:
            envelopes.append(env)
    return envelopes


def import_markdown_to_memory(
    db_path: Optional[str],
    inputs: Iterable[Path],
) -> ImportResult:
    """
    Import curated markdown notes into the SQLite-backed memory store.

    This is a one-shot, explicit bridge for selected long-term kinds only.
    """
    md_paths: List[Path] = []
    for inp in inputs:
        if inp.is_dir():
            for p in inp.rglob("*.md"):
                md_paths.append(p)
            for p in inp.rglob("*.markdown"):
                md_paths.append(p)
        elif inp.is_file():
            md_paths.append(inp)

    envs = collect_markdown_envelopes(md_paths)
    return import_records(db_path or DEFAULT_DB_PATH, envs)

