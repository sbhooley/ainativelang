#!/usr/bin/env python3
"""Run the strict-valid HTTP machine-payment example against a local 402 demo server.

Starts a temporary **127.0.0.1** server (stdlib), runs the same graph twice:

1. ``frame = {url}`` → expect ``payment_required`` from ``SimpleHttpAdapter``.
2. ``frame = {url, http_payment.x402.payment_signature}`` → expect ``http_completed`` with ``ok: true``.

Usage (from repo root)::

    python scripts/run_http_machine_payment_roundtrip_demo.py

Exit **0** on success, **1** on failure. Suitable for agents and CI smoke checks.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import threading
from http.server import HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from runtime.adapters.base import AdapterRegistry  # noqa: E402
from runtime.adapters.builtins import CoreBuiltinAdapter  # noqa: E402
from runtime.adapters.http import SimpleHttpAdapter  # noqa: E402
from runtime.engine import RuntimeEngine  # noqa: E402


def _load_demo_handler():
    demo_path = ROOT / "scripts" / "http_machine_payment_demo_server.py"
    spec = importlib.util.spec_from_file_location("_http_payment_demo_server", demo_path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod._Handler


def _build_registry() -> AdapterRegistry:
    reg = AdapterRegistry(allowed=None)
    reg.register("core", CoreBuiltinAdapter())
    reg.register(
        "http",
        SimpleHttpAdapter(
            default_timeout_s=10.0,
            max_response_bytes=256_000,
            allow_hosts=["127.0.0.1"],
            payment_profile="auto",
            max_payment_rounds=2,
        ),
    )
    return reg


def _load_example_source() -> str:
    path = ROOT / "examples" / "http" / "http_machine_payment_flow_compact.ainl"
    return path.read_text(encoding="utf-8")


def run_roundtrip() -> int:
    Handler = _load_demo_handler()
    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    port = int(httpd.server_address[1])
    url = f"http://127.0.0.1:{port}/"
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        code = _load_example_source()
        reg = _build_registry()
        src_path = str(ROOT / "examples" / "http" / "http_machine_payment_flow_compact.ainl")
        try:
            eng = RuntimeEngine.from_code(
                code,
                strict=True,
                trace=False,
                adapters=reg,
                source_path=src_path,
            )
        except RuntimeError as exc:
            print("compile failed:", exc, file=sys.stderr, flush=True)
            return 1
        try:
            lid = eng.default_entry_label()
            r1 = eng.run_label(lid, frame={"url": url})
        finally:
            eng.close()

        if r1 != "payment_required":
            print("expected step1 result 'payment_required', got:", repr(r1), file=sys.stderr, flush=True)
            return 1

        # Fresh registry for step 2 so adapter state cannot leak between runs.
        reg2 = _build_registry()
        eng2 = RuntimeEngine.from_code(
            code,
            strict=True,
            trace=False,
            adapters=reg2,
            source_path=src_path,
        )
        try:
            lid2 = eng2.default_entry_label()
            r2 = eng2.run_label(
                lid2,
                frame={
                    "url": url,
                    "http_payment": {"x402": {"payment_signature": "demo-local-signature"}},
                },
            )
        finally:
            eng2.close()

        if r2 != 200:
            print("expected step2 HTTP status 200, got:", repr(r2), file=sys.stderr, flush=True)
            return 1

        print(json.dumps({"ok": True, "demo_url": url, "step1": r1, "step2_status": r2}, indent=2, default=str))
        return 0
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5.0)


def main() -> None:
    raise SystemExit(run_roundtrip())


if __name__ == "__main__":
    main()
