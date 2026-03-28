"""
Code context adapter with tiered chunking (Tier 0/1/2).
Concept and design heavily inspired by BradyD2003/ctxzip
https://github.com/BradyD2003/ctxzip
Full credit to Brady Drexler for the original idea.
This is a clean, minimal re-implementation for AINL’s adapter system.

Import-graph dependencies, reverse impact (transitive importers), PageRank-style
scores, and greedy token-budget packing (``COMPRESS_CONTEXT``) follow ideas from
chrismicah/forgeindex (https://github.com/chrismicah/forgeindex); credit **Chris Micah**.

Optional local code index with ctxzip-style tiers. Enable on the CLI host with
``--enable-adapter code_context`` (see cli/main.py registration).

Tiers:
  Tier 0 — compact list of all chunk signatures (directory-style view).
  Tier 1 — signatures plus docstring/summary for the top-ranked chunks (TF–IDF over
           indexed text; optional embedding-based ranking for ``COMPRESS_CONTEXT`` when
           ``embedding_memory`` is importable — see below).
  Tier 2 — full source for ranked chunks (only when max_tier >= 2), or use GET_FULL_SOURCE.

``COMPRESS_CONTEXT`` ranks chunks with the ``embedding_memory`` adapter when available
(import + embed succeeds): cosine similarity between the query embedding and each
chunk’s text embedding; otherwise falls back to TF–IDF (unchanged behavior).

Env:
  AINL_CODE_CONTEXT_STORE — JSON store path (default: .ainl_code_context.json in cwd).

Verbs (target, case-insensitive):
  INDEX <path>
  QUERY_CONTEXT <query> [max_tier] [limit]
  GET_FULL_SOURCE <chunk_id>
  GET_SKELETON [path_or_chunk_id …]
  STATS  (no args — index size, paths, last update time, optional graph metrics)
  GET_DEPENDENCIES <chunk_id>
  GET_IMPACT <chunk_id>
  COMPRESS_CONTEXT <query> [max_tokens]

Module helpers — same behavior as the verbs above; use these from plain Python, tests, or
custom tooling/nodes when you do not want to go through ``adapter.call(...)``. They use the
default JSON store in the current working directory unless ``AINL_CODE_CONTEXT_STORE`` is set.

  index_repository(path) -> None
  query_context(query, max_tier=1, limit=50) -> str
  get_full_source(chunk_id: str) -> str
  get_skeleton(*filters: str) -> str
  get_dependencies(chunk_id: str) -> List[str]
  get_impact(chunk_id: str) -> Dict[str, Any]
  compress_context(query: str, max_tokens: int = 32000) -> str
"""

# adapters/code_context.py
# Note: This adapter has no extra runtime dependencies beyond stdlib + AINL base classes.
# Any import issues are from the broader runtime/adapters package (same as vector_memory).

from __future__ import annotations

import ast
import json
import math
import os
import re
import time
import hashlib
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from runtime.adapters.base import AdapterError, RuntimeAdapter

_DEFAULT_STORE = ".ainl_code_context.json"
_SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".tox",
}
_PY_SUFFIXES = {".py"}
_JS_SUFFIXES = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}


def _tokenize(text: str) -> List[str]:
    return [t for t in re.split(r"[^\w]+", (text or "").lower()) if len(t) > 1]


def _stable_chunk_id(repo_root: Path, rel: str, kind: str, name: str, start: int) -> str:
    raw = f"{rel}:{kind}:{name}:{start}"
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"{kind}:{rel}:{name}@{start}:{h}"


