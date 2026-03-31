#!/usr/bin/env python3
"""Summarize token/budget signals for ArmaraOS crons and ainl-advocate continuity."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_BRIDGE = Path(__file__).resolve().parent
ROOT = _BRIDGE.parent.parent
sys.path.insert(0, str(ROOT))

from adapters.armaraos_memory import OpenFangMemoryAdapter

_TOKEN_RE = re.compile(r"(?i)(?:tokens?|input[_-]?tokens?|output[_-]?tokens?|total[_-]?tokens?)[\s:=]+([\d_,]+)")
_CACHE = Path(os.getenv("MONITOR_CACHE_JSON", "/tmp/monitor_state.json")).expanduser()
_DEFAULT_BUDGET = int(os.getenv("AINL_ADVOCATE_DAILY_TOKEN_BUDGET", "500000"))


def _memory_dir() -> Path:
    o = os.getenv("ARMARAOS_MEMORY_DIR") or os.getenv("ARMARAOS_DAILY_MEMORY_DIR")
    if o:
        return Path(o).expanduser()
    ws = os.getenv("ARMARAOS_WORKSPACE", str(Path.home() / ".armaraos" / "workspace"))
    return Path(ws).expanduser() / "memory"


def _load_cache() -> dict:
    try:
        with open(_CACHE, encoding="utf-8") as f:
            d = json.load(f)
            return d if isinstance(d, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _cache_token_hint(data: object, out: list[int]) -> None:
    if isinstance(data, dict):
        for k, v in data.items():
            lk = str(k).lower()
            if any(x in lk for x in ("token", "usage", "cost")) and isinstance(v, (int, float)):
                out.append(int(v))
            _cache_token_hint(v, out)
    elif isinstance(data, list):
        for x in data:
            _cache_token_hint(x, out)


def _cache_size_mb(path: Path) -> float:
    try:
        if path.is_file():
            return round(path.stat().st_size / (1024 * 1024), 4)
    except OSError:
        pass
    return 0.0


def _tokens_by_model_from_cache(data: object) -> dict[str, int]:
    """Heuristic buckets when MONITOR_CACHE_JSON keys look like model:role or contain model ids."""
    acc: dict[str, int] = {}
    model_markers = ("gpt-", "claude", "openrouter", "o1", "o3", "llama", "mistral", "gemini")

    def walk(obj: object) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                ks = str(k)
                lk = ks.lower()
                if isinstance(v, (int, float)) and any(x in lk for x in ("token", "usage", "prompt", "completion")):
                    bucket: str | None = None
                    if ":" in ks:
                        bucket = ks.split(":", 1)[0].strip() or None
                    elif any(m in lk for m in model_markers):
                        bucket = ks
                    if bucket:
                        acc[bucket] = acc.get(bucket, 0) + int(v)
                else:
                    walk(v)
        elif isinstance(obj, list):
            for x in obj:
                walk(x)

    walk(data)
    return acc


def _scan_md_days(days: int) -> tuple[list[str], int]:
    hits: list[str] = []
    approx = 0
    base = _memory_dir()
    for i in range(days):
        day = (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
        p = base / f"{day}.md"
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for m in _TOKEN_RE.finditer(text):
            raw = m.group(1).replace(",", "")
            try:
                approx += int(raw)
            except ValueError:
                pass
        if "token" in text.lower() or "budget" in text.lower():
            hits.append(str(p))
    return hits, approx


def main() -> None:
    ap = argparse.ArgumentParser(description="Token usage / budget reporter for bridge + ArmaraOS memory.")
    ap.add_argument("--dry-run", action="store_true", help="skip armaraos_memory append (stdout/JSON only)")
    ap.add_argument("--json-output", action="store_true", help="emit one JSON object on stdout (for wrappers / parsing)")
    ap.add_argument("--notify", action="store_true", help="stub: stderr hint (wire QueuePut in ainl for Telegram)")
    ap.add_argument("--days-back", type=int, default=1, metavar="N", help="scan last N daily memory files (default 1)")
    args = ap.parse_args()
    dry = args.dry_run or os.getenv("AINL_DRY_RUN", "").strip().lower() in ("1", "true", "yes")

    session = os.getenv("AINL_SESSION_KEY", "agent:default:ainl-advocate")
    budget = int(os.getenv("AINL_ADVOCATE_DAILY_TOKEN_BUDGET", str(_DEFAULT_BUDGET)))

    cache = _load_cache()
    cache_nums: list[int] = []
    _cache_token_hint(cache, cache_nums)
    cache_sum = sum(cache_nums) if cache_nums else 0
    by_model = _tokens_by_model_from_cache(cache) if args.json_output else {}
    cache_mb = _cache_size_mb(_CACHE)
    md_paths, md_approx = _scan_md_days(max(1, args.days_back))
    total_est = max(cache_sum, md_approx)
    pct = (100.0 * total_est / budget) if budget > 0 else 0.0
    warn = pct >= 80.0
    status = "WARNING (>80% of daily budget)" if warn else "OK"

    lines = [
        "## Token Usage Report",
        f"- session_key: `{session}`",
        f"- window_days: {args.days_back}",
        f"- monitor_cache: `{_CACHE}` ({'present' if _CACHE.is_file() else 'missing'})",
        f"- monitor_cache_size_mb: {cache_mb}",
        f"- estimated_total_tokens: ~{total_est} (heuristic: MONITOR_CACHE_JSON vs daily memory)",
        f"- daily_budget_tokens: {budget}",
        f"- budget_used_pct: {pct:.1f}%",
        f"- status: **{status}**",
        f"- memory_files_scanned: {len(md_paths)}",
    ]
    if by_model:
        lines.append("- tokens_by_model (heuristic): " + ", ".join(f"{k}={v}" for k, v in sorted(by_model.items())))
    body = "\n".join(lines)

    payload = {
        "total_tokens": int(total_est),
        "budget_percent": round(pct, 2),
        "budget_warning": bool(warn),
        "daily_budget_tokens": budget,
        "session_key": session,
        "window_days": int(args.days_back),
        "report_markdown": body,
        "monitor_cache_path": str(_CACHE),
        "monitor_cache_present": _CACHE.is_file(),
        "cache_size_mb": cache_mb,
        "tokens_by_model": by_model if by_model else {},
    }

    if args.json_output:
        print(json.dumps(payload, indent=2))
    else:
        print(body)

    mem = OpenFangMemoryAdapter()
    mem.call("append_today", [body], {"dry_run": dry})

    if args.notify and not dry:
        sys.stderr.write("[notify] stub: wire QueuePut in supervisor.ainl or ARMARAOS notify hook.\n")
    elif args.notify and dry:
        sys.stderr.write("[notify] skipped (--dry-run)\n")


if __name__ == "__main__":
    try:  # AINL-ARMARAOS-TOP5
        main()  # AINL-ARMARAOS-TOP5
    except SystemExit:  # AINL-ARMARAOS-TOP5
        raise  # AINL-ARMARAOS-TOP5
    except BaseException as _e:  # AINL-ARMARAOS-TOP5
        try:  # AINL-ARMARAOS-TOP5
            from armaraos.bridge.user_friendly_error import user_friendly_ainl_error  # AINL-ARMARAOS-TOP5

            print(user_friendly_ainl_error(_e), file=sys.stderr)  # AINL-ARMARAOS-TOP5
        except Exception:  # AINL-ARMARAOS-TOP5
            print(str(_e), file=sys.stderr)  # AINL-ARMARAOS-TOP5
        raise SystemExit(1) from _e  # AINL-ARMARAOS-TOP5
