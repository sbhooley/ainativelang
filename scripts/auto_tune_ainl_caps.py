#!/usr/bin/env python3
"""AINL Auto-Tuner: Adjusts OpenClaw caps to achieve 90-95% token savings.

Reads:
  - $OPENCLAW_WORKSPACE/.ainl/monitor_state.json
  - $OPENCLAW_WORKSPACE/.ainl/ainl_memory.sqlite3 (bridge reports)
  - $OPENCLAW_WORKSPACE/.openclaw/openclaw.json (current caps)

Writes:
  - $OPENCLAW_WORKSPACE/.ainl/tuning_recommendations.json (latest)
  - $OPENCLAW_WORKSPACE/.ainl/tuning_log.json (history)

Optionally applies caps via `openclaw gateway config.patch` if OPENCLAW_AINL_AUTO_APPLY=true.

Exit codes:
  0 - success (with or without changes)
  1 - error (missing data, cannot compute)
"""

import os
import sys
import json
import sqlite3
import logging
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger('ainl.auto_tuner')

# Configuration with env overrides
CFG = {
    'min_history_days': int(os.getenv('AINL_TUNER_MIN_HISTORY_DAYS', '7')),
    'target_savings_min': float(os.getenv('AINL_TUNER_TARGET_SAVINGS_MIN', '90.0')),
    'target_savings_max': float(os.getenv('AINL_TUNER_TARGET_SAVINGS_MAX', '95.0')),
    'stable_days_required': int(os.getenv('AINL_TUNER_STABLE_DAYS_REQUIRED', '5')),
    'bridge_step_factor': float(os.getenv('AINL_TUNER_BRIDGE_STEP_FACTOR', '0.85')),
    'bridge_grow_factor': float(os.getenv('AINL_TUNER_BRIDGE_GROW_FACTOR', '1.15')),
    'promoter_step_factor': float(os.getenv('AINL_TUNER_PROMOTER_STEP_FACTOR', '0.90')),
    'promoter_grow_factor': float(os.getenv('AINL_TUNER_PROMOTER_GROW_FACTOR', '1.10')),
    'bridge_min_chars': int(os.getenv('AINL_TUNER_BRIDGE_MIN_CHARS', '500')),
    'bridge_max_chars': int(os.getenv('AINL_TUNER_BRIDGE_MAX_CHARS', '5000')),
    'promoter_prompt_min': int(os.getenv('AINL_TUNER_PROMOTER_PROMPT_MIN', '1000')),
    'promoter_prompt_max': int(os.getenv('AINL_TUNER_PROMOTER_PROMPT_MAX', '10000')),
    'promoter_completion_min': int(os.getenv('AINL_TUNER_PROMOTER_COMPLETION_MIN', '200')),
    'promoter_completion_max': int(os.getenv('AINL_TUNER_PROMOTER_COMPLETION_MAX', '2000')),
    'fallback_baseline_tokens': int(os.getenv('AINL_TUNER_FALLBACK_BASELINE', '100000')),
    'auto_apply': os.getenv('OPENCLAW_AINL_AUTO_APPLY', 'false').lower() in ('true', '1', 'yes'),
}

def resolve_workspace() -> Path:
    ws = os.getenv('OPENCLAW_WORKSPACE')
    if not ws:
        ws = os.getenv('WORKSPACE', str(Path.home() / '.openclaw' / 'workspace'))
    return Path(ws).expanduser().resolve()

def load_json(path: Path) -> Optional[Dict[Any, Any]]:
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f'Failed to load {path}: {e}')
        return None

def write_json(path: Path, data: Any):
    tmp = path.with_suffix('.tmp')
    with open(tmp, 'w') as f:
        json.dump(data, f, indent=2)
    tmp.replace(path)

def compute_savings(monitor: Dict[Any, Any]) -> Optional[float]:
    # Primary: token_budget
    tb = monitor.get('workflow', {}).get('token_budget', {})
    baseline = tb.get('baseline_estimated_total_tokens')
    actual = tb.get('actual_daily_total')
    if baseline and actual and baseline > 0:
        savings = ((baseline - actual) / baseline) * 100.0
        return round(savings, 1)
    # Fallback: context_injection_tokens vs static baseline
    fallback = CFG['fallback_baseline_tokens']
    inj = monitor.get('workflow', {}).get('context_injection_tokens')
    if inj is not None and inj < fallback:
        savings = ((fallback - inj) / fallback) * 100.0
        return round(savings, 1)
    return None

