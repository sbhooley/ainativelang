"""
Effect analysis: per-node effect_tier, per-label effect_summary, and capability/effect sets.
Provides a stable contract for agents (io-read vs io-write, control, meta) and enables
strict checks (defined-before-use, call effect inclusion, adapter contracts).
"""
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

# Effect tiers: finer than effect (io|pure|meta) for planning and safety.
EFFECT_TIER_PURE = "pure"
EFFECT_TIER_IO_READ = "io-read"
EFFECT_TIER_IO_WRITE = "io-write"
EFFECT_TIER_CONTROL = "control"
EFFECT_TIER_META = "meta"

# Capability/effect kinds used in effect_summary.effects set.
EFFECT_KIND_DB_READ = "db_read"
EFFECT_KIND_DB_WRITE = "db_write"
EFFECT_KIND_HTTP = "http"
EFFECT_KIND_CACHE_READ = "cache_read"
EFFECT_KIND_CACHE_WRITE = "cache_write"
EFFECT_KIND_QUEUE = "queue"
EFFECT_KIND_TXN = "txn"
EFFECT_KIND_SQLITE = "sqlite"
EFFECT_KIND_FS = "fs"
EFFECT_KIND_MEMORY_READ = "memory_read"
EFFECT_KIND_MEMORY_WRITE = "memory_write"
EFFECT_KIND_TOOL = "tool"
EFFECT_KIND_CALL = "call"
EFFECT_KIND_CONTROL = "control"
EFFECT_KIND_META = "meta"
EFFECT_KIND_COMPUTE = "compute"

