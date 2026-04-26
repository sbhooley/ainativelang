"""Deterministic AINL authoring wizard and corpus reverse-engineering helpers.

This module is deliberately LLM-free.  It powers the MCP ``ainl_get_started``
tool by turning natural-language goals into a small wizard state, and by
reverse-engineering existing ``.ainl`` / ``.lang`` programs into human-like
requests that can seed classifier fixtures.

Reverse-engineering patterns used here:

- Comments and filenames provide the strongest human intent signal.
- Adapter calls identify external contracts the original author needed.
- Output verbs and paths identify side effects: files, queues, cache, CRM, etc.
- Scheduler/header forms identify automation goals, not just one-shot scripts.
- ``demo/``-style ad hoc syntax should be treated as negative signal unless a
  path is explicitly known strict-valid.

The output is meant for agents and humans who do not know AINL yet: every
workflow gets an intent-to-syntax guide rather than a bare verb list.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple


DETAIL_LEVELS = {"brief", "standard", "full"}

REVERSE_ENGINEERING_PATTERNS: Tuple[Dict[str, str], ...] = (
    {
        "name": "comments_to_goal",
        "description": "Treat leading comments and README-style headings as the closest thing to the original human intent.",
    },
    {
        "name": "filename_to_domain",
        "description": "Use path parts like monitoring, scraper, openclaw, intelligence, lead, digest, or watchdog as domain clues.",
    },
    {
        "name": "adapter_calls_to_contracts",
        "description": "Map adapter verbs to contracts the author needed, such as http/browser/fs/cache/solana/llm.",
    },
    {
        "name": "side_effect_verbs_to_outputs",
        "description": "Infer promised side effects from fs/cache/queue/social/email calls and output filenames.",
    },
    {
        "name": "scheduler_headers_to_automation",
        "description": "Treat cron/schedule markers as recurring automation goals, not one-shot scripts.",
    },
    {
        "name": "negative_demo_signal",
        "description": "Use demo/ and legacy/non-strict files as cautionary examples unless artifact profiles mark them strict-valid.",
    },
)

CORPUS_INTENT_BUCKETS: Tuple[Dict[str, Any], ...] = (
    {
        "bucket": "memory_consolidation",
        "terms": ("memory", "consolidation", "daily log", "session continuity", "startup context"),
        "human_goal": "Can you make a workflow that keeps my agent memory useful by summarizing sessions and carrying the important context forward?",
    },
    {
        "bucket": "digest_or_briefing",
        "terms": ("digest", "summary", "briefing", "daily"),
        "human_goal": "I want a daily digest that pulls together the important updates and gives me a quick summary.",
    },
    {
        "bucket": "social_monitoring",
        "terms": ("twitter", "tweet", "x", "tiktok", "lead", "social"),
        "human_goal": "Can you watch social activity, find useful posts or leads, and help me respond or track them?",
    },
    {
        "bucket": "scheduled_ops",
        "terms": ("cron", "schedule", "hourly", "daily", "poll"),
        "human_goal": "I need this to run on a schedule and tell me when something changes or needs attention.",
    },
    {
        "bucket": "service_watchdog",
        "terms": ("watchdog", "health", "infrastructure", "status", "sla", "monitor"),
        "human_goal": "Build me a watchdog that checks service health and escalates when something looks wrong.",
    },
    {
        "bucket": "scraping_and_file_output",
        "terms": ("scraper", "scrape", "csv", "file", "results", "form"),
        "human_goal": "I need a scraper that gathers records from a page or form and saves the results to a file I can inspect.",
    },
    {
        "bucket": "llm_workflow",
        "terms": ("llm", "ai", "classify", "summarize", "generate", "prompt"),
        "human_goal": "Use AI inside the workflow to classify, summarize, or generate a response from the input.",
    },
    {
        "bucket": "lead_routing_crm",
        "terms": ("lead", "router", "crm", "pipeline", "salesforce", "hubspot", "deal"),
        "human_goal": "Route inbound leads to the right owner, score them, and keep an audit trail in CRM or a spreadsheet.",
    },
    {
        "bucket": "outreach_sequences",
        "terms": ("outreach", "sequence", "drip", "campaign", "cold email", "follow-up", "follow up"),
        "human_goal": "Run a respectful outreach sequence with logging, opt-out handling, and a clear paper trail of what was sent.",
    },
    {
        "bucket": "machine_readable_exports",
        "terms": ("jsonl", "ndjson", "newline", "append log", "event log", "audit log"),
        "human_goal": "Append structured lines to a JSONL or log file using strict-safe string building (no fake formatting verbs).",
    },
)


@dataclass(frozen=True)
class RuleBucket:
    name: str
    task_type: str
    subtypes: Tuple[str, ...]
    terms: Tuple[str, ...]
    adapters: Tuple[str, ...]
    strict_examples: Tuple[str, ...]
    readiness: Tuple[str, ...]
    weight: int = 1


RULE_BUCKETS: Tuple[RuleBucket, ...] = (
    RuleBucket(
        name="browser_or_http_scraper",
        task_type="adapter_workflow",
        subtypes=("browser_or_http_scraper", "form_submission", "results_extraction"),
        terms=(
            "scraper",
            "scrape",
            "crawl",
            "visit",
            "visits",
            "page",
            "form",
            "input",
            "inputs",
            "click",
            "search results",
            "results",
            "pagination",
        ),
        adapters=("http_or_browser",),
        strict_examples=("http_form_submit", "browser_form_scrape"),
        readiness=(
            "Target host must be allowed for http/browser access.",
            "Browser runtime may be required if the form uses JavaScript or interactive clicks.",
        ),
        weight=3,
    ),
    RuleBucket(
        name="file_output",
        task_type="adapter_workflow",
        subtypes=("local_file_output",),
        terms=("csv", "json", "jsonl", "file", "save", "saves", "write", "locally", "log", "logs"),
        adapters=("fs",),
        strict_examples=("fs_write_csv", "fs_write_json_or_csv"),
        readiness=("Filesystem root must allow writing the requested output path.",),
        weight=2,
    ),
    RuleBucket(
        name="external_api",
        task_type="adapter_workflow",
        subtypes=("external_api",),
        terms=("api", "http", "webhook", "url", "endpoint", "post", "get", "request"),
        adapters=("http",),
        strict_examples=("http_get", "http_post"),
        readiness=("HTTP allow_hosts must include every outbound host.",),
        weight=2,
    ),
    RuleBucket(
        name="social_or_sms",
        task_type="adapter_workflow",
        subtypes=("messaging_or_social", "compliance_sensitive_messaging", "stateful_tracking"),
        terms=("twilio", "sms", "text", "texting", "phone numbers", "x.com", "twitter", "tweet", "reply"),
        adapters=("http_or_provider_adapter", "llm", "state_or_database"),
        strict_examples=("http_post_api", "llm_generate_response", "stateful_conversation_log"),
        readiness=(
            "Provider credentials and sender identity must be configured.",
            "Outbound messaging needs consent, opt-out, and rate-limit handling.",
        ),
        weight=3,
    ),
    RuleBucket(
        name="llm",
        task_type="adapter_workflow",
        subtypes=("llm_generation_or_classification",),
        terms=("ai", "llm", "classify", "summarize", "generate", "respond", "responses", "prompt"),
        adapters=("llm",),
        strict_examples=("llm_generate_response", "llm_classification"),
        readiness=("LLM provider config must be available to the runtime.",),
        weight=2,
    ),
    RuleBucket(
        name="state",
        task_type="adapter_workflow",
        subtypes=("stateful_tracking",),
        terms=("sqlite", "postgres", "mysql", "redis", "cache", "memory", "database", "history", "state"),
        adapters=("state_or_database",),
        strict_examples=("cache_lookup", "database_write", "memory_store"),
        readiness=("Persistent store path/connection must be configured before run.",),
        weight=2,
    ),
    RuleBucket(
        name="schedule",
        task_type="scheduled_workflow",
        subtypes=("scheduled_automation",),
        terms=("cron", "schedule", "daily", "hourly", "every", "poll", "recurring"),
        adapters=("scheduler_or_cron",),
        strict_examples=("cron_monitor", "scheduled_scraper"),
        readiness=("Scheduler host must know the program path and runtime adapter config.",),
        weight=2,
    ),
    RuleBucket(
        name="run_existing",
        task_type="run_or_debug_existing",
        subtypes=("existing_ainl",),
        terms=(".ainl", ".lang", "run", "execute", "compile"),
        adapters=(),
        strict_examples=("validate_compile_run_existing",),
        readiness=("Read the existing source, validate strict, compile, then run with required adapters.",),
        weight=2,
    ),
    RuleBucket(
        name="debug",
        task_type="run_or_debug_existing",
        subtypes=("validation_repair",),
        terms=("validate", "error", "diagnostic", "fix", "failed", "not working", "invalid"),
        adapters=(),
        strict_examples=("diagnostic_repair_loop",),
        readiness=("Use diagnostics and source context before editing or rerunning unchanged source.",),
        weight=2,
    ),
)


ADAPTER_TO_CONTRACT = {
    "http_or_browser": "adapter_contract:http_or_browser",
    "browser_or_web": "adapter_contract:browser_or_web",
    "http": "adapter_contract:http",
    "browser": "adapter_contract:browser",
    "fs": "adapter_contract:fs",
    "cache": "adapter_contract:cache",
    "llm": "adapter_contract:llm",
    "http_or_provider_adapter": "adapter_contract:provider_or_http",
    "state_or_database": "adapter_contract:state_or_database",
    "scheduler_or_cron": "scheduler_readiness",
}

ADAPTER_CONTRACTS: Dict[str, Dict[str, Any]] = {
    "http": {
        "adapter": "http",
        "status": "known",
        "summary": "Plain HTTP client for deterministic machine-readable endpoints.",
        "runtime_registration": {
            "enable": ["http"],
            "http": {"allow_hosts": ["<host>"], "timeout_s": 15},
        },
        "verbs": {
            "GET": {
                "args": ["url: string", "headers?: dict", "timeout_s?: number"],
                "example": 'res = http.GET "https://example.com/api?x=1" {} 15',
                "returns": ["ok", "status", "status_code", "body", "headers", "url"],
            },
            "POST": {
                "args": ["url: string", "body?: dict|string|bytes", "headers?: dict", "timeout_s?: number"],
                "example": "res = http.POST url body headers 15",
                "returns": ["ok", "status", "status_code", "body", "headers", "url"],
            },
        },
        "pitfalls": [
            "Put GET query parameters in the URL; do not use fake params= arguments.",
            "Inline dict literals on R/opcode lines are not reliable runtime dicts; pass dict body via frame or build it first.",
            "MCP ainl_run must register http with allow_hosts.",
        ],
    },
    "browser": {
        "adapter": "browser",
        "status": "known",
        "summary": "ArmaraOS browser automation proxy for pages that require interaction or JavaScript.",
        "runtime_registration": {
            "enable": ["browser"],
            "browser": {
                "base_url": "http://127.0.0.1:4200",
                "agent_id": "ainl-default",
            },
        },
        "verbs": {
            "NAVIGATE": {
                "args": ["url: string", "mode?: headless|headed|attach"],
                "example": 'session = browser.NAVIGATE target_url "headless"',
                "returns": ["page/session status envelope"],
            },
            "TYPE": {
                "args": ["selector: string", "text: string"],
                "example": 'typed = browser.TYPE "input[name=\'docType\']" "lien"',
                "returns": ["tool result envelope"],
            },
            "CLICK": {
                "args": ["selector_or_text: string"],
                "example": 'clicked = browser.CLICK "button[type=\'submit\']"',
                "returns": ["tool result envelope"],
            },
            "WAIT": {
                "args": ["selector: string", "timeout_ms?: integer"],
                "example": 'visible = browser.WAIT "#results" 5000',
                "returns": ["tool result envelope"],
            },
            "READ_PAGE": {
                "args": [],
                "example": "content = browser.READ_PAGE",
                "returns": ["page text/content"],
            },
            "RUN_JS": {
                "args": ["script: string"],
                "example": 'title = browser.RUN_JS "document.title"',
                "returns": ["script return value"],
            },
        },
        "pitfalls": [
            "Requires the ArmaraOS daemon/browser stack.",
            "Selectors are site-specific; discover them before writing final AINL.",
            "Use browser when HTTP form submission is not enough.",
        ],
    },
    "fs": {
        "adapter": "fs",
        "status": "known",
        "summary": "Sandboxed local filesystem adapter for reading, writing, listing, and checking files.",
        "runtime_registration": {
            "enable": ["fs"],
            "fs": {"root": "<absolute-output-workspace>", "allow_extensions": [".csv", ".json", ".jsonl", ".txt"]},
        },
        "verbs": {
            "read": {
                "args": ["path: string"],
                "example": 'existing = fs.read "output/results.csv"',
                "returns": ["file text"],
            },
            "write": {
                "args": ["path: string", "content?: string"],
                "example": "written = fs.write output_path csv",
                "returns": ["ok", "bytes"],
            },
            "exists": {
                "args": ["path: string"],
                "example": "exists = fs.exists output_path",
                "returns": ["boolean"],
            },
            "mkdir": {
                "args": ["path: string"],
                "example": 'made = fs.mkdir "output"',
                "returns": ["ok"],
            },
        },
        "pitfalls": [
            "Paths are relative to the configured sandbox root.",
            "MCP ainl_run must register fs with a root.",
            "If allow_extensions is set, the output suffix must be allowed.",
        ],
    },
    "cache": {
        "adapter": "cache",
        "status": "known",
        "summary": "File-backed key/value cache for simple state between runs.",
        "runtime_registration": {
            "enable": ["cache"],
            "cache": {"path": "<absolute-cache-json-path>"},
        },
        "verbs": {
            "get": {
                "args": ["key: string", "or namespace: string, key: string"],
                "example": 'cached = cache.get "leadgen"',
                "returns": ["stored value or null"],
            },
            "set": {
                "args": ["key: string, value: any", "or namespace: string, key: string, value: any"],
                "example": "saved = cache.set \"leadgen\" log_text",
                "returns": ["null"],
            },
        },
        "pitfalls": [
            "Use fs for audit logs users need to inspect as files; cache is key/value state.",
            "MCP runs need cache path unless auto-registered by workspace cache file.",
        ],
    },
    "llm": {
        "adapter": "llm",
        "status": "known",
        "summary": "LLM generation/classification adapter family; exact verbs depend on provider/config.",
        "runtime_registration": {
            "enable": ["llm"],
            "llm": {"requires": "AINL_CONFIG or MCP LLM enablement/provider configuration"},
        },
        "verbs": {},
        "pitfalls": [
            "Do not invent LLM verbs; check ainl_capabilities for the configured runtime.",
            "For deterministic tests, keep LLM calls behind mocks or provider config.",
        ],
    },
    "core": {
        "adapter": "core",
        "status": "known",
        "summary": "Deterministic built-in operations for math, strings, object access, parsing, and control helpers.",
        "runtime_registration": {"enable": ["core"]},
        "verbs": {
            "CONCAT": {
                "intent": "join text together",
                "example": 'message = core.CONCAT "Hello, " name',
            },
            "GET": {
                "intent": "read a field from an object or JSON result",
                "example": 'title = core.GET item "title"',
            },
            "LEN": {
                "intent": "count list items or text length",
                "example": "count = core.LEN records",
            },
            "STR": {
                "intent": "convert a value to text",
                "example": "text_count = core.STR count",
            },
            "PARSE": {
                "intent": "parse JSON text",
                "example": "obj = core.PARSE json_text",
            },
            "STRINGIFY": {
                "intent": "serialize a value as JSON text",
                "example": "text = core.STRINGIFY obj",
            },
        },
        "pitfalls": [
            "core.GET argument order is object first, key second.",
            "Use core.CONCAT/core.STRINGIFY instead of invented formatting verbs.",
        ],
    },
}


def _dedupe(seq: Iterable[Any]) -> List[Any]:
    out: List[Any] = []
    seen: Set[str] = set()
    for item in seq:
        key = repr(item)
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def reverse_engineering_patterns() -> List[Dict[str, str]]:
    """Document the reusable signals used to reconstruct human goals."""
    return [dict(row) for row in REVERSE_ENGINEERING_PATTERNS]


def corpus_intent_buckets() -> List[Dict[str, Any]]:
    """Return corpus-derived intent buckets used by the deterministic classifier."""
    return [dict(row) for row in CORPUS_INTENT_BUCKETS]


def load_artifact_profiles(repo_root: Optional[Path] = None) -> Dict[str, Set[str]]:
    """Load artifact profile sets that decide starter-template safety."""
    root = repo_root or Path(__file__).resolve().parent.parent
    path = root / "tooling" / "artifact_profiles.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"strict-valid": set(), "non-strict-only": set(), "legacy-compat": set()}

    out: Dict[str, Set[str]] = {"strict-valid": set(), "non-strict-only": set(), "legacy-compat": set()}
    for group in ("examples", "corpus_examples"):
        rows = data.get(group) or {}
        for status in out:
            out[status].update(str(x) for x in rows.get(status, []) if isinstance(x, str))
    return out


def template_status_for_path(source_file: Optional[str], profiles: Optional[Dict[str, Set[str]]] = None) -> str:
    """Classify a source path as strict starter, non-strict, legacy, experimental, or unknown."""
    if not source_file:
        return "unknown"
    rel = str(source_file).replace("\\", "/")
    marker = rel
    for prefix in ("/AI_Native_Lang/",):
        if prefix in marker:
            marker = marker.split(prefix, 1)[1]
    loaded = profiles if profiles is not None else load_artifact_profiles()
    for status in ("strict-valid", "non-strict-only", "legacy-compat"):
        if marker in loaded.get(status, set()):
            return status
    if marker.startswith("demo/") or "/demo/" in marker:
        return "experimental_or_negative_signal"
    if marker.startswith("examples/"):
        return "unprofiled_example"
    if "intelligence/" in marker or marker.startswith("intelligence/"):
        return "real_world_intelligence_signal"
    return "unknown"


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _term_matches(normalized: str, term: str) -> bool:
    t = term.lower()
    if not re.match(r"^[a-z0-9_]+$", t):
        return t in normalized
    return re.search(rf"\b{re.escape(t)}\b", normalized) is not None


def _score_goal(goal: str) -> Tuple[List[Tuple[RuleBucket, int, List[str]]], List[str]]:
    normalized = _normalize(goal)
    scored: List[Tuple[RuleBucket, int, List[str]]] = []
    detected_all: List[str] = []
    for bucket in RULE_BUCKETS:
        detected = [term for term in bucket.terms if _term_matches(normalized, term)]
        if detected:
            score = len(detected) * bucket.weight
            scored.append((bucket, score, detected))
            detected_all.extend(detected)
    scored.sort(key=lambda row: row[1], reverse=True)
    return scored, _dedupe(detected_all)


def _confidence(scored: Sequence[Tuple[RuleBucket, int, List[str]]]) -> str:
    total = sum(score for _, score, _ in scored)
    if total >= 10 or len(scored) >= 3:
        return "high"
    if total >= 4:
        return "medium"
    return "low"


def _primary_task_type(scored: Sequence[Tuple[RuleBucket, int, List[str]]]) -> str:
    if not scored:
        return "core_workflow"
    task_scores: Dict[str, int] = {}
    for bucket, score, _ in scored:
        task_scores[bucket.task_type] = task_scores.get(bucket.task_type, 0) + score
    return max(task_scores.items(), key=lambda item: item[1])[0]


def _blocking_contracts(adapters: Sequence[str]) -> List[str]:
    return _dedupe(
        ADAPTER_TO_CONTRACT.get(adapter, f"adapter_contract:{adapter}") for adapter in adapters
    )


def adapter_contract(adapter: str, *, detail_level: str = "standard") -> Dict[str, Any]:
    """Return a deterministic adapter contract payload."""
    name = (adapter or "").strip().lower()
    aliases = {
        "http_or_browser": "http_or_browser",
        "browser_or_web": "browser_or_web",
        "provider_or_http": "provider_or_http",
        "state_or_database": "state_or_database",
    }
    if name in {"http_or_browser", "browser_or_web"}:
        return {
            "ok": True,
            "adapter": name,
            "status": "composite",
            "summary": "Choose HTTP for network-submit forms/static endpoints; choose browser for interactive/JavaScript pages.",
            "decision_guide": [
                {
                    "if": "The form endpoint and payload are known or discoverable from network requests.",
                    "choose": "http",
                    "next_contract": "http",
                },
                {
                    "if": "The page requires typing/clicking, JavaScript state, cookies, or visual interaction.",
                    "choose": "browser",
                    "next_contract": "browser",
                },
            ],
            "contracts": [ADAPTER_CONTRACTS["http"], ADAPTER_CONTRACTS["browser"]],
        }
    if name == "provider_or_http":
        return {
            "ok": True,
            "adapter": name,
            "status": "composite",
            "summary": "Use a provider-specific adapter when configured; otherwise use http against the provider API.",
            "contracts": [ADAPTER_CONTRACTS["http"]],
        }
    if name == "state_or_database":
        return {
            "ok": True,
            "adapter": name,
            "status": "composite",
            "summary": "Use cache for simple key/value state, memory for semantic memory, or a DB adapter for relational state.",
            "contracts": [ADAPTER_CONTRACTS["cache"]],
        }
    resolved = aliases.get(name, name)
    contract = ADAPTER_CONTRACTS.get(resolved)
    if contract is None:
        return {
            "ok": False,
            "adapter": adapter,
            "status": "unknown",
            "error": "adapter contract not found",
            "next_step": "Call ainl_capabilities and inspect local adapter docs or gateway/OpenAPI metadata before authoring adapter-specific AINL.",
        }
    out = dict(contract)
    out["ok"] = True
    if detail_level == "brief":
        return {
            "ok": True,
            "adapter": out["adapter"],
            "status": out["status"],
            "summary": out["summary"],
            "runtime_registration": out.get("runtime_registration"),
        }
    return out


def _intent_operation_guide(subtypes: Sequence[str], adapters: Sequence[str]) -> List[Dict[str, Any]]:
    guide: List[Dict[str, Any]] = [
        {
            "step": "Start the workflow",
            "when_you_need_to": "define the workflow",
            "use": "compact graph header",
            "example": "workflow_name:",
            "status": "ready",
        },
        {
            "step": "Declare runtime inputs",
            "when_you_need_to": "accept values at run time",
            "use": "in:",
            "example": "in: input_value output_path",
            "status": "ready",
        },
    ]
    if "browser_or_http_scraper" in subtypes:
        guide.extend(
            [
                {
                    "step": "Visit the site",
                    "when_you_need_to": "load the page",
                    "use": "http.GET or browser.NAVIGATE",
                    "example": "Blocked until http/browser contract is loaded.",
                    "status": "blocked",
                    "blocked_by": "adapter_contract:http_or_browser",
                },
                {
                    "step": "Fill and submit the form",
                    "when_you_need_to": "enter form values and submit the search",
                    "use": "http.POST for network-submit forms, or browser.TYPE/browser.CLICK for interactive forms",
                    "example": "Blocked until we know whether the form is HTTP-submit or browser-driven.",
                    "status": "blocked",
                    "blocked_by": "adapter_contract:http_or_browser",
                },
                {
                    "step": "Extract search results",
                    "when_you_need_to": "turn the results page into records",
                    "use": "browser.READ_PAGE / browser.RUN_JS, or HTTP response parsing plus core.GET/core.SPLIT depending on contract",
                    "example": "Blocked until page/result format is known.",
                    "status": "blocked",
                    "blocked_by": "adapter_contract:http_or_browser",
                },
            ]
        )
    if "local_file_output" in subtypes or "fs" in adapters:
        guide.extend(
            [
                {
                    "step": "Build CSV or JSON text",
                    "when_you_need_to": "combine extracted fields into output rows",
                    "use": "core.CONCAT",
                    "example": 'row = core.CONCAT name "," phone "," address',
                    "status": "ready",
                },
                {
                    "step": "Save locally",
                    "when_you_need_to": "write the output file",
                    "use": "fs.WRITE or fs.Write depending on the strict adapter contract",
                    "example": "Blocked until fs contract is loaded.",
                    "status": "blocked",
                    "blocked_by": "adapter_contract:fs",
                },
            ]
        )
    if "llm_generation_or_classification" in subtypes:
        guide.append(
            {
                "step": "Use AI",
                "when_you_need_to": "classify, summarize, or generate a response",
                "use": "llm operation from contract",
                "example": "Blocked until llm contract is loaded.",
                "status": "blocked",
                "blocked_by": "adapter_contract:llm",
            }
        )
    if "stateful_tracking" in subtypes:
        guide.append(
            {
                "step": "Track state",
                "when_you_need_to": "remember prior results or conversation history",
                "use": "cache/memory/database operation from contract",
                "example": "Blocked until state adapter contract is loaded.",
                "status": "blocked",
                "blocked_by": "adapter_contract:state_or_database",
            }
        )
    guide.append(
        {
            "step": "Return a summary",
            "when_you_need_to": "return what happened after the run",
            "use": "out",
            "example": "out summary",
            "status": "ready",
        }
    )
    return guide


def _first_line_for_goal(goal: str, subtypes: Sequence[str]) -> str:
    normalized = _normalize(goal)
    if "scrape" in normalized or "scraper" in normalized:
        return "scraper:"
    if "twilio" in normalized or "text" in normalized or "sms" in normalized:
        return "sms_outreach:"
    if "monitor" in normalized:
        return "monitor:"
    return "workflow:"


def _strict_resources(example_families: Sequence[str]) -> List[str]:
    del example_families  # Kept for API stability; bundle resource covers all adapters.
    return _dedupe(
        [
            "ainl://strict-authoring-cheatsheet",
            "ainl://strict-valid-examples",
            "ainl://adapter-contracts",
        ]
    )


def _contract_examples_for_adapter(adapter: str) -> Dict[str, str]:
    contract_name = adapter
    if adapter == "http_or_browser":
        contract_name = "http_or_browser"
    contract = adapter_contract(contract_name)
    examples: Dict[str, str] = {}
    for c in contract.get("contracts", [contract]):
        for verb, info in (c.get("verbs") or {}).items():
            ex = info.get("example") if isinstance(info, dict) else None
            if ex:
                examples[f"{c.get('adapter')}.{verb}"] = str(ex)
    return examples


def _clarifying_questions(subtypes: Sequence[str]) -> List[Dict[str, str]]:
    questions: List[Dict[str, str]] = []
    if "browser_or_http_scraper" in subtypes:
        questions.append(
            {
                "question": "Does the form work with a normal HTTP request, or does it require clicking/typing in a browser?",
                "why_it_matters": "This decides whether the workflow uses http or browser.",
            }
        )
    if "local_file_output" in subtypes:
        questions.append(
            {
                "question": "What should the output file be named and where should it be saved?",
                "why_it_matters": "This is needed for fs runtime configuration and side-effect verification.",
            }
        )
    return questions


def _capabilities_seen(capabilities_snapshot: Optional[Dict[str, Any]]) -> bool:
    return isinstance(capabilities_snapshot, dict) and isinstance(capabilities_snapshot.get("adapters"), dict)


def _available_adapters(capabilities_snapshot: Optional[Dict[str, Any]]) -> List[str]:
    if not _capabilities_seen(capabilities_snapshot):
        return []
    return sorted(str(k) for k in (capabilities_snapshot or {}).get("adapters", {}).keys())


def _contract_seen(contract_key: str, adapter_contracts_snapshot: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(adapter_contracts_snapshot, dict):
        return False
    name = contract_key.removeprefix("adapter_contract:")
    return bool(
        adapter_contracts_snapshot.get(name)
        or adapter_contracts_snapshot.get(contract_key)
        or (name in {"browser_or_web"} and adapter_contracts_snapshot.get("http_or_browser"))
    )


def _next_missing_contract_call(contracts: Sequence[str], adapter_contracts_snapshot: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for checkpoint in contracts:
        if checkpoint.startswith("adapter_contract:") and not _contract_seen(checkpoint, adapter_contracts_snapshot):
            return {"tool": "ainl_adapter_contract", "args": {"adapter": checkpoint.split(":", 1)[1]}}
    return None


def _runtime_output_plan_known(goal: str, subtypes: Sequence[str]) -> bool:
    normalized = _normalize(goal or "")
    if "local_file_output" not in subtypes:
        return True
    return any(term in normalized for term in ("csv", "json", "jsonl", "log", "output", "file", "save"))


def _partial_scaffold(
    *,
    goal: str,
    subtypes: Sequence[str],
    adapters: Sequence[str],
    adapter_contracts_snapshot: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    first_line = _first_line_for_goal(goal, subtypes)
    lines = [first_line]
    if "browser_or_http_scraper" in subtypes or "local_file_output" in subtypes:
        lines.append("  in: target_url output_path")
    else:
        lines.append("  in: input_value")

    slices: List[Dict[str, Any]] = [
        {
            "name": "header_and_inputs",
            "status": "ready",
            "lines": lines[:],
            "validate_after": True,
        }
    ]

    if "http_or_browser" in adapters and (
        _contract_seen("adapter_contract:http_or_browser", adapter_contracts_snapshot)
        or _contract_seen("adapter_contract:browser_or_web", adapter_contracts_snapshot)
    ):
        slices.append(
            {
                "name": "adapter_access_http_path",
                "status": "ready",
                "when_to_use": "Use this when the target page/form can be fetched or submitted as normal HTTP.",
                "lines": [*lines, "  page = http.GET target_url"],
                "validate_after": True,
            }
        )
        slices.append(
            {
                "name": "adapter_access_browser_path",
                "status": "ready",
                "when_to_use": "Use this when the page needs JavaScript, cookies, typing, clicking, or visual interaction.",
                "lines": [*lines, "  session = browser.NAVIGATE target_url"],
                "validate_after": True,
            }
        )

    if "fs" in adapters and _contract_seen("adapter_contract:fs", adapter_contracts_snapshot):
        base = [*lines, '  csv_header = "name,phone,address,parcel_number,date\\n"', "  csv = core.CONCAT csv_header rows"]
        slices.append(
            {
                "name": "output_write",
                "status": "ready",
                "lines": [*base, "  written = fs.WRITE output_path csv", "  out written"],
                "validate_after": True,
                "verify_after_run": "Read/check output_path under the configured fs.root and confirm rows were written.",
            }
        )

    if len(slices) == 1:
        return None
    return {
        "syntax_style": "compact",
        "strategy": "emit one safe slice, validate it, then expand",
        "slices": slices,
    }


def _planner_and_host_follow_ups(
    task_type: str,
    subtypes: Sequence[str],
    adapters: Sequence[str],
) -> List[str]:
    """Correlate MCP wizard output with ArmaraOS / inference deterministic-planner behavior."""
    lines: List[str] = [
        "ArmaraOS / inference: when the control plane returns structured.kind=deterministic_plan, execute plan.steps in order; read structured.follow_ups next to plan (adapters, file proof, get_started) — not a second model turn.",
        "MCP: after this wizard, follow next_tool_call and ordered_checklist; keep using mcp_ainl_ainl_validate(strict=true) after each edit.",
    ]
    if any(a in adapters for a in ("http", "http_or_browser")) or "browser_or_http_scraper" in subtypes:
        lines.append(
            "HTTP/browser graphs: before mcp_ainl_ainl_run, pass adapters with allow_hosts (http) or confirm browser runtime; validate ok alone is not runnable proof."
        )
    if "fs" in adapters or "local_file_output" in subtypes:
        lines.append(
            "File outputs: after a successful run with fs, file_read the output path before claiming CSV/JSONL/log contents in the user reply."
        )
    if "llm" in adapters or "llm_workflow" in subtypes:
        lines.append(
            "LLM adapters: discover provider config (AINL_CONFIG / env) before assuming llm.* calls will run on MCP hosts."
        )
    if task_type == "scheduled_workflow" or "scheduled_automation" in subtypes:
        lines.append(
            "Scheduled graphs: confirm the host scheduler path (e.g. ArmaraOS cron) separately from strict validate/compile."
        )
    return _dedupe(lines)


def _ordered_checklist(task_type: str, subtypes: Sequence[str], adapters: Sequence[str]) -> List[str]:
    """Task-shaped checklist (always includes proof-of-run reminders)."""
    base = [
        "Describe the goal with ainl_get_started before adapter-heavy AINL.",
        "Use compact syntax for new graphs.",
        "Call ainl_capabilities; load ainl_adapter_contract for each non-core adapter you will use.",
        "Pick a strict-valid template family (see ainl://strict-valid-examples).",
        "Write one slice; ainl_validate strict after each slice.",
        "ainl_compile for IR + frame_hints; configure adapters for ainl_run.",
        "ainl_run with explicit adapters= when http/fs/cache/sqlite/a2a are used.",
        "Verify promised side effects (files, logs, messages) before claiming success.",
    ]
    if task_type == "core_workflow" and not adapters:
        return [
            "Start from examples/compact/hello_compact.ainl shape.",
            *base[3:],
        ]
    if "browser_or_http_scraper" in subtypes:
        return [
            "Decide HTTP vs browser using ainl_adapter_contract(http_or_browser).",
            *base[2:],
        ]
    return base


def get_started(
    goal: str,
    *,
    detail_level: str = "standard",
    existing_source: Optional[str] = None,
    path: Optional[str] = None,
    diagnostics: Optional[Dict[str, Any]] = None,
    capabilities_snapshot: Optional[Dict[str, Any]] = None,
    adapter_contracts_snapshot: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Classify a natural-language goal and return a wizard state."""
    del existing_source, path  # Reserved for future repair/debug wizard stages.
    syntax_corrections: List[Dict[str, str]] = []
    if isinstance(diagnostics, dict):
        pd = diagnostics.get("primary_diagnostic")
        if isinstance(pd, dict) and (pd.get("message") or pd.get("kind")):
            syntax_corrections.append(
                {
                    "issue": str(pd.get("message") or pd.get("kind") or "diagnostic"),
                    "fix": str(
                        pd.get("suggested_fix")
                        or pd.get("llm_repair_hint")
                        or "Re-read ainl://strict-authoring-cheatsheet and re-validate strict."
                    ),
                }
            )
    detail = detail_level if detail_level in DETAIL_LEVELS else "standard"
    scored, detected_terms = _score_goal(goal or "")
    task_type = _primary_task_type(scored)
    subtypes = _dedupe(st for bucket, _, _ in scored for st in bucket.subtypes)
    adapters = _dedupe(adapter for bucket, _, _ in scored for adapter in bucket.adapters)
    strict_examples = _dedupe(example for bucket, _, _ in scored for example in bucket.strict_examples)
    readiness = _dedupe(item for bucket, _, _ in scored for item in bucket.readiness)

    if not scored:
        subtypes = ["core_only"]
        strict_examples = ["hello_compact"]
        readiness = []

    contracts = _blocking_contracts(adapters)
    complete_checkpoints = [
        "goal_classified",
        "syntax_style_selected",
        "intent_operation_guide_generated",
    ]
    missing = []
    if adapters and _capabilities_seen(capabilities_snapshot):
        complete_checkpoints.append("ainl_capabilities")
    elif adapters:
        missing.append("ainl_capabilities")
    for contract in contracts:
        if _contract_seen(contract, adapter_contracts_snapshot):
            complete_checkpoints.append(contract)
        else:
            missing.append(contract)
    if strict_examples:
        complete_checkpoints.append(f"strict_example:{strict_examples[0]}")
    if "fs" in adapters and not _runtime_output_plan_known(goal or "", subtypes):
        missing.append("runtime_output_plan")
    missing = _dedupe(missing)

    can_author_now = (not adapters and task_type == "core_workflow") or (
        bool(adapters) and not missing
    )
    first_line = _first_line_for_goal(goal or "", subtypes)
    intent_guide = _intent_operation_guide(subtypes, adapters)
    next_contract_call = _next_missing_contract_call(contracts, adapter_contracts_snapshot)
    partial_scaffold = _partial_scaffold(
        goal=goal or "",
        subtypes=subtypes,
        adapters=adapters,
        adapter_contracts_snapshot=adapter_contracts_snapshot,
    )
    if not adapters:
        wizard_stage = "core_starter"
    elif not _capabilities_seen(capabilities_snapshot):
        wizard_stage = "capability_discovery"
    elif next_contract_call:
        wizard_stage = "contract_resolution"
    else:
        wizard_stage = "incremental_authoring"
    next_tool_call = (
        {
            "tool": "ainl_validate",
            "args": {
                "code": f"{first_line}\n  out \"Hello from AINL\"\n",
                "strict": True,
            },
        }
        if not adapters
        else ({"tool": "ainl_capabilities", "args": {}} if not _capabilities_seen(capabilities_snapshot) else next_contract_call)
    )
    if next_tool_call is None:
        next_tool_call = {
            "tool": "ainl_validate",
            "args": {"code": "\n".join((partial_scaffold or {}).get("slices", [{}])[0].get("lines", [first_line])), "strict": True},
        }

    profiles = load_artifact_profiles()
    strict_paths = sorted(profiles.get("strict-valid", set()))
    strict_idx = {
        "resource_uri": "ainl://strict-valid-examples",
        "count": len(strict_paths),
        "sample_paths": strict_paths[:24],
    }

    out: Dict[str, Any] = {
        "ok": True,
        "goal": goal,
        "detail_level": detail,
        "wizard_stage": wizard_stage,
        "inferred_task_type": task_type,
        "subtypes": subtypes,
        "confidence": _confidence(scored),
        "detected_terms": detected_terms,
        "wizard_state": {
            "can_author_now": can_author_now,
            "blocking_reason": (
                "Core-only compact workflow; a strict starter scaffold is available."
                if can_author_now and not adapters
                else "Capabilities and adapter contracts are loaded; write one compact slice, validate it, then expand."
                if can_author_now
                else "This workflow needs discovery before full authoring. Complete the missing checkpoints before writing adapter-specific AINL."
            ),
            "complete_checkpoints": complete_checkpoints,
            "missing_checkpoints": [] if can_author_now else missing,
        },
        "available_adapters": _available_adapters(capabilities_snapshot),
        "syntax_style": {
            "recommended": "compact",
            "reason": "Use compact syntax for new AINL. It is easier to read and avoids most opcode formatting mistakes.",
        },
        "minimum_checklist": [
            "Use compact syntax.",
            "Inspect AINL capabilities.",
            "Load adapter contracts for non-core adapters.",
            "Pick a strict-valid example for this workflow shape.",
            "Write one safe slice at a time.",
            "Validate strict after each slice.",
            "Compile and check required adapters.",
            "Run with required adapters configured.",
            "Verify promised side effects.",
        ],
        "ordered_checklist": _ordered_checklist(task_type, subtypes, adapters),
        "quick_start": [
            "Call ainl_capabilities before writing new adapter.VERB lines.",
            "Fetch MCP resources ainl://strict-authoring-cheatsheet and ainl://strict-valid-examples.",
            "Use ainl_validate(strict=true) after every small edit; compile before run when side effects matter.",
        ],
        "planner_and_host_follow_ups": _planner_and_host_follow_ups(task_type, subtypes, adapters),
        "why_this_matters": (
            "Compiler-valid AINL is not the same as runnable AINL on an MCP host: `ainl_run` must opt in "
            "to http/fs/cache/sqlite/a2a with explicit adapter configuration."
        ),
        "syntax_corrections": syntax_corrections,
        "strict_valid_example_index": strict_idx,
        "intent_operation_guide": intent_guide,
        "required_before_authoring": [] if can_author_now else missing,
        "adapter_contracts_needed": adapters,
        "strict_example_family": strict_examples,
        "runtime_readiness_needed": readiness,
        "clarifying_questions": _clarifying_questions(subtypes),
        "next_tool_call": next_tool_call,
        "copy_paste_next_call": next_tool_call,
        "recommended_resources": _strict_resources(strict_examples),
        "authoring_status": {
            "can_write_first_line": True,
            "first_line": first_line,
            "can_write_full_workflow": can_author_now,
            "reason": (
                "A complete core-only starter scaffold is available."
                if can_author_now
                else "The graph header and core intent are known, but adapter-specific lines depend on contracts."
            ),
        },
        "agent_authoring_policy": {
            "adapter_specific_source_allowed": can_author_now or not adapters,
            "first_line_allowed": True,
            "must_not_do": (
                []
                if can_author_now or not adapters
                else [
                    "Do not write adapter-specific AINL lines yet.",
                    "Do not remove requested side effects just to pass validation.",
                    "Do not claim success until validate/compile/run and side-effect checks prove it.",
                ]
            ),
            "required_proof_before_final": [
                "ainl_validate strict result",
                "ainl_compile required_adapters/runtime readiness",
                "ainl_run result when execution was requested",
                "side-effect verification for files, logs, messages, replies, or external writes",
            ],
        },
        "corpus_grounding": {
            "source": "examples/ and intelligence/ reverse-engineered human goals; demo/ is negative/experimental signal unless profiled strict-valid.",
            "reverse_engineering_patterns": reverse_engineering_patterns(),
            "intent_buckets": corpus_intent_buckets(),
        },
    }
    if can_author_now and not adapters:
        out["starter_scaffold"] = {"code": f"{first_line}\n  out \"Hello from AINL\"\n"}
    if partial_scaffold:
        out["partial_scaffold"] = partial_scaffold
        out["incremental_authoring"] = {
            "rule": "Do not generate the whole workflow at once; validate each slice before adding the next.",
            "stages": ["header_and_inputs", "adapter_access", "form_submission", "extraction", "csv_build", "output_write", "summary_return"],
        }
    if wizard_stage == "contract_resolution":
        out["contract_resolution"] = {
            "capabilities_seen": True,
            "still_needed": [m for m in missing if m.startswith("adapter_contract:")],
            "next_contract_call": next_contract_call,
            "decision": "Load contracts, then choose HTTP for plain request/response pages or browser for JavaScript/session/click workflows.",
        }
    if wizard_stage == "incremental_authoring":
        out["runtime_readiness_stage"] = {
            "after_compile": [
                "Read required_adapters and frame_hints from ainl_compile.",
                "Use suggested adapters payloads for ainl_run.",
                "Set host allowlists, fs.root, browser availability, and provider env before run.",
            ],
            "after_run": [
                "Verify promised side effects such as CSV/log files/replies.",
                "Final answer must state what was validated, compiled, run, and verified.",
            ],
        }
    if detail == "brief":
        return {
            key: out[key]
            for key in (
                "ok",
                "goal",
                "wizard_stage",
                "inferred_task_type",
                "confidence",
                "wizard_state",
                "intent_operation_guide",
                "next_tool_call",
                "authoring_status",
                "quick_start",
                "planner_and_host_follow_ups",
                "why_this_matters",
                "ordered_checklist",
                "syntax_corrections",
                "strict_valid_example_index",
            )
        }
    return out


