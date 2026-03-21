"""MCP helpers: fetch Markdown and produce AINL via ``markdown_importer`` (no CLI).

Used by ``scripts/ainl_mcp_server.py``. Network I/O only; does not write the repo.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from tooling.markdown_importer import (
    AGENCY_AGENTS_SAMPLE_URLS,
    CLAWFLOWS_SAMPLE_URLS,
    DEFAULT_FETCH_TIMEOUT_S,
    load_markdown_source,
    markdown_to_ainl_from_body,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _is_url(s: str) -> bool:
    t = s.strip().lower()
    return t.startswith("http://") or t.startswith("https://")


def _match_preset(name: str, table: List[Tuple[str, str]]) -> Optional[str]:
    raw = name.strip()
    if not raw:
        return None
    if _is_url(raw):
        return raw.strip()
    key = raw.lower().replace(" ", "-").replace("_", "-")
    for slug, url in table:
        if slug == key:
            return url
        if key in slug or slug in key:
            return url
    return None


def list_ecosystem_templates() -> Dict[str, Any]:
    """Curated preset URLs + local ``examples/ecosystem`` folders (if present)."""
    local: List[str] = []
    eco = _REPO_ROOT / "examples" / "ecosystem"
    for group in ("clawflows", "agency-agents"):
        base = eco / group
        if not base.is_dir():
            continue
        for p in sorted(base.iterdir()):
            if p.is_dir() and (p / "converted.ainl").is_file():
                try:
                    local.append(str(p.relative_to(_REPO_ROOT)))
                except ValueError:
                    local.append(str(p))
    return {
        "clawflows_presets": [{"slug": s, "url": u} for s, u in CLAWFLOWS_SAMPLE_URLS],
        "agency_agents_presets": [{"slug": s, "url": u} for s, u in AGENCY_AGENTS_SAMPLE_URLS],
        "local_template_paths": local,
    }


def import_clawflow_mcp(
    url_or_name: str,
    *,
    openclaw_bridge: bool = True,
    timeout_s: float = DEFAULT_FETCH_TIMEOUT_S,
    import_all_preset_samples: bool = False,
) -> Dict[str, Any]:
    """
    Single preset/URL workflow import, or all curated Clawflows presets when
    ``import_all_preset_samples`` is True (ignores ``url_or_name`` in that mode).
    """
    if import_all_preset_samples:
        results: List[Dict[str, Any]] = []
        for slug, url in CLAWFLOWS_SAMPLE_URLS:
            try:
                prov, md = load_markdown_source(url, timeout_s=timeout_s)
                ainl, meta = markdown_to_ainl_from_body(
                    md,
                    provenance=prov,
                    md_type="workflow",
                    openclaw_bridge=openclaw_bridge,
                )
                results.append(
                    {
                        "slug": slug,
                        "source_url": url,
                        "ok": True,
                        "ainl": ainl,
                        "meta": {k: v for k, v in meta.items() if k != "sidecars"},
                    }
                )
            except Exception as e:
                results.append({"slug": slug, "source_url": url, "ok": False, "error": str(e)})
        return {"ok": True, "mode": "all_presets", "count": len(results), "results": results}

    url = _match_preset(url_or_name, CLAWFLOWS_SAMPLE_URLS)
    if not url:
        return {
            "ok": False,
            "error": f"unknown_clawflow: {url_or_name!r} (use a URL or a preset slug; see ainl_list_ecosystem)",
        }
    try:
        prov, md = load_markdown_source(url, timeout_s=timeout_s)
        ainl, meta = markdown_to_ainl_from_body(
            md,
            provenance=prov,
            md_type="workflow",
            openclaw_bridge=openclaw_bridge,
        )
    except Exception as e:
        return {"ok": False, "error": str(e), "source_url": url}
    return {
        "ok": True,
        "source_url": url,
        "ainl": ainl,
        "meta": {k: v for k, v in meta.items() if k != "sidecars"},
    }


def import_agency_agent_mcp(
    personality_name: str,
    *,
    tone: Optional[str] = None,
    openclaw_bridge: bool = True,
    timeout_s: float = DEFAULT_FETCH_TIMEOUT_S,
    import_all_preset_samples: bool = False,
) -> Dict[str, Any]:
    """
    ``personality_name`` is a preset slug (e.g. ``mcp-builder``) or HTTPS URL to agent Markdown.
    Optional ``tone`` is merged like CLI ``--personality``.
    """
    if import_all_preset_samples:
        results: List[Dict[str, Any]] = []
        for slug, url in AGENCY_AGENTS_SAMPLE_URLS:
            try:
                prov, md = load_markdown_source(url, timeout_s=timeout_s)
                ainl, meta = markdown_to_ainl_from_body(
                    md,
                    provenance=prov,
                    md_type="agent",
                    personality=tone or "",
                    openclaw_bridge=openclaw_bridge,
                )
                results.append(
                    {
                        "slug": slug,
                        "source_url": url,
                        "ok": True,
                        "ainl": ainl,
                        "meta": {k: v for k, v in meta.items() if k != "sidecars"},
                    }
                )
            except Exception as e:
                results.append({"slug": slug, "source_url": url, "ok": False, "error": str(e)})
        return {"ok": True, "mode": "all_presets", "count": len(results), "results": results}

    url = _match_preset(personality_name, AGENCY_AGENTS_SAMPLE_URLS)
    if not url:
        return {
            "ok": False,
            "error": f"unknown_agent: {personality_name!r} (use a URL or preset slug; see ainl_list_ecosystem)",
        }
    try:
        prov, md = load_markdown_source(url, timeout_s=timeout_s)
        ainl, meta = markdown_to_ainl_from_body(
            md,
            provenance=prov,
            md_type="agent",
            personality=tone or "",
            openclaw_bridge=openclaw_bridge,
        )
    except Exception as e:
        return {"ok": False, "error": str(e), "source_url": url}
    return {
        "ok": True,
        "source_url": url,
        "ainl": ainl,
        "meta": {k: v for k, v in meta.items() if k != "sidecars"},
    }


def import_markdown_mcp(
    url: str,
    md_type: str,
    personality: Optional[str] = None,
    *,
    openclaw_bridge: bool = True,
    timeout_s: float = DEFAULT_FETCH_TIMEOUT_S,
) -> Dict[str, Any]:
    if md_type not in ("workflow", "agent"):
        return {"ok": False, "error": f"type must be 'workflow' or 'agent', got {md_type!r}"}
    try:
        prov, md = load_markdown_source(url.strip(), timeout_s=timeout_s)
        ainl, meta = markdown_to_ainl_from_body(
            md,
            provenance=prov,
            md_type=md_type,
            personality=personality or "",
            openclaw_bridge=openclaw_bridge,
        )
    except Exception as e:
        return {"ok": False, "error": str(e)}
    return {
        "ok": True,
        "provenance": prov,
        "ainl": ainl,
        "meta": {k: v for k, v in meta.items() if k != "sidecars"},
    }