# Canonical strict-mode adapter contract:
# adapter.verb -> (effect_tier, effect_kind)
#
# This map is the compiler-owned allowlist for strict adapter validation.
# Unknown adapter.verb remains strict-fail by design.
ADAPTER_EFFECT: Dict[str, Tuple[str, str]] = {
    "core.ADD": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.SUB": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.MUL": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.DIV": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.MIN": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.MAX": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.CLAMP": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.CONCAT": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.SPLIT": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.JOIN": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.LOWER": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.UPPER": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.REPLACE": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.CONTAINS": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.STARTSWITH": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.ENDSWITH": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.TRIM": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.STRIP": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.LSTRIP": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.RSTRIP": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.GET": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.PARSE": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.STRINGIFY": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.NOW": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.ISO": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.ISO_TS": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.ENV": (EFFECT_TIER_IO_READ, EFFECT_KIND_MEMORY_READ),
    "core.SUBSTR": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.IDIV": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.SLEEP": (EFFECT_TIER_CONTROL, EFFECT_KIND_CONTROL),
    "core.ECHO": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.ID": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "db.F": (EFFECT_TIER_IO_READ, EFFECT_KIND_DB_READ),
    "db.G": (EFFECT_TIER_IO_READ, EFFECT_KIND_DB_READ),
    "db.P": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_DB_WRITE),
    "db.C": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_DB_WRITE),
    "db.U": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_DB_WRITE),
    "db.D": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_DB_WRITE),
    "api.G": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "api.P": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "api.POST": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "email.G": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "calendar.G": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "social.G": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    # apollo-x-bot / bridge-friendly placeholders (strict allowlist; wire in runtime or bridge).
    "x.SEARCH": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "x.POST_REPLY": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "state.GET_SEEN_IDS": (EFFECT_TIER_IO_READ, EFFECT_KIND_DB_READ),
    "state.MARK_SEEN": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_DB_WRITE),
    "classify.SCORE_RELEVANCE": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "core.FILTER_HIGH_SCORE": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "cache.GET": (EFFECT_TIER_IO_READ, EFFECT_KIND_CACHE_READ),
    "cache.SET": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_CACHE_WRITE),
    "queue.PUT": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_QUEUE),
    "txn.BEGIN": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_TXN),
    "txn.COMMIT": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_TXN),
    "txn.ROLLBACK": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_TXN),
    "auth.VALIDATE": (EFFECT_TIER_IO_READ, EFFECT_KIND_CONTROL),
    "ext.G": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "ext.P": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "ext.OP": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "ext.NEXT": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "ext.ECHO": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "ext.EXEC": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "ext.RUN": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "fanout.ALL": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_CALL),
    "http.GET": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "http.POST": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "http.PUT": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "http.PATCH": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "http.DELETE": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "http.HEAD": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "http.OPTIONS": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    # Config-mapped POST to external executor URLs (optional adapter; same network tier as http.Post).
    "bridge.POST": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "sqlite.QUERY": (EFFECT_TIER_IO_READ, EFFECT_KIND_SQLITE),
    "sqlite.EXECUTE": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_SQLITE),
    "postgres.QUERY": (EFFECT_TIER_IO_READ, EFFECT_KIND_DB_READ),
    "postgres.EXECUTE": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_DB_WRITE),
    "postgres.TRANSACTION": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_DB_WRITE),
    "mysql.QUERY": (EFFECT_TIER_IO_READ, EFFECT_KIND_DB_READ),
    "mysql.EXECUTE": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_DB_WRITE),
    "mysql.TRANSACTION": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_DB_WRITE),
    "redis.GET": (EFFECT_TIER_IO_READ, EFFECT_KIND_CACHE_READ),
    "redis.SET": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_CACHE_WRITE),
    "redis.DELETE": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_CACHE_WRITE),
    "redis.INCR": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_CACHE_WRITE),
    "redis.DECR": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_CACHE_WRITE),
    "redis.HGET": (EFFECT_TIER_IO_READ, EFFECT_KIND_CACHE_READ),
    "redis.HSET": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_CACHE_WRITE),
    "redis.HDEL": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_CACHE_WRITE),
    "redis.HMGET": (EFFECT_TIER_IO_READ, EFFECT_KIND_CACHE_READ),
    "redis.LPUSH": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_QUEUE),
    "redis.RPUSH": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_QUEUE),
    "redis.LPOP": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_QUEUE),
    "redis.RPOP": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_QUEUE),
    "redis.LLEN": (EFFECT_TIER_IO_READ, EFFECT_KIND_QUEUE),
    "redis.PUBLISH": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_QUEUE),
    "redis.SUBSCRIBE": (EFFECT_TIER_IO_READ, EFFECT_KIND_QUEUE),
    "redis.PING": (EFFECT_TIER_IO_READ, EFFECT_KIND_CACHE_READ),
    "redis.INFO": (EFFECT_TIER_IO_READ, EFFECT_KIND_CACHE_READ),
    "redis.TRANSACTION": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_CACHE_WRITE),
    "dynamodb.GET": (EFFECT_TIER_IO_READ, EFFECT_KIND_DB_READ),
    "dynamodb.QUERY": (EFFECT_TIER_IO_READ, EFFECT_KIND_DB_READ),
    "dynamodb.SCAN": (EFFECT_TIER_IO_READ, EFFECT_KIND_DB_READ),
    "dynamodb.BATCH_GET": (EFFECT_TIER_IO_READ, EFFECT_KIND_DB_READ),
    "dynamodb.TRANSACT_GET": (EFFECT_TIER_IO_READ, EFFECT_KIND_DB_READ),
    "dynamodb.LIST_TABLES": (EFFECT_TIER_IO_READ, EFFECT_KIND_DB_READ),
    "dynamodb.DESCRIBE_TABLE": (EFFECT_TIER_IO_READ, EFFECT_KIND_DB_READ),
    "dynamodb.STREAMS_SUBSCRIBE": (EFFECT_TIER_IO_READ, EFFECT_KIND_DB_READ),
    "dynamodb.STREAMS_UNSUBSCRIBE": (EFFECT_TIER_IO_READ, EFFECT_KIND_DB_READ),
    "dynamodb.PUT": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_DB_WRITE),
    "dynamodb.UPDATE": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_DB_WRITE),
    "dynamodb.DELETE": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_DB_WRITE),
    "dynamodb.BATCH_WRITE": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_DB_WRITE),
    "dynamodb.TRANSACT_WRITE": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_DB_WRITE),
    "airtable.LIST": (EFFECT_TIER_IO_READ, EFFECT_KIND_DB_READ),
    "airtable.FIND": (EFFECT_TIER_IO_READ, EFFECT_KIND_DB_READ),
    "airtable.GET_TABLE": (EFFECT_TIER_IO_READ, EFFECT_KIND_DB_READ),
    "airtable.LIST_TABLES": (EFFECT_TIER_IO_READ, EFFECT_KIND_DB_READ),
    "airtable.LIST_BASES": (EFFECT_TIER_IO_READ, EFFECT_KIND_DB_READ),
    "airtable.CREATE": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_DB_WRITE),
    "airtable.UPDATE": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_DB_WRITE),
    "airtable.DELETE": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_DB_WRITE),
    "airtable.UPSERT": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_DB_WRITE),
    "airtable.ATTACHMENT_UPLOAD": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "airtable.ATTACHMENT_DOWNLOAD": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "airtable.WEBHOOK_CREATE": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "airtable.WEBHOOK_LIST": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "airtable.WEBHOOK_DELETE": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "supabase.FROM": (EFFECT_TIER_IO_READ, EFFECT_KIND_DB_READ),
    "supabase.SELECT": (EFFECT_TIER_IO_READ, EFFECT_KIND_DB_READ),
    "supabase.QUERY": (EFFECT_TIER_IO_READ, EFFECT_KIND_DB_READ),
    "supabase.INSERT": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_DB_WRITE),
    "supabase.UPDATE": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_DB_WRITE),
    "supabase.UPSERT": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_DB_WRITE),
    "supabase.DELETE": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_DB_WRITE),
    "supabase.RPC": (EFFECT_TIER_IO_READ, EFFECT_KIND_DB_READ),
    "supabase.AUTH_SIGN_UP": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "supabase.AUTH_SIGN_IN_WITH_PASSWORD": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "supabase.AUTH_SIGN_OUT": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "supabase.AUTH_GET_USER": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "supabase.AUTH_RESET_PASSWORD_FOR_EMAIL": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "supabase.STORAGE_UPLOAD": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "supabase.STORAGE_DOWNLOAD": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "supabase.STORAGE_LIST": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "supabase.STORAGE_REMOVE": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "supabase.STORAGE_GET_PUBLIC_URL": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "supabase.REALTIME_SUBSCRIBE": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "supabase.REALTIME_UNSUBSCRIBE": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "supabase.REALTIME_BROADCAST": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "supabase.REALTIME_REPLAY": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "supabase.REALTIME_GET_CURSOR": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "supabase.REALTIME_ACK": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "fs.READ": (EFFECT_TIER_IO_READ, EFFECT_KIND_FS),
    "fs.LIST": (EFFECT_TIER_IO_READ, EFFECT_KIND_FS),
    "fs.WRITE": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_FS),
    "fs.DELETE": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_FS),
    "memory.PUT": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_MEMORY_WRITE),
    "memory.GET": (EFFECT_TIER_IO_READ, EFFECT_KIND_MEMORY_READ),
    "memory.APPEND": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_MEMORY_WRITE),
    "memory.LIST": (EFFECT_TIER_IO_READ, EFFECT_KIND_MEMORY_READ),
    "memory.DELETE": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_MEMORY_WRITE),
    "memory.PRUNE": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_MEMORY_WRITE),
    # Bridge / ArmaraOS JSON graph store (IR MemoryRecall / MemorySearch also dispatch here).
    "ainl_graph_memory.MEMORY_RECALL": (EFFECT_TIER_IO_READ, EFFECT_KIND_MEMORY_READ),
    "ainl_graph_memory.MEMORY_SEARCH": (EFFECT_TIER_IO_READ, EFFECT_KIND_MEMORY_READ),
    "vector_memory.SEARCH": (EFFECT_TIER_IO_READ, EFFECT_KIND_MEMORY_READ),
    "vector_memory.LIST_SIMILAR": (EFFECT_TIER_IO_READ, EFFECT_KIND_MEMORY_READ),
    "vector_memory.UPSERT": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_MEMORY_WRITE),
    "crm_db.F": (EFFECT_TIER_IO_READ, EFFECT_KIND_DB_READ),
    "crm_db.P": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_DB_WRITE),
    "code_context.INDEX": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_MEMORY_WRITE),
    "code_context.QUERY_CONTEXT": (EFFECT_TIER_IO_READ, EFFECT_KIND_MEMORY_READ),
    "code_context.GET_FULL_SOURCE": (EFFECT_TIER_IO_READ, EFFECT_KIND_MEMORY_READ),
    "code_context.GET_SKELETON": (EFFECT_TIER_IO_READ, EFFECT_KIND_MEMORY_READ),
    "code_context.GET_DEPENDENCIES": (EFFECT_TIER_IO_READ, EFFECT_KIND_MEMORY_READ),
    "code_context.GET_IMPACT": (EFFECT_TIER_IO_READ, EFFECT_KIND_MEMORY_READ),
    "code_context.COMPRESS_CONTEXT": (EFFECT_TIER_IO_READ, EFFECT_KIND_MEMORY_READ),
    "code_context.STATS": (EFFECT_TIER_IO_READ, EFFECT_KIND_MEMORY_READ),
    "tool_registry.LIST": (EFFECT_TIER_IO_READ, EFFECT_KIND_MEMORY_READ),
    "tool_registry.DISCOVER": (EFFECT_TIER_IO_READ, EFFECT_KIND_MEMORY_READ),
    "tool_registry.GET": (EFFECT_TIER_IO_READ, EFFECT_KIND_MEMORY_READ),
    "tool_registry.REGISTER": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_MEMORY_WRITE),
    # LangChain / CrewAI-style external tools; dynamic side effects depend on the registered tool.
    "langchain_tool.CALL": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_TOOL),
    "langchain_tool.MY_SEARCH_TOOL": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_TOOL),
    "ptc_runner.RUN": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "ptc_runner.HEALTH": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "ptc_runner.STATUS": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "llm_query.QUERY": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "llm_query.RUN": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "llm.COMPLETION": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "tools.CALL": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_TOOL),
    # Solana RPC (network); reads vs writes follow HTTP effect kinds for planning compatibility.
    # Contract detail (docs-only; not enforced here): solana.GET_PYTH_PRICE may take optional
    # expect_update_account (bool) for pull/update-account handling; solana.INVOKE may take optional
    # trailing priority_fee_microlamports (micro-lamports per CU, SetComputeUnitPrice).
    "solana.TRANSFER": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "solana.TRANSFER_SPL": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "solana.INVOKE": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "solana.GET_ACCOUNT": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "solana.GET_BALANCE": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "solana.GET_TOKEN_ACCOUNTS": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "solana.GET_PROGRAM_ACCOUNTS": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "solana.GET_SIGNATURES_FOR_ADDRESS": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "solana.GET_LATEST_BLOCKHASH": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "solana.GET_PYTH_PRICE": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "solana.HERMES_FALLBACK": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "solana.GET_MARKET_STATE": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "solana.DERIVE_PDA": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "solana.SIMULATE_EVENTS": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    # wasm compute calls are treated as pure compute effects.
    "wasm.CALL": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    # web adapter (search / fetch)
    "web.SEARCH": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "web.FETCH": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "web.GET": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "web.POST": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    # tiktok adapter
    "tiktok.RECENT": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "tiktok.SEARCH": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "tiktok.PROFILE": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "tiktok.VIDEO": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "tiktok.TRENDING": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "tiktok.ANALYTICS": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    # svc adapter (service health / restart)
    "svc.CADDY": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "svc.CLOUDFLARED": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "svc.MADDY": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "svc.CRM": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "svc.RESTART": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "svc.STATUS": (EFFECT_TIER_IO_READ, EFFECT_KIND_HTTP),
    "svc.START": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    "svc.STOP": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP),
    # Additional core ops used in programs
    "core.LEN": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.LT": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.GT": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.LTE": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.GTE": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.EQ": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.NEQ": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.AND": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.OR": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.NOT": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.ABS": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.ROUND": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.FLOOR": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.CEIL": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.MOD": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.POW": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.KEYS": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.VALUES": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.MERGE": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.PICK": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.OMIT": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.MAP": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.FILTER": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.REDUCE": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.SORT": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.REVERSE": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.SLICE": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.UNIQUE": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.FLATTEN": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.ZIP": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.RANGE": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.TYPE": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.BOOL": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.INT": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.FLOAT": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.STR": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.FORMAT": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.HASH": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.UUID": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    "core.NOOP": (EFFECT_TIER_PURE, EFFECT_KIND_COMPUTE),
    # crm adapter ops
    "crm.QUERY": (EFFECT_TIER_IO_READ, EFFECT_KIND_DB_READ),
    "crm.UPDATE": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_DB_WRITE),
    "crm.CREATE": (EFFECT_TIER_IO_WRITE, EFFECT_KIND_DB_WRITE),
}