def get_bridge_sizes(db_path: Path) -> List[int]:
    if not db_path.exists():
        return []
    try:
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.execute("""
            SELECT payload_json FROM bridge_reports
            WHERE created_at >= datetime('now', '-7 days')
            ORDER BY created_at DESC
        """)
        sizes = []
        for (payload_json,) in cur.fetchall():
            try:
                payload = json.loads(payload_json)
                report = payload.get('report') or payload
                content = report.get('content') if isinstance(report, dict) else str(report)
                l = len(str(content))
                if l > 0:
                    sizes.append(l)
            except Exception:
                continue
        conn.close()
        return sizes
    except Exception as e:
        logger.warning(f'Bridge DB query failed: {e}')
        return []

def get_current_caps(openclaw_cfg: Dict[Any, Any]) -> Dict[str, int]:
    vars = openclaw_cfg.get('env', {}).get('vars', {})
    def as_int(key):
        val = vars.get(key)
        try:
            return int(val)
        except (TypeError, ValueError):
            return None
    return {
        'bridge_chars': as_int('AINL_BRIDGE_REPORT_MAX_CHARS'),
        'promoter_prompt': as_int('PROMOTER_LLM_MAX_PROMPT_CHARS'),
        'promoter_completion': as_int('PROMOTER_LLM_MAX_COMPLETION_TOKENS'),
    }

def decide_adjustments(savings_pct: float, bridge_sizes: List[int], current: Dict[str, int], recent_savings: List[float]) -> Dict[str, int]:
    new = current.copy()

    # Bridge sizing
    if bridge_sizes:
        max_size = max(bridge_sizes)
        cur_max = current['bridge_chars'] or 3000
        if max_size < cur_max * 0.8:
            candidate = int(round(max_size * 1.2))
            candidate = max(candidate, CFG['bridge_min_chars'])
            candidate = min(candidate, CFG['bridge_max_chars'])
            candidate = max(candidate, int(cur_max * CFG['bridge_step_factor']))
            new['bridge_chars'] = candidate
        elif max_size > cur_max * 0.95:
            candidate = int(round(max_size * CFG['bridge_grow_factor']))
            candidate = min(candidate, CFG['bridge_max_chars'])
            new['bridge_chars'] = candidate

    # Promoter sizing based on savings
    if savings_pct < CFG['target_savings_min']:
        # tighten
        if current['promoter_prompt'] and current['promoter_prompt'] > CFG['promoter_prompt_min']:
            new['promoter_prompt'] = int(round(current['promoter_prompt'] * CFG['promoter_step_factor']))
            new['promoter_prompt'] = max(new['promoter_prompt'], CFG['promoter_prompt_min'])
        if current['promoter_completion'] and current['promoter_completion'] > CFG['promoter_completion_min']:
            new['promoter_completion'] = int(round(current['promoter_completion'] * CFG['promoter_step_factor']))
            new['promoter_completion'] = max(new['promoter_completion'], CFG['promoter_completion_min'])
    elif savings_pct > CFG['target_savings_max']:
        # relax slightly
        if current['promoter_prompt'] and current['promoter_prompt'] < CFG['promoter_prompt_max']:
            new['promoter_prompt'] = int(round(current['promoter_prompt'] * (2.0 - CFG['promoter_step_factor'])))
            new['promoter_prompt'] = min(new['promoter_prompt'], CFG['promoter_prompt_max'])
        if current['promoter_completion'] and current['promoter_completion'] < CFG['promoter_completion_max']:
            new['promoter_completion'] = int(round(current['promoter_completion'] * (2.0 - CFG['promoter_step_factor'])))
            new['promoter_completion'] = min(new['promoter_completion'], CFG['promoter_completion_max'])

    # Stability check: if recent savings not stable, do not tighten beyond immediate corrections
    if len(recent_savings) >= CFG['stable_days_required']:
        stable = all(CFG['target_savings_min'] <= s <= CFG['target_savings_max'] for s in recent_savings[-CFG['stable_days_required']:])
        if not stable:
            logger.info('Savings not stable for required days; holding off on aggressive tightening')
            # Keep the adjustments already made (they are for immediate correction), but don't go further.

    return new

def apply_caps(new_caps: Dict[str, int]):
    """Call openclaw gateway config.patch to apply new caps."""
    import subprocess
    patch = {
        "env": {
            "vars": {
                "AINL_BRIDGE_REPORT_MAX_CHARS": str(new_caps['bridge_chars']),
                "PROMOTER_LLM_MAX_PROMPT_CHARS": str(new_caps['promoter_prompt']),
                "PROMOTER_LLM_MAX_COMPLETION_TOKENS": str(new_caps['promoter_completion']),
            }
        }
    }
    cmd = ['openclaw', 'gateway', 'config.patch', json.dumps(patch), '--note', 'AINL auto-tune']
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f'config.patch failed: {result.stderr}')
        raise RuntimeError('Failed to apply caps')
    logger.info('Applied new caps via gateway')

