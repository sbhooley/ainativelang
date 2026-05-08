#!/usr/bin/env python3
"""Refresh headline repo statistics in STATUS.yaml and AGENTS.md.

Computes line counts, test inventory, pytest collection summary, and adapter
counts from the working tree. Run from repo root:

    python scripts/refresh_repo_stats.py
    python scripts/refresh_repo_stats.py --check    # exit 2 if files would change

See CONTRIBUTING.md for when to run this (releases, large compiler/test edits).
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def _normalize_status_yaml_for_repo_stats_compare(text: str) -> str:
    """Strip the rolling ``# stats_refreshed: YYYY-MM-DD (UTC)`` comment line.

    ``render_status_real_section`` embeds *today's* UTC calendar date on every
    regeneration. Without ignoring that line, ``--check`` fails on CI whenever
    the committed snapshot was refreshed on a different UTC day than the
    workflow run, even when all counters match the tree.
    """
    out: list[str] = []
    for line in text.splitlines(keepends=True):
        if line.startswith("# stats_refreshed:"):
            continue
        out.append(line)
    return "".join(out)


@dataclass
class RepoStats:
    generated_at: str
    compiler_lines: int
    runtime_lines: int
    cli_lines: int
    preprocessor_lines: int
    adapter_py_files: int
    examples_ainl_files: int
    tests_py_files: int
    tests_test_named_py: int
    tests_python_lines: int
    pytest_selected: int | None
    pytest_total: int | None
    pytest_deselected: int | None
    pytest_collect_error: str | None


def _count_lines(path: Path) -> int:
    if not path.is_file():
        return 0
    # wc -l semantics (count newline-terminated lines)
    text = path.read_bytes()
    if not text:
        return 0
    n = text.count(b"\n")
    if not text.endswith(b"\n"):
        n += 1
    return n


def _iter_tests_py(root: Path):
    tests = root / "tests"
    if not tests.is_dir():
        return
    for p in tests.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        yield p


def _compute_test_metrics(root: Path) -> tuple[int, int, int]:
    py_files = 0
    test_named = 0
    total_lines = 0
    for p in _iter_tests_py(root):
        py_files += 1
        if p.name.startswith("test_") and p.suffix == ".py":
            test_named += 1
        try:
            total_lines += _count_lines(p)
        except OSError:
            pass
    return py_files, test_named, total_lines


def _count_examples_ainl(root: Path) -> int:
    ex = root / "examples"
    if not ex.is_dir():
        return 0
    n = 0
    for p in ex.rglob("*.ainl"):
        if "__pycache__" in p.parts:
            continue
        n += 1
    return n


def _count_adapter_py(root: Path) -> int:
    ad = root / "adapters"
    if not ad.is_dir():
        return 0
    n = 0
    for p in ad.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        n += 1
    return n


def _pytest_python_candidates(root: Path) -> list[Path]:
    """Interpreters to try for ``python -m pytest`` when refreshing stats.

    Prefer the repo virtualenv (``.venv-ainl``) even if the script was started
    with system Python, so ``python3 scripts/refresh_repo_stats.py`` works
    without activation as long as dev deps were installed into ``.venv-ainl``.
    """
    candidates: list[Path] = []
    seen: set[str] = set()

    def add(p: Path) -> None:
        if not p.is_file():
            return
        # Use `.absolute()` (no symlink expansion) for dedupe keys so a venv
        # launcher like `.venv-ainl/bin/python` stays distinct from the real
        # interpreter binary `sys.executable` may point at after `.resolve()`.
        key = str(p.absolute())
        if key not in seen:
            seen.add(key)
            candidates.append(p.absolute())

    # Unix layout
    add(root / ".venv-ainl" / "bin" / "python")
    add(root / ".venv" / "bin" / "python")
    # Windows layout (same ordering)
    add(root / ".venv-ainl" / "Scripts" / "python.exe")
    add(root / ".venv" / "Scripts" / "python.exe")
    add(Path(sys.executable).absolute())
    return candidates


def _run_pytest_collect(root: Path) -> tuple[int | None, int | None, int | None, str | None]:
    summary_re = re.compile(r"(\d+)/(\d+)\s+tests\s+collected")
    desel_re = re.compile(r"\((\d+)\s+deselected\)")

    last_detail: str | None = None
    for py in _pytest_python_candidates(root):
        cmd = [str(py), "-m", "pytest", "--collect-only", "-q"]
        try:
            proc = subprocess.run(
                cmd,
                cwd=root,
                capture_output=True,
                text=True,
                timeout=180,
                env=os.environ.copy(),
            )
        except (subprocess.TimeoutExpired, OSError) as e:
            return None, None, None, str(e)
        combined = (proc.stdout or "") + (proc.stderr or "")
        if "No module named pytest" in combined:
            last_detail = f"{py.name}: No module named pytest (try .venv-ainl + pip install -e '.[dev]')"
            continue
        m = summary_re.search(combined)
        if m:
            selected, total = int(m.group(1)), int(m.group(2))
            dm = desel_re.search(combined)
            desel = int(dm.group(1)) if dm else 0
            return selected, total, desel, None
        tail = (
            "\n".join(combined.strip().splitlines()[-5:])
            if combined.strip()
            else "(empty output)"
        )
        last_detail = (
            f"{py.name}: exit {proc.returncode}; expected "
            r"'N/M tests collected' in pytest output; tail:\n{tail}"
        )

    if last_detail:
        return None, None, None, last_detail
    return None, None, None, "could not parse pytest collection output"


def collect_stats(root: Path) -> RepoStats:
    gen = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    compiler_lines = _count_lines(root / "compiler_v2.py")
    runtime_lines = _count_lines(root / "runtime" / "engine.py")
    cli_lines = _count_lines(root / "cli" / "main.py")
    preprocessor_lines = _count_lines(root / "ainl_preprocess.py")
    adapter_py_files = _count_adapter_py(root)
    examples_ainl = _count_examples_ainl(root)
    t_py, t_named, t_lines = _compute_test_metrics(root)
    sel, tot, des, err = _run_pytest_collect(root)
    return RepoStats(
        generated_at=gen,
        compiler_lines=compiler_lines,
        runtime_lines=runtime_lines,
        cli_lines=cli_lines,
        preprocessor_lines=preprocessor_lines,
        adapter_py_files=adapter_py_files,
        examples_ainl_files=examples_ainl,
        tests_py_files=t_py,
        tests_test_named_py=t_named,
        tests_python_lines=t_lines,
        pytest_selected=sel,
        pytest_total=tot,
        pytest_deselected=des,
        pytest_collect_error=err,
    )


def render_status_real_section(s: RepoStats) -> str:
    pytest_note = ""
    if s.pytest_collect_error:
        pytest_note = (
            f'    pytest_collect_only: "unavailable — {s.pytest_collect_error}"\n'
        )
    elif s.pytest_selected is not None and s.pytest_total is not None:
        des = s.pytest_deselected or 0
        pytest_note = (
            f"    pytest_collect_only_selected: {s.pytest_selected}\n"
            f"    pytest_collect_only_total: {s.pytest_total}\n"
            f"    pytest_deselected: {des}\n"
        )

    lines_k = round(s.tests_python_lines / 1000)
    return f"""# STATUS.yaml — What is real vs aspirational