def strict_adapter_key(adapter: Any, req_op: Any = "") -> str:
    """Canonical strict contract key for adapter fields (namespace.VERB)."""
    ad = str(adapter or "")
    if "." in ad:
        namespace, ad_verb = ad.split(".", 1)
        return f"{namespace}.{ad_verb.upper()}"
    verb = str(req_op or "").upper() or "F"
    if ad:
        return f"{ad}.{verb}"
    return ""


def strict_adapter_key_for_step(step: Dict[str, Any]) -> str:
    """Canonical strict contract key for compiler/runtime step data.

    Many ``R adapter verb args`` IR nodes store the verb in ``entity`` with
    ``req_op`` left empty.  Fall back to ``entity`` (then ``target``) whenever
    ``req_op`` is absent so the allowlist check uses the real verb rather than
    the sentinel ``"F"``.
    """
    adapter = step.get("adapter") or step.get("src") or ""
    req_op = step.get("req_op")
    if isinstance(adapter, str) and "." not in adapter and not str(req_op or "").strip():
        ent = (step.get("entity") or step.get("target") or "").strip()
        if ent:
            return strict_adapter_key(adapter, ent)
    return strict_adapter_key(adapter, req_op)


def strict_adapter_is_allowed(key: str) -> bool:
    return bool(key) and key in ADAPTER_EFFECT


