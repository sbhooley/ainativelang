"""Local CRM HTTP adapter: GitHub intelligence + lead upsert (paths configurable via env)."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List

import requests

from runtime.adapters.base import RuntimeAdapter, AdapterError

from adapters.openclaw_defaults import DEFAULT_CRM_API_BASE

logger = logging.getLogger(__name__)

DEFAULT_BASE = os.getenv("CRM_API_BASE", DEFAULT_CRM_API_BASE).rstrip("/")
PATH_DIGEST = os.getenv("CRM_PATH_GITHUB_INTEL_DIGEST", "/api/github-intelligence/digests")
PATH_FIND = os.getenv("CRM_PATH_GITHUB_INTEL_FIND", "/api/github-intelligence")
PATH_LEADS = os.getenv("CRM_PATH_LEADS_UPSERT", "/api/leads")


def _dry_run(context: Dict[str, Any]) -> bool:
    v = context.get("dry_run")
    if v in (True, 1, "1", "true", "True", "yes"):
        return True
    return os.environ.get("AINL_DRY_RUN", "").strip().lower() in ("1", "true", "yes")


class _JsonFileCache:
    def __init__(self) -> None:
        self.path = Path(os.getenv("MONITOR_CACHE_JSON", "/tmp/monitor_state.json")).expanduser()

    def _load(self) -> Dict[str, Any]:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _save(self, data: Dict[str, Any]) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except OSError as e:
            logger.warning("crm cache save failed: %s", e)

    def get(self, namespace: str, key: str) -> Any:
        return self._load().get(namespace, {}).get(key)

    def set(self, namespace: str, key: str, value: Any) -> None:
        data = self._load()
        data.setdefault(namespace, {})[key] = value
        self._save(data)


def _as_dict(data: Any) -> Dict[str, Any]:
    if isinstance(data, dict):
        return data
    if isinstance(data, str):
        try:
            o = json.loads(data)
            return o if isinstance(o, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


class CrmAdapter(RuntimeAdapter):
    """
    Adapter group: crm
    Verbs: create_github_intelligence_digest, find_github_intelligence, upsert_lead
    """

    def __init__(self) -> None:
        self.base = DEFAULT_BASE
        self._cache = _JsonFileCache()
        self._session = requests.Session()

    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        verb = str(target or "").strip().lower()
        dry = _dry_run(context)

        if verb == "create_github_intelligence_digest":
            if len(args) < 3:
                raise AdapterError(
                    "create_github_intelligence_digest requires generatedAt, newCount, repos"
                )
            generated_at = str(args[0])
            try:
                new_count = int(args[1]) if args[1] is not None else 0
            except (TypeError, ValueError):
                new_count = 0
            repos = args[2]
            if not isinstance(repos, list):
                repos = []
            body = {"generatedAt": generated_at, "newCount": new_count, "repos": repos}
            if dry:
                logger.info("[dry_run] crm.create_github_intelligence_digest — no POST")
                return 0
            url = f"{self.base}{PATH_DIGEST}"
            r = self._session.post(url, json=body, timeout=30)
            if r.status_code not in (200, 201):
                logger.warning("CRM digest POST %s %s", r.status_code, (r.text or "")[:300])
                return 0
            try:
                data = r.json()
            except json.JSONDecodeError:
                return 0
            if isinstance(data, dict):
                for k in ("id", "digestId", "reportId"):
                    if k in data and data[k] is not None:
                        try:
                            return int(data[k])
                        except (TypeError, ValueError):
                            continue
            return 1

        if verb == "find_github_intelligence":
            since = args[0] if len(args) > 0 else None
            try:
                limit = int(args[1]) if len(args) > 1 and args[1] is not None else 20
            except (TypeError, ValueError):
                limit = 20
            params: Dict[str, Any] = {"limit": limit}
            if since not in (None, ""):
                params["since"] = str(since)
            sig = json.dumps(params, sort_keys=True)
            ck = "find:" + hashlib.md5(sig.encode("utf-8")).hexdigest()
            hit = self._cache.get("crm", ck)
            if isinstance(hit, dict) and time.time() - float(hit.get("ts", 0)) < 60:
                return hit.get("data", [])
            if dry:
                return []
            url = f"{self.base}{PATH_FIND}"
            r = self._session.get(url, params=params, timeout=30)
            if r.status_code != 200:
                logger.warning("CRM find_github_intelligence GET %s", r.status_code)
                return []
            try:
                data = r.json()
            except json.JSONDecodeError:
                return []
            if isinstance(data, list):
                out = data
            elif isinstance(data, dict) and isinstance(data.get("items"), list):
                out = data["items"]
            elif isinstance(data, dict) and isinstance(data.get("results"), list):
                out = data["results"]
            else:
                out = []
            self._cache.set("crm", ck, {"ts": time.time(), "data": out})
            return out

        if verb == "upsert_lead":
            if not args:
                raise AdapterError("upsert_lead requires lead_data: dict")
            lead = _as_dict(args[0])
            if dry:
                logger.info("[dry_run] crm.upsert_lead — no POST")
                return 0
            url = f"{self.base}{PATH_LEADS}"
            r = self._session.post(url, json=lead, timeout=30)
            if r.status_code not in (200, 201):
                logger.warning("CRM upsert_lead POST %s", r.status_code)
                return 0
            try:
                data = r.json()
            except json.JSONDecodeError:
                return 1
            if isinstance(data, dict) and data.get("id") is not None:
                try:
                    return int(data["id"])
                except (TypeError, ValueError):
                    pass
            return 1

        raise AdapterError(f"crm unknown target: {target}")
