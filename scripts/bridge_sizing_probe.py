#!/usr/bin/env python3
"""Read-only probe for bridge sizing: SQLite namespace counts + Token Usage Report section sizes.

Use before setting AINL_BRIDGE_REPORT_MAX_CHARS or AINL_EMBEDDING_INDEX_NAMESPACE.
Does not modify databases or daily markdown.

Examples:
  python3 scripts/bridge_sizing_probe.py
  ainl bridge-sizing-probe
  ainl bridge-sizing-probe --json
  AINL_MEMORY_DB=/path/mem.sqlite3 ainl bridge-sizing-probe --days 7
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

# Repo-root execution: ``python scripts/bridge_sizing_probe.py ...``
_ROOT = str(Path(__file__).resolve().parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from scripts.memory_retention_report import run_report  # noqa: E402

_DAY_MD_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")


def _openclaw_memory_dir() -> Path:
    override = os.getenv("OPENCLAW_MEMORY_DIR") or os.getenv("OPENCLAW_DAILY_MEMORY_DIR")
    if override:
        return Path(override).expanduser()
    ws = os.getenv("OPENCLAW_WORKSPACE", str(Path.home() / ".openclaw" / "workspace"))
    return Path(ws).expanduser() / "memory"


def _token_usage_section_chars(text: str) -> Optional[int]:
    marker = "## Token Usage Report"
    if marker not in text:
        return None
    idx = text.index(marker)
    rest = text[idx + len(marker) :]
    nl = rest.find("\n")
    if nl != -1:
        rest = rest[nl + 1 :]
    m = re.search(r"^## ", rest, re.MULTILINE)
    block = rest[: m.start()] if m else rest
    return len(block.strip())


def _scan_daily_reports(mem_dir: Path, days: int) -> List[Dict[str, Any]]:
    if not mem_dir.is_dir():
        return []
    paths = [p for p in mem_dir.glob("*.md") if _DAY_MD_RE.match(p.name)]
    paths.sort(key=lambda p: p.stem, reverse=True)
    out: List[Dict[str, Any]] = []
    for p in paths[: max(0, days)]:
        try:
            body = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        n = _token_usage_section_chars(body)
        if n is not None:
            out.append({"file": p.name, "section_chars": n})
    out.sort(key=lambda x: x["file"])
    return out


def _embedding_hint(rows: List[Dict[str, Any]]) -> Optional[str]:
    """Prefer workflow vs intel when both exist; else top namespace."""
    if not rows:
        return None
    by_name = {r["namespace"]: r["count"] for r in rows}
    if "workflow" in by_name and "intel" in by_name:
        return "workflow" if by_name["workflow"] >= by_name["intel"] else "intel"
    return rows[0]["namespace"]


def run_probe(
    db_path: str,
    days: int,
    *,
    memory_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    mem_dir = memory_dir if memory_dir is not None else _openclaw_memory_dir()
    rep = run_report(db_path)
    sections = _scan_daily_reports(mem_dir, days)
    chars = [s["section_chars"] for s in sections]
    mx = max(chars) if chars else None
    med = statistics.median(chars) if len(chars) >= 1 else None
    suggested_cap: Optional[int] = None
    if mx is not None:
        suggested_cap = int(max(mx * 2, (med or mx) * 2))

    return {
        "memory_db": db_path,
        "memory_db_exists": Path(db_path).exists(),
        "openclaw_memory_dir": str(mem_dir),
        "memory_dir_exists": mem_dir.is_dir(),
        "retention_error": rep.get("error"),
        "by_namespace": rep.get("by_namespace", []),
        "embedding_namespace_hint": _embedding_hint(rep.get("by_namespace") or []),
        "token_usage_report_sections": sections,
        "token_usage_section_chars_max": mx,
        "token_usage_section_chars_median": med,
        "suggested_AINL_BRIDGE_REPORT_MAX_CHARS": suggested_cap,
    }


def print_plain_report(data: Dict[str, Any]) -> None:
    print(f"memory_db: {data['memory_db']} (exists={data['memory_db_exists']})")
    if data.get("retention_error"):
        print(f"  note: {data['retention_error']}")
    print(f"openclaw_memory_dir: {data['openclaw_memory_dir']} (exists={data['memory_dir_exists']})")
    print("by_namespace:")
    for row in data["by_namespace"]:
        print(f"  {row['namespace']}: {row['count']}")
    hint = data.get("embedding_namespace_hint")
    if hint:
        print(f"embedding_namespace_hint: {hint}  (set AINL_EMBEDDING_INDEX_NAMESPACE if different)")
    print("Token Usage Report sections (newest --days daily files, non-empty only):")
    for s in data["token_usage_report_sections"]:
        print(f"  {s['file']}: {s['section_chars']} chars")
    if not data["token_usage_report_sections"]:
        print("  (none — run token-usage live or wait for cron)")
    cap = data.get("suggested_AINL_BRIDGE_REPORT_MAX_CHARS")
    if cap is not None:
        print(f"suggested_AINL_BRIDGE_REPORT_MAX_CHARS: {cap}  (~2× observed; tune as needed)")
    else:
        print("suggested_AINL_BRIDGE_REPORT_MAX_CHARS: (no sections sampled — leave unset or set manually)")


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Read-only bridge sizing probe (namespace counts + Token Usage Report sizes).",
    )
    ap.add_argument(
        "--db-path",
        type=str,
        default=os.getenv("AINL_MEMORY_DB", "/tmp/ainl_memory.sqlite3"),
        help="SQLite memory DB (default: AINL_MEMORY_DB or /tmp/ainl_memory.sqlite3).",
    )
    ap.add_argument(
        "--memory-dir",
        type=str,
        default="",
        help="Directory for daily YYYY-MM-DD.md (overrides OPENCLAW_MEMORY_DIR / OPENCLAW_WORKSPACE for this run).",
    )
    ap.add_argument(
        "--days",
        type=int,
        default=14,
        help="How many newest daily *.md files to scan for section size (default: 14).",
    )
    ap.add_argument("--json", action="store_true", help="Emit JSON only.")
    return ap.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv)
    md = Path(args.memory_dir).expanduser() if args.memory_dir else None
    data = run_probe(args.db_path, args.days, memory_dir=md)
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print_plain_report(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
