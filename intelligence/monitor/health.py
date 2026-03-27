import os
import sqlite3
from .collector import collector

class HealthStatus:
    def __init__(self):
        self._db_path = os.path.expanduser("~/.ainl/costs.db")
    
    def live(self) -> bool:
        return True
    
    def ready(self) -> dict:
        checks = {
            "collector": True,
            "cost_db": self._check_db(),
            "disk": self._check_disk(),
        }
        all_ok = all(checks.values())
        return {"status": "ready" if all_ok else "degraded", "checks": checks}
    
    def _check_db(self) -> bool:
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("SELECT 1")
            return True
        except Exception:
            return False
    
    def _check_disk(self) -> bool:
        try:
            stat = os.statvfs(os.path.dirname(self._db_path))
            free_mb = (stat.f_bavail * stat.f_frsize) / (1024*1024)
            return free_mb > 100
        except Exception:
            return False
