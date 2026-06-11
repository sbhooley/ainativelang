#!/usr/bin/env bash
# Repair AINL install layout under ~/.armaraos (cron shim, bin cache, MCP registration).
# Used by install.sh, upgrade-cli.sh, and armaraos doctor --repair (via Rust mirror logic).
# Safe to run repeatedly (idempotent).

set -euo pipefail

ainl_layout_repair_home_dir() {
    echo "${ARMARAOS_HOME:-${OPENFANG_HOME:-${HOME}/.armaraos}}"
}

ainl_layout_repair_venv_dir() {
    echo "${ARMARAOS_AINL_VENV:-$(ainl_layout_repair_home_dir)/ainl-venv}"
}

ainl_layout_repair_is_cron_shim() {
    local path="$1"
    [ -f "$path" ] || return 1
    head -n 30 "$path" 2>/dev/null | grep -qE 'REAL_AINL=|--enable-adapter[[:space:]]+http'
}

ainl_layout_repair_remove_legacy_shim() {
    local home="$1"
    local shim="${home}/bin/ainl"
    local backup="${home}/bin/ainl.cron-shim.bak"
    if [ ! -f "$shim" ]; then
        return 0
    fi
    if ! ainl_layout_repair_is_cron_shim "$shim"; then
        return 0
    fi
    if [ -e "$backup" ]; then
        backup="${home}/bin/ainl.cron-shim.$(date +%s).bak"
    fi
    mv "$shim" "$backup"
    echo "  Removed legacy ~/.armaraos/bin/ainl cron shim (saved as $(basename "$backup"))" >&2
}

ainl_layout_repair_resolve_ainl() {
    local home="$1"
    local venv_dir venv_ainl cache_line cached
    venv_dir="$(ainl_layout_repair_venv_dir)"
    venv_ainl="${venv_dir}/bin/ainl"
    if [ -x "$venv_ainl" ]; then
        echo "$venv_ainl"
        return 0
    fi
    cache_line="${home}/.armaraos-ainl-bin"
    if [ -f "$cache_line" ]; then
        cached="$(head -n 1 "$cache_line" | tr -d '\r\n')"
        if [ -n "$cached" ] && [ -x "$cached" ] && ! ainl_layout_repair_is_cron_shim "$cached"; then
            echo "$cached"
            return 0
        fi
    fi
    if command -v ainl >/dev/null 2>&1; then
        cached="$(command -v ainl)"
        if [ -n "$cached" ] && [ -x "$cached" ] && ! ainl_layout_repair_is_cron_shim "$cached"; then
            echo "$cached"
            return 0
        fi
    fi
    return 1
}

# Main entry: fix shim + cache + MCP registration. Returns 0 when ainl is runnable.
repair_ainl_layout() {
    local home ainl_bin
    home="$(ainl_layout_repair_home_dir)"
    mkdir -p "$home"

    ainl_layout_repair_remove_legacy_shim "$home"

    if ! ainl_bin="$(ainl_layout_repair_resolve_ainl "$home")"; then
        echo "  AINL layout repair: no runnable ainl found (venv or PATH)" >&2
        return 1
    fi

    printf '%s\n' "$ainl_bin" > "${home}/.armaraos-ainl-bin"

    if ! "$ainl_bin" --version >/dev/null 2>&1; then
        echo "  AINL layout repair: ainl at $ainl_bin failed --version" >&2
        return 1
    fi

    echo "  Refreshing AINL MCP registration..." >&2
    if ! "$ainl_bin" install-mcp --host armaraos >/dev/null 2>&1; then
        echo "  Warning: ainl install-mcp returned non-zero (continuing)" >&2
    fi

    echo "  AINL layout OK ($( "$ainl_bin" --version 2>/dev/null | head -1 || echo ainl ))" >&2
    return 0
}

if [[ "${BASH_SOURCE[0]:-}" == "${0}" ]]; then
    repair_ainl_layout
fi
