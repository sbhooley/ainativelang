from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

HERMES_A2A_FILENAME = "a2a.json"


@dataclass(frozen=True)
class HermesA2aConfig:
    """Operator-local Hermes / A2A bridge routing (``a2a.json``)."""

    base_url: str
    config_path: Path
    send_binding: str = "auto"


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


def _normalize_send_binding(raw: Optional[str]) -> str:
    if not raw or not str(raw).strip():
        return "auto"
    s = str(raw).strip().lower()
    if s in ("armaraos", "armaraos_jsonrpc", "jsonrpc", "tasks_send"):
        return "armaraos_jsonrpc"
    if s in ("a2a_http", "http", "http+json", "message_send"):
        return "a2a_http"
    return "auto"


def load_hermes_a2a_config(*, hermes_root: Optional[Path] = None) -> HermesA2aConfig:
    """Load ``a2a.json`` including optional ``send_binding`` (``auto`` | ``armaraos_jsonrpc`` | ``a2a_http``)."""

    paths = resolve_hermes_paths(hermes_root=hermes_root)
    cfg_path = paths.hermes_root / HERMES_A2A_FILENAME
    if not cfg_path.is_file():
        raise FileNotFoundError(
            f"Hermes A2A config missing: {cfg_path}. "
            f'Create it with {{"base_url": "http://127.0.0.1:<port>"}} (origin only).'
        )
    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    base = str(data.get("base_url") or "").strip().rstrip("/")
    if not base:
        raise ValueError(f"{cfg_path}: missing or empty base_url")
    if not (base.startswith("http://") or base.startswith("https://")):
        raise ValueError("base_url must start with http:// or https://")
    host = (urlparse(base).hostname or "").strip().lower()
    blocked = {
        "metadata.google.internal",
        "metadata.aws.internal",
        "instance-data",
        "169.254.169.254",
        "100.100.100.200",
        "192.0.0.192",
    }
    if host in blocked:
        raise ValueError(f"base_url host {host!r} is not allowed in Hermes a2a.json")
    bind = _normalize_send_binding(data.get("send_binding"))
    return HermesA2aConfig(base_url=base, config_path=cfg_path, send_binding=bind)


def load_hermes_a2a_base_url(*, hermes_root: Optional[Path] = None) -> Tuple[str, Path]:
    """Read ``{hermes_root}/a2a.json`` and return ``(base_url, config_path)``.

    The JSON file must contain ``base_url`` — the HTTP origin used for A2A Agent Card
    discovery (``GET {base_url}/.well-known/agent.json``), same contract as ArmaraOS.
    """

    c = load_hermes_a2a_config(hermes_root=hermes_root)
    return c.base_url, c.config_path


def message_send_endpoints(base_url: str, card: Dict[str, Any]) -> List[str]:
    """Linux Foundation A2A HTTP binding: ``POST …/message:send`` candidates."""
    out: List[str] = []
    b = base_url.strip().rstrip("/")
    primary = f"{b}/message:send"
    out.append(primary)
    for si in card.get("supportedInterfaces") or []:
        if not isinstance(si, dict):
            continue
        u = str(si.get("url") or "").strip().rstrip("/")
        if not u:
            continue
        ep = f"{u}/message:send"
        if ep not in out:
            out.append(ep)
    return out

