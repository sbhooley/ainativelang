#!/usr/bin/env python3
"""Corpus mining for strict-valid AINL examples.

Analyzes strict-valid AINL files to build family indexes and reverse-prompt fixtures.
Used by the wizard to provide step-local examples and for evaluation.

Usage:
    python -m tooling.corpus_mining generate-family-index
    python -m tooling.corpus_mining generate-reverse-fixtures
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).parent.parent
ARTIFACT_PROFILES = REPO_ROOT / "tooling" / "artifact_profiles.json"
CORPUS_DIR = REPO_ROOT / "corpus"
FAMILY_INDEX_PATH = CORPUS_DIR / "strict_valid_family_index.json"
REVERSE_FIXTURES_PATH = CORPUS_DIR / "reverse_prompt_fixtures.json"


@dataclass
class ExampleMetadata:
    """Metadata extracted from a strict-valid AINL file."""

    path: str
    adapters: list[str] = field(default_factory=list)
    adapter_verbs: dict[str, list[str]] = field(default_factory=dict)
    graph_name: str = ""
    inputs: list[str] = field(default_factory=list)
    has_branching: bool = False
    has_loop: bool = False
    has_error_handling: bool = False
    line_count: int = 0
    complexity_tier: str = "minimal"
    family: str = "core"
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "adapters": self.adapters,
            "adapter_verbs": self.adapter_verbs,
            "graph_name": self.graph_name,
            "inputs": self.inputs,
            "has_branching": self.has_branching,
            "has_loop": self.has_loop,
            "has_error_handling": self.has_error_handling,
            "line_count": self.line_count,
            "complexity_tier": self.complexity_tier,
            "family": self.family,
            "description": self.description,
        }


def load_strict_valid_paths() -> list[str]:
    """Load paths from artifact_profiles.json strict-valid lists."""
    if not ARTIFACT_PROFILES.exists():
        return []
    data = json.loads(ARTIFACT_PROFILES.read_text())
    paths = []
    examples = data.get("examples", {})
    if "strict-valid" in examples:
        paths.extend(examples["strict-valid"])
    corpus = data.get("corpus_examples", {})
    if "strict-valid" in corpus:
        paths.extend(corpus["strict-valid"])
    return paths


def extract_adapters_from_source(source: str) -> tuple[list[str], dict[str, list[str]]]:
    """Extract adapter names and verbs from AINL source."""
    adapters: set[str] = set()
    adapter_verbs: dict[str, set[str]] = {}

    r_pattern = re.compile(r"R\s+(\w+)\.(\w+)")
    for m in r_pattern.finditer(source):
        adapter, verb = m.group(1), m.group(2)
        adapters.add(adapter)
        if adapter not in adapter_verbs:
            adapter_verbs[adapter] = set()
        adapter_verbs[adapter].add(verb)

    compact_pattern = re.compile(r"(\w+)\s*=\s*(\w+)\.(\w+)")
    for m in compact_pattern.finditer(source):
        adapter, verb = m.group(2), m.group(3)
        adapters.add(adapter)
        if adapter not in adapter_verbs:
            adapter_verbs[adapter] = set()
        adapter_verbs[adapter].add(verb)

    bare_call_pattern = re.compile(r"^\s+(\w+)\.(\w+)\s+", re.MULTILINE)
    for m in bare_call_pattern.finditer(source):
        adapter, verb = m.group(1), m.group(2)
        if adapter not in {"in", "out", "if", "err", "call", "config", "state"}:
            adapters.add(adapter)
            if adapter not in adapter_verbs:
                adapter_verbs[adapter] = set()
            adapter_verbs[adapter].add(verb)

    return sorted(adapters), {k: sorted(v) for k, v in adapter_verbs.items()}


def extract_graph_name(source: str) -> str:
    """Extract graph name from S header or compact header."""
    s_pattern = re.compile(r"^S\s+(\w+)", re.MULTILINE)
    m = s_pattern.search(source)
    if m:
        return m.group(1)

    compact_pattern = re.compile(r"^(\w+):\s*$", re.MULTILINE)
    m = compact_pattern.search(source)
    if m:
        return m.group(1)

    return ""


def extract_inputs(source: str) -> list[str]:
    """Extract input fields from compact in: or X var ctx.var patterns."""
    inputs: list[str] = []

    in_pattern = re.compile(r"^\s*in:\s*(.+)$", re.MULTILINE)
    m = in_pattern.search(source)
    if m:
        inputs.extend(m.group(1).split())

    x_pattern = re.compile(r"^X\s+(\w+)\s+ctx\.(\w+)", re.MULTILINE)
    for m in x_pattern.finditer(source):
        inputs.append(m.group(2))

    return list(dict.fromkeys(inputs))


def extract_description(source: str) -> str:
    """Extract description from header comment."""
    lines = source.strip().split("\n")
    for line in lines[:10]:
        if line.startswith("#") and not line.startswith("# frame:"):
            desc = line.lstrip("#").strip()
            if desc and len(desc) > 10:
                return desc[:200]
    return ""


def determine_family(adapters: list[str], path: str) -> str:
    """Determine the family based on adapters used and path."""
    path_lower = path.lower()

    if "http" in adapters or "http" in path_lower:
        if "payment" in path_lower or "machine" in path_lower:
            return "http_payment"
        return "http"
    if "browser" in adapters or "browser" in path_lower:
        return "browser"
    if "fs" in adapters:
        return "filesystem"
    if "cache" in adapters:
        return "cache"
    if "memory" in adapters:
        return "memory"
    if "queue" in adapters:
        return "queue"
    if "solana" in adapters or "solana" in path_lower:
        return "blockchain"
    if "llm" in adapters or any(a.startswith("llm") for a in adapters):
        return "llm"
    if "web" in adapters:
        return "web"
    if "crm" in adapters or "crm" in path_lower:
        return "crm"
    if "monitor" in path_lower or "cron" in path_lower:
        return "monitoring"
    if "scraper" in path_lower:
        return "scraper"
    if "rag" in path_lower:
        return "rag"

    return "core"


def determine_complexity(
    line_count: int,
    adapter_count: int,
    has_branching: bool,
    has_loop: bool,
    has_error: bool,
) -> str:
    """Determine complexity tier."""
    score = 0
    if line_count > 50:
        score += 2
    elif line_count > 20:
        score += 1

    if adapter_count > 3:
        score += 2
    elif adapter_count > 1:
        score += 1

    if has_branching:
        score += 1
    if has_loop:
        score += 2
    if has_error:
        score += 1

    if score >= 5:
        return "advanced"
    elif score >= 2:
        return "intermediate"
    return "minimal"


def analyze_file(path_str: str) -> ExampleMetadata | None:
    """Analyze a single AINL file and extract metadata."""
    full_path = REPO_ROOT / path_str
    if not full_path.exists():
        return None

    try:
        source = full_path.read_text()
    except Exception:
        return None

    adapters, adapter_verbs = extract_adapters_from_source(source)
    graph_name = extract_graph_name(source)
    inputs = extract_inputs(source)
    description = extract_description(source)

    has_branching = bool(re.search(r"\bIf\b|\bif\s+\w+", source))
    has_loop = bool(re.search(r"\bWhile\b|\bLoop\b|while\s*\(", source, re.IGNORECASE))
    has_error = bool(re.search(r"\berr\b|\bErr\b|->L_error|->L_err", source))

    line_count = len(source.strip().split("\n"))
    family = determine_family(adapters, path_str)
    complexity = determine_complexity(
        line_count, len(adapters), has_branching, has_loop, has_error
    )

    return ExampleMetadata(
        path=path_str,
        adapters=adapters,
        adapter_verbs=adapter_verbs,
        graph_name=graph_name,
        inputs=inputs,
        has_branching=has_branching,
        has_loop=has_loop,
        has_error_handling=has_error,
        line_count=line_count,
        complexity_tier=complexity,
        family=family,
        description=description,
    )


def generate_family_index() -> dict[str, Any]:
    """Generate family index from all strict-valid examples."""
    paths = load_strict_valid_paths()

    families: dict[str, list[dict[str, Any]]] = {}
    by_adapter: dict[str, list[str]] = {}
    by_complexity: dict[str, list[str]] = {}
    all_examples: list[dict[str, Any]] = []

    for path_str in paths:
        meta = analyze_file(path_str)
        if not meta:
            continue

        all_examples.append(meta.to_dict())

        if meta.family not in families:
            families[meta.family] = []
        families[meta.family].append(meta.to_dict())

        for adapter in meta.adapters:
            if adapter not in by_adapter:
                by_adapter[adapter] = []
            by_adapter[adapter].append(path_str)

        if meta.complexity_tier not in by_complexity:
            by_complexity[meta.complexity_tier] = []
        by_complexity[meta.complexity_tier].append(path_str)

    return {
        "schema_version": "1.0",
        "generated_from": "artifact_profiles.json",
        "total_examples": len(all_examples),
        "families": families,
        "by_adapter": by_adapter,
        "by_complexity": by_complexity,
        "all_examples": all_examples,
    }


def generate_reverse_prompt_fixtures() -> dict[str, Any]:
    """Generate reverse prompt fixtures for evaluation.

    These fixtures map natural language goals to expected AINL patterns,
    allowing evaluation of how well the wizard guides users.
    """
    paths = load_strict_valid_paths()
    fixtures: list[dict[str, Any]] = []

    for path_str in paths:
        meta = analyze_file(path_str)
        if not meta:
            continue

        full_path = REPO_ROOT / path_str
        try:
            source = full_path.read_text()
        except Exception:
            continue

        goal = _infer_natural_language_goal(meta, path_str)
        expected_adapters = meta.adapters
        expected_verbs = []
        for adapter, verbs in meta.adapter_verbs.items():
            for verb in verbs:
                expected_verbs.append(f"{adapter}.{verb}")

        fixtures.append({
            "id": Path(path_str).stem,
            "path": path_str,
            "family": meta.family,
            "complexity": meta.complexity_tier,
            "natural_language_goal": goal,
            "expected_adapters": expected_adapters,
            "expected_verbs": expected_verbs[:10],
            "expected_inputs": meta.inputs,
            "has_branching": meta.has_branching,
            "source_snippet": _get_source_snippet(source),
        })

    return {
        "schema_version": "1.0",
        "fixture_count": len(fixtures),
        "fixtures": fixtures,
    }


def _infer_natural_language_goal(meta: ExampleMetadata, path: str) -> str:
    """Infer a natural language goal from metadata and path."""
    if meta.description:
        return meta.description

    name = Path(path).stem.replace("_", " ").replace("-", " ")

    family_goals = {
        "http": f"Make HTTP requests: {name}",
        "http_payment": f"HTTP payment flow: {name}",
        "browser": f"Browser automation: {name}",
        "filesystem": f"File operations: {name}",
        "cache": f"Caching workflow: {name}",
        "memory": f"Memory operations: {name}",
        "queue": f"Queue messaging: {name}",
        "blockchain": f"Blockchain/Solana: {name}",
        "llm": f"LLM integration: {name}",
        "web": f"Web scraping/fetching: {name}",
        "crm": f"CRM operations: {name}",
        "monitoring": f"Monitoring/alerting: {name}",
        "scraper": f"Web scraper: {name}",
        "rag": f"RAG pipeline: {name}",
        "core": f"Workflow: {name}",
    }

    return family_goals.get(meta.family, f"Create workflow: {name}")


def _get_source_snippet(source: str) -> str:
    """Get a short snippet of the source for reference."""
    lines = source.strip().split("\n")
    snippet_lines = []
    for line in lines[:15]:
        if line.strip() and not line.strip().startswith("#"):
            snippet_lines.append(line)
        if len(snippet_lines) >= 8:
            break
    return "\n".join(snippet_lines)


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: corpus_mining.py [generate-family-index|generate-reverse-fixtures]")
        return 1

    CORPUS_DIR.mkdir(parents=True, exist_ok=True)

    cmd = sys.argv[1]
    if cmd == "generate-family-index":
        index = generate_family_index()
        FAMILY_INDEX_PATH.write_text(json.dumps(index, indent=2))
        print(f"Generated {FAMILY_INDEX_PATH} with {index['total_examples']} examples")
        print(f"Families: {list(index['families'].keys())}")
        return 0

    elif cmd == "generate-reverse-fixtures":
        fixtures = generate_reverse_prompt_fixtures()
        REVERSE_FIXTURES_PATH.write_text(json.dumps(fixtures, indent=2))
        print(f"Generated {REVERSE_FIXTURES_PATH} with {fixtures['fixture_count']} fixtures")
        return 0

    else:
        print(f"Unknown command: {cmd}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