def strict_adapter_effect(key: str) -> Optional[Tuple[str, str]]:
    return ADAPTER_EFFECT.get(key)


def _adapter_key(step: Dict[str, Any]) -> str:
    return strict_adapter_key_for_step(step)


def effect_tier_for_node(node: Dict[str, Any]) -> str:
    """Return effect_tier for a single node: pure | io-read | io-write | control | meta."""
    op = node.get("op") or (node.get("data") or {}).get("op", "")
    data = node.get("data") or {}

    if op == "Err":
        return EFFECT_TIER_META
    if op == "Retry":
        return EFFECT_TIER_CONTROL
    if op == "R":
        key = _adapter_key(data)
        tier, _ = strict_adapter_effect(key) or (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP)
        return tier
    if op in ("Call", "QueuePut", "CacheSet", "Tx"):
        return EFFECT_TIER_IO_WRITE
    if op == "CacheGet":
        return EFFECT_TIER_IO_READ
    if op in ("MemoryRecall", "MemorySearch"):
        return EFFECT_TIER_IO_READ
    if op in ("If", "Loop", "While"):
        return EFFECT_TIER_CONTROL
    return EFFECT_TIER_PURE


def effect_kinds_for_node(node: Dict[str, Any]) -> Set[str]:
    """Return set of effect kinds (db_read, http, etc.) for this node."""
    op = node.get("op") or (node.get("data") or {}).get("op", "")
    data = node.get("data") or {}
    out: Set[str] = set()

    if op == "Err":
        out.add(EFFECT_KIND_META)
        return out
    if op == "Retry":
        out.add(EFFECT_KIND_CONTROL)
        return out
    if op == "R":
        key = _adapter_key(data)
        _, kind = strict_adapter_effect(key) or (EFFECT_TIER_IO_WRITE, EFFECT_KIND_HTTP)
        out.add(kind)
        return out
    if op == "Call":
        out.add(EFFECT_KIND_CALL)
        return out
    if op == "CacheGet":
        out.add(EFFECT_KIND_CACHE_READ)
        return out
    if op in ("MemoryRecall", "MemorySearch"):
        out.add(EFFECT_KIND_MEMORY_READ)
        return out
    if op == "CacheSet":
        out.add(EFFECT_KIND_CACHE_WRITE)
        return out
    if op == "QueuePut":
        out.add(EFFECT_KIND_QUEUE)
        return out
    if op == "Tx":
        out.add(EFFECT_KIND_TXN)
        return out
    if op in ("If", "Loop", "While"):
        out.add(EFFECT_KIND_CONTROL)
    return out


