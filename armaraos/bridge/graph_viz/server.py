"""Minimal FastAPI server: ``memory_graph.html`` + ``GET /api/memory/graph``.

Run from repo root (so ``armaraos`` and ``runtime`` resolve)::

    cd /path/to/AI_Native_Lang
    PYTHONPATH=. uvicorn armaraos.bridge.graph_viz.server:app --reload --port 8765

Graph JSON is read via ``GraphStore`` from ``AINL_GRAPH_MEMORY_PATH`` (or
``~/.armaraos/ainl_graph_memory.json``). Optional query ``src`` = absolute or
``~`` path to another ``.json`` graph file (same schema as export).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from armaraos.bridge.ainl_graph_memory import GraphStore, _default_graph_path

_GRAPH_VIZ_DIR = Path(__file__).resolve().parent
_HTML = _GRAPH_VIZ_DIR / "memory_graph.html"

app = FastAPI(title="AINL Graph Memory Viz", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _resolve_graph_file(src: str | None) -> Path:
    if src and src.strip():
        p = Path(src).expanduser()
        if not p.suffix.lower() == ".json":
            raise HTTPException(400, "src must be a .json file")
        try:
            p = p.resolve()
        except OSError as e:
            raise HTTPException(400, f"invalid path: {e}") from e
        if not p.is_file():
            raise HTTPException(404, f"graph file not found: {p}")
        return p
    env = (os.environ.get("AINL_GRAPH_MEMORY_PATH") or "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return _default_graph_path()


@app.get("/api/memory/graph")
def api_memory_graph(src: str | None = Query(None, description="Optional path to graph JSON file")):
    path = _resolve_graph_file(src)
    store = GraphStore(path=path)
    return JSONResponse(store.export_graph())


@app.get("/")
def serve_index():
    if not _HTML.is_file():
        raise HTTPException(500, f"missing {_HTML}")
    return FileResponse(_HTML, media_type="text/html; charset=utf-8")


@app.get("/memory_graph.html")
def serve_html():
    return serve_index()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "armaraos.bridge.graph_viz.server:app",
        host="127.0.0.1",
        port=int(os.environ.get("GRAPH_VIZ_PORT", "8765")),
        reload=False,
    )
