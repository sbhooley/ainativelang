"""
benchmark_vs_hand_runner.py
============================

Tier 2 benchmark — closes the "AINL vs hand-written Python runner" comparison
gap that LONG_TERM_FIXES_TRACKER.md row T2.3 commits to. Pairs with the
qualitative argument in docs/competitive/VS_HAND_WRITTEN_RUNNER.md and the
§9 row in docs/CLAIMS_AND_EVIDENCE.md.

Measures three orthogonal axes across three workloads
(enterprise_monitor, support_ticket_router, data_pipeline) and three
implementation styles (AINL source, competent_python baseline-B, and
production_grade baseline-B):

  1. Authoring tokens  — tiktoken cl100k_base on each source file
  2. Source LOC        — line count of each source file
  3. Audit checklist   — declared `__benchmark_audit_checklist__` block per
                         Python file, scored against an 8-row matrix
                         (event_hash_chain / per_step_inputs /
                          per_step_outputs / adapter_args / approval_gates /
                          config_snapshot / replayable / regulatory_grade).

This benchmark does NOT measure runtime tokens — those depend on actual LLM
output, the LangGraph runtime is benchmarked separately by
benchmark_langgraph_runtime.py (currently stubbed; tracker T2.1), and the
compile-once-run-many runtime savings are measured by
benchmark_compile_once_run_many.py. The runner-vs-AINL story at runtime is
the same: deterministic graphs do not call the LLM for routing, so AINL and
a competent runner converge on LLM token spend.

WHAT THIS BENCHMARK *DOES* CLAIM
--------------------------------
The shipped result is the small honest one: AINL is ~1× to ~3× more
token-dense in source AT EQUAL audit posture (zero audit features). When
the baseline-B implementation adds the audit / observability surface a
production deployment actually needs, AINL's source LOC vs production_grade
Python drops to a measurable multiple (~3–4×) — but the audit-checklist
score is finally comparable.

WHAT THIS BENCHMARK *DOES NOT* CLAIM
------------------------------------
- That AINL beats a competent hand-written runner on tokens. It does not.
- That the production_grade Python is "the right answer" for ops orgs that
  already operate competent runners. For those orgs the cost story is a
  wash; the audit / multi-target-emit story is where AINL has to win or
  lose on its own.

OUTPUT
------
tooling/benchmark_vs_hand_runner.json   — machine-readable results
stdout                                  — human-readable summary table
optional BENCHMARK.md section update    — between
                                          <!-- benchmark:vs-hand-runner-begin -->
                                          <!-- benchmark:vs-hand-runner-end -->

USAGE
-----
    python3 scripts/benchmark_vs_hand_runner.py
    python3 scripts/benchmark_vs_hand_runner.py --output results/runner.json
    python3 scripts/benchmark_vs_hand_runner.py --no-benchmark-md
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import statistics
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

try:
    import tiktoken  # type: ignore[import-not-found]

    _ENC = tiktoken.get_encoding("cl100k_base")

    def count_tokens(text: str) -> int:
        return len(_ENC.encode(text))

    TOKENIZER = "tiktoken cl100k_base (GPT-4o)"

except ImportError:  # pragma: no cover — graceful degradation
    print("WARNING: tiktoken not installed; falling back to len(text)//4 approximation.",
          file=sys.stderr)

    def count_tokens(text: str) -> int:  # type: ignore[misc]
        return max(1, len(text) // 4)

    TOKENIZER = "fallback len(text)//4 (tiktoken unavailable)"


# ---------------------------------------------------------------------------
# Workload definitions
# ---------------------------------------------------------------------------

WORKLOADS = [
    {
        "name": "enterprise_monitor",
        "description": "Infrastructure health monitor (HTTP poll, IR routing, 0–1 LLM calls, cache state)",
        "ainl_path": "examples/benchmark/enterprise_monitor.ainl",
        "competent_python_path": "benchmarks/handwritten_baselines/authoring_density/enterprise_monitor.py",
        "production_python_path": "benchmarks/handwritten_baselines/production/enterprise_monitor.py",
    },
    {
        "name": "support_ticket_router",
        "description": "Support ticket triage (LLM classify × 2, IR routing × 4, LLM draft)",
        "ainl_path": "examples/workflows/support_ticket_router.ainl",
        "competent_python_path": "benchmarks/handwritten_baselines/authoring_density/support_ticket_router.py",
        "production_python_path": "benchmarks/handwritten_baselines/production/support_ticket_router.py",
    },
    {
        "name": "data_pipeline",
        "description": "Multi-source order processing (8 IR branches, 5 adapters, 0–1 LLM calls)",
        "ainl_path": "examples/workflows/data_pipeline.ainl",
        "competent_python_path": "benchmarks/handwritten_baselines/authoring_density/data_pipeline_competent.py",
        "production_python_path": "benchmarks/handwritten_baselines/production/data_pipeline.py",
    },
]


# 8-row audit checklist — every Python implementation is scored against this
# matrix via the `__benchmark_audit_checklist__` module constant. AINL source
# scoring is hard-coded below (see `AINL_AUDIT_DEFAULTS`) and reflects the
# guarantees the runtime + compiler enforce by construction.
AUDIT_ROWS = [
    "event_hash_chain",
    "per_step_inputs",
    "per_step_outputs",
    "adapter_args",
    "approval_gates",
    "config_snapshot",
    "replayable",
    "regulatory_grade",
]


# AINL gets these for free because the runtime + audit_trail emission writes
# every step as a hash-chained JSONL event with per-step inputs/outputs and
# adapter args. Approval gates are exposed via the AINL kernel approval API.
# `replayable` is True because the IR + a frame deterministically replay the
# same graph. `regulatory_grade` is conservatively False — that's a
# certification claim that requires more than a JSONL emitter, and we won't
# claim it without an external audit.
AINL_AUDIT_DEFAULTS: dict[str, bool] = {
    "event_hash_chain":   True,   # ainl audit verify-jsonl event_hash chain
    "per_step_inputs":    True,   # every R/X step records inputs in audit JSONL
    "per_step_outputs":   True,   # every R/X step records outputs in audit JSONL
    "adapter_args":       True,   # IR captures adapter args; JSONL records resolved values
    "approval_gates":     True,   # kernel approval API gates HumanRequired steps
    "config_snapshot":    True,   # frame + IR + adapter config dumped at start
    "replayable":         True,   # IR + frame = deterministic replay
    "regulatory_grade":   False,  # no SOC2 / HIPAA attestation yet — open audit on the tracker
}


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class ImplementationMeasurement:
    style: str                       # "ainl" | "competent_python" | "production_python"
    path: str
    tokens: int
    loc: int
    audit_checklist: dict[str, bool]
    audit_score: int                 # count of True rows out of 8


@dataclass
class WorkloadResult:
    name: str
    description: str
    implementations: list[ImplementationMeasurement] = field(default_factory=list)


@dataclass
class BenchmarkReport:
    methodology: str
    tokenizer: str
    timestamp_utc: str
    workloads: list[WorkloadResult]
    aggregate_competent_token_ratio_mean: float
    aggregate_competent_loc_ratio_mean: float
    aggregate_production_token_ratio_mean: float
    aggregate_production_loc_ratio_mean: float
    aggregate_competent_audit_score_mean: float
    aggregate_production_audit_score_mean: float
    aggregate_ainl_audit_score: int
    notes: str


# ---------------------------------------------------------------------------
# Audit-checklist extractor
# ---------------------------------------------------------------------------

def extract_audit_checklist_from_python(src: str) -> dict[str, bool]:
    """Parse a Python source file and return the __benchmark_audit_checklist__
    constant, or all-False if absent / malformed. We use AST so a comment-out
    of the constant has no effect on scoring."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return {row: False for row in AUDIT_ROWS}

    for node in ast.walk(tree):
        target_name: Optional[str] = None
        value_node: Optional[ast.AST] = None
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__benchmark_audit_checklist__":
                    target_name = target.id
                    value_node = node.value
                    break
        elif isinstance(node, ast.AnnAssign):
            if (
                isinstance(node.target, ast.Name)
                and node.target.id == "__benchmark_audit_checklist__"
                and node.value is not None
            ):
                target_name = node.target.id
                value_node = node.value

        if target_name is not None and value_node is not None:
            try:
                value = ast.literal_eval(value_node)
            except (ValueError, SyntaxError):
                return {row: False for row in AUDIT_ROWS}
            if isinstance(value, dict):
                return {row: bool(value.get(row, False)) for row in AUDIT_ROWS}
    return {row: False for row in AUDIT_ROWS}


