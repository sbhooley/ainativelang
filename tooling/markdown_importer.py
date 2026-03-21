"""Markdown → AINL import helpers (Clawflows WORKFLOW.md, Agency-Agents style docs).

Phase 1: stub graph (fallback). Phase 2: schedule/steps → cron + Call chain; agent frontmatter/sections → branching graph.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_FETCH_TIMEOUT_S = 30.0
_USER_AGENT = "ainl-markdown-importer/1.0 (+https://github.com/sbhooley/ainativelang)"

# Curated samples for `ainl import clawflows` / `ainl import agency-agents`.
CLAWFLOWS_SAMPLE_URLS: List[Tuple[str, str]] = [
    (
        "check-calendar",
        "https://raw.githubusercontent.com/nikilster/clawflows/main/workflows/available/community/check-calendar/WORKFLOW.md",
    ),
    (
        "morning-journal",
        "https://raw.githubusercontent.com/nikilster/clawflows/main/workflows/available/community/morning-journal/WORKFLOW.md",
    ),
    (
        "prep-tomorrow",
        "https://raw.githubusercontent.com/nikilster/clawflows/main/workflows/available/community/prep-tomorrow/WORKFLOW.md",
    ),
    (
        "plan-week",
        "https://raw.githubusercontent.com/nikilster/clawflows/main/workflows/available/community/plan-week/WORKFLOW.md",
    ),
    (
        "check-email",
        "https://raw.githubusercontent.com/nikilster/clawflows/main/workflows/available/community/check-email/WORKFLOW.md",
    ),
]

AGENCY_AGENTS_SAMPLE_URLS: List[Tuple[str, str]] = [
    (
        "mcp-builder",
        "https://raw.githubusercontent.com/msitarzewski/agency-agents/main/specialized/specialized-mcp-builder.md",
    ),
    (
        "agents-orchestrator",
        "https://raw.githubusercontent.com/msitarzewski/agency-agents/main/specialized/agents-orchestrator.md",
    ),
    (
        "engineering-frontend-developer",
        "https://raw.githubusercontent.com/msitarzewski/agency-agents/main/engineering/engineering-frontend-developer.md",
    ),
    (
        "specialized-workflow-architect",
        "https://raw.githubusercontent.com/msitarzewski/agency-agents/main/specialized/specialized-workflow-architect.md",
    ),
    (
        "accounts-payable-agent",
        "https://raw.githubusercontent.com/msitarzewski/agency-agents/main/specialized/accounts-payable-agent.md",
    ),
]


def github_blob_url_to_raw(url: str) -> str:
    """Turn a github.com/.../blob/... link into raw.githubusercontent.com."""
    m = re.match(
        r"^https?://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)$",
        url.strip(),
    )
    if not m:
        return url.strip()
    org, repo, ref, path = m.groups()
    return f"https://raw.githubusercontent.com/{org}/{repo}/{ref}/{path}"


def _is_probably_url(s: str) -> bool:
    t = s.strip().lower()
    return t.startswith("http://") or t.startswith("https://")


def load_markdown_source(url_or_path: str, *, timeout_s: float = DEFAULT_FETCH_TIMEOUT_S) -> Tuple[str, str]:
    """
    Load markdown text from a URL or local path.

    Returns:
        (provenance_label, markdown_body)
    """
    raw = url_or_path.strip()
    if not raw:
        raise ValueError("url_or_path is empty")

    if _is_probably_url(raw):
        fetch_url = github_blob_url_to_raw(raw)
        req = urllib.request.Request(
            fetch_url,
            headers={"User-Agent": _USER_AGENT},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                body = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"HTTP {e.code} fetching {fetch_url!r}: {e.reason}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"failed to fetch {fetch_url!r}: {e}") from e
        return fetch_url, body

    p = Path(raw).expanduser()
    if not p.is_file():
        raise FileNotFoundError(f"not a file: {p}")
    return str(p.resolve()), p.read_text(encoding="utf-8", errors="replace")


def _escape_comment(s: str, max_len: int = 200) -> str:
    one_line = " ".join(s.split())
    if len(one_line) > max_len:
        one_line = one_line[: max_len - 3] + "..."
    return one_line.replace("\x00", "")


def _ainl_double_quoted_json(obj: Any) -> str:
    """Escape JSON for use inside AINL `R core.parse "..."` double-quoted argument."""
    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return raw.replace("\\", "\\\\").replace('"', '\\"')


def split_frontmatter(markdown: str) -> Tuple[Dict[str, str], str]:
    """Split YAML-like `---` frontmatter from body (simple key: value lines only)."""
    text = markdown.lstrip("\ufeff")
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text
    fm_lines = lines[1:end]
    body = "\n".join(lines[end + 1 :]).lstrip("\n")
    fm: Dict[str, str] = {}
    for line in fm_lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        k = key.strip().lower()
        v = val.strip()
        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
            v = v[1:-1]
        fm[k] = v
    return fm, body


_RE_CRON_INLINE = re.compile(
    r"cron\s*[:=]\s*[`'\"]?([*0-9,\s/@-]+)`?'?",
    re.IGNORECASE,
)
_RE_HEADING_STEP = re.compile(r"^#{1,6}\s*(\d+)\.\s*(.+?)\s*$")
_RE_NUMBERED_LINE = re.compile(r"^\s*(\d+)\.\s+(.+?)\s*$")
_RE_BULLET = re.compile(r"^\s*[-*]\s+(.+?)\s*$")


def _normalize_step_title(s: str) -> str:
    t = s.strip()
    t = re.sub(r"\*\*([^*]+)\*\*", r"\1", t)
    t = re.sub(r"`([^`]+)`", r"\1", t)
    t = " ".join(t.split())
    return t[:500] if len(t) > 500 else t


def extract_workflow_steps(body: str) -> List[str]:
    """Prefer Clawflows-style `## 1. Title` sections; else numbered lines; else bullets."""
    steps: List[str] = []
    seen: set[str] = set()
    for line in body.splitlines():
        m = _RE_HEADING_STEP.match(line)
        if m:
            title = _normalize_step_title(m.group(2))
            if title and title not in seen:
                seen.add(title)
                steps.append(title)
    if steps:
        return steps
    for line in body.splitlines():
        m = _RE_NUMBERED_LINE.match(line)
        if m and not line.lstrip().startswith("#"):
            title = _normalize_step_title(m.group(2))
            if title and title not in seen:
                seen.add(title)
                steps.append(title)
    if steps:
        return steps
    for line in body.splitlines():
        m = _RE_BULLET.match(line)
        if m:
            title = _normalize_step_title(m.group(1))
            if title and title not in seen and not title.lower().startswith("using your"):
                steps.append(title)
            if len(steps) >= 25:
                break
    return steps


def _parse_hour_from_token(tok: str) -> Optional[int]:
    t = tok.strip().lower().replace(" ", "")
    m = re.match(r"^(\d{1,2})(?::00)?(am|pm)?$", t)
    if not m:
        m2 = re.match(r"^(\d{1,2})(am|pm)$", t)
        if not m2:
            return None
        h = int(m2.group(1))
        ap = m2.group(2)
    else:
        h = int(m.group(1))
        ap = m.group(2) or ""
    if ap == "pm" and h != 12:
        h += 12
    if ap == "am" and h == 12:
        h = 0
    if 0 <= h <= 23:
        return h
    return None


def schedule_to_cron(fm: Dict[str, str], body: str) -> Tuple[str, str]:
    """
    Return (cron_expr, note). Defaults to 09:00 daily.
    """
    note = ""
    for key in ("cron", "schedule_cron", "crontab"):
        if key in fm and fm[key].strip():
            c = fm[key].strip().strip('"').strip("'")
            if re.match(r"^[\d*/,\s-]+$", c) or "*" in c:
                return c, note

    blob = " ".join(fm.get("schedule", "")) + "\n" + body[:4000]
    m = _RE_CRON_INLINE.search(blob)
    if m:
        cand = m.group(1).strip()
        if len(cand) >= 9 and all(x in "0123456789*,-/ " for x in cand):
            return cand, "from inline cron pattern"

    sched = fm.get("schedule", "").strip()
    if sched:
        parts = [p.strip() for p in re.split(r"[,;]", sched) if p.strip()]
        hours: List[int] = []
        for p in parts:
            h = _parse_hour_from_token(p)
            if h is not None:
                hours.append(h)
        if hours:
            h0 = hours[0]
            note_extra = ""
            if len(hours) > 1:
                note_extra = f" (import used first slot; also: {', '.join(str(h) for h in hours[1:])}h)"
            return f"0 {h0} * * *", f"daily @ {h0}:00 UTC" + note_extra

    bl = body.lower()
    if "every 5 minute" in bl or "every five minute" in bl:
        return "*/5 * * * *", "matched 'every 5 minutes'"
    if "every hour" in bl or "hourly" in bl:
        return "0 * * * *", "matched hourly"
    m2 = re.search(r"every\s+day\s+at\s+(\d{1,2})\s*(am|pm)?", bl)
    if m2:
        h = int(m2.group(1))
        ap = (m2.group(2) or "").lower()
        if ap == "pm" and h != 12:
            h += 12
        if ap == "am" and h == 12:
            h = 0
        return f"0 {h} * * *", "matched 'every day at …'"
    if "every day" in bl or "daily" in bl:
        return "0 9 * * *", "default daily"

    return "0 9 * * *", "default (no schedule matched)"


def _workflow_slug(fm: Dict[str, str], provenance: str) -> str:
    name = (fm.get("name") or "").strip() or Path(provenance.split("?")[0]).stem
    slug = re.sub(r"[^a-z0-9_-]+", "-", name.lower()).strip("-") or "imported_workflow"
    return slug[:80]


def convert_workflow_to_ainl(
    *,
    provenance: str,
    fm: Dict[str, str],
    body: str,
    openclaw_bridge: bool,
) -> str:
    steps = extract_workflow_steps(body)
    if not steps:
        raise ValueError("no workflow steps extracted")

    cron, sched_note = schedule_to_cron(fm, body)
    slug = _workflow_slug(fm, provenance)
    title = fm.get("name", slug).strip() or slug

    lines: List[str] = [
        "# Imported from Markdown (workflow) — parsed Clawflows-style graph.",
        f"# Source: {_escape_comment(provenance, max_len=240)}",
        f"# Workflow: {_escape_comment(title)}",
        f"# Schedule → cron: {cron} ({sched_note})",
        "",
        f'S core cron "{cron}"',
        "",
        "L_cron:",
    ]
    for i in range(len(steps)):
        lines.append(f"  Call L_step_{i + 1} ->_r{i + 1}")
    if openclaw_bridge:
        lines.append("  Call L_emit_queue ->_rq")
    lines.append("  If (core.eq 1 1) ->L_exit ->L_exit")
    lines.append("")

    for i, step_title in enumerate(steps, start=1):
        payload = {
            "step": i,
            "title": step_title,
            "workflow": slug,
            "source": "md_import",
        }
        j = _ainl_double_quoted_json(payload)
        lines.append(f"L_step_{i}:")
        lines.append(f'  R core.parse "{j}" ->step_payload')
        lines.append("  R core.now ->now")
        if openclaw_bridge:
            mm = _ainl_double_quoted_json({"source": "md_import", "workflow": slug})
            lines.append(f'  R core.parse "{mm}" ->memory_meta')
            lines.append(
                f'  R memory put "workflow" "{slug}" "step_{i}" step_payload 3600 memory_meta ->_m{i}'
            )
        else:
            lines.append(f'  R cache set "md_import" "{slug}/step_{i}" step_payload ->_c{i}')
        lines.append("  J step_payload")
        lines.append("")

    if openclaw_bridge:
        done_payload = {"workflow": slug, "steps": len(steps), "event": "workflow_complete"}
        dj = _ainl_double_quoted_json(done_payload)
        lines.append("L_emit_queue:")
        lines.append("  R core.now ->now")
        lines.append(f'  R core.parse "{dj}" ->out_payload')
        lines.append('  R queue Put imported_workflow out_payload ->_q')
        lines.append("  J out_payload")
        lines.append("")

    lines.append("L_exit:")
    lines.append('  J "markdown_import_workflow_ok"')
    lines.append("")
    return "\n".join(lines)


def _split_sections_by_heading(md: str) -> Dict[str, str]:
    """Map lowercased heading text (first line of heading) to body until next heading."""
    lines = md.splitlines()
    sections: Dict[str, str] = {}
    current_key: Optional[str] = None
    buf: List[str] = []
    for line in lines:
        if re.match(r"^#{1,6}\s+", line):
            if current_key is not None:
                sections[current_key] = "\n".join(buf).strip()
            buf = []
            title = re.sub(r"^#+\s*", "", line).strip()
            current_key = title.lower()
        else:
            buf.append(line)
    if current_key is not None:
        sections[current_key] = "\n".join(buf).strip()
    return sections


def _first_paragraph(text: str, limit: int = 400) -> str:
    t = text.strip()
    if not t:
        return ""
    para = t.split("\n\n")[0].strip()
    para = " ".join(para.split())
    return para[:limit]


def convert_agent_to_ainl(
    *,
    provenance: str,
    fm: Dict[str, str],
    body: str,
    personality: str,
    openclaw_bridge: bool,
) -> str:
    sections = _split_sections_by_heading(body)
    identity = (
        fm.get("identity", "").strip()
        or f"{fm.get('name', '').strip()}\n{fm.get('description', '').strip()}".strip()
    )
    if not identity:
        h1 = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        identity = h1.group(1).strip() if h1 else "imported_agent"

    mission = fm.get("mission", "").strip() or _first_paragraph(
        sections.get("🎯 your core mission", "")
        or sections.get("your core mission", "")
        or sections.get("mission", "")
        or next((sections[k] for k in sections if "core mission" in k), "")
    )
    rules = fm.get("rules", "").strip() or _first_paragraph(
        sections.get("🔧 critical rules", "")
        or sections.get("critical rules", "")
        or sections.get("rules", "")
        or next((sections[k] for k in sections if "critical rules" in k), "")
    )
    deliverables = fm.get("deliverables", "").strip() or _first_paragraph(
        sections.get("deliverables", "") or sections.get("outputs", "")
    )
    workflows = fm.get("workflows", "").strip() or _first_paragraph(
        sections.get("workflows", "") or sections.get("workflow", "")
    )

    tone = personality.strip() or fm.get("vibe", "").strip() or fm.get("tone", "").strip()

    slug = re.sub(r"[^a-z0-9_-]+", "-", (fm.get("name") or identity)[:60].lower()).strip("-") or "imported_agent"

    lines: List[str] = [
        "# Imported from Markdown (agent) — parsed Agency-Agents-style graph.",
        f"# Source: {_escape_comment(provenance, max_len=240)}",
    ]
    if tone:
        lines.append(f"# Personality / tone: {_escape_comment(tone)}")
    lines.append("")

    entry_payload = {
        "kind": "agent_entry",
        "slug": slug,
        "identity": identity[:800],
        "mission": mission[:800],
        "tone": tone[:200],
    }
    lines.append("L_entry:")
    lines.append(f'  R core.parse "{_ainl_double_quoted_json(entry_payload)}" ->agent_ctx')
    lines.append("  If (core.eq 1 1) ->L_check_rules ->L_exit")
    lines.append("")

    lines.append("L_check_rules:")
    rules_payload = {"kind": "rules_gate", "text": rules[:1200] if rules else "(see source doc)"}
    lines.append(f'  R core.parse "{_ainl_double_quoted_json(rules_payload)}" ->rules_ctx')
    if openclaw_bridge:
        mm = _ainl_double_quoted_json({"source": "md_import", "agent": slug})
        lines.append(f'  R core.parse "{mm}" ->memory_meta')
        lines.append(f'  R memory put "workflow" "{slug}" "rules_snapshot" rules_ctx 7200 memory_meta ->_mr')
    else:
        lines.append(f'  R cache set "md_import" "{slug}/rules" rules_ctx ->_cr')
    lines.append("  If (core.eq 1 1) ->L_check_deliverables ->L_exit")
    lines.append("")

    lines.append("L_check_deliverables:")
    del_payload = {"kind": "deliverables_gate", "text": deliverables[:1200] if deliverables else "(unspecified)"}
    lines.append(f'  R core.parse "{_ainl_double_quoted_json(del_payload)}" ->del_ctx')
    lines.append("  If (core.eq 1 1) ->L_workflows_hint ->L_exit")
    lines.append("")

    lines.append("L_workflows_hint:")
    wf_payload = {"kind": "workflows_hint", "text": workflows[:1200] if workflows else "(see source doc)"}
    lines.append(f'  R core.parse "{_ainl_double_quoted_json(wf_payload)}" ->wf_ctx')
    if openclaw_bridge:
        lines.append("  R core.now ->now")
        lines.append(f'  R queue Put agency_agent_hint wf_ctx ->_qh')
    lines.append("  J wf_ctx")
    lines.append("")

    lines.append("L_exit:")
    lines.append('  J "markdown_import_agent_ok"')
    lines.append("")
    return "\n".join(lines)


def build_soul_sidecars(
    *,
    fm: Dict[str, str],
    body: str,
    personality: str,
) -> Dict[str, str]:
    """Markdown sidecars for OpenClaw-style agent bootstrapping."""
    name = fm.get("name", "Agent").strip() or "Agent"
    desc = fm.get("description", "").strip()
    identity = fm.get("identity", "").strip() or f"{name}\n{desc}".strip()
    mission = fm.get("mission", "").strip()
    tone = personality.strip() or fm.get("vibe", "").strip()

    soul = "\n".join(
        [
            f"# SOUL — {name}",
            "",
            "## Identity",
            identity or "(imported from markdown)",
            "",
            "## Mission",
            mission or "(see imported agent markdown)",
            "",
            "## Tone",
            tone or "(default)",
            "",
            "## Raw provenance excerpt",
            "```",
            _escape_comment(body, max_len=1200),
            "```",
            "",
        ]
    )
    ident = "\n".join(
        [
            f"# IDENTITY — {name}",
            "",
            identity[:2000],
            "",
        ]
    )
    return {"SOUL.md": soul, "IDENTITY.md": ident}


def generate_stub_ainl(
    *,
    provenance: str,
    md_type: str,
    markdown_preview: str,
    personality: str = "",
    openclaw_bridge: bool = True,
) -> str:
    """
    Emit minimal valid AINL that compiles. Used when structured parsing fails.

    md_type: ``workflow`` | ``agent``
    """
    prev = _escape_comment(markdown_preview)
    lines = [
        f"# Imported from Markdown ({md_type}) — stub graph; replace with full conversion.",
        f"# Source: {_escape_comment(provenance, max_len=240)}",
    ]
    if personality.strip():
        lines.append(f"# Personality hint: {_escape_comment(personality)}")
    if openclaw_bridge:
        lines.append(
            "# OpenClaw: extend with memory.PUT/LIST, queue.Put, cron — see examples/openclaw/"
        )
    lines.append("")

    if md_type == "workflow":
        lines.extend(
            [
                "# Stub: single exit; map schedule + steps to S core cron / If / Call in a later revision.",
                "L_entry:",
                "  J L_exit",
                "",
                "L_exit:",
                '  J "markdown_import_workflow_stub"',
            ]
        )
    elif md_type == "agent":
        lines.extend(
            [
                "# Stub: personality → LLM / branch nodes in a later revision.",
                "L_entry:",
                "  J L_exit",
                "",
                "L_exit:",
                '  J "markdown_import_agent_stub"',
            ]
        )
    else:
        raise ValueError(f"unknown md_type: {md_type!r}")

    return "\n".join(lines) + "\n"


def markdown_to_ainl_from_body(
    markdown: str,
    *,
    provenance: str,
    md_type: str,
    personality: str = "",
    openclaw_bridge: bool = True,
    generate_soul: bool = False,
) -> Tuple[str, Dict[str, Any]]:
    fm, body = split_frontmatter(markdown)
    meta: Dict[str, Any] = {
        "provenance": provenance,
        "type": md_type,
        "markdown_chars": len(markdown),
        "openclaw_bridge": openclaw_bridge,
        "parsed": False,
        "fallback_stub": False,
        "sidecars": None,
    }
    if generate_soul and md_type == "agent":
        meta["sidecars"] = build_soul_sidecars(fm=fm, body=body, personality=personality)
    try:
        if md_type == "workflow":
            ainl = convert_workflow_to_ainl(
                provenance=provenance,
                fm=fm,
                body=body,
                openclaw_bridge=openclaw_bridge,
            )
            cron, note = schedule_to_cron(fm, body)
            meta["parsed"] = True
            meta["cron"] = cron
            meta["schedule_note"] = note
            meta["steps"] = len(extract_workflow_steps(body))
        elif md_type == "agent":
            ainl = convert_agent_to_ainl(
                provenance=provenance,
                fm=fm,
                body=body,
                personality=personality,
                openclaw_bridge=openclaw_bridge,
            )
            meta["parsed"] = True
            meta["agent_slug"] = re.sub(
                r"[^a-z0-9_-]+",
                "-",
                (fm.get("name") or "agent").lower(),
            ).strip("-")
        else:
            raise ValueError(f"unknown md_type: {md_type!r}")
    except Exception:
        meta["fallback_stub"] = True
        ainl = generate_stub_ainl(
            provenance=provenance,
            md_type=md_type,
            markdown_preview=markdown[:800],
            personality=personality,
            openclaw_bridge=openclaw_bridge,
        )
    return ainl, meta


def import_markdown_to_ainl(
    url_or_path: str,
    *,
    md_type: str,
    personality: str = "",
    openclaw_bridge: bool = True,
    timeout_s: float = DEFAULT_FETCH_TIMEOUT_S,
    generate_soul: bool = False,
) -> Tuple[str, Dict[str, Any]]:
    """Load markdown and produce AINL (parsed when possible, else stub) + metadata dict."""
    provenance, md = load_markdown_source(url_or_path, timeout_s=timeout_s)
    return markdown_to_ainl_from_body(
        md,
        provenance=provenance,
        md_type=md_type,
        personality=personality,
        openclaw_bridge=openclaw_bridge,
        generate_soul=generate_soul,
    )
