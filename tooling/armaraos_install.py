"""Bootstrap AINL for OpenFang: thin wrapper around tooling.mcp_host_install."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from tooling.mcp_host_install import (
    ensure_ainl_run_wrapper as _ensure_ainl_run_wrapper,
    ensure_mcp_registration as _ensure_mcp_registration,
    ensure_path_hint_in_shell_rc as _ensure_path_hint,
    run_install_mcp_host,
)
from tooling.mcp_host_install import ARMARAOS_PROFILE  # will be added


def ensure_mcp_registration(*, home: Path, dry_run: bool, verbose: bool) -> None:
    _ensure_mcp_registration(ARMARAOS_PROFILE, home=home, dry_run=dry_run, verbose=verbose)


def ensure_ainl_run_wrapper(*, home: Path, dry_run: bool, verbose: bool) -> Path:
    return _ensure_ainl_run_wrapper(ARMARAOS_PROFILE, home=home, dry_run=dry_run, verbose=verbose)


def ensure_path_hint_in_shell_rc(*, home: Path, dry_run: bool, verbose: bool) -> list[str]:
    return _ensure_path_hint(ARMARAOS_PROFILE, home=home, dry_run=dry_run, verbose=verbose)


def run_install_armaraos(
    *,
    dry_run: bool,
    verbose: bool,
    home: Optional[Path] = None,
    run_pip: Optional[Callable[[bool], int]] = None,
) -> int:
    return run_install_mcp_host("armaraos", dry_run=dry_run, verbose=verbose, home=home, run_pip=run_pip)


def run_install_armaraos_main(argv: Optional[list[str]] = None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="ainl install-armaraos")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--verbose", "-v", action="store_true")
    ns = p.parse_args(argv)
    return run_install_armaraos(dry_run=ns.dry_run, verbose=ns.verbose)