def _read_lines(path: Path) -> List[str]:
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def _py_chunks(repo_root: Path, path: Path) -> List[Dict[str, Any]]:
    rel = str(path.relative_to(repo_root))
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(src, filename=str(path))
    except Exception:
        return []

    lines = src.splitlines()
    out: List[Dict[str, Any]] = []

    class V(ast.NodeVisitor):
        def _span(self, node: ast.AST) -> Tuple[int, int]:
            if not hasattr(node, "lineno") or node.lineno is None:
                return 1, 1
            end = getattr(node, "end_lineno", None) or node.lineno
            return int(node.lineno), int(end)

        def _doc_first_line(self, node: ast.AST) -> str:
            ds = ast.get_docstring(node, clean=True)
            if not ds:
                return ""
            return ds.strip().split("\n", 1)[0].strip()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self._add_fn(node.name, node, async_fn=False)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self._add_fn(node.name, node, async_fn=True)

        def _add_fn(self, name: str, node: ast.AST, async_fn: bool) -> None:
            a, b = self._span(node)
            body = "\n".join(lines[a - 1 : b])
            sig = lines[a - 1].strip() if a <= len(lines) else f"def {name}(...)"
            doc = self._doc_first_line(node)
            cid = _stable_chunk_id(repo_root, rel, "fn" if not async_fn else "async_fn", name, a)
            out.append(
                {
                    "id": cid,
                    "language": "python",
                    "path": rel,
                    "kind": "async_function" if async_fn else "function",
                    "name": name,
                    "signature": sig,
                    "summary": doc,
                    "start_line": a,
                    "end_line": b,
                    "source": body,
                }
            )

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            a, b = self._span(node)
            body = "\n".join(lines[a - 1 : b])
            sig = lines[a - 1].strip() if a <= len(lines) else f"class {node.name}(...)"
            doc = self._doc_first_line(node)
            cid = _stable_chunk_id(repo_root, rel, "class", node.name, a)
            out.append(
                {
                    "id": cid,
                    "language": "python",
                    "path": rel,
                    "kind": "class",
                    "name": node.name,
                    "signature": sig,
                    "summary": doc,
                    "start_line": a,
                    "end_line": b,
                    "source": body,
                }
            )

    V().visit(tree)
    return out


