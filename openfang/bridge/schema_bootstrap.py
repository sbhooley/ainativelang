from __future__ import annotations  # AINL-OPENFANG-TOP5
import sqlite3  # AINL-OPENFANG-TOP5
from pathlib import Path  # AINL-OPENFANG-TOP5
from typing import Tuple  # AINL-OPENFANG-TOP5


def bootstrap_tables(db_path: Path) -> Tuple[bool, str]:  # AINL-OPENFANG-TOP5
    """Idempotent CREATE IF NOT EXISTS for `weekly_remaining_v1` only (gold-standard budget row)."""  # AINL-OPENFANG-TOP5
    return ensure_openfang_bridge_schema(db_path=db_path)  # AINL-OPENFANG-TOP5


def dry_run_sql_preview() -> str:  # AINL-OPENFANG-TOP5
    """SQL echoed for `ainl install openfang --dry-run` (no I/O). IntelligenceReport not used — reports are Markdown."""  # AINL-OPENFANG-TOP5
    return (  # AINL-OPENFANG-TOP5
        "CREATE TABLE IF NOT EXISTS weekly_remaining_v1 (\n"  # AINL-OPENFANG-TOP5
        "  week_start TEXT PRIMARY KEY,\n"  # AINL-OPENFANG-TOP5
        "  remaining_budget INTEGER,\n"  # AINL-OPENFANG-TOP5
        "  updated_at TEXT\n"  # AINL-OPENFANG-TOP5
        ");\n"  # AINL-OPENFANG-TOP5
    )  # AINL-OPENFANG-TOP5


def ensure_openfang_bridge_schema(*, db_path: Path) -> Tuple[bool, str]:  # AINL-OPENFANG-TOP5
    """Create `weekly_remaining_v1` if missing. Legacy `IntelligenceReport` references elsewhere are no-ops here."""  # AINL-OPENFANG-TOP5
    try:  # AINL-OPENFANG-TOP5
        db_path = Path(db_path).expanduser()  # AINL-OPENFANG-TOP5
        db_path.parent.mkdir(parents=True, exist_ok=True)  # AINL-OPENFANG-TOP5
        con = sqlite3.connect(str(db_path))  # AINL-OPENFANG-TOP5
        cur = con.cursor()  # AINL-OPENFANG-TOP5
        cur.execute(  # AINL-OPENFANG-TOP5
            "CREATE TABLE IF NOT EXISTS weekly_remaining_v1 ("  # AINL-OPENFANG-TOP5
            "week_start TEXT PRIMARY KEY, "  # AINL-OPENFANG-TOP5
            "remaining_budget INTEGER, "  # AINL-OPENFANG-TOP5
            "updated_at TEXT"  # AINL-OPENFANG-TOP5
            ");"  # AINL-OPENFANG-TOP5
        )  # AINL-OPENFANG-TOP5
        con.commit()  # AINL-OPENFANG-TOP5
        con.close()  # AINL-OPENFANG-TOP5
        return True, f"ok ({db_path})"  # AINL-OPENFANG-TOP5
    except Exception as e:  # AINL-OPENFANG-TOP5
        return False, f"schema bootstrap failed: {e}"  # AINL-OPENFANG-TOP5
