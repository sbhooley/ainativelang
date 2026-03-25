#!/usr/bin/env python3
"""Runner for AINL intelligence programs (context injection, summarizer, consolidation).

Usage:
    python3 run_intelligence.py <program>  [--trace] [--dry-run]

Programs:
    context    — Token-aware startup context injection
    summarizer — Proactive session summarizer (LLM-backed)
    consolidation — Memory consolidation (keyword-based)
    all        — Run all three in order

Examples:
    python3 run_intelligence.py context
    python3 run_intelligence.py summarizer --trace
    python3 run_intelligence.py all
"""
import sys
import os
import json
import logging
import time

# Ensure project root is on path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from compiler_v2 import AICodeCompiler
from runtime.engine import RuntimeEngine
from adapters.openclaw_integration import openclaw_monitor_registry
from tooling.intelligence_budget_hydrate import hydrate_budget_cache_from_rolling_memory

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger('ainl.intelligence')

PROGRAMS = {
    'context': 'intelligence/token_aware_startup_context.lang',
    'summarizer': 'intelligence/proactive_session_summarizer.lang',
    'consolidation': 'intelligence/memory_consolidation.lang',
    'continuity': 'intelligence/session_continuity_enhanced.lang',
}


def compile_and_run(program_path: str, trace: bool = False, dry_run: bool = False) -> dict:
    """Compile an AINL program and execute it."""
    full_path = os.path.join(PROJECT_ROOT, program_path)
    logger.info(f'Loading: {program_path}')

    with open(full_path) as f:
        source = f.read()

    # Compile
    compiler = AICodeCompiler()
    ir = compiler.compile(source, emit_graph=True)

    errors = ir.get('errors', [])
    if errors:
        logger.error(f'Compilation errors: {errors}')
        return {'status': 'compile_error', 'errors': errors}

    warnings = ir.get('warnings', [])
    if warnings:
        # Filter out lint warnings (not real issues)
        real_warnings = [w for w in warnings if isinstance(w, dict) and 'CANONICAL' not in w.get('code', '')]
        if real_warnings:
            logger.warning(f'Compilation warnings: {len(real_warnings)}')

    if dry_run:
        labels = list(ir.get('labels', {}).keys())
        logger.info(f'Dry run — labels: {labels}')
        return {'status': 'dry_run', 'labels': labels}

    # Set up adapters (registry already has all allowed adapters)
    registry = openclaw_monitor_registry()
    hydrate = hydrate_budget_cache_from_rolling_memory(registry)
    if hydrate.get("ok") and not hydrate.get("skipped"):
        logger.info("Rolling budget → cache hydrate: %s", hydrate)
    elif hydrate.get("skipped"):
        logger.debug("Rolling budget hydrate skipped: %s", hydrate.get("reason"))
    elif not hydrate.get("ok"):
        logger.warning("Rolling budget hydrate failed: %s", hydrate)

    engine = RuntimeEngine(ir, adapters=registry, trace=trace)

    # Run from label 0
    start = time.time()
    try:
        result = engine.run_label('0')
        elapsed = time.time() - start
        logger.info(f'Completed in {elapsed:.2f}s — result: {result}')
        return {'status': 'ok', 'result': result, 'elapsed_s': round(elapsed, 2), 'budget_hydrate': hydrate}
    except Exception as e:
        elapsed = time.time() - start
        logger.error(f'Runtime error after {elapsed:.2f}s: {e}')
        return {'status': 'error', 'error': str(e), 'elapsed_s': round(elapsed, 2), 'budget_hydrate': hydrate}


def main():
    args = sys.argv[1:]
    trace = '--trace' in args
    dry_run = '--dry-run' in args
    args = [a for a in args if not a.startswith('--')]

    if not args:
        print(__doc__)
        sys.exit(1)

    program = args[0].lower()

    if program == 'all':
        results = {}
        for name in ['context', 'consolidation', 'summarizer']:
            logger.info(f'\n{"="*60}\nRunning: {name}\n{"="*60}')
            results[name] = compile_and_run(PROGRAMS[name], trace=trace, dry_run=dry_run)
        print(json.dumps(results, indent=2, default=str))
    elif program in PROGRAMS:
        result = compile_and_run(PROGRAMS[program], trace=trace, dry_run=dry_run)
        print(json.dumps(result, indent=2, default=str))
    else:
        print(f'Unknown program: {program}')
        print(f'Available: {", ".join(PROGRAMS.keys())}, all')
        sys.exit(1)


if __name__ == '__main__':
    main()
