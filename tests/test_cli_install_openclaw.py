import os
import subprocess
import sys
from pathlib import Path


def test_install_openclaw_dry_run_succeeds_without_openclaw_cli(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["PATH"] = "/nonexistent"
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "cli.main",
            "install",
            "openclaw",
            "--dry-run",
            "--workspace",
            str(tmp_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Dry-run complete" in result.stdout
    assert "openclaw CLI not found on PATH" in result.stdout
