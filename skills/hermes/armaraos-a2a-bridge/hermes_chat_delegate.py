#!/usr/bin/env python3
"""Bridge delegate: read user message on stdin, run ``hermes chat -q``, print reply on stdout.

Hermes may print Rich borders on stdout; this strips obvious frame/session lines so ArmaraOS
sees mostly model text. Set ``HERMES_BIN`` if ``hermes`` is not on ``PATH``. Uses ``--yolo``
so automated / headless runs are not blocked by approval prompts (operator choice).
"""

from __future__ import annotations

import os
import subprocess
import sys


def _clean_hermes_output(raw_stdout: str) -> str:
    lines_out: list[str] = []
    for line in raw_stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("session_id:"):
            continue
        if stripped[0] in ("╭", "│", "╰"):
            continue
        if stripped.startswith("─") and "Hermes" in stripped:
            continue
        if "╭" in line or "╰" in line:
            continue
        lines_out.append(stripped)
    return "\n".join(lines_out).strip()


def main() -> int:
    hermes = (os.environ.get("HERMES_BIN") or "hermes").strip()
    timeout_s = int((os.environ.get("HERMES_DELEGATE_TIMEOUT_S") or "600").strip())
    user = sys.stdin.read()
    env = {**os.environ, "NO_COLOR": "1", "TERM": "dumb", "CI": "1"}
    proc = subprocess.run(
        [hermes, "chat", "-q", user, "-Q", "--source", "tool", "--yolo"],
        capture_output=True,
        text=True,
        timeout=timeout_s,
        env=env,
    )
    cleaned = _clean_hermes_output(proc.stdout or "")
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        if not cleaned:
            sys.stdout.write(
                f"hermes_delegate_failed rc={proc.returncode}: {err[:4000]}\n"
            )
            return min(proc.returncode, 255) if proc.returncode > 0 else 1
    sys.stdout.write(cleaned if cleaned else "(empty)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
