"""
OpenFang Knowledge Graph ↔ AINL Memory Adapter

This adapter provides a bidirectional mapping between OpenFang's knowledge graph
and AINL's memory system, enabling seamless data sharing and persistence.
"""

from __future__ import annotations
import os
import datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
import json
import sqlite3
from pathlib import Path


@dataclass
class KnowledgeNode:
    """Represents a node in OpenFang's knowledge graph."""
    id: str
    type: str
    properties: Dict[str, Any]
    embeddings: Optional[List[float]] = None


class OpenFangMemoryAdapter:
    """Adapter that translates between OpenFang KG and AINL memory."""

    def __init__(self, db_path: str = None, use_sqlite: bool = True):
        self.use_sqlite = use_sqlite
        if db_path is None:
            db_path = os.getenv("OPENFANG_MEMORY_DB", ":memory:")
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        if not self.use_sqlite:
            return
        self._conn = sqlite3.connect(self.db_path)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS openfang_memory (
                node_id TEXT PRIMARY KEY,
                node_type TEXT NOT NULL,
                properties JSON NOT NULL,
                embeddings BLOB,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self._conn.commit()

    def kg_to_ainl_memory(self, node: KnowledgeNode) -> Dict[str, Any]:
        """Convert OpenFang KG node to AINL memory dump format."""
        memory_entry = {
            "key": f"openfang:node:{node.id}",
            "value": {
                "type": node.type,
                "properties": node.properties,
                "source": "openfang",
                "updated_at": datetime.datetime.utcnow().isoformat() + "Z",
            },
            "embedding": node.embeddings,
        }
        return memory_entry

    def ainl_memory_to_kg(self, memory_data: Dict[str, Any]) -> KnowledgeNode:
        """Convert AINL memory entry back to OpenFang KG node."""
        value = memory_data.get("value", {})
        node_id = memory_data.get("key", "").replace("openfang:node:", "")
        return KnowledgeNode(
            id=node_id,
            type=value.get("type", "unknown"),
            properties=value.get("properties", {}),
            embeddings=memory_data.get("embedding"),
        )

    def store_node(self, node: KnowledgeNode) -> None:
        """Persist a KG node to AINL memory (SQLite)."""
        if self.use_sqlite and self._conn:
            props_json = json.dumps(node.properties)
            emb_blob = None
            if node.embeddings:
                emb_blob = json.dumps(node.embeddings).encode('utf-8')
            self._conn.execute(
                "INSERT OR REPLACE INTO openfang_memory (node_id, node_type, properties, embeddings) VALUES (?, ?, ?, ?)",
                (node.id, node.type, props_json, emb_blob)
            )
            self._conn.commit()

    def load_node(self, node_id: str) -> Optional[KnowledgeNode]:
        """Load a KG node from AINL memory."""
        if self.use_sqlite and self._conn:
            cur = self._conn.execute(
                "SELECT node_type, properties, embeddings FROM openfang_memory WHERE node_id = ?",
                (node_id,)
            )
            row = cur.fetchone()
            if row:
                node_type, props_json, emb_blob = row
                props = json.loads(props_json)
                embeddings = json.loads(emb_blob) if emb_blob else None
                return KnowledgeNode(id=node_id, type=node_type, properties=props, embeddings=embeddings)
        return None

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
