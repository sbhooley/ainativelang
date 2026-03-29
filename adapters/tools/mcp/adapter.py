"""MCP adapter for AINL runtime.

Enables calls like:
  R mcp.openspace.execute_task task="..." search_scope="..."

group = mcp
target format: <server_name>.<tool_name>
args: dict of arguments to the tool.
"""
import json
import os
from pathlib import Path
from typing import Any, Dict

from runtime.adapters.base import RuntimeAdapter, AdapterError

# Import MCP client and registry from the same package (relative imports)
from .client import MCPClient
from .registry import MCPRegistry


class MCPToolAdapter(RuntimeAdapter):
    """Adapter that forwards tool calls to configured MCP servers."""

    def __init__(self):
        self.config_path = os.path.expanduser(os.getenv("OPENCLAW_CONFIG", "~/.openclaw/openclaw.json"))
        self.config: Dict[str, Any] = {}
        self._servers_initialized = False
        self._load_config()

    def _load_config(self):
        try:
            with open(self.config_path, "r") as f:
                self.config = json.load(f)
        except Exception as e:
            raise AdapterError(f"Failed to load OpenClaw config: {e}")

    def _ensure_servers(self):
        if self._servers_initialized:
            return
        if MCPRegistry is None:
            raise AdapterError("MCP support not available (MCPRegistry missing)")

        mcp_cfg = self.config.get("mcp", {}).get("servers", {})
        for name, server_cfg in mcp_cfg.items():
            # Only register if not already
            try:
                MCPRegistry.register_server(name, server_cfg)
            except Exception:
                # Might already be registered
                pass
        self._servers_initialized = True

    def call(self, target: str, args: list, context: Dict[str, Any]) -> Any:
        """
        target: expected format "server_name.tool_name", e.g. "openspace.execute_task"
        args: list of positional args; typically a single dict with named parameters
        """
        if '.' not in target:
            raise AdapterError(f"Invalid mcp target format: {target}. Use 'server.tool'.")
        server_name, tool_name = target.split('.', 1)

        self._ensure_servers()
        try:
            client = MCPRegistry.get_client(server_name)
        except KeyError:
            raise AdapterError(f"MCP server '{server_name}' not configured")

        # AINL passes args as a list; we expect a single dict (keyword args)
        if args and isinstance(args, list) and len(args) > 0:
            # Usually the first arg is the dict of named parameters
            arguments = args[0] if isinstance(args[0], dict) else {}
            # Append any extra args if needed? MCP tool expects a dict.
        else:
            arguments = {}
        try:
            result = client.call(tool_name, arguments or {})
            return result
        except Exception as e:
            raise AdapterError(f"MCP call failed: {e}") from e