# stats_refreshed: {s.generated_at} (UTC) — run: python scripts/refresh_repo_stats.py

real_and_working:
  compiler:
    file: compiler_v2.py
    lines: {s.compiler_lines}
    status: production
    notes: "Parses .ainl → IR. Multiple emitters. Fully tested."

  runtime:
    file: runtime/engine.py
    lines: {s.runtime_lines}
    status: production
    notes: "Executes IR graphs. Async support. Observability."

  cli:
    file: cli/main.py
    lines: {s.cli_lines}
    status: production
    commands:
      - "ainl run"
      - "ainl validate [--strict] [--json-output]"
      - "ainl emit --target <target>"
      - "ainl serve [--port PORT]"
      - "ainl compile"
      - "ainl check"
      - "ainl visualize"
      - "ainl inspect"
      - "ainl init"
      - "ainl doctor"

  adapters:
    status: production
    python_modules_under_adapters: {s.adapter_py_files}
    notes: "Count = recursive *.py under adapters/ (excludes __pycache__). Older docs said '54 modules' — this is the live count."
    key_adapters:
      - "solana"
      - "postgres"
      - "dynamodb"
      - "redis"
      - "supabase"
      - "mysql"
      - "airtable"
      - "llm/openrouter"
      - "llm/ollama"
      - "llm/anthropic"
      - "llm/cohere"
      - "http, memory, cache, queue"

  tests:
    definitions:
      py_files_under_tests: "Every *.py under tests/ (includes conftest.py, helpers, harnesses)."
      test_named_py_files: "Files named test_*.py under tests/ (pytest test modules)."
      lines_python_under_tests: "Sum of lines of all *.py under tests/."
      pytest_collect_only: "pytest --collect-only -q (selected vs total reflects default deselection)."
    py_files_under_tests: {s.tests_py_files}
    test_named_py_files: {s.tests_test_named_py}
    lines_python_under_tests: {s.tests_python_lines}
    lines_python_under_tests_rounded: "~{lines_k}k"
{pytest_note.rstrip()}
    status: "Pass/fail counts vary by optional deps; run CI or pytest locally. Collection counts above are machine-generated."

  examples:
    count: {s.examples_ainl_files}
    format: ".ainl under examples/ (real, compilable syntax)"

  http_server:
    command: "ainl serve --port 8080"
    endpoints:
      - "POST /validate"
      - "POST /compile"
      - "POST /run"
      - "GET /health"
    status: working
    notes: "Zero-dependency HTTP server using stdlib. Foundation for cloud."

  compact_syntax_preprocessor:
    file: ainl_preprocess.py
    lines: {s.preprocessor_lines}
    status: production
    tests: 54
    notes: >
      Human-friendly compact syntax (Python-like) that transpiles to standard
      opcodes before the compiler sees it. Zero compiler changes. Both strict
      and non-strict modes supported. 66% token reduction vs raw opcodes.
    examples: "examples/compact/"

