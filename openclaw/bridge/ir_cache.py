"""Compile IR cache for OpenClaw wrapper runs (integration layer; not compiler core).

Disable with AINL_IR_CACHE=0. Override directory with AINL_IR_CACHE_DIR (default ~/.cache/ainl/ir).
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional


def _cache_enabled() -> bool:
    v = os.environ.get("AINL_IR_CACHE", "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def _cache_dir() -> Path:
    raw = os.environ.get("AINL_IR_CACHE_DIR", "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".cache" / "ainl" / "ir"


def _meta_path(source: Path, stat) -> Path:
    h = hashlib.sha256(
        f"{source.resolve()}:{stat.st_mtime_ns}:{stat.st_size}".encode("utf-8")
    ).hexdigest()[:24]
    return _cache_dir() / f"{h}.meta.json"


def _ir_path(source: Path, stat) -> Path:
    h = hashlib.sha256(
        f"{source.resolve()}:{stat.st_mtime_ns}:{stat.st_size}".encode("utf-8")
    ).hexdigest()[:24]
    return _cache_dir() / f"{h}.ir.json"


def load_cached_ir(source: Path) -> Optional[Dict[str, Any]]:
    if not _cache_enabled():
        return None
    try:
        stat = source.stat()
    except OSError:
        return None
    ir_p = _ir_path(source, stat)
    meta_p = _meta_path(source, stat)
    if not ir_p.is_file() or not meta_p.is_file():
        return None
    try:
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
        if (
            meta.get("path") != str(source.resolve())
            or meta.get("mtime_ns") != stat.st_mtime_ns
            or meta.get("size") != stat.st_size
        ):
            return None
        raw = ir_p.read_text(encoding="utf-8")
        return json.loads(raw)
    except (OSError, json.JSONDecodeError, TypeError):
        return None


def save_cached_ir(source: Path, ir: Dict[str, Any]) -> None:
    if not _cache_enabled():
        return
    try:
        stat = source.stat()
    except OSError:
        return
    d = _cache_dir()
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        return
    ir_p = _ir_path(source, stat)
    meta_p = _meta_path(source, stat)
    meta = {
        "path": str(source.resolve()),
        "mtime_ns": stat.st_mtime_ns,
        "size": stat.st_size,
    }
    tmp_ir = ir_p.with_suffix(".ir.json.tmp")
    tmp_meta = meta_p.with_suffix(".meta.json.tmp")
    try:
        payload = json.dumps(ir, ensure_ascii=False, default=str, indent=2)
        tmp_ir.write_text(payload + "\n", encoding="utf-8")
        tmp_meta.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        tmp_ir.replace(ir_p)
        tmp_meta.replace(meta_p)
    except OSError:
        try:
            if tmp_ir.is_file():
                tmp_ir.unlink(missing_ok=True)  # type: ignore[arg-type]
            if tmp_meta.is_file():
                tmp_meta.unlink(missing_ok=True)  # type: ignore[arg-type]
        except OSError:
            pass


def compile_source_cached(
    source: Path,
    compile_fn: Callable[[str], Dict[str, Any]],
) -> Dict[str, Any]:
    cached = load_cached_ir(source)
    if cached is not None:
        return cached
    text = source.read_text(encoding="utf-8")
    ir = compile_fn(text)
    save_cached_ir(source, ir)
    return ir
