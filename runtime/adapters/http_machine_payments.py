"""HTTP machine-payment helpers (x402, MPP) for :class:`SimpleHttpAdapter`.

**Implemented here:** HTTP ``402`` challenge / proof header shapes for **x402**
and **MPP** (see ``docs/integrations/HTTP_MACHINE_PAYMENTS.md`` for the full
agentic-commerce landscape: **AP2**, **ACP** checkout vs IBM **ACP** messaging,
**AGTP**, and how each maps to native profiles vs generic ``http`` REST).

New HTTP-402 dialects can be added here without inventing parallel adapter names.
Protocols that are primarily **REST checkout** or **non-HTTP** transports stay
out of this module.

Spec pointers (human docs; wire formats evolve — keep parsers tolerant):

- x402: https://docs.x402.org/core-concepts/http-402
- MPP: https://mpp.dev/protocol/ (HTTP 402 + ``WWW-Authenticate: Payment``)
"""

from __future__ import annotations

import base64
import json
import re
from typing import Any, Dict, Mapping, Optional, Tuple


def normalize_header_dict(headers: Mapping[str, str]) -> Dict[str, str]:
    return {str(k).lower(): str(v) for k, v in dict(headers).items()}


def detect_402_wire_profile(headers_lc: Mapping[str, str]) -> Optional[str]:
    """Return ``\"x402\"``, ``\"mpp\"``, or ``None`` based on response headers."""
    if not headers_lc:
        return None
    if "payment-required" in headers_lc:
        # x402 V2 uses PAYMENT-REQUIRED on 402 responses.
        return "x402"
    www = (headers_lc.get("www-authenticate") or "").strip()
    if not www:
        return None
    # MPP uses the Payment HTTP auth scheme inside WWW-Authenticate.
    if re.search(r"(?i)\bPayment\b", www):
        return "mpp"
    return None


def resolve_payment_profile(declared: str, headers_lc: Mapping[str, str]) -> Optional[str]:
    """Return effective wire profile for a 402 response, or ``None`` if undeclarable."""
    d = (declared or "none").strip().lower()
    if d == "none":
        return None
    if d in {"mpp", "x402"}:
        return d
    if d == "auto":
        return detect_402_wire_profile(headers_lc)
    return None


def _b64url_decode_optional(raw: str) -> Tuple[Optional[Any], Optional[str]]:
    s = (raw or "").strip()
    if not s:
        return None, None
    pad = "=" * ((4 - (len(s) % 4)) % 4)
    try:
        dec = base64.urlsafe_b64decode(s + pad)
    except Exception:
        try:
            dec = base64.standard_b64decode(s + pad)
        except Exception:
            return None, None
    try:
        return json.loads(dec.decode("utf-8")), None
    except Exception:
        try:
            return json.loads(dec.decode("utf-8", errors="replace")), None
        except Exception as exc:  # pragma: no cover - defensive
            return None, str(exc)


def summarize_x402_payment_required(value: str) -> Dict[str, Any]:
    """Best-effort decode of ``PAYMENT-REQUIRED`` (base64 JSON in x402 V2 docs)."""
    parsed, err = _b64url_decode_optional(value)
    out: Dict[str, Any] = {"encoding": "base64+json", "decoded": parsed}
    if err:
        out["decode_error"] = err
    return out


def summarize_mpp_www_authenticate(value: str) -> Dict[str, Any]:
    """Surface MPP ``WWW-Authenticate: Payment`` parameters without pretending full ABNF coverage."""
    raw = (value or "").strip()
    out: Dict[str, Any] = {"raw": raw, "params": {}}
    if not raw:
        return out
    # Strip scheme token (Payment) then split comma-separated auth-params (tolerant).
    m = re.match(r"(?is)^\s*Payment\s+(.*)$", raw)
    tail = m.group(1) if m else raw
    # Split on commas not inside quotes (good enough for typical challenges).
    parts: list[str] = []
    buf: list[str] = []
    in_q = False
    esc = False
    for ch in tail:
        if esc:
            buf.append(ch)
            esc = False
            continue
        if ch == "\\":
            esc = True
            buf.append(ch)
            continue
        if ch == '"':
            in_q = not in_q
            buf.append(ch)
            continue
        if ch == "," and not in_q:
            parts.append("".join(buf).strip())
            buf = []
            continue
        buf.append(ch)
    if buf:
        parts.append("".join(buf).strip())
    params: Dict[str, str] = {}
    for p in parts:
        if "=" not in p:
            continue
        k, v = p.split("=", 1)
        k = k.strip().lower()
        vv = v.strip()
        if len(vv) >= 2 and vv[0] == vv[-1] == '"':
            vv = vv[1:-1]
        params[k] = vv
    out["params"] = params
    return out


def merge_frame_payment_headers(
    headers: Mapping[str, str],
    context: Mapping[str, Any],
) -> Dict[str, str]:
    """Merge operator-supplied payment headers from the runtime frame (``http_payment``).

    Supported shapes (all optional; can be combined with ``headers``):

    - ``{"headers": {"PAYMENT-SIGNATURE": "...", "Authorization": "..."}}``
    - ``{"x402": {"payment_signature": "..."}}`` → ``PAYMENT-SIGNATURE``
    - ``{"mpp": {"authorization_payment": "eyJ..."}}`` → ``Authorization: Payment ...``
    - ``{"mpp": {"authorization": "Payment eyJ..."}}`` → ``Authorization`` as given
    """
    out: Dict[str, str] = {str(k): str(v) for k, v in dict(headers).items()}
    if not isinstance(context, Mapping):
        return out
    hp = context.get("http_payment")
    if not isinstance(hp, Mapping):
        return out

    extra = hp.get("headers")
    if isinstance(extra, Mapping):
        for k, v in extra.items():
            if v is None:
                continue
            out[str(k)] = str(v)

    x402 = hp.get("x402")
    if isinstance(x402, Mapping):
        sig = x402.get("payment_signature")
        if sig is not None and str(sig).strip():
            out.setdefault("PAYMENT-SIGNATURE", str(sig))

    mpp = hp.get("mpp")
    if isinstance(mpp, Mapping):
        auth = mpp.get("authorization")
        if auth is not None and str(auth).strip():
            out.setdefault("Authorization", str(auth))
        else:
            cred = mpp.get("authorization_payment") or mpp.get("credential")
            if cred is not None and str(cred).strip():
                c = str(cred).strip()
                if c.lower().startswith("payment "):
                    out.setdefault("Authorization", c)
                else:
                    out.setdefault("Authorization", f"Payment {c}")

    return out


def build_payment_challenge_envelope(
    *,
    profile: str,
    headers_lc: Mapping[str, str],
    headers_orig: Mapping[str, str],
    body: Any,
    url: str,
) -> Dict[str, Any]:
    """Structured challenge metadata for 402 responses (no secrets)."""
    block: Dict[str, Any] = {"profile": profile, "kind": "http_402"}
    if profile == "x402":
        pr = headers_lc.get("payment-required") or headers_orig.get("PAYMENT-REQUIRED")
        if pr:
            block["payment_required"] = summarize_x402_payment_required(str(pr))
            block["payment_required_header"] = str(pr)
    elif profile == "mpp":
        www = headers_lc.get("www-authenticate") or headers_orig.get("WWW-Authenticate")
        if www:
            block["www_authenticate"] = summarize_mpp_www_authenticate(str(www))
    if body is not None:
        block["body"] = body
    if url:
        block["url"] = url
    return block