def extract_adapters(source: str) -> List[str]:
    """Best-effort adapter extraction from compact/opcode AINL-like text."""
    adapters: List[str] = []
    for match in re.finditer(r"\b(?:R\s+)?([A-Za-z_][A-Za-z0-9_]*)\.[A-Za-z_][A-Za-z0-9_]*", source):
        adapters.append(match.group(1))
    return _dedupe(adapters)


def _workflow_family(path: str, lowered: str, adapters: Sequence[str]) -> str:
    hay = _normalize(f"{path} {lowered} {' '.join(adapters)}")
    if "solana" in hay:
        return "blockchain_monitoring"
    for row in CORPUS_INTENT_BUCKETS:
        if any(term in hay for term in row["terms"]):
            return str(row["bucket"])
    if "http" in adapters:
        return "external_api"
    if not adapters or adapters == ["core"]:
        return "core_workflow"
    return "adapter_workflow"


def _human_goals_from_corpus(path: str, lowered: str, adapters: Sequence[str], comments: Sequence[str]) -> List[str]:
    goals: List[str] = []
    family = _workflow_family(path, lowered, adapters)
    bucket_goal = next((str(row["human_goal"]) for row in CORPUS_INTENT_BUCKETS if row["bucket"] == family), None)
    if bucket_goal:
        goals.append(bucket_goal)
    if "scrape" in lowered or "scraper" in lowered:
        goals.append("I need a scraper that visits a site, gathers the results I care about, and saves them somewhere useful.")
    if "solana" in lowered or "get_balance" in lowered:
        goals.append("Can you make me a little monitor that checks this Solana wallet and tells me if the balance drops under my budget?")
    if "lead" in lowered and ("crm" in lowered or "router" in lowered):
        goals.append("I want a lead workflow that figures out which leads are hot, routes them to sales, and keeps an audit trail.")
    if "daily" in lowered and "digest" in lowered:
        goals.append("Make me a daily digest that pulls the important stuff together so I can skim it quickly.")
    if "watchdog" in lowered or "health" in lowered:
        goals.append("Build me a watchdog that checks whether the system is healthy and tells me when something needs attention.")
    if "http" in adapters or "http.get" in lowered:
        goals.append("Build a workflow that calls an HTTP endpoint, reads the response, and returns the part I need.")
    if "browser" in adapters:
        goals.append("Build a workflow that opens a browser page, interacts with it if needed, reads the page, and returns the result.")
    if "fs" in adapters or any(x in lowered for x in ("csv", "jsonl", "write", "log")):
        goals.append("Have it save a local file or log so I can verify what happened after the run.")
    if not goals and comments:
        goals.append(f"Can you turn this into an AINL workflow for me: {comments[0]}")
    if not goals:
        goals.append(f"Can you build me an AINL workflow like `{Path(path).name}`?")
    return _dedupe(goals)


