from __future__ import annotations

"""Hermes-facing MCP entrypoint shim.

Hermes Agent installs the AINL MCP server via `ainl install-mcp --host hermes`
and executes the canonical server module directly. This file exists to mirror
other host integration folders and to provide a stable import path for any
Hermes-specific server configuration in the future.
"""

from scripts.ainl_mcp_server import main


if __name__ == "__main__":
    main()