def compute_label_effect_summary(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    entry: Any,
) -> Dict[str, Any]:
    """Compute effect_summary for a label: reads, writes, effects (set of kinds)."""
    all_reads: Set[str] = set()
    all_writes: Set[str] = set()
    all_effects: Set[str] = set()
    for n in nodes:
        for r in n.get("reads") or []:
            all_reads.add(r)
        for w in n.get("writes") or []:
            all_writes.add(w)
        all_effects.update(effect_kinds_for_node(n))
    return {
        "reads": sorted(all_reads),
        "writes": sorted(all_writes),
        "effects": sorted(all_effects),
    }


def annotate_label_with_effect_summary(label: Dict[str, Any]) -> Dict[str, Any]:
    """Add effect_summary and node effect_tier/effect_kinds to a label. Returns new dict."""
    import copy
    out = copy.deepcopy(label)
    nodes = list(out.get("nodes") or [])
    edges = list(out.get("edges") or [])
    entry = out.get("entry")
    new_nodes = []
    for n in nodes:
        nn = dict(n)
        nn["effect_tier"] = effect_tier_for_node(nn)
        nn["effect_kinds"] = sorted(effect_kinds_for_node(nn))
        new_nodes.append(nn)
    out["nodes"] = new_nodes
    if nodes:
        out["effect_summary"] = compute_label_effect_summary(new_nodes, edges, entry)
    else:
        out["effect_summary"] = {"reads": [], "writes": [], "effects": []}
    return out