def _pitfalls_for_fixture(path: str, status: str, adapters: Sequence[str], lowered: str) -> List[str]:
    pitfalls: List[str] = []
    if status != "strict-valid":
        pitfalls.append("Do not recommend this file as a starter template unless it is repaired and strict-valid.")
    if "demo/" in path.replace("\\", "/"):
        pitfalls.append("demo/ files are experimental or negative signal by default.")
    if "http" in adapters:
        pitfalls.append("ainl_run must register http with allow_hosts for every target host.")
    if "fs" in adapters:
        pitfalls.append("ainl_run must register fs with a sandbox root and allowed output extensions.")
    if "browser" in adapters:
        pitfalls.append("Browser workflows require ArmaraOS browser runtime availability and site-specific selectors.")
    if "llm" in adapters or "llm" in lowered:
        pitfalls.append("LLM verbs/provider config must be discovered; do not invent llm.GENERATE-style syntax.")
    if "{" in lowered and "}" in lowered:
        pitfalls.append("Inline JSON-looking literals may tokenize as raw slots; strict authoring should build/pass structured data safely.")
    return _dedupe(pitfalls)


def reverse_engineer_source(
    source: str,
    *,
    source_file: Optional[str] = None,
    profile: Optional[str] = None,
) -> Dict[str, Any]:
    """Reverse-engineer a program into human-like goals and classifier fixtures."""
    path = source_file or "<inline>"
    adapters = extract_adapters(source)
    comments = [
        line.lstrip("# ").strip()
        for line in source.splitlines()
        if line.strip().startswith("#") and line.lstrip("# ").strip()
    ]
    lowered = _normalize("\n".join([path, source, *comments]))
    status = profile or template_status_for_path(path)
    goals = _human_goals_from_corpus(path, lowered, adapters, comments)

    classifier_goal = " ".join(goals)
    expected = get_started(classifier_goal)
    return {
        "source_file": path,
        "profile": status,
        "recommended_template_status": status,
        "workflow_family": _workflow_family(path, lowered, adapters),
        "detected_adapters": adapters,
        "required_contracts": _blocking_contracts([a for a in adapters if a != "core"]),
        "reconstruction_patterns": reverse_engineering_patterns(),
        "reconstructed_user_goals": _dedupe(goals),
        "pitfalls": _pitfalls_for_fixture(path, status, adapters, lowered),
        "expected_classifier": {
            "inferred_task_type": expected["inferred_task_type"],
            "subtypes": expected["subtypes"],
            "adapter_contracts_needed": expected["adapter_contracts_needed"],
            "strict_example_family": expected["strict_example_family"],
        },
    }