_RE_JS_FUNC = re.compile(
    r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\("
)
_RE_JS_ARROW = re.compile(
    r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\("
)
_RE_JS_CLASS = re.compile(r"^\s*(?:export\s+)?class\s+([A-Za-z_$][\w$]*)")


def _js_ts_chunks(repo_root: Path, path: Path) -> List[Dict[str, Any]]:
    rel = str(path.relative_to(repo_root))
    try:
        lines = _read_lines(path)
    except Exception:
        return []
    lang = "javascript" if path.suffix.lower() in {".js", ".jsx", ".mjs", ".cjs"} else "typescript"
    out: List[Dict[str, Any]] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        m = _RE_JS_FUNC.match(line) or _RE_JS_ARROW.match(line)
        if m:
            name = m.group(1)
            start = i + 1
            depth = line.count("{") - line.count("}")
            j = i + 1
            while j < n and depth > 0:
                depth += lines[j].count("{") - lines[j].count("}")
                j += 1
            end = j if j > i else i + 1
            body = "\n".join(lines[start - 1 : end])
            sig = lines[start - 1].strip()
            cid = _stable_chunk_id(repo_root, rel, "function", name, start)
            out.append(
                {
                    "id": cid,
                    "language": lang,
                    "path": rel,
                    "kind": "function",
                    "name": name,
                    "signature": sig,
                    "summary": "",
                    "start_line": start,
                    "end_line": end,
                    "source": body,
                }
            )
            i = end
            continue
        m2 = _RE_JS_CLASS.match(line)
        if m2:
            name = m2.group(1)
            start = i + 1
            depth = line.count("{") - line.count("}")
            j = i + 1
            while j < n and depth > 0:
                depth += lines[j].count("{") - lines[j].count("}")
                j += 1
            end = j if j > i else i + 1
            body = "\n".join(lines[start - 1 : end])
            sig = lines[start - 1].strip()
            cid = _stable_chunk_id(repo_root, rel, "class", name, start)
            out.append(
                {
                    "id": cid,
                    "language": lang,
                    "path": rel,
                    "kind": "class",
                    "name": name,
                    "signature": sig,
                    "summary": "",
                    "start_line": start,
                    "end_line": end,
                    "source": body,
                }
            )
            i = end
            continue
        i += 1
    return out


def _index_repo(repo_root: Path) -> List[Dict[str, Any]]:
    chunks: List[Dict[str, Any]] = []
    root = repo_root.resolve()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")]
        for fn in filenames:
            p = Path(dirpath) / fn
            suf = p.suffix.lower()
            if suf in _PY_SUFFIXES:
                chunks.extend(_py_chunks(root, p))
            elif suf in _JS_SUFFIXES:
                chunks.extend(_js_ts_chunks(root, p))
    chunks.sort(key=lambda c: (c["path"], c["start_line"]))
    return chunks


def _chunk_text(c: Dict[str, Any]) -> str:
    return f"{c.get('signature', '')} {c.get('summary', '')} {c.get('path', '')} {c.get('name', '')}"


def _tfidf_rank(query: str, chunks: Sequence[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
    if not chunks:
        return []
    q = _tokenize(query)
    if not q:
        return list(chunks[: max(1, top_k)])

    docs = [_tokenize(_chunk_text(c)) for c in chunks]
    N = len(docs)
    df: Counter[str] = Counter()
    for toks in docs:
        for t in set(toks):
            df[t] += 1

    def idf(t: str) -> float:
        return math.log((N + 1) / (df.get(t, 0) + 1)) + 1.0

    def vec(toks: List[str]) -> Dict[str, float]:
        tf = Counter(toks)
        total = float(sum(tf.values())) or 1.0
        out: Dict[str, float] = {}
        for t, c in tf.items():
            out[t] = (c / total) * idf(t)
        return out

    qv = vec(q)

    def norm(v: Dict[str, float]) -> float:
        return math.sqrt(sum(x * x for x in v.values())) or 1.0

    def cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
        na, nb = norm(a), norm(b)
        dot = 0.0
        for t, av in a.items():
            bv = b.get(t)
            if bv is not None:
                dot += av * bv
        return dot / (na * nb)

    scored: List[Tuple[float, Dict[str, Any]]] = []
    for c, toks in zip(chunks, docs):
        dv = vec(toks)
        s = cosine(qv, dv)
        scored.append((s, c))
    scored.sort(key=lambda x: -x[0])
    lim = max(1, min(int(top_k), len(scored)))
    return [c for _, c in scored[:lim]]


def _cosine_vec(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _rank_chunks_embedding_or_tfidf(
    query: str,
    chunks: Sequence[Dict[str, Any]],
    top_k: int,
) -> List[Dict[str, Any]]:
    """Prefer embedding_memory adapter for ranking; fall back to TF–IDF on any failure."""
    # Best-effort: uses private _embed to stay in the same embedding space as embedding_memory; falls back silently to TF-IDF on any import or runtime issue.
    try:
        from adapters.embedding_memory import EmbeddingMemoryAdapter  # type: ignore
    except ImportError:
        return _tfidf_rank(query, list(chunks), top_k=top_k)
    try:
        emb = EmbeddingMemoryAdapter()
        qv = emb._embed((query or "").strip())
        scored: List[Tuple[float, Dict[str, Any]]] = []
        for c in chunks:
            cv = emb._embed(_chunk_text(c))
            scored.append((_cosine_vec(qv, cv), c))
        scored.sort(key=lambda x: -x[0])
        lim = max(1, min(int(top_k), len(scored)))
        return [c for _, c in scored[:lim]]
    except Exception:
        return _tfidf_rank(query, list(chunks), top_k=top_k)


_RE_JS_FROM = re.compile(
    r"""import\s+(?:[\w*{}\s,]+\s+from\s+)?['"]([^'"]+)['"]""",
    re.MULTILINE,
)
_RE_JS_REQ = re.compile(r"""require\s*\(\s*['"]([^'"]+)['"]\s*\)""")


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _extract_py_import_targets(source: str) -> List[str]:
    out: List[str] = []
    for line in source.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("from "):
            parts = s.split()
            if len(parts) >= 2 and parts[0] == "from":
                mod = parts[1]
                if mod == "." or mod.startswith("."):
                    continue
                out.append(mod.rstrip("."))
        elif s.startswith("import "):
            rest = s[6:].split("#")[0].strip()
            for part in rest.split(","):
                p = part.strip()
                if not p:
                    continue
                p = p.split()[0]
                if p.startswith("."):
                    continue
                if " as " in p:
                    p = p.split(" as ")[0].strip()
                out.append(p)
    return out


def _extract_js_import_targets(source: str) -> List[str]:
    out: List[str] = []
    for m in _RE_JS_FROM.finditer(source):
        out.append(m.group(1))
    for m in _RE_JS_REQ.finditer(source):
        out.append(m.group(1))
    return out


def _py_mod_to_candidate_paths(mod: str) -> List[str]:
    parts = mod.split(".")
    if not parts or not parts[0]:
        return []
    base = "/".join(parts)
    return [f"{base}.py", f"{base}/__init__.py"]


def _resolve_import_to_rel(
    root: Path,
    chunk_path: str,
    target: str,
    lang: str,
) -> Optional[str]:
    root = root.resolve()
    if lang == "python":
        if target.startswith("."):
            return None
        for rel in _py_mod_to_candidate_paths(target):
            p = root / rel
            if p.is_file():
                return rel.replace("\\", "/")
        return None
    chunk_path = chunk_path.replace("\\", "/")
    if target.startswith(".") or target.startswith("/"):
        base = (root / chunk_path).parent
        try:
            cand = (base / target).resolve()
            cand.relative_to(root)
        except ValueError:
            return None
        if cand.is_file():
            return str(cand.relative_to(root)).replace("\\", "/")
        for suf in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"):
            p = cand.with_suffix(suf)
            if p.is_file():
                return str(p.relative_to(root)).replace("\\", "/")
        if cand.is_dir():
            for fn in ("index.ts", "index.tsx", "index.js", "index.jsx"):
                p = cand / fn
                if p.is_file():
                    return str(p.relative_to(root)).replace("\\", "/")
        return None
    return None


def _file_canonical_id(chunks: Sequence[Dict[str, Any]]) -> Dict[str, str]:
    by_path: Dict[str, List[Dict[str, Any]]] = {}
    for c in chunks:
        p = str(c.get("path") or "")
        by_path.setdefault(p, []).append(c)
    out: Dict[str, str] = {}
    for p, lst in by_path.items():
        lst.sort(key=lambda x: int(x.get("start_line") or 0))
        if lst:
            out[p] = str(lst[0]["id"])
    return out


def _pagerank(
    nodes: List[str],
    forward: Dict[str, set],
    d: float = 0.85,
    iters: int = 24,
) -> Dict[str, float]:
    if not nodes:
        return {}
    n = len(nodes)
    idx = {name: i for i, name in enumerate(nodes)}
    outdeg = [max(1, len(forward.get(nodes[i], ()))) for i in range(n)]
    inbound: List[List[int]] = [[] for _ in range(n)]
    for i, ni in enumerate(nodes):
        for nj in forward.get(ni, ()):
            j = idx.get(nj)
            if j is not None:
                inbound[j].append(i)
    r = [1.0 / n] * n
    for _ in range(iters):
        r_new = [(1.0 - d) / n] * n
        for j in range(n):
            s = 0.0
            for i in inbound[j]:
                s += r[i] / outdeg[i]
            r_new[j] += d * s
        r = r_new
    return {nodes[i]: r[i] for i in range(n)}


def _rebuild_dep_structs(
    root: Path,
    chunks: List[Dict[str, Any]],
) -> Tuple[Dict[str, set], Dict[str, set], Dict[str, float]]:
    canon = _file_canonical_id(chunks)
    forward: Dict[str, set] = {str(c["id"]): set() for c in chunks}
    for c in chunks:
        cid = str(c["id"])
        src = str(c.get("source") or "")
        lang = str(c.get("language") or "python")
        chunk_path = str(c.get("path") or "")
        if lang == "python":
            targets = _extract_py_import_targets(src)
        else:
            targets = _extract_js_import_targets(src)
        for t in targets:
            rel = _resolve_import_to_rel(root, chunk_path, t, lang)
            if not rel:
                continue
            tid = canon.get(rel)
            if tid and tid != cid:
                forward[cid].add(tid)
    reverse: Dict[str, set] = {str(c["id"]): set() for c in chunks}
    for a, deps in forward.items():
        for b in deps:
            reverse.setdefault(b, set()).add(a)
    nodes = [str(c["id"]) for c in chunks]
    pr = _pagerank(nodes, forward)
    return forward, reverse, pr


def _transitive_importers(chunk_id: str, reverse: Dict[str, set]) -> List[str]:
    seen: set = set()
    out: List[str] = []
    stack = list(reverse.get(chunk_id, ()))
    while stack:
        x = stack.pop()
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
        stack.extend(reverse.get(x, ()))
    out.sort()
    return out


class CodeContextAdapter(RuntimeAdapter):
    """JSON-backed code chunks; tiered retrieval (ctxzip-inspired).

    Dependency graph, reverse-impact (transitive importers), PageRank-style importance,
    and greedy token-budget context packing follow ideas from import-graph workflows in
    the forgeindex ecosystem (https://github.com/chrismicah/forgeindex). Credit:
    **Chris Micah** and the forgeindex project for those concepts; this file is an
    independent implementation for AINL.

    Optional: GET_SKELETON (Tier-0 signature lines only); COMPRESS_CONTEXT may rank via
    embedding_memory when import/embed succeeds; STATS includes graph counts and top PageRank.
    """

    def __init__(self, store_path: Optional[str] = None):
        raw = (store_path or os.environ.get("AINL_CODE_CONTEXT_STORE") or "").strip()
        self.store_path = Path(raw) if raw else Path.cwd() / _DEFAULT_STORE
        self._chunks: List[Dict[str, Any]] = []
        self._by_id: Dict[str, Dict[str, Any]] = {}
        self._indexed_root: Optional[str] = None
        self._updated_at: Optional[float] = None
        self._dep_forward: Dict[str, set] = {}
        self._dep_reverse: Dict[str, set] = {}
        self._dep_pagerank: Dict[str, float] = {}
        self._load()

    def _load(self) -> None:
        if not self.store_path.is_file():
            self._chunks = []
            self._by_id = {}
            self._indexed_root = None
            self._updated_at = None
            self._clear_dep_graphs()
            return
        try:
            data = json.loads(self.store_path.read_text(encoding="utf-8"))
        except Exception as e:
            raise AdapterError(f"code_context: cannot read store {self.store_path}: {e}") from e
        if not isinstance(data, dict):
            self._chunks = []
            self._by_id = {}
            self._indexed_root = None
            self._updated_at = None
            self._clear_dep_graphs()
            return
        self._chunks = list(data.get("chunks") or [])
        ir = data.get("indexed_root", None)
        self._indexed_root = str(ir) if ir is not None else None
        raw_u = data.get("updated_at", None)
        self._updated_at = None
        if isinstance(raw_u, (int, float)):
            self._updated_at = float(raw_u)
        elif isinstance(raw_u, str) and raw_u.strip():
            try:
                self._updated_at = float(raw_u)
            except ValueError:
                self._updated_at = None
        self._by_id = {str(c.get("id")): c for c in self._chunks if c.get("id")}
        self._sync_dep_graphs()

    def _clear_dep_graphs(self) -> None:
        self._dep_forward = {}
        self._dep_reverse = {}
        self._dep_pagerank = {}

    def _sync_dep_graphs(self) -> None:
        if not self._chunks or not self._indexed_root:
            self._clear_dep_graphs()
            return
        root = Path(self._indexed_root)
        if not root.is_dir():
            self._clear_dep_graphs()
            return
        self._dep_forward, self._dep_reverse, self._dep_pagerank = _rebuild_dep_structs(
            root, self._chunks
        )

    def _save(self, root: Path, chunks: List[Dict[str, Any]]) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        ts = float(time.time())
        payload = {
            "version": 1,
            "updated_at": ts,
            "indexed_root": str(root.resolve()),
            "chunks": chunks,
        }
        self.store_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._chunks = chunks
        self._by_id = {str(c["id"]): c for c in chunks}
        self._indexed_root = str(root.resolve())
        self._updated_at = ts
        self._sync_dep_graphs()

    def index_repository(self, path: str) -> None:
        root = Path(path).expanduser().resolve()
        if not root.is_dir():
            raise AdapterError(f"code_context.INDEX: not a directory: {path}")
        chunks = _index_repo(root)
        self._save(root, chunks)

    def query_context(self, query: str, max_tier: int = 1, limit: int = 50) -> str:
        tier = max(0, min(int(max_tier), 2))
        lim = max(1, min(int(limit), 500))
        if not self._chunks:
            return "(no index; run INDEX first)"
        if tier == 0:
            lines = [f"{c['path']}:{c['start_line']}  {c['signature']}" for c in self._chunks]
            return "\n".join(lines[:lim] if len(lines) > lim else lines)

        top = _tfidf_rank(query, self._chunks, top_k=lim)
        parts: List[str] = []
        for c in top:
            block = f"[{c['id']}] {c['path']}:{c['start_line']}\n{c['signature']}"
            if tier >= 1:
                summ = (c.get("summary") or "").strip()
                if summ:
                    block += f"\n{summ}"
            if tier >= 2:
                block += f"\n---\n{c.get('source', '')}\n---"
            parts.append(block)
        return "\n\n".join(parts)

    def get_full_source(self, chunk_id: str) -> str:
        c = self._by_id.get(chunk_id)
        if not c:
            return ""
        return str(c.get("source") or "")

    def get_dependencies(self, chunk_id: str) -> List[str]:
        cid = str(chunk_id)
        return sorted(self._dep_forward.get(cid, ()))

    def get_impact(self, chunk_id: str) -> Dict[str, Any]:
        cid = str(chunk_id)
        if cid not in self._by_id:
            return {
                "chunk_id": cid,
                "direct_importers": [],
                "transitive_importers": [],
                "pagerank": 0.0,
            }
        direct = sorted(self._dep_reverse.get(cid, ()))
        trans = _transitive_importers(cid, self._dep_reverse)
        pr = float(self._dep_pagerank.get(cid, 0.0))
        return {
            "chunk_id": cid,
            "direct_importers": direct,
            "transitive_importers": trans,
            "pagerank": pr,
        }

    def get_skeleton(self, *filters: str) -> str:
        if not self._chunks:
            return "(no index; run INDEX first)"
        ordered = sorted(
            self._chunks,
            key=lambda c: (str(c.get("path") or ""), int(c.get("start_line") or 0)),
        )

        def _line(c: Dict[str, Any]) -> str:
            return f"{c['path']}:{c['start_line']}  {c['signature']}"

        flist = [f.strip() for f in filters if f and str(f).strip()]
        if len(flist) == 1 and flist[0] == "_":
            flist = []
        if not flist:
            take = ordered[:100]
            return "\n".join(_line(c) for c in take) if take else "(empty)"

        if len(flist) == 1:
            one = flist[0]
            if one in self._by_id:
                return _line(self._by_id[one])
            norm = one.replace("\\", "/")
            matches = [
                c
                for c in ordered
                if str(c.get("path") or "") == norm
                or str(c.get("path") or "").endswith(norm)
            ]
            if not matches:
                return "(empty)"
            return "\n".join(_line(c) for c in matches)

        lines: List[str] = []
        for cid in flist:
            c = self._by_id.get(cid)
            if c:
                lines.append(_line(c))
        return "\n".join(lines) if lines else "(empty)"

    def compress_context(self, query: str, max_tokens: int = 32000) -> str:
        if not self._chunks:
            return "(no index; run INDEX first)"
        mt = max(100, int(max_tokens))
        ranked = _rank_chunks_embedding_or_tfidf(
            query, self._chunks, top_k=min(500, len(self._chunks))
        )
        parts: List[str] = []
        used = 0
        for c in ranked:
            block = f"[{c['id']}] {c['path']}:{c['start_line']}\n{c['signature']}"
            summ = (c.get("summary") or "").strip()
            if summ:
                block += f"\n{summ}"
            cost = _estimate_tokens(block)
            if parts and used + cost > mt:
                break
            parts.append(block)
            used += cost
        return "\n\n".join(parts) if parts else "(empty)"

    def call(self, target: str, args: List[Any], context: Dict[str, Any]) -> Any:
        verb = (target or "").strip().upper()
        if verb == "INDEX":
            if not args:
                raise AdapterError("code_context.INDEX requires path")
            self.index_repository(str(args[0]))
            return {"ok": True, "chunks": len(self._chunks)}
        if verb == "QUERY_CONTEXT":
            if not args:
                raise AdapterError("code_context.QUERY_CONTEXT requires query string")
            q = str(args[0])
            max_tier = int(args[1]) if len(args) > 1 and args[1] is not None else 1
            limit = int(args[2]) if len(args) > 2 and args[2] is not None else 50
            return self.query_context(q, max_tier=max_tier, limit=limit)
        if verb == "GET_FULL_SOURCE":
            if not args:
                raise AdapterError("code_context.GET_FULL_SOURCE requires chunk_id")
            return self.get_full_source(str(args[0]))
        if verb == "GET_DEPENDENCIES":
            if not args:
                raise AdapterError("code_context.GET_DEPENDENCIES requires chunk_id")
            return self.get_dependencies(str(args[0]))
        if verb == "GET_IMPACT":
            if not args:
                raise AdapterError("code_context.GET_IMPACT requires chunk_id")
            return self.get_impact(str(args[0]))
        if verb == "COMPRESS_CONTEXT":
            if not args:
                raise AdapterError("code_context.COMPRESS_CONTEXT requires query string")
            q = str(args[0])
            max_tok = int(args[1]) if len(args) > 1 and args[1] is not None else 32000
            return self.compress_context(q, max_tokens=max_tok)
        if verb == "GET_SKELETON":
            flist = [str(a) for a in args if a is not None and str(a).strip() != ""]
            return self.get_skeleton(*flist)
        if verb == "STATS":
            ua: Optional[float] = getattr(self, "_updated_at", None)
            if ua is not None:
                try:
                    ua = float(ua)
                except (TypeError, ValueError):
                    ua = None
            ir: Optional[str] = self._indexed_root
            if ir is not None and not isinstance(ir, str):
                try:
                    ir = str(ir)
                except Exception:
                    ir = None
            return {
                "chunks": len(self._chunks),
                "indexed_root": ir,
                "store_path": str(self.store_path),
                "updated_at": ua,
                "num_nodes": len(self._chunks),
                "num_edges": (
                    sum(len(v) for v in self._dep_forward.values())
                    if self._dep_forward
                    else 0
                ),
                "top_pagerank": sorted(
                    (
                        {"chunk_id": cid, "score": float(sc)}
                        for cid, sc in (self._dep_pagerank or {}).items()
                    ),
                    key=lambda x: -x["score"],
                )[:5],
            }
        raise AdapterError(f"code_context unsupported verb: {target!r}")


_default: Optional[CodeContextAdapter] = None


def _get_default() -> CodeContextAdapter:
    global _default
    if _default is None:
        _default = CodeContextAdapter()
    return _default


def index_repository(path: str) -> None:
    _get_default().index_repository(path)


def query_context(query: str, max_tier: int = 1, limit: int = 50) -> str:
    return _get_default().query_context(query, max_tier=max_tier, limit=limit)


def get_full_source(chunk_id: str) -> str:
    return _get_default().get_full_source(chunk_id)


def get_dependencies(chunk_id: str) -> List[str]:
    return _get_default().get_dependencies(chunk_id)


def get_impact(chunk_id: str) -> Dict[str, Any]:
    return _get_default().get_impact(chunk_id)


def compress_context(query: str, max_tokens: int = 32000) -> str:
    return _get_default().compress_context(query, max_tokens=max_tokens)


def get_skeleton(*filters: str) -> str:
    return _get_default().get_skeleton(*filters)
