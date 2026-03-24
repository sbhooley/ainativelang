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
  PROMOTER_STATE_PATH       SQLite file (default: ./apollo-x-bot/data/promoter_state.sqlite)
  PROMOTER_DRY_RUN          If 1, no X writes; LLM falls back to heuristic scoring if no API key
  PROMOTER_MAX_REPLIES_PER_DAY   Default 10
  PROMOTER_USER_COOLDOWN_HOURS   Default 48
  PROMOTER_GATEWAY_DEBUG    If 1, stderr lines [apollo-x-gateway] with tweet counts and skip reasons
  PROMOTER_SEARCH_USE_SINCE_ID   If 1 (default), persist X recent-search newest_id and pass since_id on the next poll (fewer duplicate tweets → smaller classify batches / lower LLM cost). Ignored when PROMOTER_DRY_RUN=1.
  PROMOTER_SEARCH_MAX_RESULTS    Recent search page size 10–100 (default 10). Lower reduces payload and classify tokens when you do not need the full page.
  PROMOTER_DEDUPE_REPLIED_TWEETS If 1 (default), skip reply-draft LLM + post for tweet IDs already replied (or dry-run consumed); avoids repeat spend if the same id reappears.
  PROMOTER_PROMPTS_DIR       Directory with classify_system.txt, classify_instruction.txt, reply_system.txt (default: ./prompts beside gateway_server.py)
  PROMOTER_CANONICAL_GITHUB_URL  Repo URL injected into reply prompts and used as default for daily-post link (default: https://github.com/sbhooley/ainativelang)

  Growth pack (v1.3, all default off):
  PROMOTER_MONITOR_ENABLED     If 1, monitor-poll graphs / x.follow list maintenance active
  PROMOTER_DISCOVERY_ENABLED   If 1, x.search_users may merge high-score authors into monitored_accounts
  PROMOTER_LIKE_ENABLED        If 1, gateway may like monitored authors' tweets after process_tweet
  PROMOTER_THREAD_ENABLED      If 1, promoter.thread_continue posts thread replies
  PROMOTER_AWARENESS_BOOST     If 1, append extra AINL GitHub CTAs to daily post text
  PROMOTER_DISCOVERY_MIN_SCORE Minimum heuristic score (1-10) to merge discovered users (default 7)

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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        self._init()

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(str(self._path))
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
                CREATE TABLE IF NOT EXISTS active_threads (
                    conversation_id TEXT PRIMARY KEY NOT NULL
                );
                """
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

    def posted_original_today(self) -> bool:
        d = self.day_key()
        with self._conn() as c:
            row = c.execute("SELECT tweet_id FROM daily_original WHERE day = ?", (d,)).fetchone()
            return row is not None and bool(row[0])

    def mark_original_posted(self, tweet_id: str) -> None:
        d = self.day_key()
        with self._conn() as c:
            c.execute(
                "INSERT INTO daily_original(day, tweet_id) VALUES (?, ?) ON CONFLICT(day) DO UPDATE SET tweet_id = excluded.tweet_id",
                (d, tweet_id),
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


def _openai_chat(messages: List[Dict[str, str]], *, model: Optional[str] = None) -> str:
    key = os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY or LLM_API_KEY not set")
    base = (os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    model = model or os.environ.get("LLM_MODEL") or "gpt-4o-mini"
    payload = json.dumps(
        {"model": model, "messages": messages, "temperature": 0.2},
        ensure_ascii=False,
    ).encode("utf-8")
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


def _x_recent_search(query: str, *, since_id: Optional[str] = None, max_results: int = 10) -> Dict[str, Any]:
    q = urllib.parse.quote(query, safe="")
    mr = max(10, min(100, max_results))
    url = f"https://api.twitter.com/2/tweets/search/recent?query={q}&max_results={mr}&tweet.fields=author_id,created_at"
    sid = (since_id or "").strip()
    if sid:
        url += f"&since_id={urllib.parse.quote(sid, safe='')}"
    bearer = _x_bearer()
    oauth = _x_oauth1_creds()
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
    obj = json.loads(data.decode("utf-8"))
    raw = obj.get("data") or []
    tweets: List[Dict[str, Any]] = []
    for tw in raw:
        tweets.append(
            {
                "id": str(tw.get("id", "")),
                "text": str(tw.get("text", "")),
                "user_id": str(tw.get("author_id", "")),
                "created_at": tw.get("created_at"),
            }
        )
    return {"tweets": tweets, "meta": obj.get("meta") or {}}


def _x_post_reply(text: str, reply_to_id: str) -> Dict[str, Any]:
    url = "https://api.twitter.com/2/tweets"
    payload = json.dumps(
        {"text": text, "reply": {"in_reply_to_tweet_id": reply_to_id}},
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
        obj = json.loads(data.decode("utf-8"))
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
    if dry:
        state.audit("x.like", {"dry_run": True, "tweet_id": tid, "user_id": uid})
        _gw_debug("x.like dry_run=1 (monitored author)")
        return
    res = _x_api_like(state, tid)
    state.audit("x.like", {"tweet_id": tid, "user_id": uid, "result": res})
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
            ]
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


# -----------------------------------------------------------------------------
# Handlers
# -----------------------------------------------------------------------------


def _state_path() -> Path:
    raw = os.environ.get("PROMOTER_STATE_PATH")
    if raw:
        return Path(raw).expanduser()
    return Path(__file__).resolve().parent / "data" / "promoter_state.sqlite"


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
                }
            ]
            state.audit("x.search", {"dry_run": True, "query": query})
            _gw_debug("x.search dry_run=1 tweets=1 (sample)")
            return {"tweets": sample, "dry_run": True}
        use_since = _env_bool("PROMOTER_SEARCH_USE_SINCE_ID", True)
        since = state.kv_get("x_search_since_id") if use_since else None
        out = _x_recent_search(query, since_id=since, max_results=_search_max_results())
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
        raise


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
            text = _openai_chat(msgs)
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
        text = _openai_chat(messages)
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


def handle_promoter_gate_eval(body: Dict[str, Any], state: PromoterState) -> Dict[str, Any]:
    inner = _http_inner_dict(body)
    tweet_id = str(inner.get("tweet_id") or "")
    user_id = str(inner.get("user_id") or "")
    dry = _env_bool("PROMOTER_DRY_RUN", False)
    max_day = _env_int("PROMOTER_MAX_REPLIES_PER_DAY", 10)
    cool_h = float(_env_int("PROMOTER_USER_COOLDOWN_HOURS", 48))
    dedupe = _env_bool("PROMOTER_DEDUPE_REPLIED_TWEETS", True)
    daily_count = state.count_today_replies()

    _gw_debug(f"gate_eval tweet_id={tweet_id!r} user_id={user_id!r} daily_count={daily_count}/{max_day}")

    if dedupe and state.has_replied_to_tweet(tweet_id):
        _gw_debug("gate_eval skip reason=already_replied_tweet")
        return {
            "proceed": False,
            "reason": "already_replied_tweet",
            "dry_run": dry,
            "daily_count": daily_count,
            "daily_cap": max_day,
        }
    if daily_count >= max_day:
        _gw_debug("gate_eval skip reason=daily_reply_cap")
        return {
            "proceed": False,
            "reason": "daily_reply_cap",
            "dry_run": dry,
            "daily_count": daily_count,
            "daily_cap": max_day,
        }
    if not state.user_cooldown_ok(user_id, cool_h):
        _gw_debug("gate_eval skip reason=user_cooldown")
        return {
            "proceed": False,
            "reason": "user_cooldown",
            "dry_run": dry,
            "daily_count": daily_count,
            "daily_cap": max_day,
        }
    _gw_debug("gate_eval proceed")
    return {
        "proceed": True,
        "reason": None,
        "dry_run": dry,
        "daily_count": daily_count,
        "daily_cap": max_day,
    }


def handle_process_tweet(body: Dict[str, Any], state: PromoterState) -> Dict[str, Any]:
    payload = body.get("payload")
    if not isinstance(payload, dict):
        payload = body
    tweet = payload if isinstance(payload, dict) else {}
    rs_raw = body.get("reply_system_prompt")
    reply_system = str(rs_raw).strip() if isinstance(rs_raw, str) and str(rs_raw).strip() else ""
    if not reply_system:
        reply_system = (_load_prompt_file("reply_system") or "").strip()
    if not reply_system:
        reply_system = (
            "You are Apollo, an expert on AINL. Be accurate and concise; include a GitHub/docs CTA when natural. "
            "Max ~260 chars of guidance for the reply text itself."
        )
    reply_system = _reply_system_with_canonical_link(reply_system)
    tweet_id = str(tweet.get("id", ""))
    user_id = str(tweet.get("user_id", ""))
    dry = _env_bool("PROMOTER_DRY_RUN", False)

    _gw_debug(f"process_tweet payload keys={list(tweet.keys())} id_raw={tweet.get('id')!r}")

    max_day = _env_int("PROMOTER_MAX_REPLIES_PER_DAY", 10)
    cool_h = float(_env_int("PROMOTER_USER_COOLDOWN_HOURS", 48))

    _gw_debug(f"process_tweet begin tweet_id={tweet_id!r} user_id={user_id!r} dry_run={dry}")

    if _env_bool("PROMOTER_DEDUPE_REPLIED_TWEETS", True) and state.has_replied_to_tweet(tweet_id):
        state.audit("process_tweet_skip", {"reason": "already_replied_tweet", "tweet_id": tweet_id})
        _gw_debug("process_tweet skip reason=already_replied_tweet (no draft LLM)")
        return {"ok": True, "action": "skipped", "reason": "already_replied_tweet", "dry_run": dry}

    if state.count_today_replies() >= max_day:
        state.audit("process_tweet_skip", {"reason": "daily_cap", "tweet_id": tweet_id})
        _gw_debug(f"process_tweet skip reason=daily_reply_cap count={state.count_today_replies()}/{max_day}")
        return {"ok": True, "action": "skipped", "reason": "daily_reply_cap", "dry_run": dry}
    if not state.user_cooldown_ok(user_id, cool_h):
        state.audit("process_tweet_skip", {"reason": "user_cooldown", "user_id": user_id})
        _gw_debug(f"process_tweet skip reason=user_cooldown user_id={user_id!r} hours={cool_h}")
        return {"ok": True, "action": "skipped", "reason": "user_cooldown", "dry_run": dry}

    gh = _canonical_github_repo_url()
    reply_text = (
        "If you are standardizing agent workflows, AINL compiles graphs to a deterministic runtime "
        f"(open graphs on GitHub: {gh}). Happy to compare notes on OpenClaw-style orchestration."
    )
    try:
        if os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY"):
            reply_text = _openai_chat(
                [
                    {"role": "system", "content": reply_system},
                    {
                        "role": "user",
                        "content": f"Tweet:\n{tweet.get('text','')}\n\nDraft a helpful, expert reply from Apollo.",
                    },
                ]
            )
            reply_text = reply_text.strip()
    except Exception:
        pass
    reply_text = _normalize_promoter_github_links(reply_text)[:280]

    if dry:
        state.audit("process_tweet_dry", {"tweet_id": tweet_id, "reply": reply_text})
        state.incr_today_replies()
        state.touch_user(user_id)
        if _env_bool("PROMOTER_DEDUPE_REPLIED_TWEETS", True):
            state.mark_replied_tweet(tweet_id)
        _maybe_like_monitored_author(state, tweet)
        _gw_debug("process_tweet dry_run_reply (no X API post)")
        return {"ok": True, "action": "dry_run_reply", "tweet_id": tweet_id, "text": reply_text}

    post = _x_post_reply(reply_text, tweet_id)
    if not post.get("ok"):
        state.audit("process_tweet_post_fail", {"tweet_id": tweet_id, "detail": post})
        _gw_debug(f"process_tweet post_failed detail={post!r}")
        return {"ok": False, "action": "post_failed", "detail": post}
    state.incr_today_replies()
    state.touch_user(user_id)
    if _env_bool("PROMOTER_DEDUPE_REPLIED_TWEETS", True):
        state.mark_replied_tweet(tweet_id)
    state.audit("process_tweet_replied", {"tweet_id": tweet_id, "reply_id": post.get("tweet_id")})
    _maybe_like_monitored_author(state, tweet)
    _gw_debug(f"process_tweet replied reply_tweet_id={post.get('tweet_id')!r}")
    return {"ok": True, "action": "replied", "reply": post}


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
        state.kv_set(key, str(raw))
    return {"ok": True}


def handle_maybe_daily(body: Dict[str, Any], state: PromoterState) -> Dict[str, Any]:
    payload = body.get("payload") or {}
    topic = str(payload.get("topic", "AINL"))
    link = str(payload.get("link") or _canonical_github_repo_url())
    dry = _env_bool("PROMOTER_DRY_RUN", False)

    if state.posted_original_today():
        _gw_debug("maybe_daily noop reason=already_posted_today")
        return {"ok": True, "action": "noop", "reason": "already_posted_today"}

    text = _normalize_promoter_github_links(
        f"{topic} — deterministic agent graphs as code. {link}"
    )[:280]
    if _env_bool("PROMOTER_AWARENESS_BOOST", False):
        u = _canonical_github_repo_url()
        boosted = _normalize_promoter_github_links(
            f"{topic} — deterministic agent graphs. {link} · Issues/PRs: {u}"
        )[:280]
        if boosted:
            text = boosted
    if dry:
        state.mark_original_posted("dry_run")
        state.audit("daily_post_dry", {"text": text})
        _gw_debug("maybe_daily dry_run (marked posted_today for state)")
        return {"ok": True, "action": "dry_run_daily", "text": text}

    post = _x_post_original(text[:280])
    if not post.get("ok"):
        _gw_debug(f"maybe_daily post_failed detail={post!r}")
        return {"ok": False, "action": "daily_failed", "detail": post}
    state.mark_original_posted(str(post.get("tweet_id", "")))
    state.audit("daily_post", {"tweet_id": post.get("tweet_id")})
    _gw_debug(f"maybe_daily posted tweet_id={post.get('tweet_id')!r}")
    return {"ok": True, "action": "daily_posted", "tweet_id": post.get("tweet_id")}


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
    tw_out = _x_recent_search(query, since_id=None, max_results=_search_max_results())
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
    if merge_m and _env_bool("PROMOTER_DISCOVERY_ENABLED", False):
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
    out = _x_recent_search(q, since_id=None, max_results=_search_max_results())
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
    max_day = _env_int("PROMOTER_MAX_REPLIES_PER_DAY", 10)
    if not reply_to:
        return {"ok": False, "error": "missing_reply_to_tweet_id"}
    if state.count_today_replies() >= max_day:
        return {"ok": True, "action": "skipped", "reason": "daily_reply_cap", "dry_run": dry}
    reply_system = (_load_prompt_file("reply_system") or "").strip()
    if not reply_system:
        reply_system = (
            "You are Apollo, an expert on AINL. Be accurate and concise; include a GitHub/docs CTA when natural."
        )
    reply_system = _reply_system_with_canonical_link(reply_system)
    transcript_bits: List[str] = []
    for t in tweets:
        if isinstance(t, dict):
            transcript_bits.append(str(t.get("text", "")))
    transcript = "\n".join(transcript_bits)[:2000]
    reply_text = (
        f"Thanks for the thread — AINL graphs are deterministic and bridge-friendly. More: {_canonical_github_repo_url()}"
    )
    try:
        if os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY"):
            reply_text = _openai_chat(
                [
                    {"role": "system", "content": reply_system},
                    {
                        "role": "user",
                        "content": f"Thread so far:\n{transcript}\n\nDraft one concise reply as Apollo.",
                    },
                ]
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
    "/v1/llm.json_array_extract": handle_llm_json_array_extract,
    "/v1/llm.merge_classify_rows": handle_llm_merge_classify_rows,
    "/v1/promoter.text_contains_any": handle_text_contains_any,
    "/v1/promoter.heuristic_scores": handle_promoter_heuristic_scores,
    "/v1/promoter.classify_prompts": handle_promoter_classify_prompts,
    "/v1/promoter.gate_eval": handle_promoter_gate_eval,
    "/v1/promoter.process_tweet": handle_process_tweet,
    "/v1/promoter.search_cursor_commit": handle_search_cursor_commit,
    "/v1/promoter.maybe_daily_post": handle_maybe_daily,
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
    port = _env_int("PROMOTER_GATEWAY_PORT", 17301)
    _STATE = PromoterState(_state_path())
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
    print(f"apollo-x gateway on http://{host}:{port}/v1/… (see apollo-x-bot/README.md)", file=sys.stderr)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