"""


def render_test_hint_block(_s: RepoStats) -> str:
    """Bash snippet under ## How To Test (markers: repo-stats:test-hint-*)."""
    return (
        "```bash\n"
        "source .venv-ainl/bin/activate\n"
        "python -m pytest tests/ -x -q -k \"not test_profiles_cover\"\n"
        "# Pass/fail totals vary by machine (optional deps). Typical skips without extras:\n"
        "# ArmaraOS CLI, langgraph, temporalio — install `.[dev]` / `.[interop]` as needed.\n"
        "# Refresh STATUS.yaml + layout counts: python scripts/refresh_repo_stats.py\n"
        "```"
    )


def render_agents_layout_block(s: RepoStats) -> str:
    lines_k = round(s.tests_python_lines / 1000)
    pytest_bits = "pytest collect-only unavailable (run with dev deps)"
    if s.pytest_selected is not None and s.pytest_total is not None:
        pytest_bits = (
            f"pytest —collect-only: {s.pytest_selected}/{s.pytest_total} "
            f"(see STATUS.yaml)"
        )
    return f"""compiler_v2.py          — The compiler ({s.compiler_lines} lines). Parses .ainl → IR dict.
compiler_diagnostics.py — Error/warning types used by compiler.
runtime/engine.py       — The runtime engine ({s.runtime_lines} lines). Executes IR graphs.
runtime/adapters/       — Runtime adapter base classes and builtins.
cli/main.py             — CLI entry point ({s.cli_lines} lines). All `ainl` commands.
adapters/               — {s.adapter_py_files} Python files under `adapters/` (recursive); ArmaraOS monitor bootstrap: `armaraos_integration.py`, `armaraos_defaults.py` (`build_armaraos_monitor_registry`, `boot_armaraos_graph_memory`). See `docs/ARMARAOS_INTEGRATION.md`, `docs/adapters/AINL_GRAPH_MEMORY.md`.
armaraos/emitter/       — `armaraos.py`: `ainl emit --target armaraos` Hand pack (`HAND.toml`, IR JSON, `security.json`, README) with `schema_version` for openfang-hands validation.
scripts/                — Standalone scripts (`refresh_repo_stats.py`, emit_langgraph, emit_temporal, `ainl_mcp_server.py` MCP entrypoint, etc).
tooling/                — Graph analysis, normalization, effect analysis; `ainl_get_started.py` (authoring wizard + adapter contracts), `corpus_mining.py` (strict-valid family index for `corpus/strict_valid_family_index.json`).
corpus/                 — Generated/mined JSON (e.g. `strict_valid_family_index.json`, `reverse_prompt_fixtures.json`); see `docs/operations/MCP_AINL_WIZARD_AND_CORPUS.md`.
examples/               — {s.examples_ainl_files}+ `.ainl` files under `examples/` (strict CI subset: `tooling/artifact_profiles.json`). See `examples/README.md`.
tests/                  — {s.tests_py_files} `*.py` files under `tests/` (~{lines_k}k lines total); {s.tests_test_named_py} `test_*.py` modules; {pytest_bits}. Definitions: **`STATUS.yaml`** → `real_and_working.tests`.
docs/                   — Documentation (some accurate, some aspirational — see **`STATUS.yaml`**).
"""


