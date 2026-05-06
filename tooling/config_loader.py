"""Shared YAML configuration loader with recursive ``$VAR`` / ``${VAR}`` expansion.

Single source of truth for ``cli/main.py`` and ``scripts/ainl_mcp_server.py``,
which previously each carried their own copy of the same load + expandvars
recursion. The two had begun to drift (CLI gained env-var fallback for the
config path; MCP did not), which is the exact case this module is meant to
prevent.

Public surface
--------------

- :func:`expand_env_vars` -- recursive os.path.expandvars over nested
  dict/list/str structures (leaves non-strings untouched).
- :func:`load_yaml_config` -- read a YAML file and expand env vars in every
  string value.
- :func:`load_yaml_config_or_empty` -- same as above but returns ``{}`` when
  ``path`` is empty/None (CLI-style "config is optional" semantics).
- :func:`load_config_from_args_or_env` -- pulls path from ``args.config`` or
  the ``AINL_CONFIG`` env var, then loads (the original CLI behavior).
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional


def expand_env_vars(value: Any) -> Any:
    """Recursively expand ``$VAR`` / ``${VAR}`` in all string values.

    Mirrors the behavior previously duplicated in ``cli/main.py:_load_config``
    and ``scripts/ainl_mcp_server.py:_load_config_from_path``: leaves
    non-string scalars (numbers, booleans, ``None``) untouched, recurses
    through dicts and lists.
    """
    if isinstance(value, str):
        return os.path.expandvars(value)
    if isinstance(value, dict):
        return {k: expand_env_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [expand_env_vars(v) for v in value]
    return value


def load_yaml_config(path: str) -> Dict[str, Any]:
    """Read ``path`` as YAML and recursively expand env vars in string values.

    Raises :class:`FileNotFoundError` if the path does not exist. Returns ``{}``
    when the YAML document is empty (``yaml.safe_load`` returns ``None``).
    """
    import yaml

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return expand_env_vars(raw)


def load_yaml_config_or_empty(path: Optional[str]) -> Dict[str, Any]:
    """Load YAML config from ``path``, or return ``{}`` if no path is given."""
    if not path:
        return {}
    return load_yaml_config(path)


def load_config_from_args_or_env(
    args: Any,
    *,
    attr: str = "config",
    env_var: str = "AINL_CONFIG",
) -> Dict[str, Any]:
    """Resolve config path from ``args.<attr>`` or ``$<env_var>`` and load it.

    Returns ``{}`` when neither source provides a path. Used by the CLI's
    ``_load_config(args)`` to preserve "config is optional" behavior.
    """
    config_path = getattr(args, attr, None) or os.environ.get(env_var)
    return load_yaml_config_or_empty(config_path)