# ---------------------------------------------------------------------------
# Per-file measurement
# ---------------------------------------------------------------------------

def measure_path(
    *,
    style: str,
    abs_path: Path,
    audit_checklist: Optional[dict[str, bool]] = None,
) -> ImplementationMeasurement:
    src = abs_path.read_text(encoding="utf-8")
    tokens = count_tokens(src)
    loc = len(src.splitlines())

    if audit_checklist is None:
        if abs_path.suffix == ".py":
            audit_checklist = extract_audit_checklist_from_python(src)
        else:
            audit_checklist = {row: False for row in AUDIT_ROWS}

    return ImplementationMeasurement(
        style=style,
        path=str(abs_path.relative_to(ROOT)),
        tokens=tokens,
        loc=loc,
        audit_checklist=audit_checklist,
        audit_score=sum(1 for v in audit_checklist.values() if v),
    )


def measure_workload(workload: dict) -> WorkloadResult:
    ainl_path = ROOT / workload["ainl_path"]
    competent_path = ROOT / workload["competent_python_path"]
    production_path = ROOT / workload["production_python_path"]

    for label, p in [("ainl", ainl_path), ("competent_python", competent_path), ("production_python", production_path)]:
        if not p.exists():
            raise FileNotFoundError(f"workload '{workload['name']}' is missing the {label} file at {p}")

    return WorkloadResult(
        name=workload["name"],
        description=workload["description"],
        implementations=[
            measure_path(style="ainl", abs_path=ainl_path, audit_checklist=AINL_AUDIT_DEFAULTS),
            measure_path(style="competent_python", abs_path=competent_path),
            measure_path(style="production_python", abs_path=production_path),
        ],
    )


