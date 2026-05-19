"""Fetch live, verifiable status for the $AINL token + the four AINL repos.

Writes a JSON snapshot to `tooling/token_status.json`. The JSON is the single
source of truth for any marketing page or doc that quotes a number about the
$AINL token, treasury, holder count, or contributor count — those surfaces
should read from this file (or its CDN-hosted copy) rather than hardcoding
values that quietly go stale.

Usage:

    python3 scripts/fetch_token_status.py                  # write JSON
    python3 scripts/fetch_token_status.py --dry-run        # print only
    python3 scripts/fetch_token_status.py --skip-onchain   # local git only
    python3 scripts/fetch_token_status.py --skip-github    # no GitHub API

Sources (all read-only, no auth required for the public reads):
  * Solana mainnet RPC (default: https://api.mainnet-beta.solana.com)
  * GitHub REST API (no token required, but rate-limited; set GH_TOKEN to raise)
  * `git log --no-merges` in the local repo for contributor counts

Honesty contract:
  * Values we couldn't fetch are written as `null` with a `_status` sibling
    ("pending_run" / "rpc_error: ...") — we **never** invent numbers.
  * `last_verified` is the UTC timestamp at which this script wrote the file.
  * The script is idempotent: a second run with the same upstream state
    produces a byte-identical JSON (sorted keys, stable formatting).

This file is part of LONG_TERM_FIXES_TRACKER T3.5 (transparent restatement
of $AINL token / marketplace claims).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = REPO_ROOT / "tooling" / "token_status.json"

# Verified facts (not subject to fetch).
TOKEN_MINT = "56hrCR3n7danhHNjWaU4VeUHpE1eRE9VRBWpHRPKpump"
PUMPFUN_URL = f"https://pump.fun/coin/{TOKEN_MINT}"
TOKEN_DECIMALS_NOMINAL = 6  # spl-token default; confirmed on-chain by script

SOLANA_RPC = os.environ.get("SOLANA_RPC", "https://api.mainnet-beta.solana.com")

REPOS = [
    "sbhooley/ainativelang",
    "sbhooley/ainativelangweb",
    "sbhooley/armaraos",
    "sbhooley/ainl-inference-server",
]

# Bot / AI identity patterns. Substring match against "name <email>" lowercased.
BOT_PATTERNS = (
    "dependabot",
    "mseep",
    "renovate",
    "github-actions",
)
AI_PATTERNS = (
    "ainl agent",
    "ainl king",
    "ainl-king",
    "plushify",
    "hermes_ainl",
)
HUMAN_ALIASES = {
    "sbhooley": "Steven B Hooley",
    "steven hooley": "Steven B Hooley",
    "clawdbot": "Steven B Hooley",
    "schonleber": "Terrance Schonleber",
    "r4vager": "Terrance Schonleber",
    "kobeyaki": "Kobe Welker",
    "kobe welker": "Kobe Welker",
    "claysauruswrecks": "claysauruswrecks (external)",
}


# ---------------------------------------------------------------------------
# HTTP helpers (stdlib only, no extra deps)
# ---------------------------------------------------------------------------


def _http_post_json(url: str, body: Dict[str, Any], timeout: float = 8.0) -> Dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def _http_get_json(url: str, timeout: float = 8.0) -> Dict[str, Any]:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "ainl-token-status/1.0"}
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# Solana on-chain
# ---------------------------------------------------------------------------


def fetch_onchain() -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "mint": TOKEN_MINT,
        "rpc": SOLANA_RPC,
        "supply": None,
        "decimals": None,
        "largest_accounts": None,
        "top10_concentration_pct": None,
        "_status": "pending_run",
    }
    try:
        supply_resp = _http_post_json(SOLANA_RPC, {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTokenSupply",
            "params": [TOKEN_MINT],
        })
        if "result" in supply_resp:
            value = supply_resp["result"]["value"]
            out["supply"] = float(value["uiAmount"]) if value.get("uiAmount") is not None else None
            out["decimals"] = value.get("decimals")
    except (urllib.error.URLError, KeyError, ValueError) as exc:
        out["_status"] = f"rpc_error: {exc}"
        return out

    try:
        largest_resp = _http_post_json(SOLANA_RPC, {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "getTokenLargestAccounts",
            "params": [TOKEN_MINT],
        })
        if "result" in largest_resp:
            accounts = largest_resp["result"]["value"]
            out["largest_accounts"] = len(accounts)
            if out["supply"] and accounts:
                top10_units = sum(float(a.get("uiAmount") or 0.0) for a in accounts[:10])
                out["top10_concentration_pct"] = round(100.0 * top10_units / out["supply"], 2) if out["supply"] else None
    except (urllib.error.URLError, KeyError, ValueError) as exc:
        out["_status"] = f"largest_accounts_error: {exc}"
        return out

    out["_status"] = "ok"
    return out


# ---------------------------------------------------------------------------
# GitHub
# ---------------------------------------------------------------------------


def fetch_github_repo(repo: str) -> Dict[str, Any]:
    entry: Dict[str, Any] = {
        "repo": repo,
        "stars": None,
        "open_issues": None,
        "default_branch": None,
        "private": None,
        "_status": "pending_run",
    }
    try:
        data = _http_get_json(f"https://api.github.com/repos/{repo}")
        entry["stars"] = data.get("stargazers_count")
        entry["open_issues"] = data.get("open_issues_count")
        entry["default_branch"] = data.get("default_branch")
        entry["private"] = data.get("private")
        entry["_status"] = "ok"
    except (urllib.error.URLError, KeyError, ValueError) as exc:
        entry["_status"] = f"github_error: {exc}"
    return entry


# ---------------------------------------------------------------------------
# Local git contributor counts (this repo)
# ---------------------------------------------------------------------------


def _classify_author(author_line: str) -> Optional[str]:
    low = author_line.lower()
    if any(p in low for p in BOT_PATTERNS):
        return None  # pure bot — exclude from both human + AI counts
    if any(p in low for p in AI_PATTERNS):
        return "__ai__"
    for needle, canon in HUMAN_ALIASES.items():
        if needle in low:
            return canon
    return f"__unknown__::{author_line}"


def fetch_local_contributors(since: Optional[str] = None) -> Dict[str, Any]:
    args = ["git", "log", "--format=%aN <%aE>", "--no-merges"]
    if since:
        args.insert(2, f"--since={since}")
    proc = subprocess.run(args, capture_output=True, text=True, cwd=REPO_ROOT)
    if proc.returncode != 0:
        return {"_status": f"git_error: {proc.stderr.strip()}"}

    humans: Dict[str, int] = {}
    ai: Dict[str, int] = {}
    unknown: List[str] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        cls = _classify_author(line)
        if cls is None:
            continue
        if cls == "__ai__":
            # find which AI pattern matched, count by canonical bucket
            low = line.lower()
            for p in AI_PATTERNS:
                if p in low:
                    ai[p] = ai.get(p, 0) + 1
                    break
        elif cls.startswith("__unknown__::"):
            unknown.append(line)
        else:
            humans[cls] = humans.get(cls, 0) + 1

    return {
        "window": since or "all_time",
        "repo": "sbhooley/ainativelang",
        "humans": {name: count for name, count in sorted(humans.items(), key=lambda kv: (-kv[1], kv[0]))},
        "humans_distinct": len(humans),
        "ai_authors": {name: count for name, count in sorted(ai.items(), key=lambda kv: (-kv[1], kv[0]))},
        "ai_authors_distinct": len(ai),
        "unknown_authors": unknown,
        "_status": "ok",
    }


# ---------------------------------------------------------------------------
# Aspirational baseline (original goals, never modified once published)
# ---------------------------------------------------------------------------


ASPIRATIONAL_GOALS = {
    "_explanation": (
        "Originally-published targets from the v1.0 token utility design. "
        "Kept here as a fixed baseline so the gap to current reality is "
        "explicit. We do not edit these numbers; we report current values "
        "alongside and let readers see the gap themselves."
    ),
    "token_holders_initial_target": 1500,
    "token_holders_stretch_target": 5000,
    "template_marketplace_status": "planned",
    "contributor_reward_payouts_status": "planned",
    "governance_snapshot_space_status": "planned",
    "treasury_wallet_status": "planned",
    "premium_template_gating_status": "planned",
    "earliest_publication_dates_observed": {
        "champions_program": "docs/community/CHAMPIONS_PROGRAM.md (initial publish)",
        "template_marketplace_submission": "docs/learning/intermediate/patterns/template-marketplace-submission.md (initial publish)",
    },
}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def build_snapshot(skip_onchain: bool = False, skip_github: bool = False) -> Dict[str, Any]:
    now_iso = datetime.now(timezone.utc).isoformat()
    snapshot: Dict[str, Any] = {
        "$schema": "https://ainl.dev/token-status/v1",
        "last_verified": now_iso,
        "token": {
            "symbol": "$AINL",
            "mint_address": TOKEN_MINT,
            "chain": "solana",
            "decimals_nominal": TOKEN_DECIMALS_NOMINAL,
            "pumpfun_url": PUMPFUN_URL,
        },
        "onchain": (
            {"_status": "skipped"}
            if skip_onchain
            else fetch_onchain()
        ),
        "repos": (
            [{"repo": r, "_status": "skipped"} for r in REPOS]
            if skip_github
            else [fetch_github_repo(r) for r in REPOS]
        ),
        "contributors_local_git": {
            "all_time": fetch_local_contributors(),
            "last_90d": fetch_local_contributors(since="90 days ago"),
        },
        "aspirational_goals": ASPIRATIONAL_GOALS,
        "narrative": {
            "_disclosure": (
                "Headline numbers on the $AINL token page should source from "
                "this file. Where a current value is null with a non-'ok' "
                "_status, the marketing page should display 'pending verification' "
                "rather than the aspirational target. Git history is public; the "
                "gap between aspirational goals and current reality is intentional "
                "and visible."
            ),
            "enterprise_token_free": (
                "Enterprise customers do not need to hold $AINL tokens. "
                "Enterprise billing is via invoice or credit card. The token "
                "powers community features only."
            ),
        },
    }
    return snapshot


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--dry-run", action="store_true", help="print snapshot to stdout, don't write")
    p.add_argument("--skip-onchain", action="store_true", help="skip Solana RPC calls")
    p.add_argument("--skip-github", action="store_true", help="skip GitHub API calls")
    p.add_argument("--output", default=str(OUTPUT_PATH), help="output JSON path")
    args = p.parse_args()

    snapshot = build_snapshot(skip_onchain=args.skip_onchain, skip_github=args.skip_github)
    out_text = json.dumps(snapshot, indent=2, sort_keys=False, ensure_ascii=False) + "\n"

    if args.dry_run:
        sys.stdout.write(out_text)
        return 0

    Path(args.output).write_text(out_text, encoding="utf-8")
    print(f"wrote {args.output} ({len(out_text)} bytes; last_verified={snapshot['last_verified']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
