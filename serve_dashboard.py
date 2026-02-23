#!/usr/bin/env python3
"""Run the emitted server (API + static). Serves dashboard and any other pages under static/."""
import os
import subprocess
import sys
import webbrowser

SERVER_DIR = os.path.join(os.path.dirname(__file__), "tests", "emits", "server")
PORT = 8765

def main():
    if not os.path.isfile(os.path.join(SERVER_DIR, "server.py")):
        print("Server not built. Run first: python3 run_tests_and_emit.py")
        sys.exit(1)
    url = f"http://127.0.0.1:{PORT}/"
    print(f"Serving API + static at {url} (API at {url}api/)")
    webbrowser.open(url)
    subprocess.run([sys.executable, "server.py"], cwd=SERVER_DIR)

if __name__ == "__main__":
    main()
