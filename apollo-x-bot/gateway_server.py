#!/usr/bin/env python3
"""
HTTP executor gateway for apollo-x-bot/ainl-x-promoter.ainl (ExecutorBridgeAdapter).

Each logical executor key maps to a dedicated URL path (see README), including
`promoter.search_cursor_commit` to advance incremental X search after a full poll. The AINL runtime POSTs
the JSON body built in the graph; responses must be JSON (decoded into the http adapter's
`body` field).

Environment (production):
  X_BEARER_TOKEN          Twitter API v2 Bearer token (recent search; app-only)
  X_API_KEY / X_CONSUMER_KEY   OAuth 1.0a consumer key (from developer portal)
  X_API_SECRET / X_CONSUMER_SECRET  Consumer secret
  X_ACCESS_TOKEN          OAuth 1.0a user access token (required for posting tweets)
  X_ACCESS_TOKEN_SECRET   Access token secret
  (Posting uses OAuth 1.0a user context. Bearer alone is often rejected for POST /2/tweets.)
  OPENAI_API_KEY or LLM_API_KEY
  OPENAI_BASE_URL         Default https://api.openai.com/v1
  LLM_MODEL                 Default gpt-4o-mini
  PROMOTER_STATE_PATH       SQLite file (default: apollo-x-bot/data/promoter_state.sqlite). If set to an
                            existing directory, uses <dir>/promoter_state.sqlite. Resolved to absolute at startup.
  AINL_MEMORY_DB            Memory SQLite for dashboard memory tail; same directory rule with promoter_memory.sqlite
  PROMOTER_DRY_RUN          If 1, no X writes; LLM falls back to heuristic scoring if no API key
  PROMOTER_MAX_REPLIES_PER_DAY   Default 20 (reply/comment cap per UTC day)
  PROMOTER_MAX_ORIGINAL_POSTS_PER_DAY  Max standalone promotional posts per UTC day (default 5)
  PROMOTER_ORIGINAL_POST_MIN_INTERVAL_SEC  Min seconds between original posts (default 10800 = 3h) to spread posts
  PROMOTER_DAILY_POST_TEMPERATURE  Default 0.72 for llm.chat from ainl-x-promoter (daily post chain)
  PROMOTER_DAILY_SKIP_LLM        If 1, graph skips llm.chat and maybe_daily_post uses static body only
  PROMOTER_CODEBASE_ROOT         Root for snippet files (default: parent of apollo-x-bot = repo root)
  PROMOTER_DAILY_SNIPPET_FILES   Comma-separated paths under codebase root (default: README.md,HOW_AINL_SAVES_MONEY.md,apollo-x-bot/README.md)
  PROMOTER_DAILY_SNIPPET_MAX_CHARS  Max characters of snippets fed to the LLM (default 12000)
  PROMOTER_USER_COOLDOWN_HOURS   Default 48
  PROMOTER_GATEWAY_DEBUG    If 1, stderr lines [apollo-x-gateway] with tweet counts and skip reasons
  PROMOTER_SEARCH_USE_SINCE_ID   If 1 (default), persist X recent-search newest_id and pass since_id on the next poll (fewer duplicate tweets → smaller classify batches / lower LLM cost). Ignored when PROMOTER_DRY_RUN=1.
  PROMOTER_SEARCH_MAX_RESULTS    Recent search page size 10–100 (default 10). Lower reduces payload and classify tokens when you do not need the full page.
  PROMOTER_DEDUPE_REPLIED_TWEETS If 1 (default), skip reply-draft LLM + post for tweet IDs already replied (or dry-run consumed); avoids repeat spend if the same id reappears.
  PROMOTER_PROMPTS_DIR       Directory with classify_*.txt, reply_system.txt, daily_post_system.txt, daily_post_user_suffix.txt (default: ./prompts beside gateway_server.py)
  PROMOTER_CANONICAL_GITHUB_URL  Repo URL injected into reply prompts and used as default for daily-post link (default: https://github.com/sbhooley/ainativelang)
  PROMOTER_LLM_MAX_PROMPT_CHARS   If set, truncate chat messages to the last N characters (keeps most recent content).
  PROMOTER_LLM_MAX_COMPLETION_TOKENS  If set, pass max_tokens to the chat completions API.
  PROMOTER_LLM_EXTRA_BODY_JSON or OPENAI_CHAT_EXTRA_BODY_JSON  JSON object merged into the request body (provider-specific; e.g. sparse attention flags when supported).
  PROMOTER_PERSONA_PROFILE   Style profile for generated daily posts/replies. Default: default; also supports: fity.

  Growth pack (v1.3, all default off):
  PROMOTER_MONITOR_ENABLED     If 1, monitor-poll graphs / x.follow list maintenance active
  PROMOTER_DISCOVERY_ENABLED   If 1 (default), merge discovery + score authors from x.search and x.search_users
  PROMOTER_DISCOVERY_FROM_SEARCH  If 1 (default), after each x.search score unique tweet authors; add to monitored and optionally follow
  PROMOTER_DISCOVERY_AUTO_FOLLOW  If 1 (default), follow scored authors not already in following cache (OAuth1)
  PROMOTER_DISCOVERY_AUTO_MONITOR If 1 (default), add scored authors to monitored_accounts
  PROMOTER_DISCOVERY_MAX_AUTHORS_PER_SEARCH  Cap authors processed per x.search (default 15)
  PROMOTER_FOLLOWING_CACHE_TTL_SEC  Refresh GET /2/users/me/following cache (default 3600)
  PROMOTER_LIKE_ENABLED        If 1, gateway may like monitored authors' tweets after process_tweet
  PROMOTER_THREAD_ENABLED      If 1, promoter.thread_continue posts thread replies
  PROMOTER_AWARENESS_BOOST     If 1, append extra AINL GitHub CTAs to daily post text
  PROMOTER_DISCOVERY_MIN_SCORE Minimum heuristic score (1-10) to merge discovered users (default 7)

  Monitoring (read-only, bind localhost in production):
  PROMOTER_DASHBOARD_ENABLED   If 0/false, disables GET /v1/promoter.dashboard, .stats, .audit_tail, .memory_tail (default: 1 / on).
  PROMOTER_DASHBOARD_TWEET_LOOKUP_MAX  Max tweet IDs to resolve to @handles per dashboard JSON request via GET /2/tweets (default 120; 0 disables).
  PROMOTER_DASHBOARD_CHART_HOURS   Hour buckets for dashboard activity chart (default 48, max 168).
  PROMOTER_DASHBOARD_CHART_DAYS    Days of daily_replies history on dashboard (default 7, max 30).
  Each chat/completion logs llm.usage rows in audit (prompt/completion/total tokens + context label) when the provider returns usage.

Bind defaults to 127.0.0.1 for safety.

Optional: place a `.env` file in this directory (`apollo-x-bot/.env`) with `KEY=value` lines; the gateway loads it
on startup (see `_load_local_dotenv`). Override path with `PROMOTER_DOTENV=/path/to/file`.
"""
from __future__ import annotations

import base64
import errno
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from schemas.executor_bridge_validate import BridgeEnvelopeError, validate_executor_bridge_request

# -----------------------------------------------------------------------------
# SSL (match runtime SimpleHttpAdapter)
# -----------------------------------------------------------------------------


def _ssl_ctx() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "").strip() or default)
    except ValueError:
        return default


def _dashboard_enabled() -> bool:
    """Read-only HTML/JSON monitoring (default on; disable on shared hosts)."""
    v = os.environ.get("PROMOTER_DASHBOARD_ENABLED")
    if v is None:
        return True
    return str(v).strip().lower() in ("1", "true", "yes", "on")


_DEFAULT_CANONICAL_GITHUB = "https://github.com/sbhooley/ainativelang"


def _canonical_github_repo_url() -> str:
    raw = (os.environ.get("PROMOTER_CANONICAL_GITHUB_URL") or "").strip()
    return raw if raw else _DEFAULT_CANONICAL_GITHUB


# Known wrong / legacy URLs the reply LLM sometimes emits; rewrite before posting.
_WRONG_GITHUB_URL_PATTERNS = (
    re.compile(r"https?://(?:www\.)?github\.com/ainativelang/ainl\b", re.IGNORECASE),
)


def _normalize_promoter_github_links(text: str) -> str:
    canonical = _canonical_github_repo_url()
    out = text
    for pat in _WRONG_GITHUB_URL_PATTERNS:
        out = pat.sub(canonical, out)
    return out


def _reply_system_with_canonical_link(base: str) -> str:
    base = base.strip()
    url = _canonical_github_repo_url()
    suffix = (
        f"\n\nWhen you mention the GitHub repository, use this exact URL only (https): {url}. "
        "Do not use github.com/ainativelang/ainl or any other path."
    )
    return f"{base}{suffix}" if base else suffix.strip()


def _promoter_persona_profile() -> str:
    raw = (os.environ.get("PROMOTER_PERSONA_PROFILE") or "default").strip().lower()
    if raw in ("", "default"):
        return "default"
    if raw == "fity":
        return "fity"
    return "default"


def _promoter_persona_instructions(mode: str) -> str:
    profile = _promoter_persona_profile()
    if profile != "fity":
        return ""
    if mode == "post":
        return (
            "Persona profile: fity\n"
            "- Ultra-punchy and short: 1-2 sentences max.\n"
            "- Chill, relaxed, human motivational energy; playful edge; conversational and slightly imperfect.\n"
            "- Strong crypto/Web3 conviction with casual everyday language.\n"
            "- Start with a short observation or hot take; add a relatable human moment; add a playful/meme-friendly twist.\n"
            "- End with a direct casual question that invites replies.\n"
            "- Use light emojis naturally (for example: fire and 100).\n"
            "- Never use the word Captain or Captains."
        )
    if mode == "reply":
        return (
            "Persona profile: fity\n"
            "- Keep replies short, punchy, and conversational (1-2 sentences where possible).\n"
            "- Confident but chill crypto/Web3-native tone with light playful energy.\n"
            "- Sound human, natural, and slightly imperfect, never robotic.\n"
            "- Use simple affirmations and light emoji naturally.\n"
            "- End with a casual question when it helps drive conversation.\n"
            "- Never use the word Captain or Captains."
        )
    return ""


def _apply_persona_instructions(base: str, mode: str) -> str:
    extra = _promoter_persona_instructions(mode).strip()
    if not extra:
        return base
    b = (base or "").strip()
    return f"{b}\n\n{extra}".strip()


def _classify_score_floor() -> float:
    """Align debug metrics with graph default (see PROMOTER_CLASSIFY_MIN_SCORE in README)."""
    return float(_env_int("PROMOTER_CLASSIFY_MIN_SCORE", 5))


def _gw_debug(msg: str) -> None:
    if _env_bool("PROMOTER_GATEWAY_DEBUG", False):
        sys.stderr.write(f"[apollo-x-gateway] {msg}\n")


def _score_ge_floor(item: Dict[str, Any], floor: Optional[float] = None) -> bool:
    f = _classify_score_floor() if floor is None else floor
    raw = item.get("score", item.get("relevance", 0))
    try:
        return float(raw) >= f
    except (TypeError, ValueError):
        return False


def _count_classify_pass(items: Any, floor: Optional[float] = None) -> int:
    if not isinstance(items, list):
        return 0
    f = _classify_score_floor() if floor is None else floor
    return sum(1 for it in items if isinstance(it, dict) and _score_ge_floor(it, f))


# -----------------------------------------------------------------------------
# SQLite state
# -----------------------------------------------------------------------------