def reverse_engineer_corpus(
    paths: Sequence[Path],
    *,
    repo_root: Optional[Path] = None,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """Scan AINL/lang files into reverse-prompt fixtures for classifier evals."""
    root = repo_root or Path(__file__).resolve().parent.parent
    profiles = load_artifact_profiles(root)
    fixtures: List[Dict[str, Any]] = []
    for path in paths[: limit or None]:
        try:
            source = path.read_text(encoding="utf-8")
        except OSError:
            continue
        try:
            rel = str(path.resolve().relative_to(root.resolve()))
        except Exception:
            rel = str(path)
        status = template_status_for_path(rel, profiles)
        fixtures.append(reverse_engineer_source(source, source_file=rel, profile=status))
    return {
        "ok": True,
        "schema": {
            "source_file": "repo-relative path",
            "reconstructed_user_goals": "human-natural prompts that could have produced the program",
            "workflow_family": "corpus-derived intent bucket",
            "detected_adapters": "adapter prefixes seen in source",
            "required_contracts": "adapter contracts the wizard must load",
            "recommended_template_status": "strict-valid | non-strict-only | legacy-compat | experimental_or_negative_signal | unknown",
            "pitfalls": "authoring/runtime cautions inferred from syntax and profile",
            "expected_classifier": "assertions for ainl_get_started evals",
        },
        "patterns": reverse_engineering_patterns(),
        "intent_buckets": corpus_intent_buckets(),
        "fixtures": fixtures,
    }


def step_examples(
    *,
    current_step: str,
    request_examples_for: Optional[str] = None,
    example_count: int = 3,
) -> Dict[str, Any]:
    """Return examples for the current wizard step without advancing state."""
    topic = (request_examples_for or current_step or "").lower()
    examples: List[Dict[str, Any]]
    if "fs" in topic or "csv" in topic or "output" in topic:
        examples = [
            {
                "when_you_need_to": "write CSV text to an output path",
                "code": "written = fs.WRITE output_path csv",
                "requires": ["adapter_contract:fs"],
            },
            {
                "when_you_need_to": "build a CSV header",
                "code": 'csv_header = "name,phone,address,parcel_number,date\\n"',
                "requires": [],
            },
            {
                "when_you_need_to": "combine header and rows",
                "code": "csv = core.CONCAT csv_header rows",
                "requires": [],
            },
        ]
    elif "browser" in topic:
        examples = [
            {
                "when_you_need_to": "open a page",
                "code": "session = browser.NAVIGATE target_url",
                "requires": ["adapter_contract:browser"],
            },
            {
                "when_you_need_to": "wait for a selector",
                "code": 'visible = browser.WAIT "form" 5000',
                "requires": ["adapter_contract:browser"],
            },
        ]
    else:
        examples = [
            {
                "when_you_need_to": "start a workflow",
                "code": "workflow_name:",
                "requires": [],
            },
            {
                "when_you_need_to": "return a value",
                "code": "out result",
                "requires": [],
            },
        ]
    return {
        "wizard_stage": "incremental_authoring",
        "current_step": current_step,
        "step_status": "examples_only",
        "examples": examples[: max(1, int(example_count or 3))],
    }