# ---------------------------------------------------------------------------
# Aggregates
# ---------------------------------------------------------------------------

def _ratio(numerator: float, denominator: float) -> float:
    return round(numerator / denominator, 2) if denominator > 0 else 0.0


def build_report(workloads: list[WorkloadResult]) -> BenchmarkReport:
    competent_token_ratios: list[float] = []
    competent_loc_ratios: list[float] = []
    production_token_ratios: list[float] = []
    production_loc_ratios: list[float] = []
    competent_audit_scores: list[int] = []
    production_audit_scores: list[int] = []
    ainl_audit_scores: set[int] = set()

    for wl in workloads:
        by_style = {impl.style: impl for impl in wl.implementations}
        ainl = by_style["ainl"]
        competent = by_style["competent_python"]
        production = by_style["production_python"]

        ainl_audit_scores.add(ainl.audit_score)
        competent_audit_scores.append(competent.audit_score)
        production_audit_scores.append(production.audit_score)

        competent_token_ratios.append(_ratio(competent.tokens, ainl.tokens))
        competent_loc_ratios.append(_ratio(competent.loc, ainl.loc))
        production_token_ratios.append(_ratio(production.tokens, ainl.tokens))
        production_loc_ratios.append(_ratio(production.loc, ainl.loc))

    assert len(ainl_audit_scores) == 1, (
        f"AINL audit score should be identical across workloads (driven by AINL_AUDIT_DEFAULTS) "
        f"— got {ainl_audit_scores}"
    )
    ainl_audit_score = ainl_audit_scores.pop()

    return BenchmarkReport(
        methodology=(
            "Static measurement of three sources per workload (AINL .ainl, competent_python "
            "baseline-B .py, production_grade baseline-B .py). Token counts use tiktoken "
            "cl100k_base (GPT-4o tokeniser); LOC is raw line count including comments and "
            "blank lines. Audit checklist scores read the `__benchmark_audit_checklist__` "
            "constant via ast.literal_eval; missing/malformed constants score 0/8. "
            "AINL audit posture is hard-coded against the AINL runtime audit-trail "
            "guarantees (see AINL_AUDIT_DEFAULTS in this script). "
            "No live LLM calls; results are fully reproducible from source text."
        ),
        tokenizer=TOKENIZER,
        timestamp_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        workloads=workloads,
        aggregate_competent_token_ratio_mean=round(statistics.mean(competent_token_ratios), 2),
        aggregate_competent_loc_ratio_mean=round(statistics.mean(competent_loc_ratios), 2),
        aggregate_production_token_ratio_mean=round(statistics.mean(production_token_ratios), 2),
        aggregate_production_loc_ratio_mean=round(statistics.mean(production_loc_ratios), 2),
        aggregate_competent_audit_score_mean=round(statistics.mean(competent_audit_scores), 2),
        aggregate_production_audit_score_mean=round(statistics.mean(production_audit_scores), 2),
        aggregate_ainl_audit_score=ainl_audit_score,
        notes=(
            "Source: docs/competitive/VS_HAND_WRITTEN_RUNNER.md and §9 of "
            "docs/CLAIMS_AND_EVIDENCE.md (baseline-B comparison row). "
            "The 'production_grade' Python is a measurement skeleton, not a deployed "
            "worker — see benchmarks/handwritten_baselines/production/README.md for the "
            "explicit caveats. Real production deployments add another 200–500 LOC for "
            "OTEL exporters / dead-letter queues / secret rotation / liveness probes, "
            "which this benchmark does NOT account for — meaning it UNDERSTATES the LOC "
            "delta vs AINL on the audit / observability axis."
        ),
    )


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------

