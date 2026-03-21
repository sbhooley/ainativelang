"""Thin GitHub REST adapter: repository search, repo metadata, issue creation."""
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

logger = logging.getLogger(__name__)

GITHUB_API = os.getenv("GITHUB_API_URL", "https://api.github.com").rstrip("/")


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
            logger.warning("github cache save failed: %s", e)

    def get(self, namespace: str, key: str) -> Any:
        return self._load().get(namespace, {}).get(key)

    def set(self, namespace: str, key: str, value: Any) -> None:
        data = self._load()
        data.setdefault(namespace, {})[key] = value
        self._save(data)


class GitHubAdapter(RuntimeAdapter):
    """
    Adapter group: github
    Verbs: search_repos, get_repo, create_issue
    """

    def __init__(self) -> None:
        self._cache = _JsonFileCache()
        self._session = requests.Session()
        tok = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
        if tok:
            self._session.headers["Authorization"] = f"Bearer {tok}"
        self._session.headers.setdefault("Accept", "application/vnd.github+json")
        self._session.headers.setdefault("User-Agent", "ainl-github-adapter")

    def _respect_rate_limit(self, resp: requests.Response) -> None:
        rem = resp.headers.get("X-RateLimit-Remaining")
        reset = resp.headers.get("X-RateLimit-Reset")
        try:
            if rem is not None and int(rem) <= 0 and reset:
                sleep_s = max(0, int(reset) - int(time.time()) + 1)
                if 0 < sleep_s <= 120:
                    time.sleep(sleep_s)
        except ValueError:
            pass

    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        verb = str(target or "").strip().lower()
        dry = _dry_run(context)

        if verb == "search_repos":
            if not args:
                raise AdapterError("search_repos requires query: str")
            query = str(args[0])
            since = args[1] if len(args) > 1 else None
            q = query
            if since not in (None, ""):
                q = f"{query} pushed:>{since}"
            ck = hashlib.sha256(q.encode("utf-8")).hexdigest()[:24]
            cache_key = f"search:{ck}"
            hit = self._cache.get("github", cache_key)
            if isinstance(hit, dict) and time.time() - float(hit.get("ts", 0)) < 120:
                return hit.get("data", [])
            if dry:
                return []
            url = f"{GITHUB_API}/search/repositories"
            r = self._session.get(url, params={"q": q, "per_page": 30}, timeout=30)
            self._respect_rate_limit(r)
            if r.status_code != 200:
                logger.warning("search_repos HTTP %s", r.status_code)
                return []
            payload = r.json()
            items = payload.get("items") if isinstance(payload, dict) else None
            out: List[Dict[str, Any]] = []
            if isinstance(items, list):
                for it in items:
                    if isinstance(it, dict):
                        out.append(
                            {
                                "id": it.get("id"),
                                "name": it.get("name"),
                                "full_name": it.get("full_name"),
                                "html_url": it.get("html_url"),
                                "description": it.get("description"),
                                "pushed_at": it.get("pushed_at"),
                                "stargazers_count": it.get("stargazers_count"),
                            }
                        )
            self._cache.set("github", cache_key, {"ts": time.time(), "data": out})
            return out

        if verb == "get_repo":
            if len(args) < 2:
                raise AdapterError("get_repo requires owner: str, repo: str")
            owner, repo = str(args[0]), str(args[1])
            cache_key = f"repo:{owner}/{repo}"
            hit = self._cache.get("github", cache_key)
            if isinstance(hit, dict) and time.time() - float(hit.get("ts", 0)) < 300:
                return hit.get("data", {})
            if dry:
                return {}
            url = f"{GITHUB_API}/repos/{owner}/{repo}"
            r = self._session.get(url, timeout=30)
            self._respect_rate_limit(r)
            if r.status_code != 200:
                logger.warning("get_repo HTTP %s", r.status_code)
                return {}
            it = r.json()
            if not isinstance(it, dict):
                return {}
            slim: Dict[str, Any] = {
                "id": it.get("id"),
                "name": it.get("name"),
                "full_name": it.get("full_name"),
                "html_url": it.get("html_url"),
                "description": it.get("description"),
                "pushed_at": it.get("pushed_at"),
                "stargazers_count": it.get("stargazers_count"),
                "open_issues_count": it.get("open_issues_count"),
                "default_branch": it.get("default_branch"),
            }
            self._cache.set("github", cache_key, {"ts": time.time(), "data": slim})
            return slim

        if verb == "create_issue":
            if len(args) < 3:
                raise AdapterError("create_issue requires repo, title, body")
            repo_full = str(args[0])
            title, body = str(args[1]), str(args[2])
            labels = args[3] if len(args) > 3 else None
            if dry:
                logger.info("[dry_run] github.create_issue — no POST")
                return 0
            if "/" not in repo_full:
                raise AdapterError("create_issue repo must be owner/name")
            owner, repo = repo_full.split("/", 1)
            issue_body: Dict[str, Any] = {"title": title, "body": body}
            if isinstance(labels, list) and labels:
                issue_body["labels"] = [str(x) for x in labels]
            url = f"{GITHUB_API}/repos/{owner}/{repo}/issues"
            r = self._session.post(url, json=issue_body, timeout=30)
            self._respect_rate_limit(r)
            if r.status_code not in (200, 201):
                logger.warning("create_issue HTTP %s %s", r.status_code, (r.text or "")[:200])
                return 0
            data = r.json()
            if isinstance(data, dict) and data.get("number") is not None:
                try:
                    return int(data["number"])
                except (TypeError, ValueError):
                    return 0
            return 0

        raise AdapterError(f"github unknown target: {target}")
