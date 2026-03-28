#!/usr/bin/env python3
"""Run the emitted server (API + static). Serves dashboard and any other pages under static/."""
import argparse
import os
import subprocess
import sys
import webbrowser

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER_DIR = os.path.join(ROOT_DIR, "tests", "emits", "server")
DEFAULT_PORT = 8765


def main() -> None:
    ap = argparse.ArgumentParser(description="Serve AINL emitted dashboard (API + static).")
    ap.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("AINL_DASHBOARD_PORT", DEFAULT_PORT)),
        help=f"HTTP port (default: {DEFAULT_PORT} or AINL_DASHBOARD_PORT)",
    )
    ap.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open a browser tab automatically",
    )
    args = ap.parse_args()
    port = args.port

    if not os.path.isfile(os.path.join(SERVER_DIR, "server.py")):
        print(
            "Emitted server not built. From the AINL repo root run:\n"
            "  python3 scripts/run_tests_and_emit.py\n"
            f"Expected: {os.path.join(SERVER_DIR, 'server.py')}"
        )
        sys.exit(1)
    url = f"http://127.0.0.1:{port}/"
    print(f"Serving API + static at {url} (API at {url}api/)")
    print(f"Static files from: {os.path.join(SERVER_DIR, 'static')}")
    print("If you see the old dashboard: run 'python3 scripts/run_tests_and_emit.py' then hard-refresh (Cmd+Shift+R).")
    if not args.no_browser:
        webbrowser.open(url)
    venv_python = os.path.join(SERVER_DIR, ".venv", "bin", "python")
    python_exe = venv_python if os.path.isfile(venv_python) else sys.executable
    if python_exe == venv_python:
        print("Using server venv (.venv). If missing deps: cd tests/emits/server && .venv/bin/pip install -r requirements.txt")
    # Emitted server runtime imports compiler_v2 from the repo; ensure repo root is on PYTHONPATH.
    env = os.environ.copy()
    env["PYTHONPATH"] = ROOT_DIR if not env.get("PYTHONPATH") else (ROOT_DIR + os.pathsep + env["PYTHONPATH"])
    env["PORT"] = str(port)
    subprocess.run([python_exe, "server.py"], cwd=SERVER_DIR, env=env)


if __name__ == "__main__":
    main()