def annotate_ir_effect_analysis(ir: Dict[str, Any]) -> Dict[str, Any]:
    """Return deep copy of ir with every label annotated with effect_summary and node effect_tier/effect_kinds."""
    import copy
    ir = copy.deepcopy(ir)
    labels = ir.get("labels") or {}
    ir["labels"] = {lid: annotate_label_with_effect_summary(lb) for lid, lb in labels.items()}
    return ir


def annotate_labels_effect_analysis(labels: Dict[str, Any]) -> None:
    """Mutate labels in place: add effect_summary per label and effect_tier/effect_kinds per node."""
    for lid in list(labels.keys()):
        labels[lid] = annotate_label_with_effect_summary(labels.get(lid) or {})


# Vars that are defined by runtime/convention before label runs (no defined-before-use violation).
PREDEFINED_VARS = frozenset({"_auth_present", "_role", "_error", "_call_result", "_loop_last", "_while_last", "_txid"})

_SUCCESS_PORTS = frozenset({"next", "then", "else", "body", "after"})


def forward_dataflow_defs(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    entry: Any,
    entry_defined: Optional[Set[str]] = None,
) -> Dict[str, Set[str]]:
    """
    Intra-label forward fixpoint: defined_at[n] = vars defined on at least one path to n.
    Only follows edges with to_kind == \"node\" (not cross-label jumps).
    """
    node_by_id = {n.get("id"): n for n in nodes if n.get("id")}
    in_edges: Dict[str, List[str]] = {}
    for e in edges:
        if (e.get("port") or "next") not in _SUCCESS_PORTS:
            continue
        fr, to = e.get("from"), e.get("to")
        if e.get("to_kind") == "node" and fr and to:
            in_edges.setdefault(to, []).append(fr)
    defined_at: Dict[str, Set[str]] = {}
    if entry:
        defined_at[entry] = set(entry_defined) if entry_defined else set()
    changed = True
    max_iter = 2 * len(nodes) + 10
    while changed and max_iter > 0:
        max_iter -= 1
        changed = False
        for nid, n in node_by_id.items():
            preds = in_edges.get(nid, [])
            if not preds and nid != entry:
                continue
            incoming = set()
            for p in preds:
                if p in defined_at:
                    incoming |= defined_at[p]
            writes = set(n.get("writes") or [])
            new_defs = incoming | writes
            if nid == entry and entry_defined:
                new_defs |= entry_defined
            if nid not in defined_at or defined_at[nid] != new_defs:
                defined_at[nid] = new_defs
                changed = True
    return defined_at


