"""Tiktok adapter (Extended tier).

Provides read-only access to TiktokReport and TiktokVideo rows from a SQLite
database produced by an upstream CRM/scraper. The live CLI path (`R tiktok.*`)
is wired through `adapters.openclaw_integration.TiktokAdapter`; this module
preserves a parallel `TiktokAdapter` for programmatic users who imported
`from adapters.tiktok import TiktokAdapter` directly.

Database path resolution (layered, robust, non-breaking):
    1. Explicit constructor argument `db_path=...`
    2. Environment variable `AINL_TIKTOK_DB`
    3. Legacy default `~/.openclaw/workspace/crm/prisma/dev.db`
       (warns once; silenced by setting `AINL_TIKTOK_DB` or passing `db_path`)
    4. `TiktokAdapterConfigError` raised at construction time, not at first
       query — surfaces misconfiguration immediately with an actionable hint.

See `docs/adapters/ADAPTER_TIERS.md` for the tier model and `CHANGELOG.md`
[1.9.0] for the move from `adapters/tiktok.py` (shim still works).
"""

from __future__ import annotations

import os
import sqlite3
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional


class TiktokAdapterConfigError(RuntimeError):
    """Raised when no TikTok DB path can be resolved through any layer."""


def _resolve_db_path(explicit: Optional[str]) -> str:
    if explicit:
        return str(Path(explicit).expanduser())

    env_path = os.environ.get("AINL_TIKTOK_DB", "").strip()
    if env_path:
        return str(Path(env_path).expanduser())

    legacy = Path.home() / ".openclaw" / "workspace" / "crm" / "prisma" / "dev.db"
    if legacy.exists():
        warnings.warn(
            "tiktok adapter using legacy default DB path "
            f"({legacy}); set AINL_TIKTOK_DB=<path> or pass "
            "db_path=<path> to TiktokAdapter() to silence this warning",
            UserWarning,
            stacklevel=3,
        )
        return str(legacy)

    raise TiktokAdapterConfigError(
        "tiktok adapter: no database path configured. "
        "Set AINL_TIKTOK_DB=<path>, pass db_path=<path> to TiktokAdapter(), "
        "or place the legacy CRM SQLite at "
        f"{legacy}."
    )


class TiktokAdapter:
    """Read-only TikTok CRM adapter (Extended tier).

    Construct with an explicit `db_path`, set `AINL_TIKTOK_DB` in the
    environment, or rely on the legacy `~/.openclaw/...` default for
    backward compatibility.
    """

    group = "tiktok"

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db_path = _resolve_db_path(db_path)

    @property
    def db_path(self) -> str:
        return self._db_path

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    @staticmethod
    def _iso_to_ts(value: Any) -> int:
        if not value:
            return 0
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return int(dt.timestamp())
        except (ValueError, TypeError):
            return 0

    async def F(self, args: List[Any], frame: Any) -> List[dict]:
        """Fetch all TiktokReport records."""
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, filename, path, videoCount, createdAt "
                "FROM TiktokReport ORDER BY createdAt DESC"
            )
            rows = cur.fetchall()
        return [
            {
                "id": rid,
                "filename": filename,
                "path": path,
                "videoCount": video_count,
                "createdAt": created_at,
                "createdAt_ts": self._iso_to_ts(created_at),
            }
            for rid, filename, path, video_count, created_at in rows
        ]

    async def recent(self, args: List[Any], frame: Any) -> int:
        """Return number of TiktokReport rows created in the last N hours (default 24)."""
        hours_ago = 24
        if args and isinstance(args[0], (int, float)):
            hours_ago = int(args[0])
        cutoff_ts = int(datetime.now(timezone.utc).timestamp()) - hours_ago * 3600
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*) FROM TiktokReport "
                "WHERE createdAt >= datetime(?,'unixepoch')",
                (cutoff_ts,),
            )
            return int(cur.fetchone()[0])

    async def videos(self, args: List[Any], frame: Any) -> List[dict]:
        """Fetch all TiktokVideo records with processedAt and numeric timestamps."""
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, tiktokId, title, description, processedAt, createdAt "
                "FROM TiktokVideo ORDER BY processedAt DESC"
            )
            rows = cur.fetchall()
        return [
            {
                "id": rid,
                "tiktokId": tid,
                "title": title,
                "description": desc,
                "processedAt": processed_at,
                "processedAt_ts": self._iso_to_ts(processed_at),
            }
            for rid, tid, title, desc, processed_at, _created_at in rows
        ]


__all__ = ["TiktokAdapter", "TiktokAdapterConfigError"]