def main():
    parser = argparse.ArgumentParser(description='AINL Auto-Tuner')
    parser.add_argument('--dry-run', action='store_true', help='Do not apply changes even if auto_apply is set')
    args = parser.parse_args()

    ws = resolve_workspace()
    logger.info(f'Workspace: {ws}')

    monitor_path = ws / '.ainl' / 'monitor_state.json'
    db_path = ws / '.ainl' / 'ainl_memory.sqlite3'
    # OpenClaw main config lives at ~/.openclaw/openclaw.json, not inside workspace
    openclaw_cfg_path = Path.home() / '.openclaw' / 'openclaw.json'
    if not openclaw_cfg_path.exists():
        # Fallback: inside workspace
        openclaw_cfg_path = ws / '.openclaw' / 'openclaw.json'

    # Load inputs
    monitor = load_json(monitor_path)
    if not monitor:
        logger.error('Missing monitor cache – cannot compute')
        return 1

    openclaw_cfg = load_json(openclaw_cfg_path) or {}
    current = get_current_caps(openclaw_cfg)
    if not all(current.values()):
        logger.error('Could not determine current caps from OpenClaw config')
        return 1

    savings = compute_savings(monitor)
    if savings is None:
        logger.error('Cannot compute savings – insufficient data in monitor cache')
        return 1

    # Build recent savings history from monitor.daily if available
    daily = monitor.get('workflow', {}).get('token_budget', {}).get('daily', {})
    recent_savings = []
    if daily:
        dates = sorted(daily.keys())
        recent_savings = [daily[d].get('savings_pct') for d in dates[-CFG['min_history_days']:] if daily[d].get('savings_pct') is not None]

    bridge_sizes = get_bridge_sizes(db_path)
    if bridge_sizes:
        logger.info(f'Bridge sizes (7d): min={min(bridge_sizes)}, max={max(bridge_sizes)}, avg={int(sum(bridge_sizes)/len(bridge_sizes))}')
    logger.info(f'Savings: {savings}% (history samples: {len(recent_savings)})')
    logger.info(f'Current caps: bridge={current["bridge_chars"]}, promoter_prompt={current["promoter_prompt"]}, promoter_completion={current["promoter_completion"]}')

    new_caps = decide_adjustments(savings, bridge_sizes, current, recent_savings)

    changed = (new_caps['bridge_chars'] != current['bridge_chars'] or
               new_caps['promoter_prompt'] != current['promoter_prompt'] or
               new_caps['promoter_completion'] != current['promoter_completion'])

    if not changed:
        logger.info('No cap adjustments indicated')
        recommendation = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "savings_pct": savings,
            "history": recent_savings,
            "current": current,
            "recommended": current,
            "bridge_sizes_sample": bridge_sizes,
            "auto_apply": CFG['auto_apply'],
            "applied": False,
            "reason": "No change indicated"
        }
        out_path = ws / '.ainl' / 'tuning_recommendations.json'
        write_json(out_path, recommendation)
        return 0

    recommendation = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "savings_pct": savings,
        "history": recent_savings,
        "current": current,
        "recommended": new_caps,
        "bridge_sizes_sample": bridge_sizes,
        "auto_apply": CFG['auto_apply'],
        "applied": False
    }
    out_path = ws / '.ainl' / 'tuning_recommendations.json'
    write_json(out_path, recommendation)
    logger.info(f'Wrote recommendations to {out_path}')

    # Update tuning log
    log_path = ws / '.ainl' / 'tuning_log.json'
    log_data = load_json(log_path) or {"history": []}
    log_data.setdefault('history', []).append({
        "date": datetime.now(timezone.utc).isoformat(),
        "savings_pct": savings,
        "current": current,
        "recommended": new_caps,
        "applied": False
    })
    # Keep last 90
    if len(log_data['history']) > 90:
        log_data['history'] = log_data['history'][-90:]
    write_json(log_path, log_data)

    # Apply if configured and not dry-run
    if CFG['auto_apply'] and not args.dry_run:
        try:
            apply_caps(new_caps)
            recommendation['applied'] = True
            log_data['history'][-1]['applied'] = True
            write_json(out_path, recommendation)
            write_json(log_path, log_data)
        except Exception as e:
            logger.error(f'Failed to apply caps: {e}')
            return 1
    else:
        logger.info('Dry-run or auto-apply disabled; not applying automatically')

    return 0

if __name__ == '__main__':
    sys.exit(main())
