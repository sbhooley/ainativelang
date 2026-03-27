from __future__ import annotations  # AINL-OPENCLAW-TOP5
import sqlite3  # AINL-OPENCLAW-TOP5
from pathlib import Path  # AINL-OPENCLAW-TOP5
from typing import Tuple  # AINL-OPENCLAW-TOP5


def bootstrap_tables(db_path: Path) -> Tuple[bool, str]:  # AINL-OPENCLAW-TOP5
    """Idempotent CREATE IF NOT EXISTS for `weekly_remaining_v1` only (gold-standard budget row)."""  # AINL-OPENCLAW-TOP5
    return ensure_openclaw_bridge_schema(db_path=db_path)  # AINL-OPENCLAW-TOP5


def dry_run_sql_preview() -> str:  # AINL-OPENCLAW-TOP5
    """SQL echoed for `ainl install openclaw --dry-run` (no I/O). IntelligenceReport not used — reports are Markdown."""  # AINL-OPENCLAW-TOP5
    return (  # AINL-OPENCLAW-TOP5
        "CREATE TABLE IF NOT EXISTS weekly_remaining_v1 (\n"  # AINL-OPENCLAW-TOP5
        "  week_start TEXT PRIMARY KEY,\n"  # AINL-OPENCLAW-TOP5
        "  remaining_budget INTEGER,\n"  # AINL-OPENCLAW-TOP5
        "  updated_at TEXT\n"  # AINL-OPENCLAW-TOP5
        ");\n"  # AINL-OPENCLAW-TOP5
    )  # AINL-OPENCLAW-TOP5


def ensure_openclaw_bridge_schema(*, db_path: Path) -> Tuple[bool, str]:  # AINL-OPENCLAW-TOP5
    """Create `weekly_remaining_v1` if missing. Legacy `IntelligenceReport` references elsewhere are no-ops here."""  # AINL-OPENCLAW-TOP5
    try:  # AINL-OPENCLAW-TOP5
        db_path = Path(db_path).expanduser()  # AINL-OPENCLAW-TOP5
        db_path.parent.mkdir(parents=True, exist_ok=True)  # AINL-OPENCLAW-TOP5
        con = sqlite3.connect(str(db_path))  # AINL-OPENCLAW-TOP5
        cur = con.cursor()  # AINL-OPENCLAW-TOP5
        cur.execute(  # AINL-OPENCLAW-TOP5
            "CREATE TABLE IF NOT EXISTS weekly_remaining_v1 ("  # AINL-OPENCLAW-TOP5
            "week_start TEXT PRIMARY KEY, "  # AINL-OPENCLAW-TOP5
            "remaining_budget INTEGER, "  # AINL-OPENCLAW-TOP5
            "updated_at TEXT"  # AINL-OPENCLAW-TOP5
            ");"  # AINL-OPENCLAW-TOP5
        )  # AINL-OPENCLAW-TOP5
        con.commit()  # AINL-OPENCLAW-TOP5
        con.close()  # AINL-OPENCLAW-TOP5
        return True, f"ok ({db_path})"  # AINL-OPENCLAW-TOP5
    except Exception as e:  # AINL-OPENCLAW-TOP5
        return False, f"schema bootstrap failed: {e}"  # AINL-OPENCLAW-TOP5
