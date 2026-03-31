from __future__ import annotations  # AINL-ARMARAOS-TOP5
import sqlite3  # AINL-ARMARAOS-TOP5
from pathlib import Path  # AINL-ARMARAOS-TOP5
from typing import Tuple  # AINL-ARMARAOS-TOP5


def bootstrap_tables(db_path: Path) -> Tuple[bool, str]:  # AINL-ARMARAOS-TOP5
    """Idempotent CREATE IF NOT EXISTS for `weekly_remaining_v1` only (gold-standard budget row)."""  # AINL-ARMARAOS-TOP5
    return ensure_armaraos_bridge_schema(db_path=db_path)  # AINL-ARMARAOS-TOP5


def dry_run_sql_preview() -> str:  # AINL-ARMARAOS-TOP5
    """SQL echoed for `ainl install armaraos --dry-run` (no I/O). IntelligenceReport not used — reports are Markdown."""  # AINL-ARMARAOS-TOP5
    return (  # AINL-ARMARAOS-TOP5
        "CREATE TABLE IF NOT EXISTS weekly_remaining_v1 (\n"  # AINL-ARMARAOS-TOP5
        "  week_start TEXT PRIMARY KEY,\n"  # AINL-ARMARAOS-TOP5
        "  remaining_budget INTEGER,\n"  # AINL-ARMARAOS-TOP5
        "  updated_at TEXT\n"  # AINL-ARMARAOS-TOP5
        ");\n"  # AINL-ARMARAOS-TOP5
    )  # AINL-ARMARAOS-TOP5


def ensure_armaraos_bridge_schema(*, db_path: Path) -> Tuple[bool, str]:  # AINL-ARMARAOS-TOP5
    """Create `weekly_remaining_v1` if missing. Legacy `IntelligenceReport` references elsewhere are no-ops here."""  # AINL-ARMARAOS-TOP5
    try:  # AINL-ARMARAOS-TOP5
        db_path = Path(db_path).expanduser()  # AINL-ARMARAOS-TOP5
        db_path.parent.mkdir(parents=True, exist_ok=True)  # AINL-ARMARAOS-TOP5
        con = sqlite3.connect(str(db_path))  # AINL-ARMARAOS-TOP5
        cur = con.cursor()  # AINL-ARMARAOS-TOP5
        cur.execute(  # AINL-ARMARAOS-TOP5
            "CREATE TABLE IF NOT EXISTS weekly_remaining_v1 ("  # AINL-ARMARAOS-TOP5
            "week_start TEXT PRIMARY KEY, "  # AINL-ARMARAOS-TOP5
            "remaining_budget INTEGER, "  # AINL-ARMARAOS-TOP5
            "updated_at TEXT"  # AINL-ARMARAOS-TOP5
            ");"  # AINL-ARMARAOS-TOP5
        )  # AINL-ARMARAOS-TOP5
        con.commit()  # AINL-ARMARAOS-TOP5
        con.close()  # AINL-ARMARAOS-TOP5
        return True, f"ok ({db_path})"  # AINL-ARMARAOS-TOP5
    except Exception as e:  # AINL-ARMARAOS-TOP5
        return False, f"schema bootstrap failed: {e}"  # AINL-ARMARAOS-TOP5