def _replace_marked_section(text: str, begin: str, end: str, new_inner: str) -> str:
    if begin not in text or end not in text:
        raise ValueError(f"markers missing: {begin!r} / {end!r}")
    i = text.index(begin) + len(begin)
    j = text.index(end)
    # Strip one leading newline after begin, one before end
    inner = text[i:j]
    if inner.startswith("\n"):
        inner = inner[1:]
    return text[:i] + "\n" + new_inner + "\n" + text[j:]


def refresh_agents_md(root: Path, s: RepoStats) -> str:
    path = root / "AGENTS.md"
    text = path.read_text(encoding="utf-8")
    layout = "```\n" + render_agents_layout_block(s) + "```"
    text = _replace_marked_section(
        text,
        "<!-- repo-stats:layout-begin -->",
        "<!-- repo-stats:layout-end -->",
        layout,
    )
    hint = render_test_hint_block(s)
    text = _replace_marked_section(
        text,
        "<!-- repo-stats:test-hint-begin -->",
        "<!-- repo-stats:test-hint-end -->",
        hint,
    )
    return text


# Preserved between real_and_working and aspirational_not_built (do not move into render_status_real_section).
STATUS_TELEMETRY_AND_AUDIT_SURFACES = """
telemetry_and_audit_surfaces:
  map_doc: docs/operations/AUDIT_AND_TELEMETRY_MAP.md
  runner_structured_audit:
    status: shipped
    notes: "HTTP runner service (scripts/runtime_runner_service.py); ainl.runner JSON — docs/operations/AUDIT_LOGGING.md"
  cli_trajectory_jsonl:
    status: shipped
    notes: "RuntimeEngine per-step JSONL via ainl run --trace-jsonl or --log-trajectory / AINL_LOG_TRAJECTORY — docs/trajectory.md"
  audit_trail_adapter:
    status: shipped
    notes: "Opt-in adapter; AINL_AUDIT_SINK / --audit-sink — docs/tutorials/production_with_estimates_and_audit.md"
  runtime_observability_jsonl:
    status: shipped
    notes: "Optional metrics JSONL (AINL_OBSERVABILITY, AINL_OBSERVABILITY_JSONL) — runtime/observability.py"
"""


def refresh_status_yaml(root: Path, s: RepoStats) -> str:
    path = root / "STATUS.yaml"
    text = path.read_text(encoding="utf-8")
    key = "aspirational_not_built:"
    if key not in text:
        raise ValueError(f"{path}: missing {key!r}")
    idx = text.index(key)
    aspirational = text[idx:]
    return render_status_real_section(s) + STATUS_TELEMETRY_AND_AUDIT_SURFACES + aspirational


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 2 if STATUS.yaml or AGENTS.md would change.",
    )
    args = parser.parse_args()
    root = REPO_ROOT
    os.chdir(root)
    s = collect_stats(root)

    new_status = refresh_status_yaml(root, s)
    status_path = root / "STATUS.yaml"
    old_status = status_path.read_text(encoding="utf-8")

    new_agents = refresh_agents_md(root, s)
    agents_path = root / "AGENTS.md"
    old_agents = agents_path.read_text(encoding="utf-8")

    if args.check:
        status_ok = _normalize_status_yaml_for_repo_stats_compare(
            new_status
        ) == _normalize_status_yaml_for_repo_stats_compare(old_status)
        agents_ok = new_agents == old_agents
        if not status_ok or not agents_ok:
            print(
                "repo-stats: STATUS.yaml or AGENTS.md are out of date; run:",
                "python scripts/refresh_repo_stats.py",
                file=sys.stderr,
            )
            return 2
        print("repo-stats: STATUS.yaml and AGENTS.md match the working tree.")
        return 0

    status_path.write_text(new_status, encoding="utf-8")
    agents_path.write_text(new_agents, encoding="utf-8")
    print(f"Updated {status_path.relative_to(root)} and {agents_path.relative_to(root)}")
    print(
        f"  compiler={s.compiler_lines} engine={s.runtime_lines} cli={s.cli_lines} "
        f"adapters_py={s.adapter_py_files} tests_py={s.tests_py_files} "
        f"test_named={s.tests_test_named_py} examples_ainl={s.examples_ainl_files}"
    )
    if s.pytest_collect_error:
        print(f"  warning: pytest collect: {s.pytest_collect_error}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
