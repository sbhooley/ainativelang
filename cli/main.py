#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import ast
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from compiler_v2 import AICodeCompiler
from runtime.adapters.base import AdapterRegistry, RuntimeAdapter
from runtime.adapters.executor_bridge import ExecutorBridgeAdapter
from runtime.adapters.fs import SandboxedFileSystemAdapter
from runtime.adapters.http import SimpleHttpAdapter
from runtime.adapters.replay import RecordingAdapterRegistry, ReplayAdapterRegistry
from runtime.adapters.sqlite import SimpleSqliteAdapter
from runtime.adapters.tools import ToolBridgeAdapter
from runtime.adapters.wasm import WasmAdapter
from runtime.adapters.memory import MemoryAdapter
from runtime.sandbox_shim import SandboxClient
from runtime.engine import RuntimeEngine


def _parse_bridge_endpoints(items: List[str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for raw in items or []:
        if "=" not in raw:
            raise SystemExit(f"--bridge-endpoint must be NAME=URL, got {raw!r}")
        k, v = raw.split("=", 1)
        k, v = k.strip(), v.strip()
        if not k or not v:
            raise SystemExit(f"invalid --bridge-endpoint: {raw!r}")
        out[k] = v
    return out


def _limits_from_args(args: argparse.Namespace) -> dict:
    out = {}
    for k in ("max_steps", "max_depth", "max_adapter_calls", "max_time_ms", "max_frame_bytes", "max_loop_iters"):
        v = getattr(args, k, None)
        if v is not None:
            out[k] = v
    return out


def _adapter_registry_from_args(args: argparse.Namespace):
    if args.record_adapters and args.replay_adapters:
        raise SystemExit("--record-adapters and --replay-adapters are mutually exclusive")
    allowed = [
        "core",
        "ext",
        "http",
        "bridge",
        "sqlite",
        "postgres",
        "mysql",
        "redis",
        "dynamodb",
        "airtable",
        "supabase",
        "fs",
        "tools",
        "db",
        "api",
        "cache",
        "queue",
        "txn",
        "auth",
        "wasm",
        "memory",
        "vector_memory",
        "embedding_memory",
        "tool_registry",
        "langchain_tool",
    ]
    if args.replay_adapters:
        data = json.loads(Path(args.replay_adapters).read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise SystemExit("--replay-adapters must point to a JSON array call log")
        return ReplayAdapterRegistry(data, allowed=allowed)
    if args.record_adapters:
        return RecordingAdapterRegistry(allowed=allowed)
    return AdapterRegistry(allowed=allowed)


class _EchoAdapter(RuntimeAdapter):
    def call(self, target, args, context):
        return args[0] if args else target


class _InMemoryDbAdapter(RuntimeAdapter):
    def __init__(self):
        self.rows: Dict[str, List[Dict[str, Any]]] = {}
        self.seq = 0

    def call(self, target, args, context):
        verb = str(target or "").upper()
        entity = str(args[0]) if len(args) > 0 else "Entity"
        payload = args[1] if len(args) > 1 else None
        rows = self.rows.setdefault(entity, [])
        if verb == "F":
            return list(rows)
        if verb == "G":
            if payload is None:
                return rows[0] if rows else None
            for row in rows:
                if row.get("id") == payload:
                    return row
            return None
        if verb in {"C", "P"}:
            self.seq += 1
            row = {"id": self.seq}
            if isinstance(payload, dict):
                row.update(payload)
            rows.append(row)
            return row
        if verb == "U":
            if rows and isinstance(payload, dict):
                rows[0].update(payload)
                return rows[0]
            return rows[0] if rows else None
        if verb == "D":
            if not rows:
                return False
            if payload is None:
                rows.pop(0)
                return True
            for i, row in enumerate(rows):
                if row.get("id") == payload:
                    rows.pop(i)
                    return True
            return False
        return []


class _NullApiAdapter(RuntimeAdapter):
    def call(self, target, args, context):
        verb = str(target or "").upper()
        path = str(args[0]) if args else "/"
        body = args[1] if len(args) > 1 else None
        if verb in {"G", "GET"}:
            return {"ok": True, "method": "GET", "path": path, "data": []}
        if verb in {"P", "POST"}:
            return {"ok": True, "method": "POST", "path": path, "body": body}
        return {"ok": True, "method": verb or "GET", "path": path}


def _register_enabled_adapters(reg: AdapterRegistry, args: argparse.Namespace) -> None:
    enabled = set(args.enable_adapter or [])
    env_enable_ptc = str(os.environ.get("AINL_ENABLE_PTC", "")).strip().lower() in {"1", "true", "yes", "on"}
    if "ext" in enabled:
        reg.register("ext", _EchoAdapter())
    if "http" in enabled:
        reg.register(
            "http",
            SimpleHttpAdapter(
                default_timeout_s=args.http_timeout_s,
                max_response_bytes=args.http_max_response_bytes,
                allow_hosts=args.http_allow_host or [],
            ),
        )
    if "bridge" in enabled:
        endpoints = _parse_bridge_endpoints(getattr(args, "bridge_endpoint", None) or [])
        if not endpoints:
            raise SystemExit("--enable-adapter bridge requires at least one --bridge-endpoint NAME=URL")
        reg.register(
            "bridge",
            ExecutorBridgeAdapter(
                endpoints=endpoints,
                default_timeout_s=args.http_timeout_s,
                max_response_bytes=args.http_max_response_bytes,
                allow_hosts=args.http_allow_host or [],
            ),
        )
    if "sqlite" in enabled:
        db = args.sqlite_db or ":memory:"
        reg.register(
            "sqlite",
            SimpleSqliteAdapter(
                db_path=db,
                allow_write=bool(args.sqlite_allow_write),
                allow_tables=args.sqlite_allow_table or [],
                timeout_s=args.sqlite_timeout_s,
            ),
        )
    if "postgres" in enabled:
        from adapters.postgres import PostgresAdapter

        reg.register(
            "postgres",
            PostgresAdapter(
                dsn=args.postgres_url or None,
                host=args.postgres_host or None,
                port=args.postgres_port,
                database=args.postgres_db or None,
                user=args.postgres_user or None,
                password=args.postgres_password if args.postgres_password else None,
                sslmode=args.postgres_sslmode or None,
                sslrootcert=args.postgres_sslrootcert or None,
                timeout_s=args.postgres_timeout_s,
                statement_timeout_ms=args.postgres_statement_timeout_ms,
                allow_write=bool(args.postgres_allow_write),
                allow_tables=args.postgres_allow_table or [],
                pool_min_size=args.postgres_pool_min,
                pool_max_size=args.postgres_pool_max,
            ),
        )
    if "mysql" in enabled:
        from adapters.mysql import MySQLAdapter

        reg.register(
            "mysql",
            MySQLAdapter(
                dsn=args.mysql_url or None,
                host=args.mysql_host or None,
                port=args.mysql_port,
                database=args.mysql_db or None,
                user=args.mysql_user or None,
                password=args.mysql_password if args.mysql_password else None,
                ssl_mode=args.mysql_ssl_mode or None,
                ssl_ca=args.mysql_ssl_ca or None,
                timeout_s=args.mysql_timeout_s,
                allow_write=bool(args.mysql_allow_write),
                allow_tables=args.mysql_allow_table or [],
                pool_min_size=args.mysql_pool_min,
                pool_max_size=args.mysql_pool_max,
            ),
        )
    if "redis" in enabled:
        from adapters.redis import RedisAdapter

        reg.register(
            "redis",
            RedisAdapter(
                url=args.redis_url or None,
                host=args.redis_host or None,
                port=args.redis_port,
                db=args.redis_db,
                username=args.redis_user or None,
                password=args.redis_password if args.redis_password else None,
                ssl=bool(args.redis_ssl),
                timeout_s=args.redis_timeout_s,
                allow_write=bool(args.redis_allow_write),
                allow_prefixes=args.redis_allow_prefix or [],
            ),
        )
    if "dynamodb" in enabled:
        from adapters.dynamodb import DynamoDBAdapter

        reg.register(
            "dynamodb",
            DynamoDBAdapter(
                url=args.dynamodb_url or None,
                region=args.dynamodb_region or None,
                timeout_s=args.dynamodb_timeout_s,
                allow_write=bool(args.dynamodb_allow_write),
                allow_tables=args.dynamodb_allow_table or [],
                consistent_read=bool(args.dynamodb_consistent_read),
            ),
        )
    if "airtable" in enabled:
        from adapters.airtable import AirtableAdapter

        reg.register(
            "airtable",
            AirtableAdapter(
                api_key=args.airtable_api_key or None,
                base_id=args.airtable_base_id or None,
                timeout_s=args.airtable_timeout_s,
                allow_write=bool(args.airtable_allow_write),
                allow_tables=args.airtable_allow_table or [],
                allow_attachment_hosts=args.airtable_allow_attachment_host or [],
                max_page_size=args.airtable_max_page_size,
            ),
        )
    if "supabase" in enabled:
        from adapters.supabase import SupabaseAdapter

        reg.register(
            "supabase",
            SupabaseAdapter(
                db_url=args.supabase_db_url or None,
                supabase_url=args.supabase_url or None,
                anon_key=args.supabase_anon_key or None,
                service_role_key=args.supabase_service_role_key or None,
                timeout_s=args.supabase_timeout_s,
                allow_write=bool(args.supabase_allow_write),
                allow_tables=args.supabase_allow_table or [],
                allow_buckets=args.supabase_allow_bucket or [],
                allow_channels=args.supabase_allow_channel or [],
            ),
        )
    if "fs" in enabled:
        if not args.fs_root:
            raise SystemExit("--fs-root is required when --enable-adapter fs is used")
        reg.register(
            "fs",
            SandboxedFileSystemAdapter(
                sandbox_root=args.fs_root,
                max_read_bytes=args.fs_max_read_bytes,
                max_write_bytes=args.fs_max_write_bytes,
                allow_extensions=args.fs_allow_ext or [],
                allow_delete=bool(args.fs_allow_delete),
            ),
        )
    if "tools" in enabled:
        tools = {
            "echo": lambda *a, context=None: a[0] if a else None,
            "sum": lambda a, b, context=None: int(a) + int(b),
            "join": lambda sep, arr, context=None: str(sep).join([str(x) for x in (arr or [])]),
        }
        reg.register("tools", ToolBridgeAdapter(tools, allow_tools=args.tools_allow or tools.keys()))
    if "db" in enabled:
        reg.register("db", _InMemoryDbAdapter())
    if "api" in enabled:
        reg.register("api", _NullApiAdapter())
        if "wasm" in enabled:
            modules: Dict[str, str] = {}
            for raw in (getattr(args, "wasm_module", None) or []):
                if "=" not in raw:
                    raise SystemExit("--wasm-module entries must be name=path")
                name, path = raw.split("=", 1)
                name = name.strip()
                path = path.strip()
                if not name or not path:
                    raise SystemExit("--wasm-module entries must be name=path")
                modules[name] = path
            if not modules:
                raise SystemExit("--enable-adapter wasm requires at least one --wasm-module name=path")
            reg.register("wasm", WasmAdapter(modules=modules, allowed_modules=(getattr(args, "wasm_allow_module", None) or None)))
    # Always register memory (used by record_decision includes)
    mem_db = (
        str(getattr(args, "memory_db", "") or "").strip()
        or os.environ.get("AINL_MEMORY_DB")
        or str(Path.home() / ".openclaw" / "ainl_memory.sqlite3")
    )
    reg.register("memory", MemoryAdapter(db_path=mem_db))
    if "vector_memory" in enabled:
        from adapters.vector_memory import VectorMemoryAdapter

        reg.register("vector_memory", VectorMemoryAdapter())
    if "embedding_memory" in enabled:
        from adapters.embedding_memory import EmbeddingMemoryAdapter

        reg.register("embedding_memory", EmbeddingMemoryAdapter())
    if "tool_registry" in enabled:
        from adapters.tool_registry import ToolRegistryAdapter

        reg.register("tool_registry", ToolRegistryAdapter())
    if "langchain_tool" in enabled:
        from adapters.langchain_tool import LangchainToolAdapter

        reg.register("langchain_tool", LangchainToolAdapter())
    if "ptc_runner" in enabled or env_enable_ptc:
        from adapters.ptc_runner import PtcRunnerAdapter

        reg.register(
            "ptc_runner",
            PtcRunnerAdapter(
                enabled=True,
                allow_hosts=args.http_allow_host or [],
                timeout_s=args.http_timeout_s,
                max_response_bytes=args.http_max_response_bytes,
            ),
        )
    if "llm_query" in enabled or str(os.environ.get("AINL_ENABLE_LLM_QUERY", "")).strip().lower() in {"1", "true", "yes", "on"}:
        from adapters.llm_query import LlmQueryAdapter

        reg.register(
            "llm_query",
            LlmQueryAdapter(
                enabled=True,
                allow_hosts=args.http_allow_host or [],
                timeout_s=args.http_timeout_s,
                max_response_bytes=args.http_max_response_bytes,
            ),
        )


def _pretty_runtime_error(err: Exception) -> str:
    msg = str(err)
    m = re.search(r"\[line=(\d+)\s+source=(.+?)\]", msg)
    if not m:
        return msg
    line_no = m.group(1)
    raw_src = m.group(2)
    try:
        src = ast.literal_eval(raw_src)
    except Exception:
        src = raw_src.strip("'")
    caret_col = 0
    while caret_col < len(src) and src[caret_col] in (" ", "\t"):
        caret_col += 1
    caret = " " * caret_col + "^"
    return f"{msg}\n  line {line_no}: {src}\n           {caret}"


def cmd_run_hybrid_ptc(args: argparse.Namespace) -> int:
    """Thin wrapper that runs examples/hybrid_order_processor.ainl with sensible defaults."""
    if not args.no_mock and not os.environ.get("AINL_PTC_RUNNER_MOCK"):
        os.environ["AINL_PTC_RUNNER_MOCK"] = "1"

    print("Running hybrid PTC order processor example...")
    print("  source: examples/hybrid_order_processor.ainl")
    print(f"  trace:  {args.trace_jsonl}")
    print("  mock:  ", "yes" if os.environ.get("AINL_PTC_RUNNER_MOCK") else "no (live)")
    print()
    print("Next steps:")
    print("  Export PTC JSONL:     PYTHONPATH=. python3 scripts/ainl_trace_viewer.py --ptc-export")
    print("  LangGraph bridge:     PYTHONPATH=. python3 scripts/run_intelligence.py ptc_to_langgraph_bridge")
    print()

    # Build a namespace that cmd_run accepts, re-using all existing defaults.
    run_args = argparse.Namespace(
        file="examples/hybrid_order_processor.ainl",
        label="",
        strict=False,
        strict_reachability=False,
        trace=False,
        log_trajectory=False,
        trace_jsonl=args.trace_jsonl,
        json=False,
        no_step_fallback=False,
        execution_mode="graph-preferred",
        unknown_op_policy=None,
        runtime_async=False,
        trace_out="",
        record_adapters="",
        replay_adapters="",
        enable_adapter=["ptc_runner"],
        bridge_endpoint=[],
        http_allow_host=["localhost"],
        http_timeout_s=5.0,
        http_max_response_bytes=1_000_000,
        sqlite_db="",
        sqlite_allow_write=False,
        sqlite_allow_table=[],
        sqlite_timeout_s=5.0,
        fs_root="",
        fs_max_read_bytes=1_000_000,
        fs_max_write_bytes=1_000_000,
        fs_allow_ext=[],
        fs_allow_delete=False,
        tools_allow=[],
        wasm_module=[],
        wasm_allow_module=[],
        memory_db="",
        max_steps=None,
        max_depth=None,
        max_adapter_calls=None,
        max_time_ms=None,
        max_frame_bytes=None,
        max_loop_iters=None,
        self_test_graph=False,
    )
    return cmd_run(run_args)


def cmd_run(args: argparse.Namespace) -> int:
    if args.self_test_graph:
        return cmd_self_test_graph(args)
    if not args.file:
        raise SystemExit("run requires <file> unless --self-test-graph is set")
    src_path = str(Path(args.file).resolve())
    with open(src_path, "r", encoding="utf-8") as f:
        code = f.read()
    reg = _adapter_registry_from_args(args)
    _register_enabled_adapters(reg, args)
    env_traj = os.environ.get("AINL_LOG_TRAJECTORY", "").strip().lower()
    trajectory_path: Optional[str] = None
    if getattr(args, "trace_jsonl", ""):
        raw = str(args.trace_jsonl).strip()
        trajectory_path = "/dev/stdout" if raw == "-" else str(Path(raw).expanduser())
    elif getattr(args, "log_trajectory", False) or env_traj in ("1", "true", "yes", "on"):
        trajectory_path = str(Path(src_path).parent / (Path(src_path).stem + ".trajectory.jsonl"))
    sandbox_client = SandboxClient.try_connect(logger=lambda msg: print(msg))
    eng = RuntimeEngine.from_code(
        code,
        strict=args.strict,
        strict_reachability=getattr(args, "strict_reachability", False),
        trace=args.trace,
        step_fallback=not args.no_step_fallback,
        execution_mode=args.execution_mode,
        unknown_op_policy=args.unknown_op_policy,
        limits=_limits_from_args(args),
        adapters=reg,
        source_path=src_path,
        trajectory_log_path=trajectory_path,
        avm_event_hasher=sandbox_client.event_hash if sandbox_client.connected else None,
        sandbox_metadata_provider=sandbox_client.trajectory_metadata if sandbox_client.connected else None,
        runtime_async=bool(getattr(args, "runtime_async", False)),
    )
    label = args.label or eng.default_entry_label()
    try:
        if getattr(eng, "runtime_async", False):
            result = asyncio.run(eng.run_label_async(label, frame={}))
        else:
            result = eng.run_label(label, frame={})
        payload = {"ok": True, "label": str(label), "result": result, "runtime_version": eng.runtime_version}
    except Exception as e:
        payload = {"ok": False, "label": str(label), "error": str(e), "runtime_version": eng.runtime_version}
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(_pretty_runtime_error(e))
        return 1
    if args.trace:
        payload["trace"] = eng.trace_events
        if args.trace_out:
            Path(args.trace_out).write_text(json.dumps(eng.trace_events, indent=2), encoding="utf-8")
    if reg is not None and args.record_adapters:
        Path(args.record_adapters).write_text(json.dumps(getattr(reg, "call_log", []), indent=2), encoding="utf-8")
        payload["adapter_calls_recorded"] = len(getattr(reg, "call_log", []))
    if reg is not None and args.replay_adapters:
        payload["adapter_calls_replayed"] = len(getattr(reg, "call_log", []))
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(payload)
    return 0


def cmd_self_test_graph(args: argparse.Namespace) -> int:
    tests = [
        {
            "name": "graph_add",
            "code": "L1: R core.add 2 3 ->x J x\n",
            "expect": 5,
            "should_error": False,
        },
        {
            "name": "graph_if_call",
            "code": "L1: Set cond true If cond ->L2 ->L3\nL2: Call L9 J _call_result\nL3: Set bad nope J bad\nL9: R core.add 20 22 ->v J v\n",
            "expect": 42,
            "should_error": False,
        },
        {
            "name": "graph_while_guard",
            "code": "L1: Set cond true While cond ->L2 ->L3\nL2: J keep_going\nL3: J done\n",
            "expect_contains": "while loop iteration limit exceeded",
            "should_error": True,
        },
    ]

    results = []
    all_ok = True
    for t in tests:
        item = {"name": t["name"], "ok": False}
        try:
            eng = RuntimeEngine.from_code(
                t["code"],
                strict=True,
                trace=False,
                step_fallback=False,
                execution_mode="graph-only",
            )
            out = eng.run_label("1")
            if t["should_error"]:
                item["ok"] = False
                item["error"] = f"expected error, got result={out!r}"
                all_ok = False
            else:
                item["ok"] = out == t["expect"]
                item["result"] = out
                if not item["ok"]:
                    item["error"] = f"expected {t['expect']!r}, got {out!r}"
                    all_ok = False
        except Exception as e:
            if t["should_error"]:
                msg = str(e)
                want = t.get("expect_contains", "")
                item["ok"] = want in msg if want else True
                item["error"] = msg
                if not item["ok"]:
                    all_ok = False
            else:
                item["ok"] = False
                item["error"] = str(e)
                all_ok = False
        results.append(item)

    payload = {"ok": all_ok, "mode": "graph_only", "tests": results}
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(payload)
    return 0 if all_ok else 1


def cmd_check(args: argparse.Namespace) -> int:
    src_path = str(Path(args.file).resolve())
    with open(src_path, "r", encoding="utf-8") as f:
        code = f.read()
    c = AICodeCompiler(strict_mode=args.strict)
    ir = c.compile(code, emit_graph=True, source_path=src_path)
    ok = len(ir.get("errors", [])) == 0
    diagnostics = list(ir.get("diagnostics") or [])
    if not diagnostics:
        src_lines = (ir.get("source") or {}).get("lines", [])
        for e in ir.get("errors", []):
            m = re.search(r"Line\s+(\d+)", str(e))
            if not m:
                continue
            ln = int(m.group(1))
            line = src_lines[ln - 1] if 0 <= ln - 1 < len(src_lines) else ""
            diagnostics.append({"line": ln, "source": line, "error": e})
    payload = {
        "ok": ok,
        "ir_version": ir.get("ir_version"),
        "errors": ir.get("errors", []),
        "warnings": ir.get("warnings", []),
        "meta": ir.get("meta", []),
        "diagnostics": diagnostics,
    }
    print(json.dumps(payload, indent=2))
    return 0 if ok else 1


def cmd_inspect(args: argparse.Namespace) -> int:
    src_path = str(Path(args.file).resolve())
    with open(src_path, "r", encoding="utf-8") as f:
        code = f.read()
    c = AICodeCompiler(strict_mode=bool(getattr(args, "strict", False)))
    ir = c.compile(code, emit_graph=True, source_path=src_path)
    print(json.dumps(ir, indent=2))
    return 0 if not ir.get("errors") else 1


def cmd_generate_avm_policy(args: argparse.Namespace) -> int:
    src_path = str(Path(args.file).resolve())
    with open(src_path, "r", encoding="utf-8") as f:
        code = f.read()
    ir = AICodeCompiler(strict_mode=bool(getattr(args, "strict", False))).compile(code, emit_graph=True, source_path=src_path)
    if ir.get("errors"):
        print(json.dumps({"ok": False, "errors": ir.get("errors", [])}, indent=2))
        return 1
    fragment = ir.get("avm_policy_fragment") or {"allowed_adapters": ["core"], "capability_policy_names": []}
    print(f"# Generated AVM policy fragment from {Path(src_path).name}")
    print("# Paste or merge this object into ~/.hyperspace/avm-policy.json")
    if args.output:
        Path(args.output).write_text(json.dumps(fragment, indent=2), encoding="utf-8")
        print(f"# Wrote JSON fragment to {args.output}")
    print(json.dumps(fragment, indent=2))
    return 0


def cmd_generate_sandbox_config(args: argparse.Namespace) -> int:
    src_path = str(Path(args.file).resolve())
    with open(src_path, "r", encoding="utf-8") as f:
        code = f.read()
    ir = AICodeCompiler(strict_mode=bool(getattr(args, "strict", False))).compile(code, emit_graph=True, source_path=src_path)
    if ir.get("errors"):
        print(json.dumps({"ok": False, "errors": ir.get("errors", [])}, indent=2))
        return 1
    req = ir.get("execution_requirements") or {}
    avm_fragment = req.get("avm_policy_fragment") or ir.get("avm_policy_fragment") or {}
    target = str(args.target or "general")
    out: Dict[str, Any] = {
        "target": target,
        "execution_requirements": req,
        "avm_policy_fragment": avm_fragment,
        # Tiny, neutral sandbox hints for non-AVM runtimes.
        "sandbox_hints": {
            "isolation_level": req.get("isolation_level", "none"),
            "required_capabilities": req.get("required_capabilities", []),
            "ephemeral": req.get("ephemeral", True),
        },
    }
    print(f"# Generated sandbox config from {Path(src_path).name} (target={target})")
    print("# Paste/merge into your AVM policy, microVM wrapper, or sandbox runtime config.")
    if args.output:
        Path(args.output).write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(f"# Wrote JSON config to {args.output}")
    print(json.dumps(out, indent=2))
    return 0


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def cmd_import_markdown(args: argparse.Namespace) -> int:
    """Fetch Markdown and write compiling .ainl (parsed graph when possible, else Phase-1 stub)."""
    import sys

    root = _repo_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from tooling.markdown_importer import import_markdown_to_ainl

    openclaw = not bool(getattr(args, "no_openclaw_bridge", False))
    gen_soul = bool(getattr(args, "generate_soul", False))
    if gen_soul and args.type != "agent":
        print("import markdown: --generate-soul applies only to --type agent", file=sys.stderr)
        return 1
    try:
        ainl, meta = import_markdown_to_ainl(
            args.url_or_path,
            md_type=args.type,
            personality=args.personality or "",
            openclaw_bridge=openclaw,
            generate_soul=gen_soul,
        )
    except Exception as e:
        if args.verbose:
            raise
        print(f"import markdown: {e}", file=sys.stderr)
        return 1

    if args.verbose:
        for k, v in meta.items():
            if k == "sidecars" and v:
                print(f"{k}: SOUL.md + IDENTITY.md", file=sys.stderr)
                continue
            print(f"{k}: {v}", file=sys.stderr)

    if args.dry_run:
        print(ainl, end="")
        return 0

    out = Path(args.output).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(ainl, encoding="utf-8")
    kind = "stub AINL" if meta.get("fallback_stub") else "parsed AINL"
    print(f"Wrote {out} ({meta.get('markdown_chars', 0)} chars markdown → {kind})")
    side = meta.get("sidecars")
    if gen_soul and isinstance(side, dict):
        for fname, text in side.items():
            p = out.parent / fname
            p.write_text(text, encoding="utf-8")
            print(f"Wrote {p}")
    return 0


def _ecosystem_readme_blurb(*, upstream: str, slug: str, parsed: bool) -> str:
    p = "parsed" if parsed else "stub fallback"
    return "\n".join(
        [
            f"# {slug}",
            "",
            f"Upstream: {upstream}",
            "",
            "## Files",
            "",
            "- `original.md` — source Markdown from the ecosystem repo.",
            f"- `converted.ainl` — deterministic AINL graph ({p}).",
            "",
            "## Notes",
            "",
            "This folder is a **deterministic AINL version** of the prose workflow/agent spec — structured graph, explicit cron/steps or gates, and predictable control flow for **100% reliability** at compile/run time (vs free-form Markdown prompts).",
            "",
            "Diff vs upstream: headings and lists become `S core cron`, `Call` steps, `If` gates, and optional `memory` / `queue` bridge hooks instead of narrative instructions only.",
            "",
        ]
    )


def cmd_import_clawflows(args: argparse.Namespace) -> int:
    import sys

    root = _repo_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from tooling.markdown_importer import (
        CLAWFLOWS_SAMPLE_URLS,
        DEFAULT_FETCH_TIMEOUT_S,
        load_markdown_source,
        markdown_to_ainl_from_body,
    )

    base = Path(args.output_dir).expanduser() if args.output_dir else root / "examples" / "ecosystem" / "clawflows"
    openclaw = not bool(getattr(args, "no_openclaw_bridge", False))
    timeout = float(getattr(args, "timeout_s", DEFAULT_FETCH_TIMEOUT_S))
    ok = 0
    for slug, url in CLAWFLOWS_SAMPLE_URLS:
        try:
            _prov, md = load_markdown_source(url, timeout_s=timeout)
        except Exception as e:
            if args.verbose:
                raise
            print(f"import clawflows: skip {slug}: {e}", file=sys.stderr)
            continue
        sub = base / slug
        sub.mkdir(parents=True, exist_ok=True)
        (sub / "original.md").write_text(md, encoding="utf-8")
        ainl, meta = markdown_to_ainl_from_body(
            md,
            provenance=url,
            md_type="workflow",
            openclaw_bridge=openclaw,
        )
        (sub / "converted.ainl").write_text(ainl, encoding="utf-8")
        (sub / "README.md").write_text(
            _ecosystem_readme_blurb(
                upstream=f"[nikilster/clawflows](https://github.com/nikilster/clawflows) `{slug}`",
                slug=slug,
                parsed=bool(meta.get("parsed")),
            ),
            encoding="utf-8",
        )
        ok += 1
        if args.verbose:
            print(f"{slug}: parsed={meta.get('parsed')} stub={meta.get('fallback_stub')}", file=sys.stderr)
    print(f"import clawflows: wrote {ok} workflow(s) under {base}")
    return 0 if ok else 1


def cmd_import_agency_agents(args: argparse.Namespace) -> int:
    import sys

    root = _repo_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from tooling.markdown_importer import (
        AGENCY_AGENTS_SAMPLE_URLS,
        DEFAULT_FETCH_TIMEOUT_S,
        load_markdown_source,
        markdown_to_ainl_from_body,
    )

    base = Path(args.output_dir).expanduser() if args.output_dir else root / "examples" / "ecosystem" / "agency-agents"
    openclaw = not bool(getattr(args, "no_openclaw_bridge", False))
    timeout = float(getattr(args, "timeout_s", DEFAULT_FETCH_TIMEOUT_S))
    ok = 0
    for slug, url in AGENCY_AGENTS_SAMPLE_URLS:
        try:
            _prov, md = load_markdown_source(url, timeout_s=timeout)
        except Exception as e:
            if args.verbose:
                raise
            print(f"import agency-agents: skip {slug}: {e}", file=sys.stderr)
            continue
        sub = base / slug
        sub.mkdir(parents=True, exist_ok=True)
        (sub / "original.md").write_text(md, encoding="utf-8")
        ainl, meta = markdown_to_ainl_from_body(
            md,
            provenance=url,
            md_type="agent",
            personality=getattr(args, "personality", "") or "",
            openclaw_bridge=openclaw,
        )
        (sub / "converted.ainl").write_text(ainl, encoding="utf-8")
        (sub / "README.md").write_text(
            _ecosystem_readme_blurb(
                upstream=f"[msitarzewski/agency-agents](https://github.com/msitarzewski/agency-agents) `{slug}`",
                slug=slug,
                parsed=bool(meta.get("parsed")),
            ),
            encoding="utf-8",
        )
        ok += 1
        if args.verbose:
            print(f"{slug}: parsed={meta.get('parsed')} stub={meta.get('fallback_stub')}", file=sys.stderr)
    print(f"import agency-agents: wrote {ok} agent(s) under {base}")
    return 0 if ok else 1


def cmd_golden(args: argparse.Namespace) -> int:
    examples_dir = Path(args.examples_dir)
    ainl_files = sorted(examples_dir.rglob("*.ainl"))
    if not ainl_files:
        raise SystemExit(f"no .ainl files found in {examples_dir}")
    profile_path = Path(__file__).resolve().parent.parent / "tooling" / "artifact_profiles.json"
    strict_map: Dict[str, bool] = {}
    if profile_path.exists():
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        for rel in profile.get("examples", {}).get("strict-valid", []):
            strict_map[str(rel)] = True
        for rel in profile.get("examples", {}).get("non-strict-only", []):
            strict_map[str(rel)] = False
    results = []
    ok_all = True
    for f in ainl_files:
        expected_path = f.with_suffix(".expected.json")
        if not expected_path.exists():
            continue
        try:
            rel = str(f.resolve().relative_to(Path(__file__).resolve().parent.parent))
        except Exception:
            rel = str(f)
        strict = bool(strict_map.get(rel, False))
        code = f.read_text(encoding="utf-8")
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        payload = RuntimeEngine.run(
            code,
            frame={},
            strict=strict,
            trace=bool(args.trace),
            execution_mode=args.execution_mode,
            unknown_op_policy=args.unknown_op_policy,
            limits={"max_steps": args.max_steps} if args.max_steps else None,
        )
        same = payload.get("ok") == expected.get("ok") and str(payload.get("label")) == str(expected.get("label")) and payload.get(
            "result"
        ) == expected.get("result")
        results.append({"file": f.name, "ok": same, "result": payload.get("result"), "expected": expected.get("result")})
        if not same:
            ok_all = False
    out = {"ok": ok_all, "results": results}
    print(json.dumps(out, indent=2))
    return 0 if ok_all else 1


_INIT_MAIN_AINL = '''\
# {name}/main.ainl
# Generated by `ainl init` — edit freely, then:
#
#   ainl check main.ainl --strict   ← compile + validate strict graph semantics
#   ainl run   main.ainl            ← execute locally
#   ainl visualize main.ainl --output graph.mmd  ← render Mermaid control-flow diagram
#
# ─── AINL syntax cheat-sheet ───────────────────────────────────────────────────
#
#  HEADER LINE (required, once at the top):
#    S <scope> <adapter> <path>
#    e.g. S app core noop
#         ^   ^    ^
#         │   │    └─ route (noop = no external routing)
#         │   └────── adapter family (core, cache, email, http, llm, memory…)
#         └────────── scope name (app, worker, monitor, …)
#
#  LABELS  (L1:, L2:, END, …)
#    Each label is a control-flow node. Execution starts at L1:.
#    Every label must end with exactly one: J, If, or a jump to another label.
#
#  STEPS inside a label:
#    R <adapter>.<op> [args…] -><var>
#       "Request" — call an adapter operation and bind the result.
#       e.g.  R cache get "state" "last_run" ->last_run
#             R core.ADD 2 3 ->sum
#             R email G ->messages
#
#    X <var> <value>
#       "Assign" — set a local variable to a literal or expression.
#       e.g.  X greeting "Hello, world!"
#             X threshold 100
#
#    J <var>
#       "Join" — return the value of <var> and finish this node.
#       The runtime passes the value forward to the next graph stage.
#
#    If (<expr>) -><then-label> -><else-label>
#       "Branch" — conditional jump.
#       e.g.  If (core.gt count 0) ->L3 ->END
#
# ───────────────────────────────────────────────────────────────────────────────
# This starter program shows two patterns: a computation (L1) and a
# simple cache-read → branch flow (L2/L3/L4). Uncomment L2–L4 to try it.

S app core noop

# ── Pattern 1: Simple computation ───────────────────────────────────────────
L1:
  # R core.ADD calls the built-in core adapter's ADD operation.
  # The result is bound to the variable `sum`.
  R core.ADD 2 3 ->sum
  # J returns `sum` to the runtime and finishes this node.
  J sum

# ── Pattern 2: Cache read → branch (uncomment to activate) ──────────────────
# L2:
#   # Read a value from the cache adapter (key-value store).
#   # R cache get "<namespace>" "<key>" -><variable>
#   R cache get "state" "run_count" ->run_count
#   # Branch: if run_count > 0 go to L3, otherwise go to L4.
#   If (core.gt run_count 0) ->L3 ->L4
#
# L3:
#   X msg "Seen before — incrementing."
#   J msg
#
# L4:
#   X msg "First run!"
#   J msg

# END is the implicit terminal. Successful jumps without a target land here.
'''

_INIT_README = '''\
# {name}

Generated by `ainl init`. A minimal AINL worker ready to validate and run.

## 3-minute quickstart

```bash
# 1. Check the program compiles cleanly (strict graph semantics)
ainl check main.ainl --strict

# 2. Run it
ainl run main.ainl

# 3. Visualise the control-flow graph (paste output into https://mermaid.live)
ainl visualize main.ainl --output -

# 4. Inspect the canonical IR (useful for agent loops)
ainl inspect main.ainl --strict
```

## Next steps

- Edit `main.ainl` — add cache reads, HTTP calls, memory ops, or LLM steps.
- Browse `examples/` in the ainativelang repo for real production patterns.
- Read the docs: https://ainativelang.com/docs
- Deep dive: https://ainativelang.com/whitepaper
'''


def cmd_init(args: argparse.Namespace) -> int:
    """Create a new AINL project directory with a starter program and README."""
    import os

    name: str = args.name.strip()
    if not name:
        print("ainl init: project name must not be empty", file=sys.stderr)
        return 1

    target = os.path.join(args.output_dir or ".", name) if args.output_dir else name
    target = os.path.abspath(target)

    if os.path.exists(target):
        if not args.force:
            print(
                f"ainl init: directory already exists: {target}\n"
                "  Use --force to overwrite.",
                file=sys.stderr,
            )
            return 1
    else:
        os.makedirs(target, exist_ok=True)

    main_ainl = os.path.join(target, "main.ainl")
    readme = os.path.join(target, "README.md")

    with open(main_ainl, "w") as fh:
        fh.write(_INIT_MAIN_AINL.format(name=name))
    with open(readme, "w") as fh:
        fh.write(_INIT_README.format(name=name))

    print(f"\n✓  Created AINL project: {target}/")
    print(f"   main.ainl   — starter workflow")
    print(f"   README.md   — quickstart steps")
    print(f"\nNext steps:")
    print(f"   cd {name}")
    print(f"   ainl check main.ainl --strict")
    print(f"   ainl run   main.ainl")
    print(f"   ainl visualize main.ainl --output -")
    print()
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="AINL runtime CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    runp = sub.add_parser("run", help="Run AINL file")
    runp.add_argument("file", nargs="?")
    runp.add_argument("--label", default="")
    runp.add_argument("--strict", action="store_true")
    runp.add_argument("--strict-reachability", action="store_true")
    runp.add_argument("--trace", action="store_true")
    runp.add_argument(
        "--log-trajectory",
        action="store_true",
        help="Append one JSON object per executed step to <stem>.trajectory.jsonl next to the source file; or set AINL_LOG_TRAJECTORY=1.",
    )
    runp.add_argument(
        "--trace-jsonl",
        default="",
        metavar="PATH|-",
        help="Append structured execution trace JSONL to file PATH or '-' for stdout.",
    )
    runp.add_argument("--json", action="store_true")
    runp.add_argument("--no-step-fallback", action="store_true")
    runp.add_argument("--execution-mode", choices=["graph-preferred", "steps-only", "graph-only"], default="graph-preferred")
    runp.add_argument("--unknown-op-policy", choices=["skip", "error"], default=None)
    runp.add_argument(
        "--runtime-async",
        action="store_true",
        help="Enable async-capable adapter dispatch (or set AINL_RUNTIME_ASYNC=1).",
    )
    runp.add_argument("--trace-out", default="")
    runp.add_argument("--record-adapters", default="")
    runp.add_argument("--replay-adapters", default="")
    runp.add_argument(
        "--enable-adapter",
        action="append",
        choices=[
            "http",
            "bridge",
            "sqlite",
            "postgres",
            "mysql",
            "redis",
            "dynamodb",
            "airtable",
            "supabase",
            "fs",
            "tools",
            "ext",
            "db",
            "api",
            "wasm",
            "memory",
            "vector_memory",
            "embedding_memory",
            "tool_registry",
            "langchain_tool",
            "ptc_runner",
            "llm_query",
        ],
        default=[],
    )
    runp.add_argument(
        "--bridge-endpoint",
        action="append",
        default=[],
        metavar="NAME=URL",
        help="With --enable-adapter bridge: map executor key to POST URL (repeatable)",
    )
    runp.add_argument("--http-allow-host", action="append", default=[])
    runp.add_argument(
        "--http-timeout-s",
        type=float,
        default=5.0,
        help="Per-request timeout for http + bridge adapters (seconds). Use 60–120+ for LLM-backed bridge routes.",
    )
    runp.add_argument("--http-max-response-bytes", type=int, default=1_000_000)
    runp.add_argument("--sqlite-db", default="")
    runp.add_argument("--sqlite-allow-write", action="store_true")
    runp.add_argument("--sqlite-allow-table", action="append", default=[])
    runp.add_argument("--sqlite-timeout-s", type=float, default=5.0)
    runp.add_argument("--postgres-url", default="", help="Postgres DSN/URL (or set AINL_POSTGRES_URL)")
    runp.add_argument("--postgres-host", default="")
    runp.add_argument("--postgres-port", type=int, default=5432)
    runp.add_argument("--postgres-db", default="")
    runp.add_argument("--postgres-user", default="")
    runp.add_argument("--postgres-password", default="", help="Prefer env var AINL_POSTGRES_PASSWORD in production")
    runp.add_argument("--postgres-sslmode", default="require")
    runp.add_argument("--postgres-sslrootcert", default="", help="Path to CA root cert PEM for PostgreSQL TLS")
    runp.add_argument("--postgres-timeout-s", type=float, default=5.0)
    runp.add_argument("--postgres-statement-timeout-ms", type=int, default=5000)
    runp.add_argument("--postgres-pool-min", type=int, default=1)
    runp.add_argument("--postgres-pool-max", type=int, default=5)
    runp.add_argument("--postgres-allow-write", action="store_true")
    runp.add_argument("--postgres-allow-table", action="append", default=[])
    runp.add_argument("--mysql-url", default="", help="MySQL DSN/URL (or set AINL_MYSQL_URL)")
    runp.add_argument("--mysql-host", default="")
    runp.add_argument("--mysql-port", type=int, default=3306)
    runp.add_argument("--mysql-db", default="")
    runp.add_argument("--mysql-user", default="")
    runp.add_argument("--mysql-password", default="", help="Prefer env var AINL_MYSQL_PASSWORD in production")
    runp.add_argument("--mysql-ssl-mode", default="REQUIRED")
    runp.add_argument("--mysql-ssl-ca", default="", help="Path to CA root cert PEM for MySQL TLS")
    runp.add_argument("--mysql-timeout-s", type=float, default=5.0)
    runp.add_argument("--mysql-pool-min", type=int, default=1)
    runp.add_argument("--mysql-pool-max", type=int, default=5)
    runp.add_argument("--mysql-allow-write", action="store_true")
    runp.add_argument("--mysql-allow-table", action="append", default=[])
    runp.add_argument("--redis-url", default="", help="Redis URL/DSN (or set AINL_REDIS_URL)")
    runp.add_argument("--redis-host", default="")
    runp.add_argument("--redis-port", type=int, default=6379)
    runp.add_argument("--redis-db", type=int, default=0)
    runp.add_argument("--redis-user", default="")
    runp.add_argument("--redis-password", default="", help="Prefer env var AINL_REDIS_PASSWORD in production")
    runp.add_argument("--redis-ssl", action="store_true")
    runp.add_argument("--redis-timeout-s", type=float, default=5.0)
    runp.add_argument("--redis-allow-write", action="store_true")
    runp.add_argument("--redis-allow-prefix", action="append", default=[])
    runp.add_argument("--dynamodb-url", default="", help="DynamoDB endpoint URL (or set AINL_DYNAMODB_URL)")
    runp.add_argument("--dynamodb-region", default="us-east-1", help="AWS region for DynamoDB")
    runp.add_argument("--dynamodb-timeout-s", type=float, default=5.0)
    runp.add_argument("--dynamodb-allow-write", action="store_true")
    runp.add_argument("--dynamodb-allow-table", action="append", default=[])
    runp.add_argument("--dynamodb-consistent-read", action="store_true")
    runp.add_argument("--airtable-api-key", default="", help="Airtable personal access token (or AINL_AIRTABLE_API_KEY)")
    runp.add_argument("--airtable-base-id", default="", help="Airtable base id (or AINL_AIRTABLE_BASE_ID)")
    runp.add_argument("--airtable-timeout-s", type=float, default=8.0)
    runp.add_argument("--airtable-max-page-size", type=int, default=100)
    runp.add_argument("--airtable-allow-write", action="store_true")
    runp.add_argument("--airtable-allow-table", action="append", default=[])
    runp.add_argument("--airtable-allow-attachment-host", action="append", default=[], help="Allowed host(s) for attachment download/upload-by-url")
    runp.add_argument("--supabase-db-url", default="", help="Supabase Postgres DB URL (or AINL_SUPABASE_DB_URL / AINL_POSTGRES_URL)")
    runp.add_argument("--supabase-url", default="", help="Supabase project URL (or AINL_SUPABASE_URL)")
    runp.add_argument("--supabase-anon-key", default="", help="Supabase anon key (or AINL_SUPABASE_ANON_KEY)")
    runp.add_argument("--supabase-service-role-key", default="", help="Supabase service role key (or AINL_SUPABASE_SERVICE_ROLE_KEY)")
    runp.add_argument("--supabase-timeout-s", type=float, default=8.0)
    runp.add_argument("--supabase-allow-write", action="store_true")
    runp.add_argument("--supabase-allow-table", action="append", default=[])
    runp.add_argument("--supabase-allow-bucket", action="append", default=[])
    runp.add_argument("--supabase-allow-channel", action="append", default=[])
    runp.add_argument("--fs-root", default="")
    runp.add_argument("--fs-max-read-bytes", type=int, default=1_000_000)
    runp.add_argument("--fs-max-write-bytes", type=int, default=1_000_000)
    runp.add_argument("--fs-allow-ext", action="append", default=[])
    runp.add_argument("--fs-allow-delete", action="store_true")
    runp.add_argument("--tools-allow", action="append", default=[])
    runp.add_argument("--wasm-module", action="append", default=[], help="WASM module mapping: name=/abs/path/module.wasm")
    runp.add_argument("--wasm-allow-module", action="append", default=[], help="Optional wasm module allowlist")
    runp.add_argument(
        "--memory-db",
        default="",
        help="SQLite path for --enable-adapter memory (defaults to AINL_MEMORY_DB or ~/.openclaw/ainl_memory.sqlite3)",
    )
    runp.add_argument("--max-steps", type=int, default=None)
    runp.add_argument("--max-depth", type=int, default=None)
    runp.add_argument("--max-adapter-calls", type=int, default=None)
    runp.add_argument("--max-time-ms", type=int, default=None)
    runp.add_argument("--max-frame-bytes", type=int, default=None)
    runp.add_argument("--max-loop-iters", type=int, default=None)
    runp.add_argument("--self-test-graph", action="store_true")
    runp.set_defaults(func=cmd_run)

    hybrid_p = sub.add_parser(
        "run-hybrid-ptc",
        help="run the hybrid PTC order processor example (mock-friendly; requires ptc_runner adapter)",
    )
    hybrid_p.add_argument(
        "--no-mock",
        action="store_true",
        help="do not force AINL_PTC_RUNNER_MOCK=1 (use current env)",
    )
    hybrid_p.add_argument(
        "--trace-jsonl",
        default="/tmp/hybrid_orders.trace.jsonl",
        help="path to write hybrid trace JSONL (default: /tmp/hybrid_orders.trace.jsonl)",
    )
    hybrid_p.set_defaults(func=cmd_run_hybrid_ptc)

    chk = sub.add_parser("check", help="Compile/check AINL file")
    chk.add_argument("file")
    chk.add_argument("--strict", action="store_true")
    chk.set_defaults(func=cmd_check)

    cmp = sub.add_parser("compile", help="Same as check: compile/validate an .ainl file to IR JSON")
    cmp.add_argument("file")
    cmp.add_argument("--strict", action="store_true")
    cmp.set_defaults(func=cmd_check)

    isp = sub.add_parser("inspect", help="Compile an .ainl file and dump full canonical IR JSON")
    isp.add_argument("file")
    isp.add_argument("--strict", action="store_true")
    isp.add_argument("--json", action="store_true", help="Compatibility flag (output is always JSON)")
    isp.set_defaults(func=cmd_inspect)

    avm = sub.add_parser("generate-avm-policy", help="Generate AVM policy fragment JSON from an .ainl file")
    avm.add_argument("file")
    avm.add_argument("--strict", action="store_true")
    avm.add_argument("--output", "-o", default="")
    avm.set_defaults(func=cmd_generate_avm_policy)

    sbx = sub.add_parser("generate-sandbox-config", help="Generate sandbox/AVM config fragments from an .ainl file")
    sbx.add_argument("file")
    sbx.add_argument("--strict", action="store_true")
    sbx.add_argument("--output", "-o", default="")
    sbx.add_argument("--target", choices=["avm", "firecracker", "gvisor", "k8s", "general"], default="general")
    sbx.set_defaults(func=cmd_generate_sandbox_config)

    from tooling.mcp_host_install import list_mcp_host_ids, run_install_mcp_host

    def cmd_install_mcp(args: argparse.Namespace) -> int:
        if bool(getattr(args, "mcp_list_hosts", False)):
            print(" ".join(list_mcp_host_ids()))
            return 0
        return run_install_mcp_host(
            args.mcp_host,
            dry_run=bool(args.dry_run),
            verbose=bool(args.verbose),
        )

    mcp_inst = sub.add_parser(
        "install-mcp",
        help="Bootstrap AINL MCP + ainl-run for any supported host (same as install-openclaw / install-zeroclaw)",
    )
    mcp_mx = mcp_inst.add_mutually_exclusive_group(required=True)
    mcp_mx.add_argument(
        "--list-hosts",
        dest="mcp_list_hosts",
        action="store_true",
        help="Print supported --host values and exit",
    )
    mcp_mx.add_argument(
        "--host",
        dest="mcp_host",
        choices=list(list_mcp_host_ids()),
        help="Agent stack: openclaw, zeroclaw, …",
    )
    mcp_inst.add_argument("--dry-run", action="store_true", help="Print actions only; no pip or file writes")
    mcp_inst.add_argument("--verbose", "-v", action="store_true", help="Log each step to stderr")
    mcp_inst.set_defaults(func=cmd_install_mcp)

    def cmd_install_zeroclaw(args: argparse.Namespace) -> int:
        from tooling.zeroclaw_install import run_install_zeroclaw

        return run_install_zeroclaw(dry_run=bool(args.dry_run), verbose=bool(args.verbose))

    zcw = sub.add_parser(
        "install-zeroclaw",
        help="Bootstrap AINL for ZeroClaw: pip upgrade, ~/.zeroclaw/mcp.json, bin/ainl-run, PATH hint",
    )
    zcw.add_argument("--dry-run", action="store_true", help="Print actions only; no pip or file writes")
    zcw.add_argument("--verbose", "-v", action="store_true", help="Log each step to stderr")
    zcw.set_defaults(func=cmd_install_zeroclaw)

    def cmd_install_openclaw(args: argparse.Namespace) -> int:
        from tooling.openclaw_install import run_install_openclaw

        return run_install_openclaw(dry_run=bool(args.dry_run), verbose=bool(args.verbose))

    ocl = sub.add_parser(
        "install-openclaw",
        help="Bootstrap AINL for OpenClaw: pip upgrade, ~/.openclaw/openclaw.json MCP, bin/ainl-run, PATH hint",
    )
    ocl.add_argument("--dry-run", action="store_true", help="Print actions only; no pip or file writes")
    ocl.add_argument("--verbose", "-v", action="store_true", help="Log each step to stderr")
    ocl.set_defaults(func=cmd_install_openclaw)

    def cmd_doctor(args: argparse.Namespace) -> int:
        from tooling.doctor import run_doctor

        return run_doctor(
            host=(args.host or None),
            json_output=bool(args.json),
            verbose=bool(args.verbose),
        )

    doc = sub.add_parser(
        "doctor",
        help="Run environment diagnostics (imports, PATH, MCP config, install-mcp dry-run)",
    )
    doc.add_argument(
        "--host",
        choices=list(list_mcp_host_ids()),
        default="",
        help="Limit MCP checks to one host (default: check all known hosts)",
    )
    doc.add_argument("--json", action="store_true", help="Emit JSON diagnostics output")
    doc.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    doc.set_defaults(func=cmd_doctor)

    def cmd_bridge_sizing_probe(args: argparse.Namespace) -> int:
        import json

        from scripts.bridge_sizing_probe import print_plain_report, run_probe

        md = Path(args.bsz_memory_dir).expanduser() if args.bsz_memory_dir else None
        data = run_probe(args.bsz_db_path, args.bsz_days, memory_dir=md)
        if args.bsz_json:
            print(json.dumps(data, indent=2))
        else:
            print_plain_report(data)
        return 0

    bsz = sub.add_parser(
        "bridge-sizing-probe",
        help="Read-only OpenClaw bridge sizing: SQLite namespace counts + Token Usage Report section sizes",
    )
    bsz.add_argument(
        "--db-path",
        dest="bsz_db_path",
        type=str,
        default=os.getenv("AINL_MEMORY_DB", "/tmp/ainl_memory.sqlite3"),
        help="SQLite memory DB (default: AINL_MEMORY_DB or /tmp/ainl_memory.sqlite3)",
    )
    bsz.add_argument(
        "--memory-dir",
        dest="bsz_memory_dir",
        default="",
        help="Directory for daily YYYY-MM-DD.md (overrides OPENCLAW_* for this run)",
    )
    bsz.add_argument(
        "--days",
        dest="bsz_days",
        type=int,
        default=14,
        help="How many newest daily *.md files to scan (default: 14)",
    )
    bsz.add_argument(
        "--json",
        dest="bsz_json",
        action="store_true",
        help="Emit JSON only",
    )
    bsz.set_defaults(func=cmd_bridge_sizing_probe)

    def cmd_profile(args: argparse.Namespace) -> int:
        import json

        from tooling.ainl_profile_catalog import (
            emit_shell_exports,
            format_profile_text,
            get_profile,
            list_profile_ids,
        )

        pc = getattr(args, "profile_cmd", None)
        if pc == "list":
            for pid in list_profile_ids():
                print(pid)
            return 0
        if pc == "show":
            try:
                if args.profile_json:
                    print(json.dumps(get_profile(args.profile_id), indent=2))
                else:
                    print(format_profile_text(args.profile_id), end="")
            except KeyError:
                raise SystemExit(f"unknown profile: {args.profile_id!r} (try: ainl profile list)")
            return 0
        if pc == "emit-shell":
            try:
                print(emit_shell_exports(args.profile_id), end="")
            except KeyError:
                raise SystemExit(f"unknown profile: {args.profile_id!r} (try: ainl profile list)")
            return 0
        raise SystemExit(f"unknown profile subcommand: {pc!r}")

    prf = sub.add_parser(
        "profile",
        help="Named env profiles (IR cache, embedding mode, bridge caps, intelligence defaults)",
    )
    prf_sub = prf.add_subparsers(dest="profile_cmd", required=True)
    prf_list = prf_sub.add_parser("list", help="List profile ids")
    prf_list.set_defaults(func=cmd_profile)
    prf_show = prf_sub.add_parser("show", help="Show one profile (env + notes)")
    prf_show.add_argument("profile_id", help="Profile id (e.g. openclaw-default)")
    prf_show.add_argument(
        "--json",
        dest="profile_json",
        action="store_true",
        help="Emit JSON",
    )
    prf_show.set_defaults(func=cmd_profile)
    prf_emit = prf_sub.add_parser(
        "emit-shell",
        help="Print export VAR=value lines for bash/zsh (eval \"$(ainl profile emit-shell ID)\")",
    )
    prf_emit.add_argument("profile_id")
    prf_emit.set_defaults(func=cmd_profile)

    gld = sub.add_parser("golden", help="Run golden fixtures from examples")
    gld.add_argument("--examples-dir", default=str(Path(__file__).resolve().parent.parent / "examples"))
    gld.add_argument("--trace", action="store_true")
    gld.add_argument("--execution-mode", choices=["graph-preferred", "steps-only", "graph-only"], default="graph-preferred")
    gld.add_argument("--unknown-op-policy", choices=["skip", "error"], default=None)
    gld.add_argument("--max-steps", type=int, default=None)
    gld.set_defaults(func=cmd_golden)

    def cmd_visualize(args: argparse.Namespace) -> int:
        from scripts.visualize_ainl import main as visualize_main

        return visualize_main(list(args.visualize_argv))

    vis = sub.add_parser(
        "visualize",
        help="Compile .ainl to a Mermaid/DOT-style diagram (pass-through to ainl-visualize)",
    )
    vis.add_argument(
        "visualize_argv",
        nargs=argparse.REMAINDER,
        default=[],
        help="Arguments for ainl-visualize (path, --output, --no-clusters, …)",
    )
    vis.set_defaults(func=cmd_visualize)

    imp = sub.add_parser("import", help="Import external formats into AINL")
    imp_sub = imp.add_subparsers(dest="import_cmd", required=True)

    mdp = imp_sub.add_parser(
        "markdown",
        help="Convert Markdown (Clawflows WORKFLOW.md or Agency-Agents doc) to .ainl",
    )
    mdp.add_argument(
        "url_or_path",
        help="https URL, GitHub blob/raw link, or local Markdown file path",
    )
    mdp.add_argument(
        "--type",
        choices=("workflow", "agent"),
        required=True,
        help="workflow ≈ Clawflows WORKFLOW.md; agent ≈ Agency-Agents personality markdown",
    )
    mdp.add_argument(
        "--output",
        "-o",
        required=True,
        help="Output path (e.g. morning.ainl)",
    )
    mdp.add_argument(
        "--personality",
        default="",
        help="Optional tone/instructions for agent-type imports (stored in header comment for now)",
    )
    mdp.add_argument(
        "--no-openclaw-bridge",
        action="store_true",
        help="Use cache instead of memory/queue bridge hooks in generated graph",
    )
    mdp.add_argument(
        "--generate-soul",
        action="store_true",
        help="With --type agent: also write SOUL.md and IDENTITY.md next to -o",
    )
    mdp.add_argument("--dry-run", action="store_true", help="Print .ainl to stdout; do not write file")
    mdp.add_argument("--verbose", "-v", action="store_true")
    mdp.set_defaults(func=cmd_import_markdown)

    cfp = imp_sub.add_parser(
        "clawflows",
        help="Fetch 5 sample workflows from nikilster/clawflows into examples/ecosystem/clawflows/",
    )
    cfp.add_argument(
        "--output-dir",
        default="",
        help="Destination directory (default: <repo>/examples/ecosystem/clawflows)",
    )
    cfp.add_argument(
        "--no-openclaw-bridge",
        action="store_true",
        help="Use cache instead of memory/queue in generated graphs",
    )
    cfp.add_argument("--timeout-s", type=float, default=30.0, help="HTTP timeout per workflow")
    cfp.add_argument("--verbose", "-v", action="store_true")
    cfp.set_defaults(func=cmd_import_clawflows)

    aap = imp_sub.add_parser(
        "agency-agents",
        help="Fetch 5 sample agents from msitarzewski/agency-agents into examples/ecosystem/agency-agents/",
    )
    aap.add_argument(
        "--output-dir",
        default="",
        help="Destination directory (default: <repo>/examples/ecosystem/agency-agents)",
    )
    aap.add_argument(
        "--personality",
        default="",
        help="Optional tone merged into parsed agent graph",
    )
    aap.add_argument(
        "--no-openclaw-bridge",
        action="store_true",
        help="Use cache instead of memory/queue in generated graphs",
    )
    aap.add_argument("--timeout-s", type=float, default=30.0, help="HTTP timeout per agent file")
    aap.add_argument("--verbose", "-v", action="store_true")
    aap.set_defaults(func=cmd_import_agency_agents)

    initp = sub.add_parser(
        "init",
        help="Create a new AINL project directory with a starter main.ainl and README",
    )
    initp.add_argument("name", help="Project name (also becomes the directory name)")
    initp.add_argument(
        "--output-dir",
        default="",
        metavar="DIR",
        help="Parent directory for the new project (default: current directory)",
    )
    initp.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the target directory if it already exists",
    )
    initp.set_defaults(func=cmd_init)

    args = ap.parse_args()
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
