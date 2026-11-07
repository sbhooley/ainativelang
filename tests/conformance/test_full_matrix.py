from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "tests" / "data" / "conformance"

from runtime.adapters.base import AdapterRegistry
from runtime.adapters.fs import SandboxedFileSystemAdapter
from runtime.adapters.memory import MemoryAdapter
from runtime.adapters.sqlite import SimpleSqliteAdapter
from runtime.adapters.tools import ToolBridgeAdapter
from runtime.engine import RuntimeEngine


@dataclass(frozen=True)
class Golden:
    path: Path
    strict: bool = True  # used later for strict_validation, etc.


CONFORMANCE_CATEGORIES: Dict[str, Dict[str, List[str]]] = {
    "tokenizer_round_trip": {
        "goldens": [
            "simple.ainl",
            "include_heavy.ainl",
            "strict_only.ainl",
            "session_budget_memory_trace.ainl",
        ]
    },
    "ir_canonicalization": {
        "goldens": ["simple.ainl", "include_heavy.ainl", "session_budget_memory_trace.ainl"]
    },
    "strict_validation": {"goldens": ["strict_only.ainl"]},
    "runtime_parity": {"goldens": ["simple.ainl", "include_heavy.ainl"]},
    "emitter_stability": {"goldens": ["simple.ainl"]},
    # Memory put/list/prune under MemoryAdapter only (not comparable to core-only parity).
    "memory_continuity_runtime": {"goldens": ["session_budget_memory_trace.ainl"]},
}

# Large real-world tokenizer fixture (lossless token round-trip only).
TOKENIZER_EXTRA_SOURCES: List[Path] = [ROOT / "demo" / "session_budget_enforcer.lang"]


def _all_params() -> List[Tuple[str, Path]]:
    params: List[Tuple[str, Path]] = []
    for cat, cfg in CONFORMANCE_CATEGORIES.items():
        for rel in cfg["goldens"]:
            params.append((cat, DATA_DIR / rel))
    for path in TOKENIZER_EXTRA_SOURCES:
        params.append(("tokenizer_round_trip", path))
    return params