def render_markdown(report: BenchmarkReport) -> str:
    out: list[str] = [
        "## AINL vs hand-written Python runner — measured (baseline B)",
        "",
        f"_Tokeniser: **{report.tokenizer}** · Timestamp: **{report.timestamp_utc}**_",
        "",
        "**Scope.** Three workloads × three implementations each: AINL source,",
        "`competent_python` baseline-B (~150–250 LOC, single-file readable, no retry",
        "wrapper, no audit log), and `production_grade` baseline-B (~280–470 LOC, with",
        "retry/backoff/circuit-breaker/structured-logging/hash-chained-JSONL).",
        "All Python files are **measurement skeletons** — see",
        "[`benchmarks/handwritten_baselines/production/README.md`](../benchmarks/handwritten_baselines/production/README.md).",
        "",
        "### Per-workload measurements",
        "",
        "| Workload | Style | Tokens | LOC | Audit 0–8 | Token ratio vs AINL | LOC ratio vs AINL |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for wl in report.workloads:
        by_style = {impl.style: impl for impl in wl.implementations}
        ainl = by_style["ainl"]
        for style in ("ainl", "competent_python", "production_python"):
            impl = by_style[style]
            tok_ratio = "—" if style == "ainl" else f"{_ratio(impl.tokens, ainl.tokens):.2f}×"
            loc_ratio = "—" if style == "ainl" else f"{_ratio(impl.loc, ainl.loc):.2f}×"
            out.append(
                f"| {wl.name if style == 'ainl' else ''} | `{style}` | "
                f"{impl.tokens} | {impl.loc} | {impl.audit_score}/8 | {tok_ratio} | {loc_ratio} |"
            )

    out += [
        "",
        "### Aggregate (mean across workloads)",
        "",
        "| Comparison | Tokens vs AINL | LOC vs AINL | Audit score |",
        "|---|---:|---:|---:|",
        f"| AINL (reference) | 1.00× | 1.00× | **{report.aggregate_ainl_audit_score}/8** |",
        f"| competent_python | **{report.aggregate_competent_token_ratio_mean}×** | "
        f"**{report.aggregate_competent_loc_ratio_mean}×** | "
        f"{report.aggregate_competent_audit_score_mean}/8 |",
        f"| production_grade | **{report.aggregate_production_token_ratio_mean}×** | "
        f"**{report.aggregate_production_loc_ratio_mean}×** | "
        f"{report.aggregate_production_audit_score_mean}/8 |",
        "",
        "### Audit checklist — by row",
        "",
        "| Row | AINL | competent (mean) | production (mean) |",
        "|---|:--:|:--:|:--:|",
    ]
    for row in AUDIT_ROWS:
        ainl_v = "✓" if AINL_AUDIT_DEFAULTS[row] else "—"
        comp = sum(1 for wl in report.workloads
                   for impl in wl.implementations
                   if impl.style == "competent_python" and impl.audit_checklist.get(row))
        prod = sum(1 for wl in report.workloads
                   for impl in wl.implementations
                   if impl.style == "production_python" and impl.audit_checklist.get(row))
        n = len(report.workloads)
        out.append(f"| `{row}` | {ainl_v} | {comp}/{n} | {prod}/{n} |")

    out += [
        "",
        "### Interpretation",
        "",
        "- **Tokens / LOC:** AINL is not the lowest-source-size implementation. Competent",
        "  hand-written Python is. Production-grade Python — by virtue of carrying its own",
        "  retry, audit, and observability surface — costs roughly 3–4× more LOC than AINL.",
        "- **Audit posture:** the AINL row scores 7/8 because the runtime emits a",
        "  hash-chained JSONL trail of every step, the IR + frame deterministically replay",
        "  the program, and the kernel approval API gates `HumanRequired` steps. The 8th",
        "  row (`regulatory_grade`) requires an external SOC2 / HIPAA attestation we do",
        "  not yet have. Competent baseline-B Python scores 0/8 by default. Production-",
        "  grade baseline-B Python ranges 5–6/8 — same audit shape, more LOC.",
        "- **Headline:** AINL's measurable win against a competent runner is *not* tokens.",
        "  It is the audit / replay / multi-target-emit surface that ships for free.",
        "",
        "### Caveats",
        "",
        report.notes,
    ]

    return "\n".join(out)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _main(output_path: Optional[Path], update_benchmark_md: bool) -> int:
    print("=== AINL vs Hand-Written Runner Benchmark ===\n")

    workloads: list[WorkloadResult] = []
    for w in WORKLOADS:
        wl = measure_workload(w)
        workloads.append(wl)
        ainl = next(impl for impl in wl.implementations if impl.style == "ainl")
        comp = next(impl for impl in wl.implementations if impl.style == "competent_python")
        prod = next(impl for impl in wl.implementations if impl.style == "production_python")
        print(
            f"  {wl.name:24s} "
            f"AINL {ainl.tokens:4d}t/{ainl.loc:3d}L (audit {ainl.audit_score}/8)  "
            f"competent {comp.tokens:4d}t/{comp.loc:3d}L ({_ratio(comp.tokens, ainl.tokens):.2f}× toks, "
            f"audit {comp.audit_score}/8)  "
            f"production {prod.tokens:4d}t/{prod.loc:3d}L ({_ratio(prod.tokens, ainl.tokens):.2f}× toks, "
            f"audit {prod.audit_score}/8)"
        )

    report = build_report(workloads)
    print(
        f"\n  Aggregate competent token ratio:  {report.aggregate_competent_token_ratio_mean}×  "
        f"  LOC: {report.aggregate_competent_loc_ratio_mean}×"
    )
    print(
        f"  Aggregate production token ratio: {report.aggregate_production_token_ratio_mean}×  "
        f"  LOC: {report.aggregate_production_loc_ratio_mean}×"
    )
    print(
        f"  AINL audit: {report.aggregate_ainl_audit_score}/8   "
        f"competent audit (mean): {report.aggregate_competent_audit_score_mean}/8   "
        f"production audit (mean): {report.aggregate_production_audit_score_mean}/8"
    )

    out_path = output_path or ROOT / "tooling" / "benchmark_vs_hand_runner.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "methodology": report.methodology,
                "tokenizer": report.tokenizer,
                "timestamp_utc": report.timestamp_utc,
                "audit_rows": AUDIT_ROWS,
                "ainl_audit_defaults": AINL_AUDIT_DEFAULTS,
                "aggregate": {
                    "competent_token_ratio_mean":   report.aggregate_competent_token_ratio_mean,
                    "competent_loc_ratio_mean":     report.aggregate_competent_loc_ratio_mean,
                    "production_token_ratio_mean":  report.aggregate_production_token_ratio_mean,
                    "production_loc_ratio_mean":    report.aggregate_production_loc_ratio_mean,
                    "competent_audit_score_mean":   report.aggregate_competent_audit_score_mean,
                    "production_audit_score_mean":  report.aggregate_production_audit_score_mean,
                    "ainl_audit_score":             report.aggregate_ainl_audit_score,
                },
                "workloads": [
                    {
                        "name": wl.name,
                        "description": wl.description,
                        "implementations": [asdict(impl) for impl in wl.implementations],
                    }
                    for wl in workloads
                ],
                "notes": report.notes,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\n  Results written to {out_path.relative_to(ROOT)}")

    if update_benchmark_md:
        md_path = ROOT / "BENCHMARK.md"
        if md_path.exists():
            md = md_path.read_text(encoding="utf-8")
            marker_start = "<!-- benchmark:vs-hand-runner-begin -->"
            marker_end = "<!-- benchmark:vs-hand-runner-end -->"
            section = f"{marker_start}\n{render_markdown(report)}\n{marker_end}"
            if marker_start in md and marker_end in md:
                md = re.sub(
                    f"{re.escape(marker_start)}.*?{re.escape(marker_end)}",
                    section,
                    md,
                    flags=re.DOTALL,
                )
            else:
                md = md.rstrip() + f"\n\n{section}\n"
            md_path.write_text(md, encoding="utf-8")
            print(f"  BENCHMARK.md updated (vs-hand-runner section).")

    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, default=None, help="JSON output path")
    p.add_argument("--no-benchmark-md", action="store_true",
                   help="skip rewriting the BENCHMARK.md section")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    sys.exit(_main(args.output, not args.no_benchmark_md))
