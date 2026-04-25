#!/usr/bin/env python3
"""Minimal local HTTP server for x402-style 402 demos (stdlib only).

- GET without ``PAYMENT-SIGNATURE`` → **402** + ``PAYMENT-REQUIRED`` (base64url JSON).
- GET with ``PAYMENT-SIGNATURE`` (any non-empty value) → **200** JSON ``{"paid": true}``.

Used by ``scripts/run_http_machine_payment_roundtrip_demo.py``. Not for production.
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict


def _payment_required_header() -> str:
    payload: Dict[str, Any] = {"scheme": "x402-demo", "note": "local demo only"}
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:  # noqa: N802
        sig = (self.headers.get("PAYMENT-SIGNATURE") or "").strip()
        if sig:
            body = json.dumps({"paid": True, "path": self.path}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        msg = b'{"detail":"payment_required"}'
        self.send_response(402)
        self.send_header("Content-Type", "application/json")
        self.send_header("PAYMENT-REQUIRED", _payment_required_header())
        self.send_header("Content-Length", str(len(msg)))
        self.end_headers()
        self.wfile.write(msg)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", default="127.0.0.1", help="Bind address (default 127.0.0.1)")
    p.add_argument("--port", type=int, default=9402, help="TCP port (default 9402)")
    args = p.parse_args()
    httpd = HTTPServer((args.host, args.port), _Handler)
    print(f"http_machine_payment_demo_server listening on http://{args.host}:{args.port}/", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("shutdown", file=sys.stderr, flush=True)
        raise SystemExit(0) from None


if __name__ == "__main__":
    main()