def propagate_inter_label_entry_defs(
    labels: Dict[str, Any],
    *,
    norm_lid: Callable[[Any], Optional[str]],
    endpoint_entry_defs: Optional[Dict[str, Set[str]]] = None,
) -> Dict[str, Set[str]]:
    """
    Fixpoint over cross-label edges (If/Loop/While/Call → label): each target label's entry
    inherits vars live at the source branch node. Seeds merge ``endpoint_entry_defs`` (HTTP
    entry payloads). ``norm_lid`` must match compiler label keying (e.g. numeric \"1\" or
    ``alias/ENTRY``).
    """
    entry_vars: Dict[str, Set[str]] = {str(lid): set() for lid in labels}
    for lid, s in (endpoint_entry_defs or {}).items():
        key = norm_lid(lid) or str(lid)
        if key in entry_vars:
            entry_vars[key] |= set(s)

    cap = max(len(labels) * 6 + 12, 12)
    for _ in range(cap):
        changed = False
        new_ev = {k: set(v) for k, v in entry_vars.items()}
        for lid, body in labels.items():
            lid_s = str(lid)
            nodes = body.get("nodes") or []
            edges = body.get("edges") or []
            entry = body.get("entry")
            if not nodes or not isinstance(entry, str) or entry not in {n.get("id") for n in nodes}:
                continue
            defined_at = forward_dataflow_defs(nodes, edges, entry, new_ev.get(lid_s))
            for e in edges:
                if e.get("to_kind") != "label":
                    continue
                raw_tgt = e.get("to")
                tgt = norm_lid(raw_tgt) if raw_tgt is not None else None
                if not tgt or tgt not in entry_vars:
                    continue
                fr = e.get("from")
                if not isinstance(fr, str) or fr not in defined_at:
                    continue
                live = defined_at[fr]
                if not live <= new_ev[tgt]:
                    new_ev[tgt] |= live
                    changed = True
        entry_vars = new_ev
        if not changed:
            break
    return entry_vars


def dataflow_defined_before_use(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    entry: Any,
    entry_defined: Optional[Set[str]] = None,
) -> List[Tuple[str, str]]:
    """
    Defined-before-use: forward fixpoint. defined_at[n] = vars defined on at least one path to n.
    Returns (node_id, var) where node reads var and var not in defined_at[node].
    """
    node_by_id = {n.get("id"): n for n in nodes if n.get("id")}
    defined_at = forward_dataflow_defs(nodes, edges, entry, entry_defined)
    violations: List[Tuple[str, str]] = []
    for nid, n in node_by_id.items():
        reads = set(n.get("reads") or [])
        defs = defined_at.get(nid, set())
        for r in reads:
            if r in PREDEFINED_VARS or r in defs:
                continue
            violations.append((nid, r))
    return violations
