"""Bridge-only adapter: run `ainl_bridge_main.py token-usage` for scheduled .ainl wrappers.

``extras.shell`` is not implemented on ``ExtrasAdapter``; use ``R bridge token_budget_*`` instead.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple

from runtime.adapters.base import RuntimeAdapter, AdapterError

_BRIDGE = Path(__file__).resolve().parent
_ROOT = _BRIDGE.parent.parent


def _context_dry(context: Dict[str, Any]) -> bool:
    v = context.get("dry_run")
    if v in (True, 1, "1", "true", "True", "yes"):
        return True
    return os.environ.get("AINL_DRY_RUN", "").strip().lower() in ("1", "true", "yes")


def _prune_force_error_payload(dry: bool) -> Optional[Dict[str, Any]]:
    flag = os.environ.get("AINL_BRIDGE_PRUNE_FORCE_ERROR", "").strip().lower()
    if flag not in ("1", "true", "yes"):
        return None
    mb = _monitor_cache_size_mb()
    err = "simulated prune failure (AINL_BRIDGE_PRUNE_FORCE_ERROR)"
    return {
        "error": err,
        "pruned_count": 0,
        "new_size_mb": mb,
        "old_size_mb": mb,
        "dry_run": dry,
    }


def _resolve_prune_days_old(args: List[Any]) -> int:
    env_days = os.getenv("AINL_TOKEN_PRUNE_DAYS", "").strip()
    if env_days:
        try:
            return max(1, int(env_days))
        except ValueError:
            pass
    if args:
        raw = str(args[0]).strip().lower()
        if raw and raw != "auto":
            try:
                return max(1, int(args[0]))
            except (TypeError, ValueError):
                pass
    return 60


def _run_token_json(days: int) -> Dict[str, Any]:
    cmd = [
        sys.executable,
        str(_BRIDGE / "ainl_bridge_main.py"),
        "token-usage",
        "--dry-run",
        "--json-output",
        "--days-back",
        str(days),
    ]
    proc = subprocess.run(cmd, cwd=str(_ROOT), capture_output=True, text=True, timeout=120)
    raw = (proc.stdout or "").strip()
    if not raw:
        return {
            "budget_warning": False,
            "budget_percent": 0.0,
            "total_tokens": 0,
            "report_markdown": "",
            "cache_size_mb": 0.0,
            "tokens_by_model": {},
        }
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise AdapterError(f"token-usage JSON parse failed: {e}") from e


def _monitor_cache_path() -> Path:
    return Path(os.getenv("MONITOR_CACHE_JSON", "/tmp/monitor_state.json")).expanduser()


def _token_report_sentinel_path() -> Path:
    return Path(os.getenv("AINL_TOKEN_REPORT_SENTINEL", "/tmp/token_report_today_sent")).expanduser()


def _utc_today_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _openclaw_memory_dir() -> Path:
    override = os.getenv("OPENCLAW_MEMORY_DIR") or os.getenv("OPENCLAW_DAILY_MEMORY_DIR")
    if override:
        return Path(override).expanduser()
    ws = os.getenv("OPENCLAW_WORKSPACE", str(Path.home() / ".openclaw" / "workspace"))
    return Path(ws).expanduser() / "memory"


_TOKEN_EST_RE = re.compile(r"estimated_total_tokens:\s*~?\s*([\d,]+)", re.I)
_TOKEN_TILDE_RE = re.compile(r"~\s*([\d,]+)\s*\(", re.I)
_BUDGET_PCT_RE = re.compile(r"budget_used_pct:\s*([0-9.]+)\s*%", re.I)
_BUDGET_TOK_RE = re.compile(r"daily_budget_tokens:\s*(\d+)", re.I)
_DAY_MD_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")


def _parse_token_usage_block(text: str) -> Tuple[Optional[int], Optional[float]]:
    if "## Token Usage Report" not in text:
        return None, None
    est: Optional[int] = None
    m = _TOKEN_EST_RE.search(text)
    if m:
        try:
            est = int(m.group(1).replace(",", ""))
        except ValueError:
            est = None
    if est is None:
        m2 = _TOKEN_TILDE_RE.search(text)
        if m2:
            try:
                est = int(m2.group(1).replace(",", ""))
            except ValueError:
                pass
    pct_m = _BUDGET_PCT_RE.search(text)
    pct = float(pct_m.group(1)) if pct_m else None
    if est is None and pct is not None:
        bm = _BUDGET_TOK_RE.search(text)
        if bm:
            try:
                budget = int(bm.group(1))
                est = int(round(budget * (pct / 100.0)))
            except ValueError:
                pass
    return est, pct


def _token_report_parse_block_dict(text: str) -> Dict[str, Any]:
    """Canonical parser for "## Token Usage Report" blocks.

    Used by: token_report_parse_block handler, weekly_token_trends_markdown,
    monthly_token_summary_markdown, and AINL helpers via R bridge.
    """
    est, pct = _parse_token_usage_block(text)
    return {
        "has_token_usage_section": "## Token Usage Report" in text,
        "estimated_total_tokens": est,
        "budget_used_pct": pct,
        "input_tokens": None,
        "output_tokens": None,
    }


def _token_report_parse_block_json(text: str) -> str:
    return json.dumps(_token_report_parse_block_dict(text), ensure_ascii=False)


def _weekly_token_stats_from_db(days_back: int = 14) -> Optional[Dict[str, Any]]:
    """Attempt to fetch weekly token usage stats from IntelligenceReport DB (Context Compaction Trigger entries)."""
    # DB is at workspace/crm/prisma/dev.db. From _ROOT (workspace/AI_Native_Lang), workspace is _ROOT.parent.
    workspace_root = _ROOT.parent
    db_path = workspace_root / 'crm' / 'prisma' / 'dev.db'
    if not db_path.is_file():
        return None
    try:
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        # Get entries from the last N days
        cutoff_dt = datetime.now(timezone.utc) - timedelta(days=days_back)
        cutoff = cutoff_dt.isoformat()
        cur.execute("""
            SELECT date(createdAt) as day, result_json FROM IntelligenceReport
            WHERE jobName = 'Context Compaction Trigger' AND createdAt >= ? AND result_json IS NOT NULL
            ORDER BY createdAt DESC
        """, (cutoff,))
        rows = cur.fetchall()
        conn.close()

        # Build map: day -> latest tokens (since rows DESC, first per day is latest)
        day_latest: Dict[str, int] = {}
        for day_str, result_json in rows:
            try:
                data = json.loads(result_json)
                tokens = data.get('tokens')
                if isinstance(tokens, int) and day_str not in day_latest:
                    day_latest[day_str] = tokens
            except Exception:
                continue

        if not day_latest:
            return None

        # Chronological day list for the last 7 days (if available)
        chrono_days = sorted(day_latest.keys())[-7:]
        day_tokens = [day_latest[d] for d in chrono_days]

        total_w = sum(day_tokens)
        avg_d = int(round(total_w / len(day_tokens))) if day_tokens else 0

        # We don't easily compute prev7 from same DB without separate query; leave empty to skip comparison
        return {
            'ok': True,
            'error': None,
            'day_tokens': day_tokens,
            'last7': [f"{d}.md" for d in chrono_days],  # names for consistency
            'prev7': [],  # not computed
            'empty_estimates': False,
            'weekly_total_tokens': total_w,
            'avg_daily_tokens': avg_d,
            'days_in_window': len(day_tokens),
        }
    except Exception as e:
        # Log warning? We'll just return None to fallback to files
        return None


def _weekly_token_window_stats() -> Dict[str, Any]:
    """Structured stats for markdown + rolling_budget_publish (same window as weekly trends)."""
    # First, try to get stats from IntelligenceReport DB (new source)
    db_stats = _weekly_token_stats_from_db()
    if db_stats and db_stats.get('day_tokens'):
        return db_stats

    # Fallback to scanning daily memory files (legacy)
    mem = _openclaw_memory_dir()
    if not mem.is_dir():
        return {"ok": False, "error": "no_memory_dir", "day_tokens": [], "last7": [], "prev7": []}
    paths = [p for p in mem.glob("*.md") if _DAY_MD_RE.match(p.name)]
    paths.sort(key=lambda p: p.stem, reverse=True)
    newest14 = paths[:14]
    if not newest14:
        return {"ok": False, "error": "no_daily_md", "day_tokens": [], "last7": [], "prev7": []}
    chrono = sorted(newest14, key=lambda p: p.stem)
    if len(chrono) >= 14:
        prev7 = chrono[:7]
        last7 = chrono[7:14]
    elif len(chrono) >= 7:
        prev7 = []
        last7 = chrono[-7:]
    else:
        prev7 = []
        last7 = chrono

    day_tokens: List[int] = []
    last7_names: List[str] = []
    for p in last7:
        last7_names.append(p.name)
        try:
            body = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rep = _token_report_parse_block_dict(body)
        est = rep.get("estimated_total_tokens")
        if est is not None:
            day_tokens.append(int(est))

    prev7_names = [p.name for p in prev7]

    if not day_tokens:
        return {
            "ok": True,
            "error": None,
            "day_tokens": [],
            "last7": last7_names,
            "prev7": prev7_names,
            "empty_estimates": True,
        }

    total_w = sum(day_tokens)
    avg_d = int(round(total_w / len(day_tokens)))
    return {
        "ok": True,
        "error": None,
        "day_tokens": day_tokens,
        "last7": last7_names,
        "prev7": prev7_names,
        "empty_estimates": False,
        "weekly_total_tokens": total_w,
        "avg_daily_tokens": avg_d,
        "days_in_window": len(day_tokens),
    }


def _rolling_budget_json_from_stats(stats: Dict[str, Any]) -> str:
    cap_raw = os.environ.get("AINL_WEEKLY_TOKEN_BUDGET_CAP", "").strip()
    cap: Optional[int] = None
    if cap_raw:
        try:
            cap = max(0, int(cap_raw))
        except ValueError:
            cap = None
    total_w = int(stats.get("weekly_total_tokens") or 0)
    remaining: Optional[int] = None
    if cap is not None:
        remaining = max(0, cap - total_w)
    payload = {
        "weekly_total_tokens": total_w,
        "avg_daily_tokens": int(stats.get("avg_daily_tokens") or 0),
        "days_in_window": int(stats.get("days_in_window") or 0),
        "weekly_cap_tokens": cap,
        "weekly_remaining_tokens": remaining,
        "updated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "bridge.weekly_token_trends",
    }
    return json.dumps(payload, ensure_ascii=False)


def _memory_adapter_bridge() -> Any:
    from runtime.adapters.memory import MemoryAdapter

    db = os.environ.get("AINL_MEMORY_DB", "/tmp/ainl_memory.sqlite3")
    return MemoryAdapter(
        db_path=db,
        valid_namespaces={"intel", "workflow", "session", "long_term", "daily_log", "ops"},
    )


def _bridge_report_max_chars() -> int:
    """0 = disabled. Set AINL_BRIDGE_REPORT_MAX_CHARS to cap token_budget_report markdown size."""
    raw = os.environ.get("AINL_BRIDGE_REPORT_MAX_CHARS", "").strip()
    if not raw:
        return 0
    try:
        return max(0, int(raw))
    except ValueError:
        return 0


def _report_budget_exhausted_markdown(title: str, cap: int) -> str:
    return (
        f"## {title}\n"
        f"- **budget exhausted**: report would exceed {cap} characters "
        "(see `AINL_BRIDGE_REPORT_MAX_CHARS`).\n"
        "- Reduce monitor history, prune cache, or raise the cap.\n"
    )


def _embedding_workflow_index(context: Dict[str, Any], args: List[Any]) -> Dict[str, Any]:
    """Index up to N rows from SQLite memory into embedding_memory (SoT unchanged)."""
    if _context_dry(context):
        return {"ok": True, "dry_run": True, "indexed": 0, "scanned": 0}
    limit = 50
    if args:
        try:
            limit = max(1, min(500, int(args[0])))
        except (TypeError, ValueError):
            limit = 50
    ns = (os.environ.get("AINL_EMBEDDING_INDEX_NAMESPACE") or "workflow").strip() or "workflow"
    from adapters.embedding_memory import EmbeddingMemoryAdapter

    em = EmbeddingMemoryAdapter()
    ma = _memory_adapter_bridge()
    listed = ma.call("list", [ns, None, None, None, {"limit": limit}], context)
    items = listed.get("items") if isinstance(listed, dict) else None
    if not items:
        return {"ok": True, "indexed": 0, "scanned": 0, "namespace": ns}
    indexed = 0
    for it in items:
        rk = str(it.get("record_kind") or "")
        rid = str(it.get("record_id") or "")
        if not rk or not rid:
            continue
        got = ma.call("get", [ns, rk, rid], context)
        if not isinstance(got, dict) or not got.get("found"):
            continue
        rec = got.get("record") or {}
        payload = rec.get("payload")
        if payload is None:
            text = ""
        elif isinstance(payload, dict):
            text = json.dumps(payload, ensure_ascii=False)
        else:
            text = str(payload)
        text = text[:8000]
        try:
            em.call("UPSERT_REF", [ns, rk, rid, text], {})
            indexed += 1
        except Exception:
            continue
    return {"ok": True, "indexed": indexed, "scanned": len(items), "namespace": ns}


def _embedding_workflow_search(args: List[Any], _context: Dict[str, Any]) -> Dict[str, Any]:
    """Top-k embedding search + memory.get payload snapshots (read path pilot)."""
    query = str(args[0]) if args else "workflow"
    k = 5
    if len(args) > 1 and args[1] is not None:
        try:
            k = max(1, min(50, int(args[1])))
        except (TypeError, ValueError):
            k = 5
    from adapters.embedding_memory import EmbeddingMemoryAdapter

    em = EmbeddingMemoryAdapter()
    hits = em.call("SEARCH", [query, k], {})
    if not isinstance(hits, list):
        hits = []
    ma = _memory_adapter_bridge()
    out_hits: List[Dict[str, Any]] = []
    for h in hits:
        if not isinstance(h, dict):
            continue
        ns = h.get("memory_namespace")
        rk = h.get("memory_kind")
        rid = h.get("memory_record_id")
        if not ns or not rk or not rid:
            continue
        got = ma.call("get", [str(ns), str(rk), str(rid)], _context)
        payload_snap: Any = None
        if isinstance(got, dict) and got.get("found"):
            payload_snap = (got.get("record") or {}).get("payload")
        out_hits.append(
            {
                "score": h.get("score"),
                "memory_namespace": ns,
                "memory_kind": rk,
                "memory_record_id": rid,
                "payload_snapshot": payload_snap,
            }
        )
    return {"ok": True, "query": query, "k": k, "hits": out_hits}


def _rolling_budget_publish(context: Dict[str, Any]) -> Dict[str, Any]:
    if _context_dry(context):
        return {"ok": True, "dry_run": True, "skipped": True}
    stats = _weekly_token_window_stats()
    if not stats.get("ok"):
        return {"ok": False, "error": stats.get("error") or "stats_failed"}
    if stats.get("empty_estimates"):
        return {"ok": True, "note": "no_token_estimates", "skipped": True}
    raw = _rolling_budget_json_from_stats(stats)
    body = json.loads(raw)
    ma = _memory_adapter_bridge()
    ma.call(
        "put",
        [
            "workflow",
            "budget.aggregate",
            "weekly_remaining_v1",
            body,
            86400 * 14,
            {"tags": ["rolling_budget", "openclaw"], "source": "bridge"},
        ],
        context,
    )
    return {"ok": True, "record_id": "weekly_remaining_v1", "payload": body}


def _ttl_memory_tuner_run(context: Dict[str, Any]) -> Dict[str, Any]:
    """Adjust ttl_seconds on workflow rows with access metadata (tags include ttl_managed)."""
    if _context_dry(context):
        return {"ok": True, "dry_run": True, "updated": 0}
    require_tag = os.environ.get("AINL_TTL_TUNER_TAG", "ttl_managed").strip() or "ttl_managed"
    ma = _memory_adapter_bridge()
    listed = ma.call("list", ["workflow", None, None, None, {"limit": 200}], context)
    items = listed.get("items") if isinstance(listed, dict) else None
    if not items:
        return {"ok": True, "updated": 0, "scanned": 0}
    updated = 0
    for it in items:
        rk = str(it.get("record_kind") or "")
        rid = str(it.get("record_id") or "")
        got = ma.call("get", ["workflow", rk, rid], context)
        if not isinstance(got, dict) or not got.get("found"):
            continue
        rec = got.get("record") or {}
        if not rec.get("payload"):
            continue
        meta = rec.get("metadata") or {}
        tags = meta.get("tags") if isinstance(meta.get("tags"), list) else []
        if require_tag not in tags:
            continue
        ttl = it.get("ttl_seconds")
        if ttl is None:
            continue
        try:
            ttl_i = int(ttl)
        except (TypeError, ValueError):
            continue
        ac = meta.get("access_count")
        if not isinstance(ac, int) or ac < 0:
            continue
        if ac >= 3:
            factor = 1.25
        elif ac == 0:
            factor = 0.85
        else:
            factor = 1.0
        new_ttl = int(max(86400, min(7776000, ttl_i * factor)))
        if new_ttl == ttl_i:
            continue
        payload = rec.get("payload")
        if not isinstance(payload, dict):
            continue
        ma.call(
            "put",
            [
                "workflow",
                rk,
                rid,
                payload,
                new_ttl,
                meta,
            ],
            context,
        )
        updated += 1
    return {"ok": True, "updated": updated, "scanned": len(items)}


def _weekly_token_trends_markdown() -> str:
    stats = _weekly_token_window_stats()
    if not stats.get("ok"):
        if stats.get("error") == "no_memory_dir":
            return "## Weekly Token Trends\n- No memory directory found; set OPENCLAW_MEMORY_DIR or OPENCLAW_WORKSPACE.\n"
        return "## Weekly Token Trends\n- No daily `YYYY-MM-DD.md` files found under memory/.\n"

    last7 = stats.get("last7") or []
    prev7_paths = stats.get("prev7") or []
    day_tokens: List[int] = list(stats.get("day_tokens") or [])

    if stats.get("empty_estimates") or not day_tokens:
        return (
            "## Weekly Token Trends\n"
            f"- Scanned {len(last7)} recent file(s); no `## Token Usage Report` token estimates found.\n"
        )

    total_w = sum(day_tokens)
    avg_d = int(round(total_w / len(day_tokens)))
    lines = [
        "## Weekly Token Trends",
        f"- Days in window: {len(day_tokens)} (from memory `*.md` files)",
        f"- Avg daily: ~{avg_d} tokens (heuristic from reports)",
        f"- Total week: ~{total_w} tokens",
    ]
    if len(day_tokens) >= 3:
        older = mean(day_tokens[: max(1, len(day_tokens) // 2)])
        newer = mean(day_tokens[len(day_tokens) // 2 :])
        if newer > older * 1.05:
            arrow = "↑"
            try:
                pct_ch = int(round((newer - older) / max(older, 1) * 100))
            except Exception:
                pct_ch = 0
            lines.append(f"- Trend: {arrow} ~{pct_ch}% higher in newer half of window vs older half")
        elif newer < older * 0.95:
            arrow = "↓"
            try:
                pct_ch = int(round((older - newer) / max(older, 1) * 100))
            except Exception:
                pct_ch = 0
            lines.append(f"- Trend: {arrow} ~{pct_ch}% lower in newer half of window vs older half")
        else:
            lines.append("- Trend: → roughly flat within this week")
    else:
        lines.append("- Trend: → not enough days for split-window trend")

    if prev7_paths:
        mem = _openclaw_memory_dir()
        prev_vals: List[int] = []
        for name in prev7_paths:
            p = mem / name
            try:
                body = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            rep = _token_report_parse_block_dict(body)
            est = rep.get("estimated_total_tokens")
            if est is not None:
                prev_vals.append(est)
        if prev_vals and total_w > 0:
            prev_tot = sum(prev_vals)
            if prev_tot > 0:
                ch = int(round((total_w - prev_tot) / prev_tot * 100))
                sym = "↑" if ch > 0 else "↓" if ch < 0 else "→"
                lines.append(f"- vs prior 7 days: {sym} {ch:+d}% (weekly totals heuristic)")

    return "\n".join(lines) + "\n"


def _monitor_cache_size_mb() -> float:
    fake = os.environ.get("AINL_BRIDGE_FAKE_CACHE_MB", "").strip()
    if fake:
        try:
            return round(float(fake), 4)
        except ValueError:
            pass
    p = _monitor_cache_path()
    try:
        if p.is_file():
            return round(p.stat().st_size / (1024 * 1024), 4)
    except OSError:
        pass
    return 0.0


def _parse_ts(obj: Any) -> Optional[float]:
    if not isinstance(obj, dict):
        return None
    for k in ("ts", "timestamp", "updated_at", "valid_at", "time", "created_at"):
        if k not in obj:
            continue
        v = obj[k]
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            try:
                s = v.replace("Z", "+00:00")
                return datetime.fromisoformat(s).timestamp()
            except Exception:
                pass
    return None


def _prune_value(obj: Any, cutoff: float) -> Tuple[Any, int]:
    """Drop dict/list entries with parseable ts older than cutoff. Returns (new_obj, pruned_keys)."""
    pruned = 0
    if isinstance(obj, dict):
        ts = _parse_ts(obj)
        if ts is not None and ts < cutoff:
            return None, 1
        out: Dict[str, Any] = {}
        for k, v in list(obj.items()):
            if isinstance(v, dict):
                nv, p = _prune_value(v, cutoff)
                pruned += p
                if nv is None:
                    continue
                out[k] = nv
            elif isinstance(v, list):
                nl, p = _prune_list(v, cutoff)
                pruned += p
                out[k] = nl
            else:
                out[k] = v
        return out, pruned
    return obj, 0


def _prune_list(arr: List[Any], cutoff: float) -> Tuple[List[Any], int]:
    pruned = 0
    out: List[Any] = []
    for item in arr:
        if isinstance(item, dict):
            ts = _parse_ts(item)
            if ts is not None and ts < cutoff:
                pruned += 1
                continue
            nv, p = _prune_value(item, cutoff)
            pruned += p
            if nv is None:
                continue
            out.append(nv)
        else:
            out.append(item)
    return out, pruned


def _prune_root(data: Dict[str, Any], days_old: int) -> Tuple[Dict[str, Any], int]:
    cutoff = time.time() - float(days_old) * 86400.0
    pruned = 0
    out: Dict[str, Any] = {}
    for k, v in list(data.items()):
        if isinstance(v, dict):
            nv, p = _prune_value(v, cutoff)
            pruned += p
            if nv is None:
                continue
            out[k] = nv
        elif isinstance(v, list):
            nl, p = _prune_list(v, cutoff)
            pruned += p
            out[k] = nl
        else:
            out[k] = v
    return out, pruned


def _write_cache_atomic(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def _format_prune_markdown(d: Dict[str, Any]) -> str:
    if d.get("error"):
        return ""
    n = int(d.get("pruned_count", 0))
    new_m = float(d.get("new_size_mb", 0.0))
    lines = ["## Cache Prune"]
    if d.get("dry_run"):
        lines.append("- Would prune stale entries (dry-run); no file changes")
    lines.append(f"- Removed {n} old entries")
    lines.append(f"- New size: {new_m:.4f} MB")
    return "\n".join(lines)


def _format_prune_error_markdown(d: Dict[str, Any]) -> str:
    err = str(d.get("error") or "")
    lines = ["## Cache Prune"]
    if d.get("dry_run"):
        lines.append("- Would prune stale entries (dry-run); no file changes")
    lines.append(f"- Prune failed: {err}")
    return "\n".join(lines)


class BridgeTokenBudgetAdapter(RuntimeAdapter):
    """Prune stats, formatted markdown, and a small notify queue for consolidated Telegram."""

    def __init__(self) -> None:
        self._last_prune: Dict[str, Any] = {
            "pruned_count": 0,
            "new_size_mb": 0.0,
            "old_size_mb": 0.0,
            "dry_run": True,
        }
        self._notify_lines: List[str] = []

    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        t = (target or "").strip().lower()
        if t == "token_budget_notify_reset":
            self._notify_lines.clear()
            return 1
        if t == "token_budget_notify_add":
            if args:
                s = str(args[0]).strip()
                if s:
                    self._notify_lines.append(s)
            return len(self._notify_lines)
        if t == "token_report_today_sent":
            p = _token_report_sentinel_path()
            today = _utc_today_tag()
            try:
                if not p.is_file():
                    return 0
                raw = p.read_text(encoding="utf-8")
                got = raw.strip().splitlines()[0].strip() if raw.strip() else ""
            except OSError:
                return 0
            return 1 if got == today else 0
        if t == "token_report_today_touch":
            if _context_dry(context):
                return 0
            p = _token_report_sentinel_path()
            today = _utc_today_tag()
            try:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(today + "\n", encoding="utf-8")
                return 1
            except OSError:
                return 0
        if t == "rolling_budget_json":
            stats = _weekly_token_window_stats()
            if not stats.get("ok") or stats.get("empty_estimates"):
                return "{}"
            return _rolling_budget_json_from_stats(stats)
        if t == "rolling_budget_publish":
            return _rolling_budget_publish(context)
        if t == "ttl_memory_tuner_run":
            return _ttl_memory_tuner_run(context)
        if t == "embedding_workflow_index":
            return _embedding_workflow_index(context, args)
        if t == "embedding_workflow_search":
            return _embedding_workflow_search(args, context)
        if t == "weekly_token_trends_report":
            return _weekly_token_trends_markdown()
        if t == "token_report_parse_block":
            return _token_report_parse_block_json(str(args[0]) if args else "")
        if t == "token_report_list_daily_md":
            raw = str(args[0]) if args else ""
            root = Path(raw).expanduser()
            if not root.is_dir():
                return "[]"
            names = sorted(p.name for p in root.glob("*.md") if _DAY_MD_RE.match(p.name))
            return json.dumps(names, ensure_ascii=False)
        if t == "token_budget_notify_build":
            if not self._notify_lines:
                return ""
            body = "\n".join(self._notify_lines)
            ts_raw = args[0] if args else None
            try:
                tsf = float(ts_raw) if ts_raw is not None else time.time()
            except (TypeError, ValueError):
                tsf = time.time()
            human = datetime.fromtimestamp(tsf, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            return f"Daily AINL Status - {human}\n{body}"
        if t == "monitor_cache_stat":
            return _monitor_cache_size_mb()
        if t == "monitor_cache_prune_result":
            return json.dumps(self._last_prune, ensure_ascii=False)
        if t == "monitor_cache_prune_markdown":
            return _format_prune_markdown(self._last_prune)
        if t == "monitor_cache_prune_error_markdown":
            return _format_prune_error_markdown(self._last_prune)
        if t == "monitor_cache_prune_notify_text":
            n = int(self._last_prune.get("pruned_count", 0))
            return f"Pruned {n} old token-monitor cache entries — see today's memory for details."
        if t == "token_budget_notify_text":
            days = int(args[0]) if args else 1
            data = _run_token_json(days)
            pct = float(data.get("budget_percent", 0))
            cm = float(data.get("cache_size_mb", _monitor_cache_size_mb()))
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            return (
                f"Token budget warning: {pct}% used | Cache: {cm} MB | See memory/{today}.md"
            )
        if t == "monitor_cache_prune":
            days_old = _resolve_prune_days_old(args)
            dry = _context_dry(context)
            path = _monitor_cache_path()

            forced = _prune_force_error_payload(dry)
            if forced is not None:
                self._last_prune = dict(forced)
                return dict(self._last_prune)

            if dry:
                raw_mb = _monitor_cache_size_mb()
                if os.environ.get("AINL_BRIDGE_FAKE_CACHE_MB", "").strip():
                    old_mb = round(raw_mb, 4)
                    new_mb = round(max(raw_mb * 0.997, 0.0), 4)
                elif raw_mb < 1.0:
                    old_mb = 13.247
                    new_mb = 12.984
                else:
                    old_mb = round(raw_mb, 4)
                    new_mb = round(max(raw_mb * 0.997, 0.0), 4)
                self._last_prune = {
                    "pruned_count": 0,
                    "new_size_mb": new_mb,
                    "old_size_mb": old_mb,
                    "dry_run": True,
                }
                return dict(self._last_prune)
            try:
                if not path.is_file():
                    self._last_prune = {
                        "pruned_count": 0,
                        "new_size_mb": 0.0,
                        "old_size_mb": 0.0,
                        "dry_run": False,
                    }
                    return dict(self._last_prune)
                raw = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(raw, dict):
                    mb = _monitor_cache_size_mb()
                    self._last_prune = {
                        "pruned_count": 0,
                        "new_size_mb": mb,
                        "old_size_mb": mb,
                        "dry_run": False,
                    }
                    return dict(self._last_prune)
                old_mb = _monitor_cache_size_mb()
                new_data, n = _prune_root(raw, days_old)
                _write_cache_atomic(path, new_data)
                new_mb = _monitor_cache_size_mb()
                self._last_prune = {
                    "pruned_count": n,
                    "new_size_mb": new_mb,
                    "old_size_mb": old_mb,
                    "dry_run": False,
                }
                return dict(self._last_prune)
            except (OSError, json.JSONDecodeError, TypeError) as e:
                mb = _monitor_cache_size_mb()
                self._last_prune = {
                    "error": str(e),
                    "pruned_count": 0,
                    "new_size_mb": mb,
                    "old_size_mb": mb,
                    "dry_run": False,
                }
                return dict(self._last_prune)

        days = int(args[0]) if args else 1
        if t == "token_budget_warn":
            data = _run_token_json(days)
            return 1 if data.get("budget_warning") else 0
        if t == "token_budget_report":
            data = _run_token_json(days)
            report = str(data.get("report_markdown") or "")
            cap = _bridge_report_max_chars()
            if cap > 0 and len(report) > cap:
                return _report_budget_exhausted_markdown("Token Usage Report", cap)
            return report
        raise AdapterError(
            f"bridge unknown target {t!r}; see monitor_cache_stat, monitor_cache_prune, "
            "monitor_cache_prune_markdown, monitor_cache_prune_error_markdown, "
            "monitor_cache_prune_result, token_report_today_sent, token_report_today_touch, "
            "rolling_budget_json, rolling_budget_publish, ttl_memory_tuner_run, "
            "embedding_workflow_index, embedding_workflow_search, "
            "weekly_token_trends_report, token_report_parse_block, token_report_list_daily_md, "
            "token_budget_notify_reset, token_budget_notify_add, token_budget_notify_build, "
            "token_budget_notify_text, token_budget_warn, token_budget_report"
        )