class PromoterState:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _conn(self) -> sqlite3.Connection:
        # timeout: threaded HTTP server; avoid spurious failures under light lock contention
        c = sqlite3.connect(str(self._path), timeout=30.0)
        c.row_factory = sqlite3.Row
        return c

    def _init(self) -> None:
        with self._conn() as c:
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS user_cooldown (
                    user_id TEXT PRIMARY KEY,
                    last_reply_ts REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS daily_replies (
                    day TEXT PRIMARY KEY,
                    count INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS daily_original (
                    day TEXT PRIMARY KEY,
                    tweet_id TEXT
                );
                CREATE TABLE IF NOT EXISTS audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    action TEXT NOT NULL,
                    detail_json TEXT
                );
                CREATE TABLE IF NOT EXISTS promoter_kv (
                    k TEXT PRIMARY KEY,
                    v TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS replied_tweet (
                    tweet_id TEXT PRIMARY KEY,
                    ts REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS monitored_accounts (
                    user_id TEXT PRIMARY KEY NOT NULL
                );
                CREATE TABLE IF NOT EXISTS bot_following (
                    user_id TEXT PRIMARY KEY NOT NULL
                );
                CREATE TABLE IF NOT EXISTS active_threads (
                    conversation_id TEXT PRIMARY KEY NOT NULL
                );
                CREATE TABLE IF NOT EXISTS x_user_cache (
                    user_id TEXT PRIMARY KEY NOT NULL,
                    username TEXT NOT NULL,
                    updated_ts REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS x_tweet_author_cache (
                    tweet_id TEXT PRIMARY KEY NOT NULL,
                    author_user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    updated_ts REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS original_post_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    day TEXT NOT NULL,
                    tweet_id TEXT NOT NULL,
                    posted_ts REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_original_post_log_day ON original_post_log(day);
                """
            )
            self._migrate_original_post_log_once(c)
            self._ensure_analytics_views(c)

    def _migrate_original_post_log_once(self, c: sqlite3.Connection) -> None:
        row = c.execute("SELECT v FROM promoter_kv WHERE k = 'migration_original_post_log_v1'").fetchone()
        if row:
            return
        try:
            rows = c.execute(
                "SELECT day, tweet_id FROM daily_original "
                "WHERE tweet_id IS NOT NULL AND tweet_id != '' AND tweet_id != 'dry_run'"
            ).fetchall()
            for r in rows:
                day, tid = str(r[0]), str(r[1])
                c.execute(
                    "INSERT INTO original_post_log(day, tweet_id, posted_ts) VALUES (?, ?, ?)",
                    (day, tid, 0.0),
                )
        except Exception as e:
            _gw_debug(f"migration original_post_log warn: {e!r}")
        c.execute(
            "INSERT INTO promoter_kv(k, v) VALUES ('migration_original_post_log_v1', '1') "
            "ON CONFLICT(k) DO UPDATE SET v = excluded.v"
        )

    def _ensure_analytics_views(self, c: sqlite3.Connection) -> None:
        """Human-oriented SQL views over audit (JSON1). Safe to run every startup."""
        try:
            c.executescript(
                """
            CREATE VIEW IF NOT EXISTS v_audit_timeline AS
            SELECT
              id,
              ts,
              datetime(ts, 'unixepoch') AS ts_utc,
              action,
              json_extract(detail_json, '$.tweet_id') AS tweet_id,
              json_extract(detail_json, '$.user_id') AS user_id,
              json_extract(detail_json, '$.reply_id') AS reply_id,
              json_extract(detail_json, '$.reason') AS reason,
              json_extract(detail_json, '$.context') AS llm_context,
              json_extract(detail_json, '$.model') AS llm_model,
              json_extract(detail_json, '$.total_tokens') AS total_tokens,
              detail_json
            FROM audit;

            CREATE VIEW IF NOT EXISTS v_llm_usage AS
            SELECT
              id,
              ts,
              datetime(ts, 'unixepoch') AS ts_utc,
              json_extract(detail_json, '$.context') AS context,
              json_extract(detail_json, '$.model') AS model,
              json_extract(detail_json, '$.prompt_tokens') AS prompt_tokens,
              json_extract(detail_json, '$.completion_tokens') AS completion_tokens,
              json_extract(detail_json, '$.total_tokens') AS total_tokens,
              detail_json
            FROM audit
            WHERE action = 'llm.usage';
            """
            )
        except sqlite3.OperationalError as e:
            _gw_debug(f"analytics views skipped (JSON1 or SQL): {e!r}")

    def audit_tail(self, limit: int) -> List[Dict[str, Any]]:
        lim = max(1, min(500, int(limit)))
        with self._conn() as c:
            rows = c.execute(
                """
                SELECT id, ts, datetime(ts, 'unixepoch') AS ts_utc, action, detail_json
                FROM audit ORDER BY id DESC LIMIT ?
                """,
                (lim,),
            ).fetchall()
        out: List[Dict[str, Any]] = []
        for r in rows:
            raw = r["detail_json"]
            try:
                detail = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                detail = {"_unparsed_detail": raw[:500] if raw else ""}
            if not isinstance(detail, dict):
                detail = {"value": detail}
            out.append(
                {
                    "id": r["id"],
                    "ts": r["ts"],
                    "ts_utc": r["ts_utc"],
                    "action": r["action"],
                    "detail": detail,
                }
            )
        return out

    def audit_tail_actions(self, limit: int, actions: Sequence[str]) -> List[Dict[str, Any]]:
        """Like audit_tail but only rows whose action is in ``actions`` (for dashboard scoring view)."""
        lim = max(1, min(500, int(limit)))
        acts = tuple(str(a).strip() for a in actions if str(a).strip())
        if not acts:
            return self.audit_tail(lim)
        ph = ",".join(["?"] * len(acts))
        with self._conn() as c:
            rows = c.execute(
                f"""
                SELECT id, ts, datetime(ts, 'unixepoch') AS ts_utc, action, detail_json
                FROM audit WHERE action IN ({ph}) ORDER BY id DESC LIMIT ?
                """,
                (*acts, lim),
            ).fetchall()
        out: List[Dict[str, Any]] = []
        for r in rows:
            raw = r["detail_json"]
            try:
                detail = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                detail = {"_unparsed_detail": raw[:500] if raw else ""}
            if not isinstance(detail, dict):
                detail = {"value": detail}
            out.append(
                {
                    "id": r["id"],
                    "ts": r["ts"],
                    "ts_utc": r["ts_utc"],
                    "action": r["action"],
                    "detail": detail,
                }
            )
        return out

    def x_user_cache_put(self, user_id: str, username: str) -> None:
        uid = str(user_id).strip()
        un = str(username).strip()
        if not uid or not un:
            return
        now = time.time()
        with self._conn() as c:
            c.execute(
                "INSERT INTO x_user_cache(user_id, username, updated_ts) VALUES (?, ?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET username = excluded.username, updated_ts = excluded.updated_ts",
                (uid, un, now),
            )

    def tweet_author_cache_put(self, tweet_id: str, author_user_id: str, username: str) -> None:
        tid = str(tweet_id).strip()
        aid = str(author_user_id).strip()
        if not tid or not aid:
            return
        now = time.time()
        un = str(username).strip()
        with self._conn() as c:
            c.execute(
                "INSERT INTO x_tweet_author_cache(tweet_id, author_user_id, username, updated_ts) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(tweet_id) DO UPDATE SET author_user_id = excluded.author_user_id, "
                "username = excluded.username, updated_ts = excluded.updated_ts",
                (tid, aid, un, now),
            )

    def day_key(self) -> str:
        return time.strftime("%Y-%m-%d", time.gmtime())

    def count_today_replies(self) -> int:
        d = self.day_key()
        with self._conn() as c:
            row = c.execute("SELECT count FROM daily_replies WHERE day = ?", (d,)).fetchone()
            return int(row[0]) if row else 0

    def incr_today_replies(self) -> None:
        d = self.day_key()
        with self._conn() as c:
            c.execute(
                "INSERT INTO daily_replies(day, count) VALUES (?, 1) ON CONFLICT(day) DO UPDATE SET count = count + 1",
                (d,),
            )

    def user_cooldown_ok(self, user_id: str, hours: float) -> bool:
        if not user_id:
            return True
        now = time.time()
        with self._conn() as c:
            row = c.execute("SELECT last_reply_ts FROM user_cooldown WHERE user_id = ?", (user_id,)).fetchone()
            if not row:
                return True
            return (now - float(row[0])) >= hours * 3600.0

    def touch_user(self, user_id: str) -> None:
        if not user_id:
            return
        now = time.time()
        with self._conn() as c:
            c.execute(
                "INSERT INTO user_cooldown(user_id, last_reply_ts) VALUES (?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET last_reply_ts = excluded.last_reply_ts",
                (user_id, now),
            )

    def count_original_posts_today(self) -> int:
        d = self.day_key()
        with self._conn() as c:
            row = c.execute("SELECT COUNT(*) FROM original_post_log WHERE day = ?", (d,)).fetchone()
            return int(row[0]) if row and row[0] is not None else 0

    def last_original_post_ts_today(self) -> Optional[float]:
        d = self.day_key()
        with self._conn() as c:
            row = c.execute("SELECT MAX(posted_ts) FROM original_post_log WHERE day = ?", (d,)).fetchone()
            if row and row[0] is not None:
                return float(row[0])
        return None

    def append_original_post_log(self, tweet_id: str, posted_ts: Optional[float] = None) -> None:
        tid = str(tweet_id).strip()
        if not tid:
            return
        d = self.day_key()
        ts = float(posted_ts if posted_ts is not None else time.time())
        with self._conn() as c:
            c.execute(
                "INSERT INTO original_post_log(day, tweet_id, posted_ts) VALUES (?, ?, ?)",
                (d, tid, ts),
            )

    def audit(self, action: str, detail: Dict[str, Any]) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO audit(ts, action, detail_json) VALUES (?, ?, ?)",
                (time.time(), action, json.dumps(detail, ensure_ascii=False)),
            )

    def kv_get(self, key: str) -> Optional[str]:
        with self._conn() as c:
            row = c.execute("SELECT v FROM promoter_kv WHERE k = ?", (key,)).fetchone()
            return str(row[0]) if row else None

    def kv_set(self, key: str, value: str) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO promoter_kv(k, v) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET v = excluded.v",
                (key, value),
            )

    def kv_delete(self, key: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM promoter_kv WHERE k = ?", (key,))

    def has_replied_to_tweet(self, tweet_id: str) -> bool:
        if not tweet_id:
            return False
        with self._conn() as c:
            row = c.execute("SELECT 1 FROM replied_tweet WHERE tweet_id = ?", (tweet_id,)).fetchone()
            return row is not None

    def mark_replied_tweet(self, tweet_id: str) -> None:
        if not tweet_id:
            return
        with self._conn() as c:
            c.execute(
                "INSERT INTO replied_tweet(tweet_id, ts) VALUES (?, ?) "
                "ON CONFLICT(tweet_id) DO UPDATE SET ts = excluded.ts",
                (tweet_id, time.time()),
            )


# -----------------------------------------------------------------------------
# HTTP helpers
# -----------------------------------------------------------------------------


def _http_request(
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    body: Optional[bytes] = None,
    timeout: float = 120.0,
) -> Tuple[int, Dict[str, str], bytes]:
    req = urllib.request.Request(url, data=body, method=method.upper())
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as resp:
            status = int(getattr(resp, "status", 200))
            hdrs = {k.lower(): v for k, v in dict(resp.headers).items()}
            data = resp.read()
            return status, hdrs, data
    except urllib.error.HTTPError as e:
        hdrs = {k.lower(): v for k, v in dict(e.headers).items()} if e.headers else {}
        data = e.read() if e.fp else b""
        return int(e.code), hdrs, data


def _rfc3986(s: str) -> str:
    return urllib.parse.quote(str(s), safe="~")


def _x_oauth1_creds() -> Optional[Tuple[str, str, str, str]]:
    ck = (os.environ.get("X_API_KEY") or os.environ.get("X_CONSUMER_KEY") or "").strip()
    cs = (os.environ.get("X_API_SECRET") or os.environ.get("X_CONSUMER_SECRET") or "").strip()
    tok = (os.environ.get("X_ACCESS_TOKEN") or "").strip()
    tok_sec = (os.environ.get("X_ACCESS_TOKEN_SECRET") or "").strip()
    if ck and cs and tok and tok_sec:
        return (ck, cs, tok, tok_sec)
    return None


def _x_bearer() -> Optional[str]:
    t = (os.environ.get("X_BEARER_TOKEN") or os.environ.get("TWITTER_BEARER_TOKEN") or "").strip()
    return t or None


def _oauth1_authorization_header(method: str, full_url: str, ck: str, cs: str, tok: str, tok_sec: str) -> str:
    """OAuth 1.0a (HMAC-SHA1) for Twitter API v2. Query string on full_url is included in the signature."""
    parsed = urllib.parse.urlparse(full_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    pairs: List[Tuple[str, str]] = []
    if parsed.query:
        for k, v in urllib.parse.parse_qsl(parsed.query, strict_parsing=False):
            pairs.append((k, v))
    oauth_vals: Dict[str, str] = {
        "oauth_consumer_key": ck,
        "oauth_nonce": secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": tok,
        "oauth_version": "1.0",
    }
    for k, v in oauth_vals.items():
        pairs.append((k, v))
    sorted_pairs = sorted(pairs, key=lambda x: (x[0], x[1]))
    param_str = "&".join(f"{_rfc3986(k)}={_rfc3986(v)}" for k, v in sorted_pairs)
    sig_base = "&".join([method.upper(), _rfc3986(base_url), _rfc3986(param_str)])
    signing_key = f"{_rfc3986(cs)}&{_rfc3986(tok_sec)}"
    sig = base64.b64encode(
        hmac.new(signing_key.encode("utf-8"), sig_base.encode("utf-8"), hashlib.sha1).digest()
    ).decode("ascii")
    oauth_vals["oauth_signature"] = sig
    auth_parts = [f'{_rfc3986(k)}="{_rfc3986(v)}"' for k, v in sorted(oauth_vals.items())]
    return "OAuth " + ", ".join(auth_parts)


def _resolve_sqlite_file_path(path: Path, *, default_filename: str) -> Path:
    """
    Normalize SQLite paths for env vars. If the path exists and is a directory, use
    <dir>/<default_filename> (common misconfiguration: PROMOTER_STATE_PATH=/path/to/data).
    Prefer absolute paths so the gateway does not depend on process cwd after startup.
    """
    p = path.expanduser()
    try:
        try:
            p = p.resolve(strict=False)
        except TypeError:
            p = p.resolve()
    except (OSError, RuntimeError):
        p = Path(os.path.normpath(str(p)))
    try:
        if p.exists() and p.is_dir():
            p = p / default_filename
    except OSError:
        pass
    return p


def _memory_db_path() -> Path:
    raw = (os.environ.get("AINL_MEMORY_DB") or "").strip()
    if raw:
        return _resolve_sqlite_file_path(Path(raw), default_filename="promoter_memory.sqlite")
    return _resolve_sqlite_file_path(
        Path(__file__).resolve().parent / "data" / "promoter_memory.sqlite",
        default_filename="promoter_memory.sqlite",
    )


def _normalize_chat_usage(raw: Any) -> Dict[str, int]:
    """Map provider usage blob to prompt/completion/total (OpenAI-compatible + some aliases)."""
    if not isinstance(raw, dict):
        return {}
    pt = raw.get("prompt_tokens")
    if pt is None:
        pt = raw.get("input_tokens")
    ct = raw.get("completion_tokens")
    if ct is None:
        ct = raw.get("output_tokens")
    tt = raw.get("total_tokens")
    try:
        pi = int(pt or 0)
        ci = int(ct or 0)
        if tt is None:
            ti = pi + ci
        else:
            ti = int(tt)
    except (TypeError, ValueError):
        return {}
    if pi == 0 and ci == 0 and ti == 0:
        return {}
    return {"prompt_tokens": pi, "completion_tokens": ci, "total_tokens": ti}


def _llm_extra_chat_body() -> Dict[str, Any]:
    """Merge provider-specific keys (e.g. sparse attention) from JSON env."""
    raw = (
        os.environ.get("PROMOTER_LLM_EXTRA_BODY_JSON")
        or os.environ.get("OPENAI_CHAT_EXTRA_BODY_JSON")
        or ""
    ).strip()
    if not raw:
        return {}
    try:
        out = json.loads(raw)
        return out if isinstance(out, dict) else {}
    except json.JSONDecodeError:
        _gw_debug("llm.extra_body_json: invalid JSON, ignoring")
        return {}


def _truncate_chat_messages(messages: List[Dict[str, str]], max_chars: int) -> List[Dict[str, str]]:
    """Keep the most recent tail of the conversation under a character budget."""
    if max_chars <= 0:
        return messages
    total = sum(len(str(m.get("content") or "")) for m in messages)
    if total <= max_chars:
        return messages
    out: List[Dict[str, str]] = []
    remaining = max_chars
    for m in reversed(messages):
        c = str(m.get("content") or "")
        if len(c) <= remaining:
            out.insert(0, dict(m))
            remaining -= len(c)
        else:
            if remaining > 0:
                mm = dict(m)
                mm["content"] = c[-remaining:]
                out.insert(0, mm)
            break
    return out


def _openai_chat(
    messages: List[Dict[str, str]],
    *,
    model: Optional[str] = None,
    state: Optional[PromoterState] = None,
    usage_context: str = "",
    temperature: Optional[float] = None,
) -> str:
    key = os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY or LLM_API_KEY not set")
    base = (os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    model_env = (os.environ.get("LLM_MODEL") or "").strip()
    if not model_env and "openrouter.ai" in base.lower():
        # Keep OpenRouter default deterministic for the promoter.
        model_env = "stepfun/step-3.5-flash:free"
    model_used = model or model_env or "gpt-4o-mini"
    temp = 0.2 if temperature is None else float(temperature)
    max_prompt = 0
    try:
        max_prompt = int((os.environ.get("PROMOTER_LLM_MAX_PROMPT_CHARS") or "0").strip() or "0")
    except ValueError:
        max_prompt = 0
    if max_prompt > 0:
        before = sum(len(str(m.get("content") or "")) for m in messages)
        messages = _truncate_chat_messages(messages, max_prompt)
        after = sum(len(str(m.get("content") or "")) for m in messages)
        if after < before:
            _gw_debug(f"llm.prompt_truncated context={usage_context} chars {before}->{after}")
    max_completion = 0
    try:
        max_completion = int((os.environ.get("PROMOTER_LLM_MAX_COMPLETION_TOKENS") or "0").strip() or "0")
    except ValueError:
        max_completion = 0
    body: Dict[str, Any] = {"model": model_used, "messages": messages, "temperature": temp}
    if max_completion > 0:
        body["max_tokens"] = max_completion
    extra = _llm_extra_chat_body()
    if extra:
        body.update(extra)
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    status, _h, data = _http_request(
        "POST",
        f"{base}/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        body=payload,
        timeout=120.0,
    )
    if status >= 400:
        raise RuntimeError(f"LLM HTTP {status}: {data[:500]!r}")
    obj = json.loads(data.decode("utf-8"))
    usage_raw = _normalize_chat_usage(obj.get("usage"))
    if state is not None and usage_context and usage_raw:
        detail: Dict[str, Any] = {"context": usage_context, "model": model_used, **usage_raw}
        state.audit("llm.usage", detail)
        _gw_debug(
            f"llm.usage context={usage_context} model={model_used} "
            f"prompt_tokens={usage_raw.get('prompt_tokens')} "
            f"completion_tokens={usage_raw.get('completion_tokens')} "
            f"total_tokens={usage_raw.get('total_tokens')}"
        )
    return str((obj.get("choices") or [{}])[0].get("message", {}).get("content") or "")


def _extract_json_array(text: str) -> Any:
    text = text.strip()
    m = re.search(r"\[[\s\S]*\]", text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return json.loads(text)


_DEFAULT_HEURISTIC_KEYS: Tuple[str, ...] = (
    "openclaw",
    "zeroclaw",
    "agent framework",
    "ai agent",
    "orchestr",
    "deterministic",
    "memory",
    "workflow",
    "tokens",
    "orchestration",
    "adapters",
    "workflows",
    "graph",
    "substrate",
    "control flow",
    "IR",
    "prompt",
    "loops",
    "infastructure",
    "hermes-agent",
    "building ai agent",
)


def _heuristic_scores(
    tweets: List[Dict[str, Any]],
    *,
    keys: Optional[Tuple[str, ...]] = None,
) -> List[Dict[str, Any]]:
    use_keys = keys if keys else _DEFAULT_HEURISTIC_KEYS
    out: List[Dict[str, Any]] = []
    for t in tweets:
        tid = str(t.get("id", ""))
        blob = json.dumps(t, ensure_ascii=False).lower()
        score = 3
        for k in use_keys:
            if k in blob:
                score += 1
        score = min(10, max(1, score))
        out.append(
            {
                "id": tid,
                "score": float(score),
                "why": "heuristic_keyword_match",
                **{k: v for k, v in t.items() if k not in ("score", "why")},
            }
        )
    return out


def _http_inner_dict(body: Dict[str, Any]) -> Dict[str, Any]:
    """Prefer executor-bridge payload object when present."""
    p = body.get("payload")
    if isinstance(p, dict) and p:
        return p
    return body


def _classify_wants_envelope(inner: Dict[str, Any]) -> bool:
    """True only when the client supplied OpenAI-style chat messages.

    Do **not** treat ``classify_response=raw`` alone as envelope mode: the executor-bridge
    payload often sets that flag together with ``tweets`` but omits ``messages`` on malformed
    or probe requests; those should fall through to the legacy tweet+prompt path instead of
    ``envelope_missing_messages``.
    """
    msgs = inner.get("messages")
    return isinstance(msgs, list) and len(msgs) > 0


def _merge_scores_onto_tweets(tweets: List[Any], parsed: List[Any]) -> List[Dict[str, Any]]:
    """Same merge semantics as the historical handle_llm_classify loop (score/why, skip non-dict tweets)."""
    out: List[Dict[str, Any]] = []
    for i, tw in enumerate(tweets):
        if not isinstance(tw, dict):
            continue
        row: Dict[str, Any] = {}
        if i < len(parsed) and isinstance(parsed[i], dict):
            row = parsed[i]
        merged = dict(tw)
        sc = row.get("score", row.get("relevance", 0))
        try:
            merged["score"] = float(sc)
        except (TypeError, ValueError):
            merged["score"] = 0.0
        if row.get("why"):
            merged["why"] = row.get("why")
        out.append(merged)
    return out


# -----------------------------------------------------------------------------
# X API v2
# -----------------------------------------------------------------------------


def _search_max_results() -> int:
    n = _env_int("PROMOTER_SEARCH_MAX_RESULTS", 10)
    return max(10, min(100, n))


def _x_recent_search(
    query: str,
    *,
    since_id: Optional[str] = None,
    max_results: int = 10,
    state: Optional[PromoterState] = None,
) -> Dict[str, Any]:
    q = urllib.parse.quote(query, safe="")
    mr = max(10, min(100, max_results))
    url = (
        f"https://api.twitter.com/2/tweets/search/recent?query={q}&max_results={mr}"
        "&tweet.fields=author_id,created_at&expansions=author_id&user.fields=username"
    )
    sid = (since_id or "").strip()
    if sid:
        url += f"&since_id={urllib.parse.quote(sid, safe='')}"
    bearer = _x_bearer()
    oauth = _x_oauth1_creds()
    try:
        if bearer:
            status, _h, data = _http_request(
                "GET",
                url,
                headers={"Authorization": f"Bearer {bearer}"},
                timeout=120.0,
            )
        elif oauth:
            ck, cs, tok, ts = oauth
            auth = _oauth1_authorization_header("GET", url, ck, cs, tok, ts)
            status, _h, data = _http_request("GET", url, headers={"Authorization": auth}, timeout=120.0)
        else:
            return {"tweets": [], "warning": "Set X_BEARER_TOKEN (search) or full OAuth1 keys (X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET)"}
        if status >= 400:
            return {"tweets": [], "error": f"x_search_http_{status}", "detail": data.decode("utf-8", errors="replace")[:500]}
        raw_text = data.decode("utf-8") if data else ""
        try:
            obj = json.loads(raw_text)
        except json.JSONDecodeError as je:
            return {
                "tweets": [],
                "error": "x_search_invalid_json",
                "detail": str(je),
                "snippet": raw_text[:400],
            }
    except (urllib.error.URLError, TimeoutError, OSError, ConnectionError) as e:
        return {"tweets": [], "error": "x_search_network", "detail": str(e)}
    except Exception as e:
        return {"tweets": [], "error": "x_search_request_failed", "detail": str(e)}
    if not isinstance(obj, dict):
        return {"tweets": [], "error": "x_search_unexpected_json", "detail": type(obj).__name__}
    raw = obj.get("data") or []
    users_by_id: Dict[str, str] = {}
    for u in (obj.get("includes") or {}).get("users") or []:
        if isinstance(u, dict):
            iid = str(u.get("id", "")).strip()
            uu = str(u.get("username", "")).strip()
            if iid and uu:
                users_by_id[iid] = uu
    _x_user_cache_warm_map(state, users_by_id)
    tweets: List[Dict[str, Any]] = []
    for tw in raw:
        uid_str = str(tw.get("author_id", "")).strip()
        uname = users_by_id.get(uid_str, "")
        tweets.append(
            {
                "id": str(tw.get("id", "")),
                "text": str(tw.get("text", "")),
                "user_id": uid_str,
                "username": uname,
                "created_at": tw.get("created_at"),
            }
        )
    return {"tweets": tweets, "meta": obj.get("meta") or {}}


def _x_post_reply(text: str, reply_to_id: str) -> Dict[str, Any]:
    rid = str(reply_to_id or "").strip()
    if not rid:
        return {
            "ok": False,
            "error": "missing_in_reply_to_tweet_id",
            "detail": "Cannot reply without a valid parent tweet id (check classify/search payload includes id).",
        }
    url = "https://api.twitter.com/2/tweets"
    payload = json.dumps(
        {"text": text, "reply": {"in_reply_to_tweet_id": rid}},
        ensure_ascii=False,
    ).encode("utf-8")
    oauth = _x_oauth1_creds()
    bearer = _x_bearer()
    if oauth:
        ck, cs, tok, ts = oauth
        auth = _oauth1_authorization_header("POST", url, ck, cs, tok, ts)
        status, _h, data = _http_request(
            "POST",
            url,
            headers={"Authorization": auth, "Content-Type": "application/json"},
            body=payload,
            timeout=60.0,
        )
    elif bearer:
        status, _h, data = _http_request(
            "POST",
            url,
            headers={"Authorization": f"Bearer {bearer}", "Content-Type": "application/json"},
            body=payload,
            timeout=60.0,
        )
    else:
        return {
            "ok": False,
            "error": "no_x_auth",
            "detail": "Set OAuth 1.0a user tokens (X_ACCESS_TOKEN + X_ACCESS_TOKEN_SECRET + X_API_KEY + X_API_SECRET) to post. Bearer alone is often rejected for POST /2/tweets.",
        }
    obj = json.loads(data.decode("utf-8")) if data else {}
    if status >= 400:
        return {"ok": False, "error": f"post_http_{status}", "detail": obj}
    tid = str((obj.get("data") or {}).get("id", "") or "")
    return {"ok": True, "tweet_id": tid, "raw": obj}


def _x_post_original(text: str) -> Dict[str, Any]:
    url = "https://api.twitter.com/2/tweets"
    payload = json.dumps({"text": text}, ensure_ascii=False).encode("utf-8")
    oauth = _x_oauth1_creds()
    bearer = _x_bearer()
    if oauth:
        ck, cs, tok, ts = oauth
        auth = _oauth1_authorization_header("POST", url, ck, cs, tok, ts)
        status, _h, data = _http_request(
            "POST",
            url,
            headers={"Authorization": auth, "Content-Type": "application/json"},
            body=payload,
            timeout=60.0,
        )
    elif bearer:
        status, _h, data = _http_request(
            "POST",
            url,
            headers={"Authorization": f"Bearer {bearer}", "Content-Type": "application/json"},
            body=payload,
            timeout=60.0,
        )
    else:
        return {
            "ok": False,
            "error": "no_x_auth",
            "detail": "Set OAuth 1.0a user tokens (X_ACCESS_TOKEN + X_ACCESS_TOKEN_SECRET + X_API_KEY + X_API_SECRET) to post.",
        }
    obj = json.loads(data.decode("utf-8")) if data else {}
    if status >= 400:
        return {"ok": False, "error": f"post_http_{status}", "detail": obj}
    tid = str((obj.get("data") or {}).get("id", "") or "")
    return {"ok": True, "tweet_id": tid, "raw": obj}


def _x_error_message(post_result: Dict[str, Any]) -> str:
    """Best-effort extraction of human-readable X API error text."""
    if not isinstance(post_result, dict):
        return ""
    detail = post_result.get("detail")
    if isinstance(detail, dict):
        msg = detail.get("detail")
        if isinstance(msg, str) and msg.strip():
            return msg.strip()
        errs = detail.get("errors")
        if isinstance(errs, list):
            parts: List[str] = []
            for e in errs:
                if not isinstance(e, dict):
                    continue
                em = e.get("message")
                if isinstance(em, str) and em.strip():
                    parts.append(em.strip())
            if parts:
                return " | ".join(parts)
    if isinstance(detail, str):
        return detail.strip()
    return ""


def _is_x_duplicate_content_error(post_result: Dict[str, Any]) -> bool:
    msg = _x_error_message(post_result).lower()
    if not msg:
        return False
    return ("duplicate content" in msg) or ("duplicate" in msg and "tweet" in msg)


def _refactor_daily_text_for_duplicate(
    *,
    topic: str,
    link: str,
    previous_text: str,
    attempt: int,
    state: Optional["PromoterState"] = None,
) -> str:
    """Rewrite daily text when X rejects duplicate content."""
    prior = str(previous_text or "").strip()
    if not prior:
        prior = f"{topic} — deterministic agent graphs as code. {link}"
    # Deterministic fallback if LLM is unavailable or fails.
    fallback = _normalize_promoter_github_links(
        f"{topic} update #{attempt + 1}: new angle on deterministic AINL workflows. {link} "
        f"(fresh phrasing {int(time.time()) % 100000})"
    )
    fallback = re.sub(r"\s+", " ", fallback).strip()[:280]
    try:
        if os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY"):
            rewritten = _openai_chat(
                [
                    {
                        "role": "system",
                        "content": (
                            "You rewrite X posts to avoid duplicate-content rejection. "
                            "Output ONE unique post under 260 chars, preserving intent and the exact link."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Original post rejected as duplicate:\n{prior}\n\n"
                            f"Topic: {topic}\n"
                            f"Required link (must appear exactly): {link}\n"
                            "Rewrite with a materially different opening, structure, and wording."
                        ),
                    },
                ],
                state=state,
                usage_context="daily_original_post_refactor",
            ).strip()
            rewritten = _normalize_promoter_github_links(rewritten)
            rewritten = re.sub(r"\s+", " ", rewritten).strip()[:280]
            if rewritten and rewritten.lower() != prior.lower():
                return rewritten
    except Exception:
        pass
    return fallback


# -----------------------------------------------------------------------------
# Growth pack helpers (KV lists, X follow/like/me, conversation fetch)
# -----------------------------------------------------------------------------


def _kv_str_list_get(state: PromoterState, key: str) -> List[str]:
    raw = state.kv_get(key)
    if not raw:
        return []
    try:
        v = json.loads(raw)
        if not isinstance(v, list):
            return []
        return [str(x).strip() for x in v if str(x).strip()]
    except json.JSONDecodeError:
        return []


def _kv_str_list_set(state: PromoterState, key: str, items: List[str]) -> None:
    state.kv_set(key, json.dumps(items, ensure_ascii=False))


def _monitored_add(state: PromoterState, user_id: str) -> None:
    uid = str(user_id).strip()
    if not uid:
        return
    xs = _kv_str_list_get(state, "monitored_accounts")
    if uid not in xs:
        xs.append(uid)
        _kv_str_list_set(state, "monitored_accounts", xs)
        with state._conn() as c:
            c.execute("INSERT OR IGNORE INTO monitored_accounts(user_id) VALUES (?)", (uid,))


def _thread_track(state: PromoterState, conversation_id: str) -> None:
    cid = str(conversation_id).strip()
    if not cid:
        return
    xs = _kv_str_list_get(state, "active_threads")
    if cid not in xs:
        xs.append(cid)
        _kv_str_list_set(state, "active_threads", xs)
        with state._conn() as c:
            c.execute(
                "INSERT OR IGNORE INTO active_threads(conversation_id) VALUES (?)",
                (cid,),
            )


def _cached_me_id(state: PromoterState) -> Optional[str]:
    cached = (state.kv_get("x_promoter_user_id") or "").strip()
    if cached:
        return cached
    oauth = _x_oauth1_creds()
    if not oauth:
        return None
    url = "https://api.twitter.com/2/users/me"
    ck, cs, tok, ts = oauth
    auth = _oauth1_authorization_header("GET", url, ck, cs, tok, ts)
    status, _h, data = _http_request("GET", url, headers={"Authorization": auth}, timeout=60.0)
    if status >= 400:
        return None
    obj = json.loads(data.decode("utf-8"))
    uid = str((obj.get("data") or {}).get("id", "") or "")
    if uid:
        state.kv_set("x_promoter_user_id", uid)
    return uid or None


def _x_fetch_following_ids(state: PromoterState) -> Set[str]:
    """OAuth1: paginate GET /2/users/:me/following into a set of user ids."""
    me = _cached_me_id(state)
    if not me:
        return set()
    oauth = _x_oauth1_creds()
    if not oauth:
        return set()
    ck, cs, tok, ts = oauth
    out: Set[str] = set()
    pagination_token: Optional[str] = None
    for _ in range(200):
        url = f"https://api.twitter.com/2/users/{me}/following?max_results=1000&user.fields=id"
        if pagination_token:
            url += "&pagination_token=" + urllib.parse.quote(pagination_token, safe="")
        auth = _oauth1_authorization_header("GET", url, ck, cs, tok, ts)
        status, _h, data = _http_request("GET", url, headers={"Authorization": auth}, timeout=120.0)
        if status >= 400:
            break
        try:
            obj = json.loads(data.decode("utf-8"))
        except json.JSONDecodeError:
            break
        for u in obj.get("data") or []:
            if isinstance(u, dict):
                iid = str(u.get("id", "")).strip()
                if iid:
                    out.add(iid)
        meta = obj.get("meta") if isinstance(obj.get("meta"), dict) else {}
        pagination_token = meta.get("next_token")
        if not pagination_token:
            break
        if len(out) > 20000:
            break
    return out


def _refresh_bot_following_cache(state: PromoterState) -> Set[str]:
    ids = _x_fetch_following_ids(state)
    now = time.time()
    with state._conn() as c:
        c.execute("DELETE FROM bot_following")
        for uid in ids:
            c.execute("INSERT OR IGNORE INTO bot_following(user_id) VALUES (?)", (uid,))
    state.kv_set("following_cache_ts", str(now))
    return ids


def _following_set_cached(state: PromoterState) -> Set[str]:
    ttl = max(60, _env_int("PROMOTER_FOLLOWING_CACHE_TTL_SEC", 3600))
    raw_ts = state.kv_get("following_cache_ts")
    now = time.time()
    try:
        ts = float(raw_ts) if raw_ts else 0.0
    except ValueError:
        ts = 0.0
    if raw_ts and (now - ts) < float(ttl):
        with state._conn() as c:
            rows = c.execute("SELECT user_id FROM bot_following").fetchall()
        return {str(r[0]) for r in rows}
    return _refresh_bot_following_cache(state)


def _x_users_lookup(ids: List[str]) -> List[Dict[str, Any]]:
    ids = [str(i).strip() for i in ids if str(i).strip()]
    if not ids:
        return []
    oauth = _x_oauth1_creds()
    bearer = _x_bearer()
    out: List[Dict[str, Any]] = []
    for i in range(0, len(ids), 100):
        chunk = ids[i : i + 100]
        q = "ids=" + ",".join(_rfc3986(x) for x in chunk)
        q += "&user.fields=description,username,name"
        url = f"https://api.twitter.com/2/users?{q}"
        try:
            if oauth:
                ck, cs, tok, ts = oauth
                auth = _oauth1_authorization_header("GET", url, ck, cs, tok, ts)
                status, _h, data = _http_request("GET", url, headers={"Authorization": auth}, timeout=60.0)
            elif bearer:
                status, _h, data = _http_request(
                    "GET", url, headers={"Authorization": f"Bearer {bearer}"}, timeout=60.0
                )
            else:
                break
            if status >= 400:
                break
            try:
                obj = json.loads(data.decode("utf-8"))
            except json.JSONDecodeError:
                continue
        except (urllib.error.URLError, OSError, TimeoutError, ConnectionError):
            break
        for u in obj.get("data") or []:
            if isinstance(u, dict):
                out.append(
                    {
                        "user_id": str(u.get("id", "")),
                        "username": str(u.get("username", "")),
                        "name": str(u.get("name", "")),
                        "description": str(u.get("description", "")),
                    }
                )
    return out


_X_USER_CACHE_TTL_SEC = 7 * 24 * 3600


def _gather_numeric_user_ids(obj: Any, acc: Set[str], depth: int = 0) -> None:
    if depth > 5:
        return
    if isinstance(obj, dict):
        for k in ("user_id", "target_user_id", "author_id"):
            v = obj.get(k)
            if v is not None and str(v).strip().isdigit():
                acc.add(str(v).strip())
        for v in obj.values():
            if isinstance(v, (dict, list)):
                _gather_numeric_user_ids(v, acc, depth + 1)
    elif isinstance(obj, list):
        for it in obj[:100]:
            _gather_numeric_user_ids(it, acc, depth + 1)


def _looks_like_x_numeric_id(v: Any) -> bool:
    s = str(v).strip()
    return bool(s) and s.isdigit() and len(s) >= 15


def _gather_tweet_ids_for_author_lookup(obj: Any, acc: Set[str], depth: int = 0) -> None:
    """Collect tweet snowflake IDs from audit/memory JSON (tweet_id / reply_id; not since_id)."""
    if depth > 5:
        return
    if isinstance(obj, dict):
        for k in ("tweet_id", "reply_id", "in_reply_to_tweet_id"):
            val = obj.get(k)
            if _looks_like_x_numeric_id(val):
                acc.add(str(val).strip())
        for v in obj.values():
            if isinstance(v, (dict, list)):
                _gather_tweet_ids_for_author_lookup(v, acc, depth + 1)
    elif isinstance(obj, list):
        for it in obj[:100]:
            _gather_tweet_ids_for_author_lookup(it, acc, depth + 1)


def _x_http_tweet_id_to_author(ids: List[str]) -> Dict[str, Dict[str, str]]:
    """GET /2/tweets — map tweet_id -> {user_id, username}. Up to 100 ids per call."""
    ids = [str(x).strip() for x in ids if _looks_like_x_numeric_id(x)]
    if not ids:
        return {}
    url = (
        "https://api.twitter.com/2/tweets?ids="
        + ",".join(_rfc3986(x) for x in ids)
        + "&tweet.fields=author_id&expansions=author_id&user.fields=username"
    )
    bearer = _x_bearer()
    oauth = _x_oauth1_creds()
    try:
        if bearer:
            status, _h, data = _http_request(
                "GET",
                url,
                headers={"Authorization": f"Bearer {bearer}"},
                timeout=60.0,
            )
        elif oauth:
            ck, cs, tok, ts = oauth
            auth = _oauth1_authorization_header("GET", url, ck, cs, tok, ts)
            status, _h, data = _http_request("GET", url, headers={"Authorization": auth}, timeout=60.0)
        else:
            return {}
    except (urllib.error.URLError, OSError, TimeoutError, ConnectionError):
        return {}
    if status >= 400:
        return {}
    try:
        obj = json.loads(data.decode("utf-8"))
    except json.JSONDecodeError:
        return {}
    users_by_id: Dict[str, str] = {}
    for u in (obj.get("includes") or {}).get("users") or []:
        if isinstance(u, dict):
            iid = str(u.get("id", "")).strip()
            uu = str(u.get("username", "")).strip()
            if iid and uu:
                users_by_id[iid] = uu
    out: Dict[str, Dict[str, str]] = {}
    for tw in obj.get("data") or []:
        if not isinstance(tw, dict):
            continue
        tid = str(tw.get("id", "")).strip()
        aid = str(tw.get("author_id", "")).strip()
        if not tid or not aid:
            continue
        un = users_by_id.get(aid, "")
        out[tid] = {"user_id": aid, "username": un}
    return out


def _x_tweets_resolve_authors(state: PromoterState, tweet_ids: Set[str]) -> Dict[str, Dict[str, str]]:
    """
    Resolve tweet_id -> author user_id + @username for dashboard enrichment.
    Uses SQLite cache + batched /2/tweets (same creds as search).
    """
    cap = max(0, _env_int("PROMOTER_DASHBOARD_TWEET_LOOKUP_MAX", 120))
    if cap == 0 or not tweet_ids:
        return {}
    tids = sorted(tweet_ids)
    if len(tids) > cap:
        tids = tids[:cap]
    now = time.time()
    out: Dict[str, Dict[str, str]] = {}
    need: List[str] = []
    with state._conn() as c:
        for tid in tids:
            row = c.execute(
                "SELECT author_user_id, username, updated_ts FROM x_tweet_author_cache WHERE tweet_id = ?",
                (tid,),
            ).fetchone()
            if row and (now - float(row[2])) < _X_USER_CACHE_TTL_SEC:
                out[tid] = {"user_id": str(row[0] or ""), "username": str(row[1] or "")}
            else:
                need.append(tid)
    for i in range(0, len(need), 100):
        chunk = need[i : i + 100]
        batch = _x_http_tweet_id_to_author(chunk)
        for tid, info in batch.items():
            aid = str(info.get("user_id") or "").strip()
            un = str(info.get("username") or "").strip()
            if aid:
                state.tweet_author_cache_put(tid, aid, un)
                if un:
                    state.x_user_cache_put(aid, un)
            out[tid] = {"user_id": aid, "username": un}
    return out


def _enrich_detail_handles(
    obj: Any,
    resolved: Dict[str, str],
    by_tweet: Dict[str, Dict[str, str]],
    depth: int = 0,
) -> Any:
    if depth > 5:
        return obj
    if isinstance(obj, dict):
        newd: Dict[str, Any] = {}
        for k, v in obj.items():
            newd[k] = _enrich_detail_handles(v, resolved, by_tweet, depth + 1)
        uid = str(newd.get("user_id") or "").strip()
        if uid in resolved and not str(newd.get("username") or "").strip():
            newd["username"] = resolved[uid]
        tuid = str(newd.get("target_user_id") or "").strip()
        if tuid in resolved and not str(newd.get("target_username") or "").strip():
            newd["target_username"] = resolved[tuid]
        tid = str(newd.get("tweet_id") or "").strip()
        if tid in by_tweet:
            bt = by_tweet[tid]
            if not str(newd.get("user_id") or "").strip() and str(bt.get("user_id") or "").strip():
                newd["user_id"] = str(bt["user_id"])
            if not str(newd.get("username") or "").strip() and str(bt.get("username") or "").strip():
                newd["username"] = str(bt["username"])
        rid = str(newd.get("reply_id") or "").strip()
        if rid in by_tweet and not str(newd.get("reply_username") or "").strip():
            ru = str(by_tweet[rid].get("username") or "").strip()
            if ru:
                newd["reply_username"] = ru
        return newd
    if isinstance(obj, list):
        return [_enrich_detail_handles(x, resolved, by_tweet, depth + 1) for x in obj[:200]]
    return obj


def _resolve_usernames_batch(state: PromoterState, user_ids: Set[str]) -> Dict[str, str]:
    ids = {x for x in (str(y).strip() for y in user_ids) if x.isdigit()}
    if not ids:
        return {}
    now = time.time()
    out: Dict[str, str] = {}
    need: List[str] = []
    with state._conn() as c:
        for uid in ids:
            row = c.execute(
                "SELECT username, updated_ts FROM x_user_cache WHERE user_id = ?",
                (uid,),
            ).fetchone()
            if row and (now - float(row[1])) < _X_USER_CACHE_TTL_SEC:
                out[uid] = str(row[0])
            else:
                need.append(uid)
    for i in range(0, len(need), 100):
        chunk = need[i : i + 100]
        for u in _x_users_lookup(chunk):
            uid = str(u.get("user_id", "")).strip()
            un = str(u.get("username", "")).strip()
            if uid and un:
                out[uid] = un
                state.x_user_cache_put(uid, un)
    return out


def _x_user_cache_warm_map(state: Optional[PromoterState], id_to_username: Dict[str, str]) -> None:
    if state is None or not id_to_username:
        return
    for uid, un in id_to_username.items():
        if str(uid).strip() and str(un).strip():
            state.x_user_cache_put(str(uid).strip(), str(un).strip())


_SCORING_AUDIT_ACTIONS: Tuple[str, ...] = (
    "discovery_from_search",
    "process_tweet_skip",
    "process_tweet_dry",
    "process_tweet_post_fail",
    "process_tweet_replied",
)


def _memory_decision_verdict(action: str, detail: Dict[str, Any]) -> Tuple[str, str]:
    """Return (verdict_key, short_label) for memory record_decision rows."""
    a = (action or "").strip()
    d = detail if isinstance(detail, dict) else {}
    if a == "gate_eval":
        if d.get("proceed") is True:
            return ("approved", "Approved")
        if d.get("proceed") is False:
            return ("rejected", "Rejected")
        return ("unknown", "?")
    if a == "gate_skip":
        return ("rejected", "Skipped (gate)")
    if a == "process_tweet":
        return ("posted", "Reply posted")
    if a in ("classify_scored", "classify_filtered"):
        return ("info", "Classify batch")
    if a in ("cursor_kv_snapshot", "cursor_commit"):
        return ("info", "Cursor")
    if a == "daily_post":
        return ("posted", "Daily post")
    if a.startswith("classify") or a.startswith("cursor"):
        return ("info", a)
    return ("info", a or "—")


def _audit_decision_verdict(action: str, detail: Dict[str, Any]) -> Tuple[str, str]:
    """Return (verdict_key, short_label) for promoter SQLite audit rows."""
    a = (action or "").strip()
    d = detail if isinstance(detail, dict) else {}
    if a == "process_tweet_replied":
        return ("posted", "Replied")
    if a == "process_tweet_skip":
        return ("skipped", "Skipped")
    if a == "process_tweet_dry":
        return ("dry_run", "Dry-run reply")
    if a == "process_tweet_post_fail":
        return ("failed", "Post failed")
    if a == "discovery_from_search":
        if d.get("dry_run"):
            return ("info", "Discovery (dry)")
        if d.get("follow_attempted") and d.get("follow_ok") is True:
            return ("approved", "Followed")
        if d.get("follow_attempted") and d.get("follow_ok") is False:
            return ("failed", "Follow failed")
        if d.get("already_following"):
            return ("info", "Already following")
        return ("info", "Discovery")
    return ("info", a or "—")


def _detail_reason_snippet(detail: Dict[str, Any]) -> str:
    if not isinstance(detail, dict):
        return ""
    r = detail.get("reason")
    if r is not None and str(r).strip():
        return str(r).strip()
    if detail.get("error"):
        return str(detail.get("error"))[:200]
    return ""


def audit_tail_with_handles(
    state: PromoterState,
    limit: int,
    *,
    rows: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    rows = rows if rows is not None else state.audit_tail(limit)
    uid_set: Set[str] = set()
    tid_set: Set[str] = set()
    for r in rows:
        d = r.get("detail")
        _gather_numeric_user_ids(d, uid_set)
        _gather_tweet_ids_for_author_lookup(d, tid_set)
    by_tweet = _x_tweets_resolve_authors(state, tid_set)
    for _tid, info in by_tweet.items():
        u = str(info.get("user_id") or "").strip()
        if u:
            uid_set.add(u)
    resolved = _resolve_usernames_batch(state, uid_set)
    for _tid, info in list(by_tweet.items()):
        uid = str(info.get("user_id") or "").strip()
        if uid in resolved and not str(info.get("username") or "").strip():
            info["username"] = resolved[uid]
    enriched: List[Dict[str, Any]] = []
    for r in rows:
        nr = {str(k): v for k, v in r.items()}
        det = nr.get("detail")
        if isinstance(det, (dict, list)):
            nr["detail"] = _enrich_detail_handles(det, resolved, by_tweet)
        enriched.append(nr)
    return enriched


def _tweet_audit_fields(tweet: Dict[str, Any]) -> Dict[str, Any]:
    ex: Dict[str, Any] = {}
    tid = str(tweet.get("id") or "").strip()
    uid = str(tweet.get("user_id") or "").strip()
    un = str(tweet.get("username") or "").strip()
    if tid:
        ex["tweet_id"] = tid
    if uid:
        ex["user_id"] = uid
    if un:
        ex["username"] = un
    return ex


def _x_api_follow(state: PromoterState, target_user_id: str) -> Dict[str, Any]:
    me = _cached_me_id(state)
    if not me:
        return {"ok": False, "error": "no_me", "detail": "OAuth1 user context required for follow"}
    url = f"https://api.twitter.com/2/users/{me}/following"
    payload = json.dumps({"target_user_id": str(target_user_id)}, ensure_ascii=False).encode("utf-8")
    ck, cs, tok, ts = _x_oauth1_creds() or ("", "", "", "")
    auth = _oauth1_authorization_header("POST", url, ck, cs, tok, ts)
    status, _h, data = _http_request(
        "POST",
        url,
        headers={"Authorization": auth, "Content-Type": "application/json"},
        body=payload,
        timeout=60.0,
    )
    obj = json.loads(data.decode("utf-8")) if data else {}
    if status >= 400:
        return {"ok": False, "error": f"follow_http_{status}", "detail": obj}
    return {"ok": True, "raw": obj}


def _x_api_like(state: PromoterState, tweet_id: str) -> Dict[str, Any]:
    me = _cached_me_id(state)
    if not me:
        return {"ok": False, "error": "no_me", "detail": "OAuth1 user context required for like"}
    url = f"https://api.twitter.com/2/users/{me}/likes"
    payload = json.dumps({"tweet_id": str(tweet_id)}, ensure_ascii=False).encode("utf-8")
    oauth = _x_oauth1_creds()
    if not oauth:
        return {"ok": False, "error": "no_oauth"}
    ck, cs, tok, ts = oauth
    auth = _oauth1_authorization_header("POST", url, ck, cs, tok, ts)
    status, _h, data = _http_request(
        "POST",
        url,
        headers={"Authorization": auth, "Content-Type": "application/json"},
        body=payload,
        timeout=60.0,
    )
    obj = json.loads(data.decode("utf-8")) if data else {}
    if status >= 400:
        return {"ok": False, "error": f"like_http_{status}", "detail": obj}
    return {"ok": True, "raw": obj}


def _maybe_like_monitored_author(state: PromoterState, tweet: Dict[str, Any]) -> None:
    if not _env_bool("PROMOTER_LIKE_ENABLED", False):
        return
    uid = str(tweet.get("user_id", "") or "")
    if not uid or uid not in set(_kv_str_list_get(state, "monitored_accounts")):
        return
    tid = str(tweet.get("id", "") or "")
    if not tid:
        return
    dry = _env_bool("PROMOTER_DRY_RUN", False)
    un = _resolve_usernames_batch(state, {uid}).get(uid, "") or str(tweet.get("username") or "").strip()
    if dry:
        state.audit(
            "x.like",
            {"dry_run": True, "tweet_id": tid, "user_id": uid, **({"username": un} if un else {})},
        )
        _gw_debug("x.like dry_run=1 (monitored author)")
        return
    res = _x_api_like(state, tid)
    state.audit("x.like", {"tweet_id": tid, "user_id": uid, **({"username": un} if un else {}), "result": res})
    _gw_debug(f"x.like monitored_author tweet_id={tid!r} ok={res.get('ok')}")


def _awareness_cta_suffix() -> str:
    u = _canonical_github_repo_url()
    return f"Try AINL on GitHub: {u}"


def _discovery_llm_scores(users: List[Dict[str, Any]], state: PromoterState) -> Dict[str, float]:
    if not users or not (os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")):
        return {}
    lines = []
    for u in users[:20]:
        blob = f"{u.get('username','')} {u.get('name','')} {u.get('description','')}"
        lines.append(f"- user_id={u.get('user_id','')}: {blob[:280]}")
    instr = (_load_prompt_file("discovery_user_instruction") or "").strip() or (
        "Score each line 1-10 for relevance to AI agent frameworks, deterministic workflows, "
        "OpenClaw-style orchestration, or programming languages for graphs. Return ONLY a JSON array "
        'of {"user_id":"...","score":n} in the same order as the user list (first N lines).'
    )
    try:
        text = _openai_chat(
            [
                {"role": "system", "content": "You output only valid JSON arrays. No markdown."},
                {"role": "user", "content": instr + "\n\nUsers:\n" + "\n".join(lines)},
            ],
            state=state,
            usage_context="discovery_user_score",
        )
        arr = _extract_json_array(text)
        out: Dict[str, float] = {}
        if isinstance(arr, list):
            for row in arr:
                if isinstance(row, dict):
                    uid = str(row.get("user_id", "")).strip()
                    try:
                        out[uid] = float(row.get("score", 0))
                    except (TypeError, ValueError):
                        pass
        return out
    except Exception:
        return {}


def _discover_preflight_ok(state: PromoterState) -> bool:
    """True when discovery side-effects are allowed (matches legacy monolithic guards)."""
    if not _env_bool("PROMOTER_DISCOVERY_ENABLED", True):
        return False
    if _env_bool("PROMOTER_DRY_RUN", False):
        return False
    if not _env_bool("PROMOTER_DISCOVERY_FROM_SEARCH", True):
        return False
    if not _cached_me_id(state):
        return False
    return True


def _discover_candidates_from_tweets(
    state: PromoterState, tweets: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Unique author user records (X lookup, capped), excluding self and already monitored."""
    me = _cached_me_id(state)
    if not me:
        return []
    max_auth = max(1, min(50, _env_int("PROMOTER_DISCOVERY_MAX_AUTHORS_PER_SEARCH", 15)))
    monitored = set(_kv_str_list_get(state, "monitored_accounts"))
    uids: List[str] = []
    seen: Set[str] = set()
    for t in tweets:
        if not isinstance(t, dict):
            continue
        uid = str(t.get("user_id") or "").strip()
        if not uid or uid == me or uid in seen:
            continue
        if uid in monitored:
            continue
        seen.add(uid)
        uids.append(uid)
        if len(uids) >= max_auth:
            break
    if not uids:
        return []
    users = _x_users_lookup(uids)
    return users if users else []


def _discover_scored_user_rows(
    state: PromoterState, users: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Per-user rows with ``score`` = max(heuristic, LLM)."""
    if not users:
        return []
    pseudo = [
        {
            "id": u["user_id"],
            "text": f"{u.get('username', '')} {u.get('name', '')} {u.get('description', '')}",
        }
        for u in users
    ]
    heur_items = _heuristic_scores([t if isinstance(t, dict) else {} for t in pseudo])
    heur_by_id = {str(h.get("id", "")): h for h in heur_items if isinstance(h, dict)}
    llm_s = _discovery_llm_scores(users, state)
    out: List[Dict[str, Any]] = []
    for u in users:
        uid = str(u.get("user_id", "") or "").strip()
        if not uid:
            continue
        h = heur_by_id.get(uid, {})
        try:
            hs = float(h.get("score", 0))
        except (TypeError, ValueError):
            hs = 0.0
        ls = llm_s.get(uid)
        final = max(hs, ls) if ls is not None else hs
        row = dict(u)
        row["score"] = final
        out.append(row)
    return out


def _discover_apply_one_user(
    state: PromoterState,
    user: Dict[str, Any],
    final_score: float,
    monitored: Optional[Set[str]] = None,
    following_set: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """Monitor + optional follow + audit for one discovery candidate. Mutates ``monitored`` / ``following_set`` when passed."""
    min_sc = float(_env_int("PROMOTER_DISCOVERY_MIN_SCORE", 7))
    if final_score < min_sc:
        return {"ok": True, "action": "skipped_below_threshold"}
    auto_follow = _env_bool("PROMOTER_DISCOVERY_AUTO_FOLLOW", True)
    auto_mon = _env_bool("PROMOTER_DISCOVERY_AUTO_MONITOR", True)
    if _env_bool("PROMOTER_DRY_RUN", False):
        uid0 = str(user.get("user_id", "") or "").strip()
        un0 = str(user.get("username", "") or "").strip()
        state.audit(
            "discovery_from_search",
            {"dry_run": True, "user_id": uid0, "username": un0, "score": final_score},
        )
        return {"ok": True, "dry_run": True, "action": "discover_apply"}
    uid = str(user.get("user_id", "") or "").strip()
    if not uid:
        return {"ok": False, "error": "missing_user_id"}
    un = str(user.get("username", "") or "").strip()
    if monitored is None:
        monitored = set(_kv_str_list_get(state, "monitored_accounts"))
    fs = following_set
    if fs is None and _x_oauth1_creds():
        try:
            fs = _following_set_cached(state)
        except Exception:
            fs = set()
    already_follow = bool(fs is not None and uid in fs)
    follow_ok: Optional[bool] = None
    added_mon = False
    if auto_mon:
        if uid not in monitored:
            _monitored_add(state, uid)
            monitored.add(uid)
            added_mon = True
    if auto_follow and not already_follow:
        res = _x_api_follow(state, uid)
        follow_ok = bool(res.get("ok"))
        if follow_ok and fs is not None:
            fs.add(uid)
        state.audit(
            "discovery_from_search",
            {
                "user_id": uid,
                "username": un,
                "score": final_score,
                "already_following": already_follow,
                "follow_attempted": True,
                "follow_ok": follow_ok,
                "added_monitored": added_mon,
            },
        )
    else:
        state.audit(
            "discovery_from_search",
            {
                "user_id": uid,
                "username": un,
                "score": final_score,
                "already_following": already_follow,
                "follow_attempted": False,
                "follow_ok": follow_ok,
                "added_monitored": added_mon,
            },
        )
    return {"ok": True, "action": "discover_apply", "user_id": uid, "username": un}


def _discover_authors_from_search_results(state: PromoterState, tweets: List[Dict[str, Any]]) -> None:
    """Score unique tweet authors (not already monitored); optionally follow + add to monitored_accounts."""
    if not _discover_preflight_ok(state):
        return
    users = _discover_candidates_from_tweets(state, tweets)
    if not users:
        return
    rows = _discover_scored_user_rows(state, users)
    min_sc = float(_env_int("PROMOTER_DISCOVERY_MIN_SCORE", 7))
    monitored = set(_kv_str_list_get(state, "monitored_accounts"))
    following_set: Optional[Set[str]] = None
    if _x_oauth1_creds():
        try:
            following_set = _following_set_cached(state)
        except Exception:
            following_set = set()
    for row in rows:
        try:
            final = float(row.get("score", 0))
        except (TypeError, ValueError):
            continue
        if final < min_sc:
            continue
        uid = str(row.get("user_id", "") or "").strip()
        if not uid:
            continue
        user = {k: v for k, v in row.items() if k != "score"}
        _discover_apply_one_user(state, user, final, monitored=monitored, following_set=following_set)


# -----------------------------------------------------------------------------
# Handlers
# -----------------------------------------------------------------------------


def _state_path() -> Path:
    raw = os.environ.get("PROMOTER_STATE_PATH")
    if raw:
        return _resolve_sqlite_file_path(Path(raw.strip()), default_filename="promoter_state.sqlite")
    return _resolve_sqlite_file_path(
        Path(__file__).resolve().parent / "data" / "promoter_state.sqlite",
        default_filename="promoter_state.sqlite",
    )


def _prompts_dir() -> Path:
    raw = os.environ.get("PROMOTER_PROMPTS_DIR")
    if raw:
        return Path(raw).expanduser().resolve()
    return (Path(__file__).resolve().parent / "prompts").resolve()


def _load_prompt_file(name: str) -> Optional[str]:
    """Load UTF-8 text from <prompts_dir>/<name>.txt if the file exists."""
    base = _prompts_dir()
    path = base / f"{name}.txt"
    if not path.is_file():
        _gw_debug(f"prompt file missing: {path}")
        return None
    try:
        text = path.read_text(encoding="utf-8-sig").strip()
        return text if text else None
    except OSError as e:
        _gw_debug(f"prompt read failed {path}: {e}")
        return None


def _promoter_codebase_root() -> Path:
    raw = os.environ.get("PROMOTER_CODEBASE_ROOT")
    if raw:
        return Path(raw).expanduser().resolve()
    return Path(__file__).resolve().parent.parent


def _promoter_max_original_posts_per_day() -> int:
    return max(0, min(50, _env_int("PROMOTER_MAX_ORIGINAL_POSTS_PER_DAY", 5)))


def _promoter_original_min_interval_sec() -> int:
    return max(60, _env_int("PROMOTER_ORIGINAL_POST_MIN_INTERVAL_SEC", 10800))


def _read_daily_codebase_snippets() -> str:
    root = _promoter_codebase_root()
    raw = os.environ.get(
        "PROMOTER_DAILY_SNIPPET_FILES",
        "README.md,HOW_AINL_SAVES_MONEY.md,apollo-x-bot/README.md",
    )
    max_chars = max(2000, min(50_000, _env_int("PROMOTER_DAILY_SNIPPET_MAX_CHARS", 12000)))
    parts: List[str] = []
    total = 0
    for part in raw.split(","):
        rel = part.strip()
        if not rel:
            continue
        path = (root / rel).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            _gw_debug(f"daily snippet skipped (outside root): {rel}")
            continue
        if not path.is_file():
            _gw_debug(f"daily snippet missing: {path}")
            continue
        try:
            chunk = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            _gw_debug(f"daily snippet read failed {path}: {e}")
            continue
        header = f"--- FILE: {rel} ---\n"
        block = header + chunk
        if total + len(block) > max_chars:
            remain = max_chars - total - len(header)
            if remain < 200:
                break
            block = header + chunk[:remain] + "\n[...truncated...]"
        parts.append(block)
        total += len(block)
        if total >= max_chars:
            break
    return "\n\n".join(parts)


def handle_x_search(body: Dict[str, Any], state: PromoterState) -> Dict[str, Any]:
    try:
        payload = body.get("payload") or body
        query = str((payload if isinstance(payload, dict) else {}).get("query") or "")
        if _env_bool("PROMOTER_DRY_RUN", False):
            sample = [
                {
                    "id": "dry1",
                    "text": "OpenClaw + ZeroClaw: orchestration, deterministic agent memory workflows.",
                    "user_id": "u1",
                    "username": "dry_user",
                }
            ]
            state.audit("x.search", {"dry_run": True, "query": query})
            _gw_debug("x.search dry_run=1 tweets=1 (sample)")
            return {"tweets": sample, "dry_run": True}
        use_since = _env_bool("PROMOTER_SEARCH_USE_SINCE_ID", True)
        since = state.kv_get("x_search_since_id") if use_since else None
        out = _x_recent_search(query, since_id=since, max_results=_search_max_results(), state=state)
        n = 0
        extra = ""
        if isinstance(out, dict):
            tw = out.get("tweets")
            if isinstance(tw, list):
                n = len(tw)
            if out.get("warning"):
                extra += f" warning={out.get('warning')!r}"
            if out.get("error"):
                extra += f" error={out.get('error')!r}"
            meta = out.get("meta") if isinstance(out.get("meta"), dict) else {}
            nid = meta.get("newest_id")
            # Defer advancing x_search_since_id until promoter.search_cursor_commit (end of graph) so a
            # crash mid-loop does not skip tweets that were returned but not yet processed.
            if use_since and nid and not out.get("error"):
                state.kv_set("x_search_pending_newest_id", str(nid))
                extra += " pending_since_id=1"
            if use_since and since:
                extra += " since_id_in_request=1"
        _gw_debug(f"x.search tweets={n} query_chars={len(query)}{extra}")
        return out
    except Exception as e:
        import traceback

        _gw_debug(f"x.search exception: {e!r}\n{traceback.format_exc()}")
        try:
            state.audit("x.search", {"error": "handler_exception", "detail": str(e)[:500]})
        except Exception:
            pass
        return {"tweets": [], "error": "x_search_handler_exception", "detail": str(e)}


def handle_llm_classify(body: Dict[str, Any], state: PromoterState) -> Any:
    inner = _http_inner_dict(body)
    tweets = inner.get("tweets")
    if tweets is None:
        tweets = body.get("tweets") or []
    want_env = _classify_wants_envelope(inner)

    if not isinstance(tweets, list):
        _gw_debug("llm.classify skip: tweets is not a list -> graph gets [] and FILTER_HIGH_SCORE yields empty loop")
        if want_env:
            return {
                "v": 1,
                "kind": "llm_raw",
                "raw_text": "",
                "error": "tweets_not_list",
                "items": [],
            }
        return []

    system_raw = inner.get("system")
    if system_raw is None:
        system_raw = body.get("system")
    system_content = (
        str(system_raw).strip()
        if isinstance(system_raw, str) and str(system_raw).strip()
        else (_load_prompt_file("classify_system") or "You output only valid JSON arrays. No markdown.")
    )
    prompt_wrap = inner.get("prompt")
    if prompt_wrap is None:
        prompt_wrap = body.get("prompt") or {}
    instr = ""
    if isinstance(prompt_wrap, dict):
        instr = str(prompt_wrap.get("prompt") or prompt_wrap.get("text") or "").strip()
    else:
        instr = str(prompt_wrap).strip()
    if not instr:
        instr = (_load_prompt_file("classify_instruction") or "").strip()

    ids = [str(t.get("id", "")) for t in tweets if isinstance(t, dict)]

    if _env_bool("PROMOTER_DRY_RUN", False) and not (
        os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")
    ):
        state.audit("llm.classify", {"dry_run": True, "n": len(tweets)})
        out = _heuristic_scores([t if isinstance(t, dict) else {} for t in tweets])
        _fl = int(_classify_score_floor())
        _gw_debug(
            f"llm.classify dry_heuristic n_in={len(tweets)} n_out={len(out)} "
            f"n_score_ge_{_fl}={_count_classify_pass(out)}"
        )
        if want_env:
            return {"v": 1, "kind": "heuristic", "raw_text": "", "error": None, "items": out}
        return out

    if want_env:
        msgs = inner.get("messages")
        if not isinstance(msgs, list) or len(msgs) == 0:
            state.audit("llm.classify_error", {"error": "envelope_missing_messages", "ids": ids})
            _gw_debug("llm.classify envelope_missing_messages")
            return {
                "v": 1,
                "kind": "llm_raw",
                "raw_text": "",
                "error": "envelope_missing_messages",
                "items": [],
            }
        try:
            text = _openai_chat(msgs, state=state, usage_context="llm.classify_envelope")
            _gw_debug(
                f"llm.classify(envelope) llm_raw chars={len(text)} n_tweets={len(tweets)}"
            )
            return {"v": 1, "kind": "llm_raw", "raw_text": text, "error": None, "items": []}
        except Exception as e:
            state.audit("llm.classify_error", {"error": str(e), "ids": ids})
            _gw_debug(f"llm.classify(envelope) error={e!r}")
            return {"v": 1, "kind": "llm_raw", "raw_text": "", "error": str(e), "items": []}

    tw_dicts = [t if isinstance(t, dict) else {} for t in tweets]
    user_msg = (
        f"Instruction: {instr}\n\n"
        f"Tweets (JSON array, same order): {json.dumps(tweets, ensure_ascii=False)}\n\n"
        "Return ONLY a JSON array of objects, one per tweet in order, each like "
        '{"id":"<tweet id>","score":<number 1-10>,"why":"<short reason>"}.'
    )
    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_msg},
    ]

    try:
        text = _openai_chat(messages, state=state, usage_context="llm.classify_legacy")
        parsed = _extract_json_array(text)
        if not isinstance(parsed, list):
            raise ValueError("expected JSON array")
        out = _merge_scores_onto_tweets(tweets, parsed)
        _fl = int(_classify_score_floor())
        _gw_debug(
            f"llm.classify llm_ok n_in={len(tweets)} n_out={len(out)} "
            f"n_score_ge_{_fl}={_count_classify_pass(out)}"
        )
        return out
    except Exception as e:
        state.audit("llm.classify_error", {"error": str(e), "ids": ids})
        out = _heuristic_scores(tw_dicts)
        _fl = int(_classify_score_floor())
        _gw_debug(
            f"llm.classify fallback_heuristic n_in={len(tweets)} n_out={len(out)} "
            f"n_score_ge_{_fl}={_count_classify_pass(out)} err={e!r}"
        )
        return out


def handle_llm_json_array_extract(body: Dict[str, Any], state: PromoterState) -> Dict[str, Any]:
    inner = _http_inner_dict(body)
    t = inner.get("text")
    if t is None:
        t = body.get("text")
    t = str(t or "")
    try:
        arr = _extract_json_array(t)
        if not isinstance(arr, list):
            return {"ok": False, "array": [], "reason": "not_array"}
        return {"ok": True, "array": arr}
    except Exception as e:
        return {"ok": False, "array": [], "error": str(e)}


def handle_llm_merge_classify_rows(body: Dict[str, Any], state: PromoterState) -> Dict[str, Any]:
    inner = _http_inner_dict(body)
    tweets = inner.get("tweets") or []
    rows = inner.get("score_rows")
    if rows is None:
        rows = inner.get("parsed") or []
    if not isinstance(tweets, list):
        tweets = []
    if not isinstance(rows, list):
        rows = []
    merged = _merge_scores_onto_tweets(tweets, rows)
    _fl = int(_classify_score_floor())
    _gw_debug(
        f"llm.merge_classify_rows n_in={len(tweets)} n_out={len(merged)} "
        f"n_score_ge_{_fl}={_count_classify_pass(merged)}"
    )
    # Debug: log merged items' ids
    for i, item in enumerate(merged):
        _gw_debug(f"merge output[{i}] id={item.get('id')!r} keys={list(item.keys())}")
    return {"items": merged}


def handle_text_contains_any(body: Dict[str, Any], state: PromoterState) -> Dict[str, Any]:
    inner = _http_inner_dict(body)
    hay = str(inner.get("haystack") or inner.get("text") or "")
    phrases = inner.get("phrases") or []
    if not isinstance(phrases, list):
        phrases = []
    n = 0
    hl = hay.lower()
    for p in phrases:
        s = str(p).lower() if p is not None else ""
        if s and s in hl:
            n += 1
    return {"hit_count": n, "any": n > 0}


def handle_promoter_heuristic_scores(body: Dict[str, Any], state: PromoterState) -> Dict[str, Any]:
    inner = _http_inner_dict(body)
    tweets = inner.get("tweets") or []
    if not isinstance(tweets, list):
        tweets = []
    raw_keys = inner.get("keywords")
    keys_tuple = None
    if isinstance(raw_keys, list) and raw_keys:
        keys_tuple = tuple(str(x).lower() for x in raw_keys if str(x).strip())
    items = _heuristic_scores(
        [t if isinstance(t, dict) else {} for t in tweets],
        keys=keys_tuple,
    )
    return {"items": items}


def handle_promoter_classify_prompts(body: Dict[str, Any], state: PromoterState) -> Dict[str, Any]:
    return {
        "system": _load_prompt_file("classify_system")
        or "You output only valid JSON arrays. No markdown.",
        "instruction": (_load_prompt_file("classify_instruction") or "").strip(),
    }


def handle_promoter_daily_post_prompts(body: Dict[str, Any], state: PromoterState) -> Dict[str, Any]:
    su = (_load_prompt_file("daily_post_user_suffix") or "").strip()
    if not su:
        su = (_load_prompt_file("daily_post_user") or "").strip()
    system_prompt = (_load_prompt_file("daily_post_system") or "").strip() or (
        "You write short X posts promoting AINL from repo facts."
    )
    user_suffix = su or "Write exactly one X post under 260 chars. Energetic, accurate, include the link verbatim."
    return {
        "system": system_prompt,
        "user_suffix": user_suffix,
    }


def handle_promoter_daily_snippets(body: Dict[str, Any], state: PromoterState) -> Dict[str, Any]:
    return {"snippets": _read_daily_codebase_snippets()}


def handle_llm_chat(body: Dict[str, Any], state: PromoterState) -> Dict[str, Any]:
    """OpenAI-compatible chat completions (messages + optional temperature). Used by strict AINL daily post chain."""
    inner = _http_inner_dict(body)
    messages = inner.get("messages")
    if not isinstance(messages, list) or not messages:
        return {"ok": False, "error": "missing_messages"}
    msgs: List[Dict[str, str]] = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        role = str(m.get("role", "")).strip()
        content = str(m.get("content", ""))
        if role and content:
            msgs.append({"role": role, "content": content})
    if not msgs:
        return {"ok": False, "error": "missing_messages"}
    temp_raw = inner.get("temperature")
    temp: Optional[float] = None
    if temp_raw is not None:
        try:
            temp = float(temp_raw)
        except (TypeError, ValueError):
            temp = None
    uc = str(inner.get("usage_context") or "llm.chat").strip() or "llm.chat"
    if temp is None and uc == "daily_original_post":
        temp = 0.72
    try:
        out = _openai_chat(
            msgs,
            state=state,
            usage_context=uc,
            temperature=temp,
        )
    except Exception as e:
        _gw_debug(f"llm.chat error: {e!r}")
        return {"ok": False, "error": str(e)}
    text = (out or "").strip()
    if not text:
        return {"ok": False, "error": "empty_completion"}
    return {"ok": True, "text": text}


def handle_promoter_gate_eval(body: Dict[str, Any], state: PromoterState) -> Dict[str, Any]:
    inner = _http_inner_dict(body)
    tweet_id = str(inner.get("tweet_id") or "")
    user_id = str(inner.get("user_id") or "")
    dry = _env_bool("PROMOTER_DRY_RUN", False)
    max_day = _env_int("PROMOTER_MAX_REPLIES_PER_DAY", 20)
    cool_h = float(_env_int("PROMOTER_USER_COOLDOWN_HOURS", 48))
    dedupe = _env_bool("PROMOTER_DEDUPE_REPLIED_TWEETS", True)
    daily_count = state.count_today_replies()

    _gw_debug(f"gate_eval tweet_id={tweet_id!r} user_id={user_id!r} daily_count={daily_count}/{max_day}")

    if not str(tweet_id).strip():
        _gw_debug("gate_eval skip reason=missing_tweet_id")
        return {
            "proceed": False,
            "reason": "missing_tweet_id",
            "dry_run": dry,
            "daily_count": daily_count,
            "daily_cap": max_day,
            "tweet_id": tweet_id,
            "user_id": user_id,
        }

    if dedupe and state.has_replied_to_tweet(tweet_id):
        _gw_debug("gate_eval skip reason=already_replied_tweet")
        return {
            "proceed": False,
            "reason": "already_replied_tweet",
            "dry_run": dry,
            "daily_count": daily_count,
            "daily_cap": max_day,
            "tweet_id": tweet_id,
            "user_id": user_id,
        }
    if daily_count >= max_day:
        _gw_debug("gate_eval skip reason=daily_reply_cap")
        return {
            "proceed": False,
            "reason": "daily_reply_cap",
            "dry_run": dry,
            "daily_count": daily_count,
            "daily_cap": max_day,
            "tweet_id": tweet_id,
            "user_id": user_id,
        }
    if not state.user_cooldown_ok(user_id, cool_h):
        _gw_debug("gate_eval skip reason=user_cooldown")
        return {
            "proceed": False,
            "reason": "user_cooldown",
            "dry_run": dry,
            "daily_count": daily_count,
            "daily_cap": max_day,
            "tweet_id": tweet_id,
            "user_id": user_id,
        }
    _gw_debug("gate_eval proceed")
    return {
        "proceed": True,
        "reason": None,
        "dry_run": dry,
        "daily_count": daily_count,
        "daily_cap": max_day,
        "tweet_id": tweet_id,
        "user_id": user_id,
    }


def handle_process_tweet(body: Dict[str, Any], state: PromoterState) -> Dict[str, Any]:
    payload = body.get("payload")
    if not isinstance(payload, dict):
        payload = body
    tweet = payload if isinstance(payload, dict) else {}
    rs_raw = payload.get("reply_system_prompt")
    if not (isinstance(rs_raw, str) and str(rs_raw).strip()):
        rs_raw = body.get("reply_system_prompt")
    reply_system = str(rs_raw).strip() if isinstance(rs_raw, str) and str(rs_raw).strip() else ""
    custom_reply_system = bool(reply_system)
    if not reply_system:
        reply_system = (_load_prompt_file("reply_system") or "").strip()
    if not reply_system:
        reply_system = (
            "You are Apollo, an expert on AINL. Be accurate and concise; include a GitHub/docs CTA when natural. "
            "Max ~260 chars of guidance for the reply text itself."
        )
    reply_system = _reply_system_with_canonical_link(reply_system)
    if not custom_reply_system:
        reply_system = _apply_persona_instructions(reply_system, "reply")
    ru_raw = payload.get("reply_user_prompt")
    if not (isinstance(ru_raw, str) and str(ru_raw).strip()):
        ru_raw = body.get("reply_user_prompt")
    reply_user_prompt = (
        str(ru_raw).strip()
        if isinstance(ru_raw, str) and str(ru_raw).strip()
        else f"Tweet:\n{tweet.get('text','')}\n\nDraft a helpful, expert reply from Apollo."
    )
    rf_raw = payload.get("reply_fallback_text")
    if not (isinstance(rf_raw, str) and str(rf_raw).strip()):
        rf_raw = body.get("reply_fallback_text")
    reply_fallback_text = str(rf_raw).strip() if isinstance(rf_raw, str) and str(rf_raw).strip() else ""
    tweet_id = str(tweet.get("id", ""))
    user_id = str(tweet.get("user_id", ""))
    dry = _env_bool("PROMOTER_DRY_RUN", False)

    _gw_debug(f"process_tweet payload keys={list(tweet.keys())} id_raw={tweet.get('id')!r}")

    max_day = _env_int("PROMOTER_MAX_REPLIES_PER_DAY", 20)
    cool_h = float(_env_int("PROMOTER_USER_COOLDOWN_HOURS", 48))

    _gw_debug(f"process_tweet begin tweet_id={tweet_id!r} user_id={user_id!r} dry_run={dry}")

    ta = _tweet_audit_fields(tweet)

    if not str(tweet_id).strip():
        state.audit("process_tweet_skip", {"reason": "missing_tweet_id", **ta})
        _gw_debug("process_tweet skip reason=missing_tweet_id")
        return {"ok": True, "action": "skipped", "reason": "missing_tweet_id", "dry_run": dry, **ta}

    if _env_bool("PROMOTER_DEDUPE_REPLIED_TWEETS", True) and state.has_replied_to_tweet(tweet_id):
        state.audit("process_tweet_skip", {"reason": "already_replied_tweet", "tweet_id": tweet_id, **ta})
        _gw_debug("process_tweet skip reason=already_replied_tweet (no draft LLM)")
        return {"ok": True, "action": "skipped", "reason": "already_replied_tweet", "dry_run": dry, **ta}

    if state.count_today_replies() >= max_day:
        state.audit("process_tweet_skip", {"reason": "daily_cap", "tweet_id": tweet_id, **ta})
        _gw_debug(f"process_tweet skip reason=daily_reply_cap count={state.count_today_replies()}/{max_day}")
        return {"ok": True, "action": "skipped", "reason": "daily_reply_cap", "dry_run": dry, **ta}
    if not state.user_cooldown_ok(user_id, cool_h):
        state.audit("process_tweet_skip", {"reason": "user_cooldown", "user_id": user_id, **ta})
        _gw_debug(f"process_tweet skip reason=user_cooldown user_id={user_id!r} hours={cool_h}")
        return {"ok": True, "action": "skipped", "reason": "user_cooldown", "dry_run": dry, **ta}

    gh = _canonical_github_repo_url()
    reply_text = reply_fallback_text or (
        "If you are standardizing agent workflows, AINL compiles graphs to a deterministic runtime "
        f"(open graphs on GitHub: {gh}). Happy to compare notes on OpenClaw-style orchestration."
    )
    try:
        if os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY"):
            reply_text = _openai_chat(
                [
                    {"role": "system", "content": reply_system},
                    {"role": "user", "content": reply_user_prompt},
                ],
                state=state,
                usage_context="process_tweet_reply_draft",
            )
            reply_text = reply_text.strip()
    except Exception:
        pass
    reply_text = _normalize_promoter_github_links(reply_text)[:280]

    if dry:
        state.audit("process_tweet_dry", {"tweet_id": tweet_id, "reply": reply_text, **ta})
        state.incr_today_replies()
        state.touch_user(user_id)
        if _env_bool("PROMOTER_DEDUPE_REPLIED_TWEETS", True):
            state.mark_replied_tweet(tweet_id)
        _maybe_like_monitored_author(state, tweet)
        _gw_debug("process_tweet dry_run_reply (no X API post)")
        return {"ok": True, "action": "dry_run_reply", "tweet_id": tweet_id, "text": reply_text, **ta}

    post = _x_post_reply(reply_text, tweet_id)
    if not post.get("ok"):
        state.audit("process_tweet_post_fail", {"tweet_id": tweet_id, "detail": post, **ta})
        _gw_debug(f"process_tweet post_failed detail={post!r}")
        return {"ok": False, "action": "post_failed", "detail": post, **ta}
    state.incr_today_replies()
    state.touch_user(user_id)
    if _env_bool("PROMOTER_DEDUPE_REPLIED_TWEETS", True):
        state.mark_replied_tweet(tweet_id)
    state.audit(
        "process_tweet_replied",
        {"tweet_id": tweet_id, "reply_id": post.get("tweet_id"), **ta},
    )
    _maybe_like_monitored_author(state, tweet)
    _gw_debug(f"process_tweet replied reply_tweet_id={post.get('tweet_id')!r}")
    return {"ok": True, "action": "replied", "reply": post, **ta}


def handle_search_cursor_commit(body: Dict[str, Any], state: PromoterState) -> Dict[str, Any]:
    """Promote pending search newest_id to since_id after a full poll completes (see ainl L_after_loop)."""
    if _env_bool("PROMOTER_DRY_RUN", False):
        return {"ok": True, "action": "noop", "reason": "dry_run"}
    if not _env_bool("PROMOTER_SEARCH_USE_SINCE_ID", True):
        return {"ok": True, "action": "noop", "reason": "since_id_disabled"}
    pending = state.kv_get("x_search_pending_newest_id")
    if not pending:
        _gw_debug("search_cursor_commit noop (no pending newest_id)")
        return {"ok": True, "action": "noop", "reason": "no_pending_newest_id"}
    state.kv_set("x_search_since_id", pending)
    state.kv_delete("x_search_pending_newest_id")
    state.audit("search_cursor_commit", {"since_id": pending})
    _gw_debug(f"search_cursor_commit promoted since_id={pending!r}")
    return {"ok": True, "action": "committed", "since_id": pending}


def handle_kv_get(body: Dict[str, Any], state: PromoterState) -> Dict[str, Any]:
    inner = _http_inner_dict(body)
    key = str(inner.get("key") or "").strip()
    if not key:
        return {"ok": False, "error": "missing_key"}
    val = state.kv_get(key)
    return {"ok": True, "value": val}


def handle_kv_set(body: Dict[str, Any], state: PromoterState) -> Dict[str, Any]:
    inner = _http_inner_dict(body)
    key = str(inner.get("key") or "").strip()
    if not key:
        return {"ok": False, "error": "missing_key"}
    if "value" not in inner:
        return {"ok": False, "error": "missing_value"}
    raw = inner.get("value")
    if raw is None:
        state.kv_delete(key)
    else:
        if isinstance(raw, (dict, list, bool, int, float)):
            try:
                state.kv_set(key, json.dumps(raw, ensure_ascii=False, allow_nan=False))
            except Exception:
                state.kv_set(key, str(raw))
        else:
            state.kv_set(key, str(raw))
    return {"ok": True}


def handle_promoter_policy_cleanup(body: Dict[str, Any], state: PromoterState) -> Dict[str, Any]:
    now = time.time()
    cleared: List[str] = []
    kept: List[str] = []
    scanned = 0
    with state._conn() as c:
        rows = c.execute(
            """
            SELECT k, v FROM promoter_kv
            WHERE k = 'promoter_daily_block_flag'
               OR k = 'promoter_daily_fallback_model_flag'
               OR k = 'promoter_reply_fallback_model_flag'
               OR k LIKE 'promoter_reply_skip_target_%'
            """
        ).fetchall()
        scanned = len(rows)
        for r in rows:
            k = str(r[0] or "")
            raw = str(r[1] or "")
            s = raw.strip()
            if not s:
                c.execute("DELETE FROM promoter_kv WHERE k = ?", (k,))
                cleared.append(k)
                continue
            until = _policy_until_ts(s)
            is_legacy_block = (k == "promoter_daily_block_flag" and s == "1")
            should_clear = bool(is_legacy_block or until is None or float(until) <= now)
            if should_clear:
                c.execute("DELETE FROM promoter_kv WHERE k = ?", (k,))
                cleared.append(k)
            else:
                kept.append(k)
    out = {
        "ok": True,
        "scanned": int(scanned),
        "cleared": len(cleared),
        "kept": len(kept),
        "cleared_keys": cleared[:80],
    }
    state.audit("policy_flags_cleanup", {"scanned": int(scanned), "cleared": len(cleared), "kept": len(kept)})
    return out


def handle_maybe_daily(body: Dict[str, Any], state: PromoterState) -> Dict[str, Any]:
    payload = body.get("payload") or {}
    topic = str(payload.get("topic", "AINL"))
    link = str(payload.get("link") or _canonical_github_repo_url())
    dry = _env_bool("PROMOTER_DRY_RUN", False)

    max_posts = _promoter_max_original_posts_per_day()
    if max_posts <= 0:
        _gw_debug("maybe_daily noop reason=original_posts_disabled")
        return {"ok": True, "action": "noop", "reason": "original_posts_disabled"}

    n = state.count_original_posts_today()
    if n >= max_posts:
        _gw_debug("maybe_daily noop reason=original_posts_cap")
        return {
            "ok": True,
            "action": "noop",
            "reason": "original_posts_cap",
            "original_posts_today": n,
            "original_posts_cap": max_posts,
        }

    min_gap = float(_promoter_original_min_interval_sec())
    now = time.time()
    last_ts = state.last_original_post_ts_today()
    if last_ts is not None and (now - last_ts) < min_gap:
        wait = int(min_gap - (now - last_ts))
        _gw_debug("maybe_daily noop reason=min_interval")
        return {
            "ok": True,
            "action": "noop",
            "reason": "min_interval_not_met",
            "seconds_until_eligible": max(0, wait),
            "original_posts_today": n,
            "original_posts_cap": max_posts,
        }

    static = _normalize_promoter_github_links(
        f"{topic} — deterministic agent graphs as code. {link}"
    )[:280]
    if _env_bool("PROMOTER_AWARENESS_BOOST", False):
        u = _canonical_github_repo_url()
        boosted = _normalize_promoter_github_links(
            f"{topic} — deterministic agent graphs. {link} · Issues/PRs: {u}"
        )[:280]
        if boosted:
            static = boosted

    text_raw = payload.get("text")
    if isinstance(text_raw, str) and text_raw.strip():
        text = _normalize_promoter_github_links(text_raw.strip())
        text = re.sub(r"\s+", " ", text).strip()[:280]
    else:
        text = static[:280]
    if not text:
        text = static[:280]

    if dry:
        state.audit(
            "daily_post_dry",
            {"text": text, "would_be_post_index": n + 1, "original_posts_today": n},
        )
        _gw_debug("maybe_daily dry_run (no original_post_log row)")
        return {
            "ok": True,
            "action": "dry_run_daily",
            "text": text,
            "original_posts_today": n,
            "original_posts_cap": max_posts,
        }

    attempt_cap = max(0, _env_int("PROMOTER_DAILY_DUPLICATE_REWRITE_ATTEMPTS", 2))
    text_try = text[:280]
    post = _x_post_original(text_try)
    attempts = 0
    while (not post.get("ok")) and _is_x_duplicate_content_error(post) and attempts < attempt_cap:
        err_msg = _x_error_message(post)
        state.audit(
            "daily_post_retry_duplicate",
            {
                "attempt": attempts + 1,
                "max_attempts": attempt_cap,
                "reason": err_msg,
                "prior_text": text_try,
            },
        )
        _gw_debug(
            f"maybe_daily duplicate_content_retry attempt={attempts + 1}/{attempt_cap} msg={err_msg!r}"
        )
        text_try = _refactor_daily_text_for_duplicate(
            topic=topic,
            link=link,
            previous_text=text_try,
            attempt=attempts,
            state=state,
        )[:280]
        attempts += 1
        post = _x_post_original(text_try)
    if not post.get("ok"):
        _gw_debug(f"maybe_daily post_failed detail={post!r}")
        return {
            "ok": False,
            "action": "daily_failed",
            "detail": post,
            "attempted_rewrites": attempts,
            "x_error_message": _x_error_message(post),
        }
    tw_id = str(post.get("tweet_id") or "").strip()
    if tw_id:
        state.append_original_post_log(tw_id)
    state.audit("daily_post", {"tweet_id": post.get("tweet_id"), "rewrite_attempts": attempts})
    _gw_debug(f"maybe_daily posted tweet_id={post.get('tweet_id')!r}")
    return {
        "ok": True,
        "action": "daily_posted",
        "tweet_id": post.get("tweet_id"),
        "text": text_try,
        "rewrite_attempts": attempts,
        "original_posts_today": n + (1 if tw_id else 0),
        "original_posts_cap": max_posts,
    }


def handle_x_follow(body: Dict[str, Any], state: PromoterState) -> Dict[str, Any]:
    inner = _http_inner_dict(body)
    tid = str(inner.get("target_user_id") or inner.get("user_id") or "").strip()
    add_mon = inner.get("add_to_monitored", True)
    if isinstance(add_mon, str):
        add_mon = str(add_mon).strip().lower() in ("1", "true", "yes", "on")
    dry = _env_bool("PROMOTER_DRY_RUN", False)
    if not tid:
        return {"ok": False, "error": "missing_target_user_id"}
    if dry:
        state.audit("x.follow", {"dry_run": True, "target_user_id": tid, "add_to_monitored": add_mon})
        return {"ok": True, "dry_run": True, "target_user_id": tid, "followed": False, "add_to_monitored": add_mon}
    res = _x_api_follow(state, tid)
    if res.get("ok") and add_mon:
        _monitored_add(state, tid)
    return {"ok": bool(res.get("ok")), "target_user_id": tid, "detail": res}


def handle_promoter_discover_tweet_authors(body: Dict[str, Any], state: PromoterState) -> Dict[str, Any]:
    """AINL-orchestrated: run discovery/monitor/follow for authors in an x.search tweet list (see modules/common/promoter_discover_from_tweets.ainl)."""
    inner = _http_inner_dict(body)
    tweets = inner.get("tweets")
    if not isinstance(tweets, list):
        return {"ok": False, "error": "tweets_not_list"}
    try:
        _discover_authors_from_search_results(state, tweets)
    except Exception as e:
        _gw_debug(f"promoter.discover_tweet_authors failed: {e!r}")
        return {"ok": False, "error": str(e)}
    return {"ok": True, "action": "discover_tweet_authors"}


def handle_promoter_discovery_candidates_from_tweets(body: Dict[str, Any], state: PromoterState) -> Dict[str, Any]:
    """AINL Track A: unique author user rows from an x.search ``tweets[]`` list (no scoring yet)."""
    inner = _http_inner_dict(body)
    tweets = inner.get("tweets")
    if not isinstance(tweets, list):
        return {"ok": False, "error": "tweets_not_list"}
    if not _discover_preflight_ok(state):
        return {"ok": True, "users": [], "skipped": True}
    users = _discover_candidates_from_tweets(state, tweets)
    return {"ok": True, "users": users}


def handle_promoter_discovery_score_users(body: Dict[str, Any], state: PromoterState) -> Dict[str, Any]:
    """AINL Track A: heuristic + discovery LLM scores for ``users[]`` from candidates."""
    inner = _http_inner_dict(body)
    users = inner.get("users")
    if not isinstance(users, list):
        return {"ok": False, "error": "users_not_list"}
    if not _discover_preflight_ok(state):
        return {"ok": True, "items": [], "skipped": True}
    items = _discover_scored_user_rows(state, [u for u in users if isinstance(u, dict)])
    return {"ok": True, "items": items}


def handle_promoter_discovery_apply_one(body: Dict[str, Any], state: PromoterState) -> Dict[str, Any]:
    """AINL Track A: monitor + optional follow + audit for one scored user (payload includes ``score``)."""
    inner = _http_inner_dict(body)
    sc = inner.get("score")
    if sc is None:
        return {"ok": False, "error": "missing_score"}
    try:
        final_score = float(sc)
    except (TypeError, ValueError):
        return {"ok": False, "error": "score_not_numeric"}
    user = {k: v for k, v in inner.items() if k != "score"}
    if not str(user.get("user_id") or "").strip():
        return {"ok": False, "error": "missing_user_id"}
    if not _discover_preflight_ok(state):
        return {"ok": True, "skipped": True}
    return _discover_apply_one_user(state, user, final_score)


def handle_promoter_discovery_apply_batch(body: Dict[str, Any], state: PromoterState) -> Dict[str, Any]:
    """AINL Track A: apply monitor/follow for each scored row (same ordering as monolithic loop; shared caches)."""
    inner = _http_inner_dict(body)
    items = inner.get("items")
    if not isinstance(items, list):
        return {"ok": False, "error": "items_not_list"}
    if not _discover_preflight_ok(state):
        return {"ok": True, "skipped": True}
    monitored = set(_kv_str_list_get(state, "monitored_accounts"))
    following_set: Optional[Set[str]] = None
    if _x_oauth1_creds():
        try:
            following_set = _following_set_cached(state)
        except Exception:
            following_set = set()
    for row in items:
        if not isinstance(row, dict):
            continue
        try:
            final = float(row.get("score", 0))
        except (TypeError, ValueError):
            continue
        user = {k: v for k, v in row.items() if k != "score"}
        if not str(user.get("user_id") or "").strip():
            continue
        _discover_apply_one_user(state, user, final, monitored=monitored, following_set=following_set)
    return {"ok": True, "action": "discovery_apply_batch"}


def handle_x_search_users(body: Dict[str, Any], state: PromoterState) -> Dict[str, Any]:
    inner = _http_inner_dict(body)
    query = str(inner.get("query") or "").strip()
    merge_m = inner.get("merge_monitored", False)
    if isinstance(merge_m, str):
        merge_m = str(merge_m).strip().lower() in ("1", "true", "yes", "on")
    min_sc = float(_env_int("PROMOTER_DISCOVERY_MIN_SCORE", 7))
    dry = _env_bool("PROMOTER_DRY_RUN", False)
    if not query:
        return {"users": [], "error": "missing_query"}
    if dry:
        sample = [
            {
                "user_id": "dry_u1",
                "username": "dry_user",
                "name": "",
                "description": "openclaw ai agent workflow",
                "score": 8.0,
                "why": "heuristic_keyword_match",
            }
        ]
        state.audit("x.search_users", {"dry_run": True, "query": query})
        return {"users": sample, "dry_run": True, "merged_user_ids": []}
    tw_out = _x_recent_search(query, since_id=None, max_results=_search_max_results(), state=state)
    tweets = tw_out.get("tweets") if isinstance(tw_out, dict) else []
    if not isinstance(tweets, list):
        tweets = []
    uid_order: List[str] = []
    seen: set[str] = set()
    for t in tweets:
        if isinstance(t, dict):
            uid = str(t.get("user_id") or "").strip()
            if uid and uid not in seen:
                seen.add(uid)
                uid_order.append(uid)
    users = _x_users_lookup(uid_order)
    pseudo = [
        {
            "id": u["user_id"],
            "text": f"{u.get('username', '')} {u.get('name', '')} {u.get('description', '')}",
        }
        for u in users
    ]
    heur_items = _heuristic_scores([t if isinstance(t, dict) else {} for t in pseudo])
    heur_by_id = {str(h.get("id", "")): h for h in heur_items if isinstance(h, dict)}
    llm_s = _discovery_llm_scores(users, state)
    out_users: List[Dict[str, Any]] = []
    for u in users:
        uid = u["user_id"]
        h = heur_by_id.get(uid, {})
        try:
            hs = float(h.get("score", 0))
        except (TypeError, ValueError):
            hs = 0.0
        ls = llm_s.get(uid)
        final = max(hs, ls) if ls is not None else hs
        row = dict(u)
        row["score"] = final
        row["why"] = h.get("why", "heuristic_keyword_match")
        out_users.append(row)
    out_users.sort(key=lambda x: -float(x.get("score", 0)))
    merged: List[str] = []
    if merge_m and _env_bool("PROMOTER_DISCOVERY_ENABLED", True):
        for u in out_users:
            try:
                sc = float(u.get("score", 0))
            except (TypeError, ValueError):
                sc = 0.0
            if sc >= min_sc:
                _monitored_add(state, str(u.get("user_id", "")))
                merged.append(str(u.get("user_id", "")))
    return {"users": out_users, "merged_user_ids": merged}


def handle_x_like(body: Dict[str, Any], state: PromoterState) -> Dict[str, Any]:
    inner = _http_inner_dict(body)
    tweet_id = str(inner.get("tweet_id") or "").strip()
    if not tweet_id:
        return {"ok": False, "error": "missing_tweet_id"}
    if _env_bool("PROMOTER_DRY_RUN", False):
        state.audit("x.like", {"dry_run": True, "tweet_id": tweet_id})
        return {"ok": True, "dry_run": True, "tweet_id": tweet_id}
    res = _x_api_like(state, tweet_id)
    out = dict(res)
    out["tweet_id"] = tweet_id
    return out


def handle_x_get_conversation(body: Dict[str, Any], state: PromoterState) -> Dict[str, Any]:
    inner = _http_inner_dict(body)
    cid = str(inner.get("conversation_id") or "").strip()
    if not cid:
        heads = _kv_str_list_get(state, "active_threads")
        if heads:
            cid = heads[0]
    if not cid:
        if _env_bool("PROMOTER_DRY_RUN", False):
            state.audit("x.get_conversation", {"dry_run": True, "conversation_id": None})
            return {
                "tweets": [{"id": "dryc1", "text": "thread sample", "user_id": "u1"}],
                "dry_run": True,
                "conversation_id": "dry_conv",
            }
        return {"tweets": [], "error": "missing_conversation_id"}
    if _env_bool("PROMOTER_DRY_RUN", False):
        state.audit("x.get_conversation", {"dry_run": True, "conversation_id": cid})
        return {
            "tweets": [{"id": "dryc1", "text": "thread sample", "user_id": "u1"}],
            "dry_run": True,
            "conversation_id": cid,
        }
    q = f"conversation_id:{cid}"
    out = _x_recent_search(q, since_id=None, max_results=_search_max_results(), state=state)
    tw = out.get("tweets", []) if isinstance(out, dict) else []
    if not isinstance(tw, list):
        tw = []
    meta = out.get("meta") if isinstance(out, dict) and isinstance(out.get("meta"), dict) else {}
    return {"tweets": tw, "conversation_id": cid, "meta": meta}


def handle_promoter_thread_continue(body: Dict[str, Any], state: PromoterState) -> Dict[str, Any]:
    if not _env_bool("PROMOTER_THREAD_ENABLED", False):
        return {"ok": False, "reason": "thread_pack_disabled", "action": "noop"}
    inner = _http_inner_dict(body)
    tweets = inner.get("tweets") or []
    if not isinstance(tweets, list):
        tweets = []
    reply_to = str(inner.get("reply_to_tweet_id") or "").strip()
    conv = str(inner.get("conversation_id") or "").strip()
    dry = _env_bool("PROMOTER_DRY_RUN", False)
    max_day = _env_int("PROMOTER_MAX_REPLIES_PER_DAY", 20)
    if not reply_to:
        return {"ok": False, "error": "missing_reply_to_tweet_id"}
    if state.count_today_replies() >= max_day:
        return {"ok": True, "action": "skipped", "reason": "daily_reply_cap", "dry_run": dry}
    rs_raw = inner.get("reply_system_prompt")
    if not (isinstance(rs_raw, str) and str(rs_raw).strip()):
        rs_raw = body.get("reply_system_prompt")
    reply_system = str(rs_raw).strip() if isinstance(rs_raw, str) and str(rs_raw).strip() else ""
    custom_reply_system = bool(reply_system)
    if not reply_system:
        reply_system = (_load_prompt_file("reply_system") or "").strip()
    if not reply_system:
        reply_system = (
            "You are Apollo, an expert on AINL. Be accurate and concise; include a GitHub/docs CTA when natural."
        )
    reply_system = _reply_system_with_canonical_link(reply_system)
    if not custom_reply_system:
        reply_system = _apply_persona_instructions(reply_system, "reply")
    transcript_bits: List[str] = []
    for t in tweets:
        if isinstance(t, dict):
            transcript_bits.append(str(t.get("text", "")))
    transcript = "\n".join(transcript_bits)[:2000]
    ru_raw = inner.get("reply_user_prompt")
    if not (isinstance(ru_raw, str) and str(ru_raw).strip()):
        ru_raw = body.get("reply_user_prompt")
    reply_user_prompt = (
        str(ru_raw).strip()
        if isinstance(ru_raw, str) and str(ru_raw).strip()
        else f"Thread so far:\n{transcript}\n\nDraft one concise reply as Apollo."
    )
    rf_raw = inner.get("reply_fallback_text")
    if not (isinstance(rf_raw, str) and str(rf_raw).strip()):
        rf_raw = body.get("reply_fallback_text")
    reply_text = (
        str(rf_raw).strip()
        if isinstance(rf_raw, str) and str(rf_raw).strip()
        else f"Thanks for the thread — AINL graphs are deterministic and bridge-friendly. More: {_canonical_github_repo_url()}"
    )
    try:
        if os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY"):
            reply_text = _openai_chat(
                [
                    {"role": "system", "content": reply_system},
                    {
                        "role": "user",
                        "content": reply_user_prompt,
                    },
                ],
                state=state,
                usage_context="thread_continue_reply_draft",
            ).strip()
    except Exception:
        pass
    reply_text = _normalize_promoter_github_links(reply_text)[:280]
    if dry:
        state.audit("thread_continue_dry", {"reply_to": reply_to, "text": reply_text, "conversation_id": conv})
        if conv:
            _thread_track(state, conv)
        return {"ok": True, "action": "dry_run_thread", "text": reply_text}
    post = _x_post_reply(reply_text, reply_to)
    if post.get("ok") and conv:
        _thread_track(state, conv)
    if not post.get("ok"):
        return {"ok": False, "action": "post_failed", "detail": post}
    state.incr_today_replies()
    return {"ok": True, "action": "thread_replied", "reply": post}


def handle_promoter_awareness_boost(body: Dict[str, Any], state: PromoterState) -> Dict[str, Any]:
    u = _canonical_github_repo_url()
    lines = [
        f"AINL: strict graphs, deterministic runtime — {u}",
        f"Try issues/PRs on the repo: {u}",
    ]
    state.audit("awareness_boost", {"link": u})
    return {"ok": True, "cta_lines": lines, "link": u}


_DASHBOARD_STACK_ACTIONS: List[Tuple[str, str]] = [
    ("process_tweet_replied", "Replied"),
    ("process_tweet_post_fail", "Post failed"),
    ("process_tweet_skip", "Skipped"),
    ("process_tweet_dry", "Dry run reply"),
    ("x.search", "x.search"),
    ("search_cursor_commit", "Cursor commit"),
    ("llm.usage", "LLM calls"),
    ("daily_post", "Daily post"),
    ("llm.classify_error", "Classify error"),
    ("discovery_from_search", "Search discovery"),
]


def _utc_hour_keys(start_ts: float, end_ts: float) -> List[str]:
    z = timezone.utc
    cur = datetime.fromtimestamp(start_ts, tz=z).replace(minute=0, second=0, microsecond=0)
    end = datetime.fromtimestamp(end_ts, tz=z).replace(minute=0, second=0, microsecond=0)
    keys: List[str] = []
    while cur <= end and len(keys) < 200:
        keys.append(cur.strftime("%Y-%m-%d %H"))
        cur = cur + timedelta(hours=1)
    return keys


def _llm_usage_sums_python_24h(state: PromoterState, since_24h: float) -> Tuple[int, int, int, int]:
    """Aggregate llm.usage token fields without SQL json_extract (JSON1 missing or query failed)."""
    pt = ct = tt = n = 0
    with state._conn() as c:
        rows = c.execute(
            "SELECT detail_json FROM audit WHERE ts >= ? AND action = 'llm.usage'",
            (since_24h,),
        ).fetchall()
    for row in rows:
        raw = row[0]
        n += 1
        try:
            d = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            continue
        if not isinstance(d, dict):
            continue
        try:
            pt += int(float(d.get("prompt_tokens") or 0))
            ct += int(float(d.get("completion_tokens") or 0))
            tt += int(float(d.get("total_tokens") or 0))
        except (TypeError, ValueError):
            pass
    return (pt, ct, tt, n)


def _tokens_per_hour_python_merge(
    state: PromoterState, start: float, hour_keys: List[str], tokens_per_hour: Dict[str, int]
) -> None:
    hk_set = set(hour_keys)
    with state._conn() as c:
        rows = c.execute(
            "SELECT ts, detail_json FROM audit WHERE ts >= ? AND action = 'llm.usage'",
            (start,),
        ).fetchall()
    for row in rows:
        ts_raw, raw = row[0], row[1]
        try:
            tsf = float(ts_raw)
        except (TypeError, ValueError):
            continue
        hk = datetime.fromtimestamp(tsf, tz=timezone.utc).strftime("%Y-%m-%d %H")
        if hk not in hk_set:
            continue
        try:
            d = json.loads(raw) if raw else {}
            tok = int(float(d.get("total_tokens") or 0)) if isinstance(d, dict) else 0
        except (TypeError, ValueError, json.JSONDecodeError):
            tok = 0
        tokens_per_hour[hk] = tokens_per_hour.get(hk, 0) + tok


def _dashboard_json_bytes(obj: Any) -> bytes:
    try:
        return json.dumps(obj, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as e:
        return json.dumps({"ok": False, "error": "json_encode_failed", "detail": str(e)}).encode("utf-8")


def _promoter_charts_bundle(state: PromoterState, counts_24h: Dict[str, int]) -> Dict[str, Any]:
    now = time.time()
    hours = max(12, min(168, _env_int("PROMOTER_DASHBOARD_CHART_HOURS", 48)))
    days = max(3, min(30, _env_int("PROMOTER_DASHBOARD_CHART_DAYS", 7)))
    start = now - hours * 3600.0
    hour_keys = _utc_hour_keys(start, now)
    stacked_keys = {a for a, _ in _DASHBOARD_STACK_ACTIONS}
    per_hour: Dict[str, Dict[str, int]] = {hk: {} for hk in hour_keys}
    tokens_per_hour: Dict[str, int] = {hk: 0 for hk in hour_keys}
    with state._conn() as c:
        rows = c.execute(
            """
            SELECT strftime('%Y-%m-%d %H', datetime(ts, 'unixepoch')) AS hk,
                   action,
                   COUNT(*) AS n
            FROM audit
            WHERE ts >= ?
            GROUP BY hk, action
            """,
            (start,),
        ).fetchall()
        for hk, action, n in rows:
            hks = str(hk or "")
            act = str(action or "")
            if hks in per_hour:
                per_hour[hks][act] = int(n)
        try:
            tok_rows = c.execute(
                """
                SELECT strftime('%Y-%m-%d %H', datetime(ts, 'unixepoch')) AS hk,
                       IFNULL(SUM(COALESCE(json_extract(detail_json, '$.total_tokens'), 0)), 0) AS t
                FROM audit
                WHERE ts >= ? AND action = 'llm.usage'
                GROUP BY hk
                """,
                (start,),
            ).fetchall()
            for hk, t in tok_rows:
                hks = str(hk or "")
                if hks in tokens_per_hour:
                    tokens_per_hour[hks] = int(float(t or 0))
        except sqlite3.OperationalError:
            _tokens_per_hour_python_merge(state, start, hour_keys, tokens_per_hour)
        day_rows = c.execute(
            """
            SELECT day, count FROM daily_replies
            ORDER BY day DESC
            LIMIT ?
            """,
            (days,),
        ).fetchall()
    daily_labels = [str(r[0]) for r in reversed(day_rows)]
    daily_counts = [int(r[1]) for r in reversed(day_rows)]
    stacked_series: Dict[str, List[int]] = {}
    other_per_hour: List[int] = []
    for hk in hour_keys:
        row = per_hour.get(hk, {})
        known = sum(row.get(a, 0) for a in stacked_keys)
        total = sum(row.values())
        other_per_hour.append(max(0, total - known))
    for action, _label in _DASHBOARD_STACK_ACTIONS:
        stacked_series[action] = [per_hour.get(hk, {}).get(action, 0) for hk in hour_keys]
    stacked_series["other"] = other_per_hour
    short_labels = []
    for hk in hour_keys:
        try:
            dt = datetime.strptime(hk, "%Y-%m-%d %H").replace(tzinfo=timezone.utc)
            short_labels.append(dt.strftime("%m/%d %Hh"))
        except ValueError:
            short_labels.append(hk)
    pie_labels: List[str] = []
    pie_values: List[int] = []
    pie_top = sorted(counts_24h.items(), key=lambda x: -x[1])[:12]
    top_set = set()
    for k, v in pie_top:
        pie_labels.append(k)
        pie_values.append(int(v))
        top_set.add(k)
    rest = sum(int(v) for kk, v in counts_24h.items() if kk not in top_set)
    if rest > 0:
        pie_labels.append("other")
        pie_values.append(rest)
    return {
        "hour_keys_utc": hour_keys,
        "hour_labels_short": short_labels,
        "stacked_actions": [{"key": a, "label": lab} for a, lab in _DASHBOARD_STACK_ACTIONS],
        "stacked_counts": stacked_series,
        "llm_tokens_per_hour": [tokens_per_hour.get(hk, 0) for hk in hour_keys],
        "daily_reply_days": daily_labels,
        "daily_reply_counts": daily_counts,
        "pie_24h_labels": pie_labels,
        "pie_24h_values": pie_values,
        "window_hours": hours,
        "window_days": days,
    }


def _policy_until_ts(raw_value: Optional[str]) -> Optional[int]:
    s = str(raw_value or "").strip()
    if not s:
        return None
    try:
        parsed = json.loads(s)
    except Exception:
        return None
    if isinstance(parsed, dict):
        v = parsed.get("until_ts")
    elif isinstance(parsed, (int, float)):
        v = parsed
    else:
        return None
    try:
        ts = int(float(v))
    except Exception:
        return None
    return ts if ts > 0 else None


def _fmt_utc_unix(ts: Optional[int]) -> Optional[str]:
    if ts is None:
        return None
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(float(ts)))
    except Exception:
        return None


def _promoter_stats_bundle(state: PromoterState) -> Dict[str, Any]:
    now = time.time()
    since_24h = now - 86400.0
    since_7d = now - 86400.0 * 7.0
    with state._conn() as c:
        counts_24h = {
            str(r[0]): int(r[1])
            for r in c.execute(
                "SELECT action, COUNT(*) AS n FROM audit WHERE ts >= ? GROUP BY action ORDER BY n DESC",
                (since_24h,),
            ).fetchall()
        }
        counts_7d = {
            str(r[0]): int(r[1])
            for r in c.execute(
                "SELECT action, COUNT(*) AS n FROM audit WHERE ts >= ? GROUP BY action ORDER BY n DESC",
                (since_7d,),
            ).fetchall()
        }
        try:
            tok_row = c.execute(
                """
                SELECT
                  IFNULL(SUM(COALESCE(json_extract(detail_json, '$.prompt_tokens'), 0)), 0),
                  IFNULL(SUM(COALESCE(json_extract(detail_json, '$.completion_tokens'), 0)), 0),
                  IFNULL(SUM(COALESCE(json_extract(detail_json, '$.total_tokens'), 0)), 0),
                  COUNT(*)
                FROM audit WHERE ts >= ? AND action = 'llm.usage'
                """,
                (since_24h,),
            ).fetchone()
        except sqlite3.OperationalError:
            tok_row = None
        if tok_row is None:
            pt, ct, tt, n = _llm_usage_sums_python_24h(state, since_24h)
            tok_row = (pt, ct, tt, n)
        last_ok_row = c.execute(
            "SELECT MAX(ts) FROM audit WHERE action = 'search_cursor_commit'"
        ).fetchone()
        last_poll_success_ts = float(last_ok_row[0]) if last_ok_row and last_ok_row[0] is not None else None
        commits_last_hour_row = c.execute(
            "SELECT COUNT(*) FROM audit WHERE ts >= ? AND action = 'search_cursor_commit'",
            (now - 3600.0,),
        ).fetchone()
        poll_commits_last_hour = int(commits_last_hour_row[0]) if commits_last_hour_row else 0
        recent_actions = [
            str(r[0] or "")
            for r in c.execute(
                "SELECT action FROM audit WHERE action IN ('llm.classify_error','search_cursor_commit') ORDER BY id DESC LIMIT 50"
            ).fetchall()
        ]
    classify_error_streak = 0
    for a in recent_actions:
        if a == "llm.classify_error":
            classify_error_streak += 1
            continue
        if a == "search_cursor_commit":
            break
    run_health = {
        "last_poll_success_ts": last_poll_success_ts,
        "last_poll_success_utc": _fmt_utc_unix(int(last_poll_success_ts)) if last_poll_success_ts is not None else None,
        "seconds_since_last_poll_success": int(max(0.0, now - last_poll_success_ts)) if last_poll_success_ts is not None else None,
        "poll_commits_last_hour": int(poll_commits_last_hour),
        "classify_error_streak": int(classify_error_streak),
    }
    day = state.day_key()
    with state._conn() as c:
        dr = c.execute("SELECT count FROM daily_replies WHERE day = ?", (day,)).fetchone()
        reply_count_today = int(dr[0]) if dr else 0
        rt = c.execute("SELECT COUNT(*) FROM replied_tweet").fetchone()
        dedupe_size = int(rt[0]) if rt else 0
    mem_p = _memory_db_path()
    charts = _promoter_charts_bundle(state, counts_24h)
    with state._conn() as c:
        daily_block_raw_row = c.execute(
            "SELECT v FROM promoter_kv WHERE k = 'promoter_daily_block_flag'"
        ).fetchone()
        daily_fb_row = c.execute(
            "SELECT v FROM promoter_kv WHERE k = 'promoter_daily_fallback_model_flag'"
        ).fetchone()
        reply_fb_row = c.execute(
            "SELECT v FROM promoter_kv WHERE k = 'promoter_reply_fallback_model_flag'"
        ).fetchone()
        skip_rows = c.execute(
            "SELECT k, v FROM promoter_kv WHERE k LIKE ?",
            ("%_skip_target_%",),
        ).fetchall()
    daily_block_raw = str(daily_block_raw_row[0]) if daily_block_raw_row else ""
    daily_block_set = bool(daily_block_raw.strip())
    daily_block_until = _policy_until_ts(daily_block_raw)
    daily_fb_until = _policy_until_ts(str(daily_fb_row[0]) if daily_fb_row else "")
    reply_fb_until = _policy_until_ts(str(reply_fb_row[0]) if reply_fb_row else "")
    active_skip_target_count = 0
    for r in skip_rows:
        try:
            raw_v = str(r[1] or "")
        except Exception:
            raw_v = ""
        uts = _policy_until_ts(raw_v)
        if uts is not None and float(uts) > now:
            active_skip_target_count += 1
    policy_state = {
        "daily_block_flag_set": daily_block_set,
        "daily_block_until_ts": daily_block_until,
        "daily_block_until_utc": _fmt_utc_unix(daily_block_until),
        "daily_fallback_active": bool(daily_fb_until is not None and float(daily_fb_until) > now),
        "daily_fallback_until_ts": daily_fb_until,
        "daily_fallback_until_utc": _fmt_utc_unix(daily_fb_until),
        "reply_fallback_active": bool(reply_fb_until is not None and float(reply_fb_until) > now),
        "reply_fallback_until_ts": reply_fb_until,
        "reply_fallback_until_utc": _fmt_utc_unix(reply_fb_until),
        "active_skip_target_count": int(active_skip_target_count),
        "skip_target_keys_scanned": int(len(skip_rows)),
    }
    policy_counts_24h = {
        k: int(v)
        for k, v in counts_24h.items()
        if (
            k.startswith("process_tweet_policy_")
            or k.startswith("daily_post_rate_limit_")
            or k.startswith("daily_post_deferred_")
            or k.startswith("process_tweet_fallback_model_")
            or k.startswith("daily_post_fallback_model_")
            or k.startswith("policy_flags_cleanup")
        )
    }
    policy_counts_7d = {
        k: int(v)
        for k, v in counts_7d.items()
        if (
            k.startswith("process_tweet_policy_")
            or k.startswith("daily_post_rate_limit_")
            or k.startswith("daily_post_deferred_")
            or k.startswith("process_tweet_fallback_model_")
            or k.startswith("daily_post_fallback_model_")
            or k.startswith("policy_flags_cleanup")
        )
    }
    mem_policy_24h, mem_policy_7d, mem_policy_day_7d = _memory_policy_action_counts(now)
    for k, v in mem_policy_24h.items():
        policy_counts_24h[k] = int(policy_counts_24h.get(k, 0)) + int(v)
    for k, v in mem_policy_7d.items():
        policy_counts_7d[k] = int(policy_counts_7d.get(k, 0)) + int(v)
    policy_aliases = {
        "process_tweet_policy_skip_target": "reply.skip_target",
        "process_tweet_fallback_model_active": "reply.fallback_active",
        "daily_post_fallback_model_active": "daily.fallback_active",
        "daily_post_deferred_rate_limit": "daily.rate_limit_deferred",
        "daily_post_rate_limit_cooldown_set": "daily.rate_limit_cooldown_set",
        "policy_flags_cleanup": "ops.policy_cleanup",
    }
    policy_norm_24h: Dict[str, int] = {}
    for k, v in policy_counts_24h.items():
        nk = policy_aliases.get(k, k)
        policy_norm_24h[nk] = int(policy_norm_24h.get(nk, 0)) + int(v)
    policy_norm_7d: Dict[str, int] = {}
    for k, v in policy_counts_7d.items():
        nk = policy_aliases.get(k, k)
        policy_norm_7d[nk] = int(policy_norm_7d.get(nk, 0)) + int(v)
    llm_calls_avoided_24h = int(policy_norm_24h.get("reply.skip_target", 0)) + int(
        policy_norm_24h.get("reply.fallback_active", 0)
    ) + int(policy_norm_24h.get("daily.fallback_active", 0))
    # When daily defer short-circuits execution, fallback-active action may be masked.
    # Count one avoided LLM call if fallback flag is active but no daily fallback action was recorded.
    if bool(policy_state.get("daily_fallback_active")) and int(policy_norm_24h.get("daily.fallback_active", 0)) <= 0:
        llm_calls_avoided_24h += 1
    x_calls_avoided_24h = int(policy_norm_24h.get("reply.skip_target", 0)) + int(
        policy_norm_24h.get("daily.rate_limit_deferred", 0)
    )
    day_keys_7d: List[str] = []
    llm_avoided_daily_7d: List[int] = []
    x_avoided_daily_7d: List[int] = []
    by_day_norm: Dict[str, Dict[str, int]] = {}
    for d, amap in mem_policy_day_7d.items():
        if not d:
            continue
        dn = by_day_norm.setdefault(d, {})
        for a, n in amap.items():
            an = policy_aliases.get(str(a), str(a))
            dn[an] = int(dn.get(an, 0)) + int(n or 0)
    for i in range(6, -1, -1):
        d = time.strftime("%Y-%m-%d", time.gmtime(now - (i * 86400.0)))
        day_keys_7d.append(d)
        m = by_day_norm.get(d, {})
        llm_avoided_daily_7d.append(
            int(m.get("reply.skip_target", 0))
            + int(m.get("reply.fallback_active", 0))
            + int(m.get("daily.fallback_active", 0))
        )
        if (
            i == 0
            and bool(policy_state.get("daily_fallback_active"))
            and int(m.get("daily.fallback_active", 0)) <= 0
        ):
            llm_avoided_daily_7d[-1] = int(llm_avoided_daily_7d[-1]) + 1
        x_avoided_daily_7d.append(int(m.get("reply.skip_target", 0)) + int(m.get("daily.rate_limit_deferred", 0)))
    return {
        "ok": True,
        "generated_at_unix": now,
        "promoter_state_db": str(state._path),
        "memory_db_path": str(mem_p),
        "memory_db_readable": mem_p.is_file(),
        "utc_day": day,
        "reply_count_today": reply_count_today,
        "max_replies_per_day": _env_int("PROMOTER_MAX_REPLIES_PER_DAY", 20),
        "original_posts_today": state.count_original_posts_today(),
        "original_posts_cap": _promoter_max_original_posts_per_day(),
        "replied_tweet_dedupe_rows": dedupe_size,
        "audit_actions_last_24h": counts_24h,
        "audit_actions_last_7d": counts_7d,
        "policy_actions_last_24h": policy_counts_24h,
        "policy_actions_last_7d": policy_counts_7d,
        "policy_actions_normalized_last_24h": policy_norm_24h,
        "policy_actions_normalized_last_7d": policy_norm_7d,
        "cost_avoidance_last_24h": {
            "llm_calls_avoided": llm_calls_avoided_24h,
            "x_calls_avoided_est": x_calls_avoided_24h,
        },
        "cost_avoidance_daily_7d": {
            "days": day_keys_7d,
            "llm_calls_avoided": llm_avoided_daily_7d,
            "x_calls_avoided_est": x_avoided_daily_7d,
        },
        "run_health": run_health,
        "policy_state": policy_state,
        "llm_usage_last_24h": {
            "prompt_tokens": int(float(tok_row[0] or 0)),
            "completion_tokens": int(float(tok_row[1] or 0)),
            "total_tokens": int(float(tok_row[2] or 0)),
            "api_calls_recorded": int(tok_row[3] or 0),
        },
        "charts": charts,
    }


def _memory_decisions_tail(state: Optional[PromoterState], limit: int) -> List[Dict[str, Any]]:
    lim = max(1, min(200, int(limit)))
    p = _memory_db_path()
    if not p.is_file():
        return []
    try:
        c = sqlite3.connect(str(p.expanduser().resolve()), timeout=5.0)
        c.row_factory = sqlite3.Row
        try:
            rows = c.execute(
                """
                SELECT id, record_id, created_at, updated_at, payload_json
                FROM memory_records
                WHERE namespace = 'ops' AND record_kind = 'promoter.decision'
                ORDER BY id DESC LIMIT ?
                """,
                (lim,),
            ).fetchall()
        finally:
            c.close()
    except sqlite3.Error:
        return []
    parsed: List[Tuple[sqlite3.Row, Dict[str, Any], Dict[str, Any]]] = []
    uid_set: Set[str] = set()
    tid_set: Set[str] = set()
    for r in rows:
        try:
            payload = json.loads(r["payload_json"] or "{}")
        except json.JSONDecodeError:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        detail = payload.get("detail")
        if not isinstance(detail, dict):
            detail = {}
        _gather_numeric_user_ids(payload, uid_set)
        _gather_numeric_user_ids(detail, uid_set)
        _gather_tweet_ids_for_author_lookup(payload, tid_set)
        _gather_tweet_ids_for_author_lookup(detail, tid_set)
        parsed.append((r, payload, detail))
    by_tweet: Dict[str, Dict[str, str]] = (
        _x_tweets_resolve_authors(state, tid_set) if state is not None else {}
    )
    for _tid, info in by_tweet.items():
        u = str(info.get("user_id") or "").strip()
        if u:
            uid_set.add(u)
    resolved: Dict[str, str] = _resolve_usernames_batch(state, uid_set) if state is not None else {}
    for _tid, info in list(by_tweet.items()):
        uid = str(info.get("user_id") or "").strip()
        if uid in resolved and not str(info.get("username") or "").strip():
            info["username"] = resolved[uid]
    out: List[Dict[str, Any]] = []
    for r, payload, detail in parsed:
        ed = (
            _enrich_detail_handles(dict(detail), resolved, by_tweet)
            if isinstance(detail, dict)
            else {}
        )
        un = str(ed.get("username") or "").strip()
        uid_for_row = str(ed.get("user_id") or "").strip()
        if not un and uid_for_row.isdigit():
            un = resolved.get(uid_for_row, "")
        tid_top = str(payload.get("tweet_id") or "").strip()
        if not un and tid_top in by_tweet:
            un = str(by_tweet[tid_top].get("username") or "").strip()
        prev_items = list(ed.items())[:10]
        act = str(payload.get("action") or "")
        v_key, v_label = _memory_decision_verdict(act, ed)
        reason = _detail_reason_snippet(ed)
        uid_out = uid_for_row or str(ed.get("user_id") or "").strip()
        out.append(
            {
                "id": r["id"],
                "record_id": r["record_id"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
                "action": act,
                "tweet_id": payload.get("tweet_id"),
                "score": payload.get("score"),
                "scope": payload.get("scope"),
                "username": un,
                "user_id": uid_out or None,
                "verdict": v_key,
                "verdict_label": v_label,
                "reason": reason,
                "proceed": ed.get("proceed") if isinstance(ed.get("proceed"), bool) else None,
                "detail_preview": dict(prev_items),
                "detail": ed,
            }
        )
    return out


def _memory_policy_action_counts(now_ts: float) -> Tuple[Dict[str, int], Dict[str, int], Dict[str, Dict[str, int]]]:
    """Policy action counts from memory records (24h, 7d, and per-day 7d)."""
    p = _memory_db_path()
    if not p.is_file():
        return {}, {}, {}
    since_24h = now_ts - 86400.0
    since_7d = now_ts - 7.0 * 86400.0
    out_24h: Dict[str, int] = {}
    out_7d: Dict[str, int] = {}
    out_day_7d: Dict[str, Dict[str, int]] = {}
    try:
        c = sqlite3.connect(str(p.expanduser().resolve()), timeout=5.0)
        c.row_factory = sqlite3.Row
        try:
            rows = c.execute(
                """
                SELECT created_at, payload_json
                FROM memory_records
                WHERE namespace = 'ops' AND record_kind = 'promoter.decision'
                ORDER BY id DESC LIMIT 2000
                """
            ).fetchall()
        finally:
            c.close()
    except sqlite3.Error:
        return {}, {}, {}
    for r in rows:
        created = str(r["created_at"] or "")
        try:
            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            ts = float(dt.timestamp())
        except Exception:
            continue
        if ts < since_7d:
            continue
        raw = str(r["payload_json"] or "{}")
        try:
            payload = json.loads(raw)
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        action = str(payload.get("action") or "").strip()
        if not (
            action.startswith("process_tweet_policy_")
            or action.startswith("daily_post_rate_limit_")
            or action.startswith("daily_post_deferred_")
            or action.startswith("process_tweet_fallback_model_")
            or action.startswith("daily_post_fallback_model_")
            or action.startswith("policy_flags_cleanup")
        ):
            continue
        out_7d[action] = int(out_7d.get(action, 0)) + 1
        d = time.strftime("%Y-%m-%d", time.gmtime(ts))
        by = out_day_7d.setdefault(d, {})
        by[action] = int(by.get(action, 0)) + 1
        if ts >= since_24h:
            out_24h[action] = int(out_24h.get(action, 0)) + 1
    return out_24h, out_7d, out_day_7d


# Read-only HTML monitor: Chart.js from jsDelivr CDN; all data from same-origin JSON.
_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Apollo-X promoter — monitor</title>
<style>
:root { --bg:#0f1419; --card:#1a2332; --txt:#e7ecf3; --muted:#8b9cb3; --acc:#3d8bfd; }
body { font-family: ui-sans-serif, system-ui, sans-serif; background: var(--bg); color: var(--txt);
  margin:0; padding:1rem 1.25rem; line-height:1.5; }
h1 { font-size:1.15rem; margin:0 0 0.5rem; }
.grid { display:grid; gap:1rem; grid-template-columns: repeat(auto-fit, minmax(240px,1fr)); margin-bottom:1rem; }
.grid-charts { display:grid; gap:1rem; grid-template-columns: 1fr; margin-bottom:1rem; }
@media (min-width:900px){ .grid-charts.split { grid-template-columns: 1fr 1fr; } }
.card { background:var(--card); border-radius:8px; padding:1rem; }
.card h2 { font-size:0.85rem; color:var(--muted); margin:0 0 0.5rem; text-transform:uppercase; letter-spacing:.04em; }
.mono { font-family: ui-monospace, monospace; font-size:0.78rem; white-space:pre-wrap; word-break:break-word; }
table { width:100%; border-collapse:collapse; font-size:0.78rem; }
th, td { text-align:left; padding:0.35rem 0.5rem; border-bottom:1px solid #2a3544; vertical-align:top; }
th { color:var(--muted); font-weight:600; }
.badge { display:inline-block; background:#243044; padding:0.1rem 0.35rem; border-radius:4px; margin-right:0.25rem; }
.badge.ok { background:rgba(46,160,67,0.35); color:#aff1c9; }
.badge.bad { background:rgba(229,83,75,0.35); color:#ffc9c6; }
.badge.warn { background:rgba(212,167,44,0.35); color:#ffe8a8; }
.badge.neutral { background:rgba(120,130,150,0.3); color:var(--txt); }
details.sumd { margin-top:0.25rem; }
details.sumd > summary { cursor:pointer; color:var(--acc); font-size:0.72rem; }
a { color: var(--acc); }
.chart-wrap { position:relative; height:min(320px, 55vw); width:100%; }
.chart-wrap.tall { height:min(260px, 50vw); }
.chart-wrap.wide { height:min(240px, 45vw); }
</style>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js" crossorigin="anonymous"></script>
</head>
<body>
<h1>Apollo-X promoter</h1>
<p class="mono" style="color:var(--muted);margin:0 0 0.4rem">Read-only · refreshes every 60s · JSON: <a href="promoter.stats">promoter.stats</a> · scoring audit: <a href="promoter.audit_tail?focus=scoring&amp;limit=80"><code>audit_tail?focus=scoring</code></a></p>
<p class="mono" style="margin:0 0 1rem"><button id="btnPolicyCleanup" class="badge neutral" style="cursor:pointer;border:0">Clear stale policy flags</button> <span id="policyCleanupMsg" style="color:var(--muted)"></span></p>
<div class="grid" id="cards"></div>
<p id="chartJsWarn" class="mono" style="display:none;color:#e5756b;margin:0 0 0.75rem"></p>
<h2 style="font-size:0.95rem; margin:1.2rem 0 0.5rem">Charts</h2>
<p class="mono" style="color:var(--muted);font-size:0.75rem;margin:0 0 0.75rem">UTC hour buckets · stacked audit actions · cursor commits show polling rhythm</p>
<div class="grid-charts">
<div class="card"><h2>Activity by hour (UTC)</h2><div class="chart-wrap"><canvas id="chartHourly" aria-label="Stacked audit counts by hour"></canvas></div></div>
</div>
<div class="grid-charts split">
<div class="card"><h2>LLM total_tokens / hour</h2><div class="chart-wrap tall"><canvas id="chartTokens" aria-label="LLM tokens per hour"></canvas></div></div>
<div class="card"><h2>Audit mix (last 24h)</h2><div class="chart-wrap tall"><canvas id="chartPie" aria-label="Action mix doughnut"></canvas></div></div>
<div class="card"><h2>Policy actions (24h)</h2><div class="chart-wrap tall"><canvas id="chartPolicy" aria-label="Policy action counts"></canvas></div></div>
<div class="card"><h2>Cost avoidance trend (7d)</h2><div class="chart-wrap tall"><canvas id="chartAvoided" aria-label="Avoided calls trend"></canvas></div></div>
</div>
<div class="grid-charts">
<div class="card"><h2>Replies recorded by UTC day</h2><p class="mono" style="color:var(--muted);font-size:0.75rem;margin:0 0 0.5rem">From <code>daily_replies</code> table (promoter reply counter)</p><div class="chart-wrap wide"><canvas id="chartDaily" aria-label="Daily reply counts"></canvas></div></div>
</div>
<h2 style="font-size:0.95rem; margin:1.2rem 0 0.5rem">Scoring &amp; reply outcomes</h2>
<p class="mono" style="color:var(--muted);font-size:0.75rem;margin:0 0 0.5rem">Filtered audit: discovery follows, reply skips, dry-run replies, post failures, successful replies. Full JSON per row: <code>verdict</code>, <code>reason</code>, <code>detail</code>.</p>
<div class="card"><table id="audit_scoring"><thead><tr><th>UTC</th><th>Action</th><th>Verdict</th><th>Handle</th><th>Tweet / target</th><th>Reason</th><th>Summary</th></tr></thead><tbody></tbody></table></div>
<h2 style="font-size:0.95rem; margin:1.2rem 0 0.5rem">Recent audit log (all actions)</h2>
<div class="card"><table id="audit"><thead><tr><th>UTC</th><th>Action</th><th>Summary</th></tr></thead><tbody></tbody></table></div>
<h2 style="font-size:0.95rem; margin:1.2rem 0 0.5rem">AINL decisions (memory / record_decision)</h2>
<p class="mono" style="color:var(--muted);font-size:0.75rem;margin:0 0 0.5rem">Gate, classify batch counts, process_tweet, cursor — requires <code>--enable-adapter memory</code> on the runner.</p>
<div class="card"><table id="mem"><thead><tr><th>Created</th><th>Action</th><th>Verdict</th><th>Handle</th><th>User id</th><th>Tweet id</th><th>Score</th><th>Reason</th><th>Detail</th></tr></thead><tbody></tbody></table></div>
<script>
function esc(s){ if(s==null)return ''; var d=document.createElement('div'); d.textContent=String(s); return d.innerHTML; }
function apiUrl(rel){
  try { return new URL(rel, window.location.href).href; }
  catch(e){ return '/' + String(rel||'').replace(/^\\//,''); }
}
var _dashCharts = { hourly:null, tokens:null, pie:null, daily:null, policy:null, avoided:null };
function _destroyDashCharts(){
  Object.keys(_dashCharts).forEach(function(k){ if(_dashCharts[k]){ _dashCharts[k].destroy(); _dashCharts[k]=null; } });
}
var _chartMuted = '#8b9cb3';
var _chartGrid = '#2a3544';
var _chartColors = {
  process_tweet_replied:'rgba(61,139,253,0.88)',
  process_tweet_post_fail:'rgba(229,83,75,0.88)',
  process_tweet_skip:'rgba(212,167,44,0.85)',
  process_tweet_dry:'rgba(107,142,127,0.8)',
  'x.search':'rgba(144,97,207,0.82)',
  search_cursor_commit:'rgba(90,101,120,0.65)',
  'llm.usage':'rgba(56,232,198,0.55)',
  daily_post:'rgba(255,159,64,0.75)',
  'llm.classify_error':'rgba(255,99,132,0.75)',
  discovery_from_search:'rgba(163,139,255,0.72)',
  other:'rgba(120,130,150,0.45)'
};
function _colorForActionKey(k){
  var c = _chartColors[k];
  return c || _chartColors.other;
}
function renderCharts(st){
  var ch = st && st.charts;
  var warn = document.getElementById('chartJsWarn');
  if(warn){ warn.style.display='none'; warn.textContent=''; }
  if(!ch){ return; }
  if(typeof Chart === 'undefined'){
    if(warn){
      warn.style.display='block';
      warn.textContent='Chart.js did not load (CDN blocked or offline). Allow cdn.jsdelivr.net or use a network that can reach it — summary tables below still update.';
    }
    return;
  }
  _destroyDashCharts();
  var lbl = ch.hour_labels_short || [];
  var sc = ch.stacked_counts || {};
  var order = (ch.stacked_actions||[]).map(function(x){ return x.key; }).concat(['other']);
  var labelMap = { other:'Other' };
  (ch.stacked_actions||[]).forEach(function(x){ labelMap[x.key]=x.label; });
  var datasets = [];
  order.forEach(function(k){
    if(!Array.isArray(sc[k])) return;
    datasets.push({
      label: labelMap[k] || k,
      data: sc[k],
      backgroundColor: _colorForActionKey(k),
      stack: 'ops',
      borderWidth: 0
    });
  });
  var commonLegend = { labels:{ color:_chartMuted, boxWidth:10, font:{ size:10 } } };
  var commonScales = {
    x:{ stacked:true, ticks:{ color:_chartMuted, maxRotation:60, minRotation:45, font:{ size:9 } }, grid:{ color:_chartGrid } },
    y:{ stacked:true, beginAtZero:true, ticks:{ color:_chartMuted, callback:function(v){ return Number.isFinite(v) ? v : ''; } }, grid:{ color:_chartGrid } }
  };
  var elH = document.getElementById('chartHourly');
  if(elH && lbl.length && datasets.length){
    _dashCharts.hourly = new Chart(elH, {
      type: 'bar',
      data: { labels: lbl, datasets: datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: { legend: Object.assign({ position:'bottom' }, commonLegend), tooltip: { itemSort: function(a,b){ return b.parsed.y - a.parsed.y; } } },
        scales: commonScales
      }
    });
  }
  var elT = document.getElementById('chartTokens');
  var tok = ch.llm_tokens_per_hour || [];
  if(elT && lbl.length && tok.length === lbl.length){
    _dashCharts.tokens = new Chart(elT, {
      type: 'line',
      data: {
        labels: lbl,
        datasets: [{
          label: 'total_tokens (llm.usage)',
          data: tok,
          borderColor: 'rgba(56,232,198,0.95)',
          backgroundColor: 'rgba(56,232,198,0.12)',
          fill: true,
          tension: 0.2,
          pointRadius: 0,
          pointHitRadius: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: Object.assign({ position:'bottom' }, commonLegend) },
        scales: {
          x: { ticks:{ color:_chartMuted, maxRotation:60, minRotation:45, font:{ size:9 } }, grid:{ color:_chartGrid } },
          y: { beginAtZero:true, ticks:{ color:_chartMuted }, grid:{ color:_chartGrid } }
        }
      }
    });
  }
  var elP = document.getElementById('chartPie');
  var pl = ch.pie_24h_labels || [];
  var pv = ch.pie_24h_values || [];
  if(elP && pl.length && pl.length === pv.length){
    var pieColors = pl.map(function(_,i){
      var hue = (i * 47) % 360;
      return 'hsla('+hue+',55%,58%,0.85)';
    });
    _dashCharts.pie = new Chart(elP, {
      type: 'doughnut',
      data: { labels: pl, datasets: [{ data: pv, backgroundColor: pieColors, borderWidth: 0 }] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: Object.assign({ position:'right' }, commonLegend),
          tooltip: { callbacks: { label: function(ctx){ var t = ctx.dataset.data[ctx.dataIndex]; var s = (ctx.label||'') + ': ' + t; var sum = pv.reduce(function(a,b){ return a+b; },0); return sum ? s + ' (' + (100*t/sum).toFixed(1) + '%)' : s; } } }
        }
      }
    });
  }
  var elD = document.getElementById('chartDaily');
  var dl = ch.daily_reply_days || [];
  var dc = ch.daily_reply_counts || [];
  if(elD && dl.length && dl.length === dc.length){
    _dashCharts.daily = new Chart(elD, {
      type: 'bar',
      data: {
        labels: dl,
        datasets: [{ label: 'replies (daily_replies.count)', data: dc, backgroundColor: 'rgba(61,139,253,0.75)', borderWidth: 0 }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: Object.assign({ position:'bottom' }, commonLegend) },
        scales: {
          x: { ticks:{ color:_chartMuted }, grid:{ color:_chartGrid } },
          y: { beginAtZero:true, ticks:{ color:_chartMuted, callback:function(v){ return Number.isFinite(v) ? v : ''; } }, grid:{ color:_chartGrid } }
        }
      }
    });
  }
  var elPol = document.getElementById('chartPolicy');
  var polMap = st.policy_actions_normalized_last_24h || st.policy_actions_last_24h || {};
  var polKeys = Object.keys(polMap || {});
  if(elPol && polKeys.length){
    var polPairs = polKeys.map(function(k){ return { k:k, v:Number(polMap[k] || 0) }; });
    polPairs.sort(function(a,b){ return b.v - a.v; });
    var polLabels = polPairs.map(function(x){ return x.k; });
    var polVals = polPairs.map(function(x){ return x.v; });
    _dashCharts.policy = new Chart(elPol, {
      type: 'bar',
      data: {
        labels: polLabels,
        datasets: [{
          label: 'policy action count (24h)',
          data: polVals,
          backgroundColor: 'rgba(163,139,255,0.78)',
          borderWidth: 0
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: 'y',
        plugins: { legend: Object.assign({ position:'bottom' }, commonLegend) },
        scales: {
          x: { beginAtZero:true, ticks:{ color:_chartMuted, callback:function(v){ return Number.isFinite(v) ? v : ''; } }, grid:{ color:_chartGrid } },
          y: { ticks:{ color:_chartMuted, font:{ size:10 } }, grid:{ color:_chartGrid } }
        }
      }
    });
  }
  var elAv = document.getElementById('chartAvoided');
  var cav = st.cost_avoidance_daily_7d || {};
  var cavDays = cav.days || [];
  var cavLlm = cav.llm_calls_avoided || [];
  var cavX = cav.x_calls_avoided_est || [];
  if(elAv && cavDays.length && cavDays.length === cavLlm.length && cavDays.length === cavX.length){
    _dashCharts.avoided = new Chart(elAv, {
      type: 'line',
      data: {
        labels: cavDays,
        datasets: [
          {
            label: 'llm_calls_avoided',
            data: cavLlm,
            borderColor: 'rgba(56,232,198,0.95)',
            backgroundColor: 'rgba(56,232,198,0.12)',
            fill: false,
            tension: 0.2,
            pointRadius: 2,
          },
          {
            label: 'x_calls_avoided_est',
            data: cavX,
            borderColor: 'rgba(255,159,64,0.95)',
            backgroundColor: 'rgba(255,159,64,0.12)',
            fill: false,
            tension: 0.2,
            pointRadius: 2,
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: Object.assign({ position:'bottom' }, commonLegend) },
        scales: {
          x: { ticks:{ color:_chartMuted }, grid:{ color:_chartGrid } },
          y: { beginAtZero:true, ticks:{ color:_chartMuted, callback:function(v){ return Number.isFinite(v) ? v : ''; } }, grid:{ color:_chartGrid } }
        }
      }
    });
  }
}
function summarize(detail){
  if(!detail||typeof detail!=='object') return '';
  var keys=['username','target_username','reply_username','tweet_id','user_id','reply_id','reason','score','proceed','why','heuristic_score','context','model','total_tokens','query','n','dry_run','error','since_id','follow_ok','already_following','daily_count','daily_cap'];
  var parts=[]; for(var i=0;i<keys.length;i++){ var k=keys[i]; var v=detail[k]; if(v==null||v==='') continue;
    if(k==='username'||k==='target_username'||k==='reply_username'){ v=String(v).replace(/^@+/,''); parts.push(k+': @'+v); }
    else parts.push(k+': '+v);
  }
  return parts.slice(0,12).join(' · ') || JSON.stringify(detail).slice(0,180);
}
function verdictCls(vk){
  if(vk==='approved'||vk==='posted') return 'ok';
  if(vk==='rejected'||vk==='skipped'||vk==='failed') return 'bad';
  if(vk==='dry_run') return 'warn';
  return 'neutral';
}
function verdictSpan(row){
  var vk = row.verdict || 'info';
  var lab = row.verdict_label || vk;
  return '<span class="badge '+verdictCls(vk)+'">'+esc(lab)+'</span>';
}
function detailJsonBlock(obj){
  if(!obj||typeof obj!=='object') return '';
  var j = JSON.stringify(obj);
  if(j.length > 2800) j = j.slice(0,2800)+'…';
  return '<details class="sumd"><summary>JSON</summary><pre class="mono">'+esc(j)+'</pre></details>';
}
async function load(){
  try{
    async function jget(rel){
      var u = apiUrl(rel);
      var r = await fetch(u);
      if(!r.ok){ throw new Error(rel + ' HTTP '+r.status+' ('+u+')'); }
      var j = await r.json();
      if(j && j.ok === false){ throw new Error((j.error||'error') + (j.detail ? ': '+j.detail : '')); }
      return j;
    }
    async function jpost(rel, payload){
      var u = apiUrl(rel);
      var r = await fetch(u, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload || {})
      });
      if(!r.ok){ throw new Error(rel + ' HTTP '+r.status+' ('+u+')'); }
      var j = await r.json();
      if(j && j.ok === false){ throw new Error((j.error||'error') + (j.detail ? ': '+j.detail : '')); }
      return j;
    }
    var st = await jget('promoter.stats');
    var au = await jget('promoter.audit_tail?limit=60');
    var aus = await jget('promoter.audit_tail?limit=80&focus=scoring');
    var mem = await jget('promoter.memory_tail?limit=50');
    var u = st.llm_usage_last_24h || {};
    var ps = st.policy_state || {};
    var rh = st.run_health || {};
    var ca = st.cost_avoidance_last_24h || {};
    var wh = (st.charts && st.charts.window_hours) ? ' · charts: last '+st.charts.window_hours+'h' : '';
    var dailyBlockBadge = ps.daily_block_flag_set
      ? '<span class="badge warn">daily block: ON</span>'
      : '<span class="badge ok">daily block: off</span>';
    var dailyFbBadge = ps.daily_fallback_active
      ? '<span class="badge warn">daily fallback: ON</span>'
      : '<span class="badge neutral">daily fallback: off</span>';
    var replyFbBadge = ps.reply_fallback_active
      ? '<span class="badge warn">reply fallback: ON</span>'
      : '<span class="badge neutral">reply fallback: off</span>';
    var skipBadge = '<span class="badge '+((Number(ps.active_skip_target_count||0) > 0) ? 'warn' : 'ok')+'">active skip-targets: '+esc(ps.active_skip_target_count||0)+'</span>';
    document.getElementById('cards').innerHTML =
      '<div class="card"><h2>LLM tokens (24h)</h2><div class="mono">total: '+esc(u.total_tokens)+'<br/>'+
      'prompt: '+esc(u.prompt_tokens)+' · completion: '+esc(u.completion_tokens)+'<br/>'+
      'calls logged: '+esc(u.api_calls_recorded)+'</div></div>'+
      '<div class="card"><h2>Today (UTC)</h2><div class="mono">replies counted: '+esc(st.reply_count_today)+
      ' / cap '+esc(st.max_replies_per_day)+' (set <code>PROMOTER_MAX_REPLIES_PER_DAY</code> in .env)<br/>'+
      'original posts: '+esc(st.original_posts_today)+' / '+esc(st.original_posts_cap)+'<br/>'+
      'dedupe rows: '+esc(st.replied_tweet_dedupe_rows)+'</div></div>'+
      '<div class="card"><h2>SQLite paths</h2><div class="mono">'+esc(st.promoter_state_db)+'<br/><br/>'+esc(st.memory_db_path)+'<br/>memory readable: '+esc(st.memory_db_readable)+'</div></div>'+
      '<div class="card"><h2>Audit actions (24h)</h2><div class="mono">'+
      Object.keys(st.audit_actions_last_24h||{}).map(function(a){ return a+': '+(st.audit_actions_last_24h[a]); }).join('<br/>')+esc(wh)+'</div></div>'+
      '<div class="card"><h2>Run health</h2><div class="mono">'+
      'last poll success: '+esc(rh.last_poll_success_utc || 'n/a')+'<br/>'+
      'seconds since success: '+esc(rh.seconds_since_last_poll_success == null ? 'n/a' : rh.seconds_since_last_poll_success)+'<br/>'+
      'poll commits last hour: '+esc(rh.poll_commits_last_hour || 0)+'<br/>'+
      'classify error streak: '+esc(rh.classify_error_streak || 0)+
      '</div></div>'+
      '<div class="card"><h2>Policy actions (24h)</h2><div class="mono">'+
      (Object.keys(st.policy_actions_normalized_last_24h||{}).length
        ? Object.keys(st.policy_actions_normalized_last_24h||{}).map(function(a){ return a+': '+(st.policy_actions_normalized_last_24h[a]); }).join('<br/>')
        : 'none recorded')+'</div></div>'+
      '<div class="card"><h2>Cost avoidance (24h)</h2><div class="mono">'+
      'llm calls avoided: '+esc(ca.llm_calls_avoided || 0)+'<br/>'+
      'x calls avoided (est): '+esc(ca.x_calls_avoided_est || 0)+
      '</div></div>'+
      '<div class="card"><h2>Policy state (live)</h2><div class="mono">'+
      dailyBlockBadge+' '+dailyFbBadge+' '+replyFbBadge+' '+skipBadge+'<br/>'+
      'daily block until: '+esc(ps.daily_block_until_utc || 'n/a')+'<br/>'+
      'daily fallback until: '+esc(ps.daily_fallback_until_utc || 'n/a')+'<br/>'+
      'reply fallback until: '+esc(ps.reply_fallback_until_utc || 'n/a')+'<br/>'+
      'skip-target keys scanned: '+esc(ps.skip_target_keys_scanned || 0)+
      '</div></div>';
    renderCharts(st);
    var sb = document.querySelector('#audit_scoring tbody');
    sb.innerHTML = (aus.rows||[]).map(function(r){
      var d = r.detail||{};
      var h = (d.username && String(d.username).trim()) ? '@'+String(d.username).replace(/^@+/,'') : '';
      var tid = d.tweet_id || d.target_user_id || '';
      return '<tr><td class="mono">'+esc(r.ts_utc)+'</td><td><span class="badge">'+esc(r.action)+'</span></td><td>'+verdictSpan(r)+'</td><td class="mono">'+esc(h)+'</td><td class="mono">'+esc(tid)+'</td><td class="mono">'+esc(r.reason||'')+'</td><td class="mono">'+esc(summarize(d))+'</td></tr>';
    }).join('');
    var tb = document.querySelector('#audit tbody');
    tb.innerHTML = (au.rows||[]).map(function(r){
      return '<tr><td class="mono">'+esc(r.ts_utc)+'</td><td><span class="badge">'+esc(r.action)+'</span></td><td class="mono">'+esc(summarize(r.detail))+'</td></tr>';
    }).join('');
    var mb = document.querySelector('#mem tbody');
    mb.innerHTML = (mem.rows && mem.rows.length) ? mem.rows.map(function(r){
      var h = (r.username && String(r.username).trim()) ? '@'+String(r.username).trim() : '';
      var det = r.detail || {};
      return '<tr><td class="mono">'+esc(r.created_at)+'</td><td><span class="badge">'+esc(r.action)+'</span></td><td>'+verdictSpan(r)+'</td><td class="mono">'+esc(h)+'</td><td class="mono">'+esc(r.user_id)+'</td><td class="mono">'+esc(r.tweet_id)+'</td><td>'+esc(r.score)+'</td><td class="mono">'+esc(r.reason||'')+'</td><td>'+detailJsonBlock(det)+'</td></tr>';
    }).join('') : '<tr><td colspan="9" style="color:var(--muted)">No memory DB or no rows (run polls with --enable-adapter memory)</td></tr>';
  }catch(e){ document.getElementById('cards').innerHTML='<div class="card">Load error: '+esc(e)+'</div>'; _destroyDashCharts(); }
}
var _policyCleanupBusy = false;
async function cleanupPolicyFlags(){
  if(_policyCleanupBusy) return;
  var ok = window.confirm('Clear stale policy flags now? This removes expired/legacy policy keys from promoter_kv.');
  if(!ok) return;
  var msg = document.getElementById('policyCleanupMsg');
  _policyCleanupBusy = true;
  if(msg) msg.textContent = 'running...';
  try{
    var r = await fetch(apiUrl('promoter.policy_cleanup'), {
      method:'POST',
      headers:{ 'Content-Type':'application/json' },
      body:'{}'
    });
    if(!r.ok){ throw new Error('policy_cleanup HTTP '+r.status); }
    var j = await r.json();
    if(!j || j.ok === false){ throw new Error((j&&j.error)||'policy_cleanup failed'); }
    if(msg) msg.textContent = 'done: cleared '+(j.cleared||0)+' / scanned '+(j.scanned||0);
    await load();
  }catch(e){
    if(msg) msg.textContent = 'error: '+String(e);
  }finally{
    _policyCleanupBusy = false;
  }
}
var _btnPolicyCleanup = document.getElementById('btnPolicyCleanup');
if(_btnPolicyCleanup){ _btnPolicyCleanup.addEventListener('click', cleanupPolicyFlags); }
load(); setInterval(load, 60000);
</script>
</body>
</html>"""


# -----------------------------------------------------------------------------
# HTTP server
# -----------------------------------------------------------------------------

_STATE: Optional[PromoterState] = None

# Client closed the socket early (timeout, cancel) — normal; do not log tracebacks from worker threads.
_CLIENT_DISCONNECT = (BrokenPipeError, ConnectionResetError, ConnectionAbortedError)


ROUTES = {
    "/v1/kv.get": handle_kv_get,
    "/v1/kv.set": handle_kv_set,
    "/v1/x.search": handle_x_search,
    "/v1/llm.classify": handle_llm_classify,
    "/v1/llm.chat": handle_llm_chat,
    "/v1/llm.json_array_extract": handle_llm_json_array_extract,
    "/v1/llm.merge_classify_rows": handle_llm_merge_classify_rows,
    "/v1/promoter.text_contains_any": handle_text_contains_any,
    "/v1/promoter.heuristic_scores": handle_promoter_heuristic_scores,
    "/v1/promoter.classify_prompts": handle_promoter_classify_prompts,
    "/v1/promoter.daily_post_prompts": handle_promoter_daily_post_prompts,
    "/v1/promoter.daily_snippets": handle_promoter_daily_snippets,
    "/v1/promoter.gate_eval": handle_promoter_gate_eval,
    "/v1/promoter.process_tweet": handle_process_tweet,
    "/v1/promoter.discover_tweet_authors": handle_promoter_discover_tweet_authors,
    "/v1/promoter.discovery_candidates_from_tweets": handle_promoter_discovery_candidates_from_tweets,
    "/v1/promoter.discovery_score_users": handle_promoter_discovery_score_users,
    "/v1/promoter.discovery_apply_one": handle_promoter_discovery_apply_one,
    "/v1/promoter.discovery_apply_batch": handle_promoter_discovery_apply_batch,
    "/v1/promoter.search_cursor_commit": handle_search_cursor_commit,
    "/v1/promoter.maybe_daily_post": handle_maybe_daily,
    "/v1/promoter.policy_cleanup": handle_promoter_policy_cleanup,
    "/v1/x.follow": handle_x_follow,
    "/v1/x.search_users": handle_x_search_users,
    "/v1/x.like": handle_x_like,
    "/v1/x.get_conversation": handle_x_get_conversation,
    "/v1/promoter.thread_continue": handle_promoter_thread_continue,
    "/v1/promoter.awareness_boost": handle_promoter_awareness_boost,
}


class GatewayHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def send_error(self, code: int, message: Optional[str] = None, explain: Optional[str] = None) -> None:
        try:
            super().send_error(code, message, explain)
        except _CLIENT_DISCONNECT:
            pass

    def _send_json_body(self, status: int, data: bytes) -> None:
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except _CLIENT_DISCONNECT:
            pass

    def _send_html_body(self, status: int, data: bytes) -> None:
        try:
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
        except _CLIENT_DISCONNECT:
            pass

    def do_GET(self) -> None:
        if not _dashboard_enabled():
            self.send_error(404, "dashboard disabled (set PROMOTER_DASHBOARD_ENABLED=1 to enable)")
            return
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        qs = urllib.parse.parse_qs(parsed.query)
        try:
            assert _STATE is not None
            if path in ("/", "/v1/promoter.dashboard"):
                self._send_html_body(200, _DASHBOARD_HTML.encode("utf-8"))
                return
            if path == "/v1/promoter.stats":
                payload = _dashboard_json_bytes(_promoter_stats_bundle(_STATE))
                self._send_json_body(200, payload)
                return
            if path == "/v1/promoter.audit_tail":
                try:
                    lim = int((qs.get("limit") or ["80"])[0] or 80)
                except ValueError:
                    lim = 80
                focus = (qs.get("focus") or [""])[0].strip().lower()
                if focus == "scoring":
                    raw_audit = _STATE.audit_tail_actions(lim, _SCORING_AUDIT_ACTIONS)
                    enriched = audit_tail_with_handles(_STATE, lim, rows=raw_audit)
                else:
                    enriched = audit_tail_with_handles(_STATE, lim)
                for row in enriched:
                    det = row.get("detail")
                    d = det if isinstance(det, dict) else {}
                    vk, vl = _audit_decision_verdict(str(row.get("action") or ""), d)
                    row["verdict"] = vk
                    row["verdict_label"] = vl
                    row["reason"] = _detail_reason_snippet(d)
                out = _dashboard_json_bytes({"ok": True, "focus": focus or None, "rows": enriched})
                self._send_json_body(200, out)
                return
            if path == "/v1/promoter.memory_tail":
                try:
                    lim = int((qs.get("limit") or ["40"])[0] or 40)
                except ValueError:
                    lim = 40
                blob = _dashboard_json_bytes(
                    {
                        "ok": True,
                        "memory_db": str(_memory_db_path()),
                        "rows": _memory_decisions_tail(_STATE, lim),
                    }
                )
                self._send_json_body(200, blob)
                return
            self.send_error(404, "unknown GET path; try /v1/promoter.dashboard")
        except Exception as e:
            import traceback

            _gw_debug(f"GET dashboard error: {e!r}\n{traceback.format_exc()}")
            err = _dashboard_json_bytes({"ok": False, "error": "dashboard_exception", "detail": str(e)})
            self._send_json_body(200, err)

    def do_POST(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        path = path.rstrip("/") or "/"

        handler = ROUTES.get(path)
        if handler is None:
            self.send_error(404, f"unknown path {path!r}; expected one of {list(ROUTES)}")
            return

        n = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(n) if n else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self.send_error(400, "invalid JSON")
            return

        if isinstance(body, dict) and "executor" in body:
            try:
                validate_executor_bridge_request(body)
            except BridgeEnvelopeError as e:
                self.send_error(400, str(e))
                return

        try:
            assert _STATE is not None
            out = handler(body, _STATE)
        except Exception as e:
            err = json.dumps({"ok": False, "error": str(e)}).encode("utf-8")
            self._send_json_body(500, err)
            return

        data = json.dumps(out, ensure_ascii=False).encode("utf-8")
        self._send_json_body(200, data)


_DOTENV_PRESERVE_IF_SET = frozenset(
    {"PROMOTER_GATEWAY_PORT", "PROMOTER_GATEWAY_HOST", "PROMOTER_DRY_RUN"}
)


def _load_local_dotenv() -> None:
    """Load KEY=VALUE from optional `.env` beside this file.

    Non-empty values from the file **overwrite** os.environ so a filled `.env` wins over empty
    placeholders exported in the shell (a common reason X_BEARER_TOKEN appeared \"missing\").
    Keys in ``_DOTENV_PRESERVE_IF_SET`` are not overwritten when the environment already has a
    non-empty value (so e.g. ``PROMOTER_GATEWAY_PORT=17311`` survives for a side-by-side gateway).
    """
    raw = os.environ.get("PROMOTER_DOTENV")
    p = Path(raw).expanduser() if raw else Path(__file__).resolve().parent / ".env"
    if not p.is_file():
        return
    for line in p.read_text(encoding="utf-8-sig").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("export "):
            s = s[7:].strip()
        if "=" not in s:
            continue
        k, _, v = s.partition("=")
        k = k.strip().lstrip("\ufeff")
        v = v.strip().strip("'").strip('"')
        if k and v:
            # Keep explicit shell/cron overrides for bind + dry-run; .env still fills missing keys and overwrites secrets.
            if k in _DOTENV_PRESERVE_IF_SET and (os.environ.get(k) or "").strip():
                continue
            os.environ[k] = v


def _log_auth_env_summary() -> None:
    if not _env_bool("PROMOTER_GATEWAY_DEBUG", False):
        return
    raw = os.environ.get("PROMOTER_DOTENV")
    p = Path(raw).expanduser() if raw else Path(__file__).resolve().parent / ".env"
    _gw_debug(f"startup: dotenv_path={p} exists={p.is_file()}")
    _gw_debug(
        f"startup: bearer_set={bool(_x_bearer())} oauth1_complete={bool(_x_oauth1_creds())} "
        f"openai_set={bool((os.environ.get('OPENAI_API_KEY') or os.environ.get('LLM_API_KEY') or '').strip())}"
    )


def main() -> int:
    global _STATE
    _load_local_dotenv()
    _log_auth_env_summary()
    host = os.environ.get("PROMOTER_GATEWAY_HOST", "127.0.0.1")
    port = _env_int("PROMOTER_GATEWAY_PORT", 17302)
    state_path = _state_path()
    _STATE = PromoterState(state_path)
    try:
        httpd = ThreadingHTTPServer((host, port), GatewayHandler)
    except OSError as e:
        if e.errno == errno.EADDRINUSE:
            print(
                f"apollo-x gateway: cannot bind {host!r}:{port} (address already in use). "
                f"Stop the other process on this port or set PROMOTER_GATEWAY_PORT to a free port.",
                file=sys.stderr,
            )
            return 1
        raise
    mr = _env_int("PROMOTER_MAX_REPLIES_PER_DAY", 20)
    mo = _env_int("PROMOTER_MAX_ORIGINAL_POSTS_PER_DAY", 5)
    print(
        f"apollo-x gateway on http://{host}:{port}/v1/… (see apollo-x-bot/README.md)\n"
        f"  caps: PROMOTER_MAX_REPLIES_PER_DAY={mr}  PROMOTER_MAX_ORIGINAL_POSTS_PER_DAY={mo}\n"
        f"  state db: {state_path}",
        file=sys.stderr,
    )
    dash_ref = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    if _dashboard_enabled():
        print(
            f"apollo-x monitor  http://{dash_ref}:{port}/v1/promoter.dashboard",
            file=sys.stderr,
        )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
