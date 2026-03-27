import os
import sqlite3
import threading
from datetime import datetime
from typing import Optional
from .collector import collector

class CostTracker:
    def __init__(self, db_path: Optional[str] = None):
        self._db = db_path or os.path.expanduser("~/.ainl/costs.db")
        if self._db != ":memory:":
            os.makedirs(os.path.dirname(self._db), exist_ok=True)
        # Maintain a single connection so that in-memory databases
        # (db_path=":memory:") keep their schema across operations.
        self._conn = sqlite3.connect(self._db, check_same_thread=False)
        self._lock = threading.Lock()
        self._init_db()
    
    def _init_db(self):
        conn = self._conn
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS run_costs (
                run_id TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                provider TEXT,
                model TEXT,
                prompt_tokens INT,
                completion_tokens INT,
                cost_usd REAL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS budget (
                monthly_limit_usd REAL DEFAULT 20.0,
                alert_threshold_pct REAL DEFAULT 0.8,
                throttle_threshold_pct REAL DEFAULT 0.95,
                current_month TEXT DEFAULT (strftime('%Y-%m', 'now'))
            )
            """
        )
        conn.commit()
    
    def add_cost(self, run_id: str, provider: str, model: str, prompt_tokens: int, completion_tokens: int, cost_usd: float):
        with self._lock:
            self._conn.execute(
                "INSERT INTO run_costs (run_id, provider, model, prompt_tokens, completion_tokens, cost_usd) VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, provider, model, prompt_tokens, completion_tokens, cost_usd),
            )
            self._conn.commit()
        collector.increment("ainl_llm_tokens_total", prompt_tokens + completion_tokens, labels={"provider": provider, "model": model})
        collector.set("ainl_llm_cost_total", cost_usd, labels={"provider": provider, "model": model})
    
    def get_month_total(self, month: Optional[str] = None) -> float:
        if month is None:
            month = datetime.now().strftime("%Y-%m")
        cur = self._conn.execute(
            "SELECT SUM(cost_usd) FROM run_costs WHERE strftime('%Y-%m', timestamp) = ?",
            (month,),
        )
        row = cur.fetchone()
        return row[0] or 0.0
    
    def get_budget(self) -> dict:
        cur = self._conn.execute("SELECT * FROM budget ORDER BY rowid DESC LIMIT 1")
        row = cur.fetchone()
        if row:
            keys = [description[0] for description in cur.description]
            return dict(zip(keys, row))
        return {}
    
    def update_month_spending(self):
        total = self.get_month_total()
        budget = self.get_budget()
        limit = budget.get("monthly_limit_usd", 20.0)
        pct = total / limit if limit > 0 else 0.0
        collector.set("ainl_budget_spent_usd", total)
        collector.set("ainl_budget_limit_usd", limit)
        collector.set("ainl_budget_usage_pct", pct)
        return total, limit, pct