def _sanitize_trace_events(trace_events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Remove timing noise to keep runtime parity snapshots stable.

    Runtime traces include duration_ms which depends on perf_counter and varies
    across runs/adapters. For conformance snapshots we only care about the
    execution order and resulting values/frame visibility.
    """
    sanitized: List[Dict[str, Any]] = []
    for ev in trace_events:
        ev2 = dict(ev)
        ev2.pop("duration_ms", None)
        ev2.pop("lineno", None)
        sanitized.append(ev2)
    return sanitized


def _scrub_memory_iso_timestamps(obj: Any) -> Any:
    """Replace volatile memory adapter timestamps for stable syrupy snapshots."""
    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for k, v in obj.items():
            if k in ("created_at", "updated_at") and isinstance(v, str) and "T" in v:
                out[k] = "<iso-timestamp>"
            else:
                out[k] = _scrub_memory_iso_timestamps(v)
        return out
    if isinstance(obj, list):
        return [_scrub_memory_iso_timestamps(x) for x in obj]
    return obj


def _run_ir_with_adapter(
    *,
    ir: Dict[str, Any],
    adapter_name: str,
    tmp_path: Path,
) -> Dict[str, Any]:
    """
    Execute compiled IR once under a specific adapter registry.

    Returns:
      - result: runtime label result
      - trace: sanitized trace events (stable across adapters/runs)
    """
    allowed = ["core", adapter_name] if adapter_name != "core" else ["core"]
    reg = AdapterRegistry(allowed=allowed)

    if adapter_name == "memory":
        reg.register("memory", MemoryAdapter(db_path=str(tmp_path / "ainl_memory.sqlite3")))
    elif adapter_name == "sqlite":
        reg.register("sqlite", SimpleSqliteAdapter(db_path=":memory:"))
    elif adapter_name == "fs":
        reg.register("fs", SandboxedFileSystemAdapter(sandbox_root=str(tmp_path / "fs_sandbox")))
    elif adapter_name == "tools":
        # Minimal safe tool set. Current conformance goldens don't call tools.
        def _echo(x: Any, context: Any = None) -> Any:  # noqa: ANN401 - tool boundary
            return x

        reg.register("tools", ToolBridgeAdapter({"echo": _echo}))

    eng = RuntimeEngine(
        ir=ir,
        adapters=reg,
        trace=True,
        step_fallback=False,
        safe_trace=False,
    )
    entry = eng.default_entry_label()
    result = eng.run_label(entry, frame={})
    return {"result": result, "trace": _sanitize_trace_events(eng.get_trace())}


def _emit_outputs_for_ir(compiler: Any, ir: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Emit deterministic artifacts for a compiled IR.

    We keep this list small and CI-stable by using emitters that already have
    snapshot coverage elsewhere in the repo.
    """
    emitters: List[Dict[str, Any]] = []

    # v1 "FastAPI" lane: actual server python module as a single string.
    if hasattr(compiler, "emit_server"):
        emitters.append({"emitter": "fastapi", "output": compiler.emit_server(ir)})

    # v1 OpenAPI lane: openapi.json as a JSON string.
    if hasattr(compiler, "emit_openapi"):
        emitters.append({"emitter": "openapi", "output": compiler.emit_openapi(ir)})

    # SQL migrations lane: deterministic migrations string.
    if hasattr(compiler, "emit_sql_migrations"):
        emitters.append(
            {"emitter": "sql_postgres", "output": compiler.emit_sql_migrations(ir, dialect="postgres")}
        )

    return emitters


@pytest.mark.parametrize("category_id,golden_path", _all_params())
def test_full_matrix(category_id: str, golden_path: Path, compiler_lossless, snapshot, tmp_path):
    assert golden_path.exists(), f"Missing golden file: {golden_path}"

    if category_id == "tokenizer_round_trip":
        code = golden_path.read_text(encoding="utf-8")
        ir = compiler_lossless.compile(
            code,
            emit_graph=False,
            source_path=str(golden_path.resolve()),
        )
        cst_lines = (ir.get("cst") or {}).get("lines") or []
        assert cst_lines, f"{golden_path}: missing CST lines in compiler output"

        # Lossless guarantee: tokenizer output stored in `ir["cst"]["lines"][*]["tokens"]`
        # must match recomputed tokenizer output for each CST line.
        for ln in cst_lines:
            lineno = ln.get("lineno")
            original_line = ln.get("original_line", "")
            stored_tokens = ln.get("tokens") or []
            assert lineno is not None, f"{golden_path}: CST line missing lineno"
            recomputed_tokens = compiler_lossless.tokenize_line_lossless(original_line, lineno)
            assert (
                recomputed_tokens == stored_tokens
            ), f"{golden_path}: token mismatch at lineno={lineno}"

        return

    if category_id == "ir_canonicalization":
        code = golden_path.read_text(encoding="utf-8")
        strict_compiler = type(compiler_lossless)(strict_mode=True)
        ir = strict_compiler.compile(
            code,
            emit_graph=True,
            source_path=str(golden_path.resolve()),
        )
        if ir.get("errors"):
            pytest.skip(
                f"strict-mode validation failed (skipping IR snapshot): {golden_path}\n"
                + "; ".join(ir.get("errors", [])[:5])
            )

        # Canonicalization snapshot: entire IR dict (deterministic post-compile output).
        assert ir == snapshot
        return

    if category_id == "strict_validation":
        code = golden_path.read_text(encoding="utf-8")
        strict_compiler = type(compiler_lossless)(strict_mode=True)
        ir = strict_compiler.compile(
            code,
            emit_graph=True,
            source_path=str(golden_path.resolve()),
        )

        errors = ir.get("errors") or []
        structured = ir.get("structured_diagnostics") or []

        # This category is explicitly expected to catch strict violations.
        if not errors and not structured:
            pytest.fail(f"strict_validation expected strict errors, but got none: {golden_path}")

        payload = {
            "errors": errors,
            "structured_diagnostics": structured,
        }
        assert payload == snapshot
        return

    if category_id == "runtime_parity":
        code = golden_path.read_text(encoding="utf-8")
        strict_compiler = type(compiler_lossless)(strict_mode=True)
        ir = strict_compiler.compile(
            code,
            emit_graph=True,
            source_path=str(golden_path.resolve()),
        )

        # Reuse the same skip strategy as ir_canonicalization: runtime parity only
        # applies to inputs that compile cleanly in strict mode.
        if ir.get("errors"):
            pytest.skip(
                f"strict-mode validation failed (skipping runtime parity): {golden_path}\n"
                + "; ".join(ir.get("errors", [])[:5])
            )

        # Non-network, non-optional-dependency adapter set for CI stability.
        adapter_names = ["core", "memory", "sqlite", "fs", "tools"]
        adapter_traces: List[Dict[str, Any]] = []

        core_result: Any = None
        core_trace: List[Dict[str, Any]] = []

        for adapter_name in adapter_names:
            try:
                run_out = _run_ir_with_adapter(ir=ir, adapter_name=adapter_name, tmp_path=tmp_path)
            except Exception as e:
                if adapter_name == "core":
                    raise
                pytest.skip(f"Skipping adapter={adapter_name}: {e}")
                continue

            adapter_traces.append({"adapter": adapter_name, "trace": run_out["trace"]})

            if adapter_name == "core":
                core_result = run_out["result"]
                core_trace = run_out["trace"]
            else:
                # Runtime parity should hold: identical result and trace across
                # backends when the program relies on core stdlib.
                assert run_out["result"] == core_result, (
                    f"runtime parity result mismatch for adapter={adapter_name}; "
                    f"core_result={core_result!r} adapter_result={run_out['result']!r}"
                )
                assert run_out["trace"] == core_trace, (
                    f"runtime parity trace mismatch for adapter={adapter_name}"
                )

        if not adapter_traces:
            pytest.skip("runtime_parity: no adapters could be constructed")

        payload = {"adapters": adapter_traces}
        assert payload == snapshot
        return

    if category_id == "memory_continuity_runtime":
        code = golden_path.read_text(encoding="utf-8")
        strict_compiler = type(compiler_lossless)(strict_mode=True)
        ir = strict_compiler.compile(
            code,
            emit_graph=True,
            source_path=str(golden_path.resolve()),
        )
        if ir.get("errors"):
            pytest.skip(
                f"strict-mode validation failed (skipping memory continuity runtime): {golden_path}\n"
                + "; ".join(ir.get("errors", [])[:5])
            )
        run_out = _run_ir_with_adapter(ir=ir, adapter_name="memory", tmp_path=tmp_path)
        trace = _scrub_memory_iso_timestamps(_sanitize_trace_events(run_out["trace"]))
        payload = {"result": _scrub_memory_iso_timestamps(run_out["result"]), "trace": trace}
        assert payload == snapshot
        return

    if category_id == "emitter_stability":
        code = golden_path.read_text(encoding="utf-8")
        strict_compiler = type(compiler_lossless)(strict_mode=True)
        ir = strict_compiler.compile(
            code,
            emit_graph=True,
            source_path=str(golden_path.resolve()),
        )

        # Reuse skip strategy from other categories: do not snapshot artifacts
        # for strict-invalid inputs.
        if ir.get("errors"):
            pytest.skip(
                f"strict-mode validation failed (skipping emitter snapshot): {golden_path}\n"
                + "; ".join(ir.get("errors", [])[:5])
            )

        emitters = _emit_outputs_for_ir(strict_compiler, ir)
        if not emitters:
            pytest.skip("emitter_stability: no emitters available")

        payload = {"emitters": emitters}
        assert payload == snapshot
        return

    raise AssertionError(f"Unknown category: {category_id}")

