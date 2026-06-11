#!/usr/bin/env bash
# ArmaraOS installer — Linux, macOS, WSL (Windows: use install.ps1 in PowerShell)
# Installs the ArmaraOS CLI and AINL (ainativelang[mcp]) — both are required.
# Usage: curl -sSfL https://ainativelang.com/install.sh | sh
#
# Environment variables:
#   ARMARAOS_INSTALL_DIR  — custom install directory (default: ~/.armaraos/bin)
#   ARMARAOS_VERSION      — install a specific version tag (default: latest)
#   ARMARAOS_AUTO_PYTHON  — set to 0 to skip auto-installing Python (macOS: brew; default: 1)
#   ARMARAOS_AINL_VENV       — AINL virtualenv when system Python is PEP 668 (default: ~/.armaraos/ainl-venv)
#   ARMARAOS_DOWNLOAD_BASE — CLI mirror base (default: raw.githubusercontent.com/.../downloads/armaraos/cli)
#   ARMARAOS_SKIP_AUTO_LAUNCH — set to 1 to skip auto start + dashboard (default: 0)
#   ARMARAOS_DAEMON_START_TIMEOUT — seconds to poll /api/health after spawn (default: 45)
#   ARMARAOS_INSTALL_DAEMON_BUDGET — max seconds for the whole launch phase (default: 120)
#   ARMARAOS_INSTALL_DAEMON_GRACE_SEC — final recheck after main wait (default: 15)
#   ARMARAOS_SKIP_INSTALL_REPAIR — set to 1 to skip repair+retry during launch (default: 0)
#
# Legacy aliases (supported for compatibility):
#   OPENFANG_INSTALL_DIR, OPENFANG_VERSION

set -euo pipefail

# Public CLI binaries + checksums (hosted on sbhooley/ainativelang — same pattern as desktop DMGs).
DOWNLOAD_BASE="${ARMARAOS_DOWNLOAD_BASE:-https://raw.githubusercontent.com/sbhooley/ainativelang/main/downloads/armaraos/cli}"
INSTALL_DIR="${ARMARAOS_INSTALL_DIR:-${OPENFANG_INSTALL_DIR:-$HOME/.armaraos/bin}}"
SHELL_RC=""

resolve_latest_tag() {
    if [ -n "${ARMARAOS_VERSION:-}" ]; then
        echo "$ARMARAOS_VERSION"
        return 0
    fi
    if [ -n "${OPENFANG_VERSION:-}" ]; then
        echo "$OPENFANG_VERSION"
        return 0
    fi
    local json tag base
    for base in \
        "${DOWNLOAD_BASE%/}" \
        "https://ainativelang.com/downloads/armaraos/cli" \
        "https://raw.githubusercontent.com/sbhooley/ainativelang/main/downloads/armaraos/cli"; do
        json="$(curl -fsSL "${base}/latest.json" 2>/dev/null)" || continue
        tag="$(printf '%s' "$json" | sed -n 's/.*"tag"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)"
        if [ -n "$tag" ]; then
            echo "$tag"
            return 0
        fi
    done
    return 1
}

detect_platform() {
    OS=$(uname -s | tr '[:upper:]' '[:lower:]')
    ARCH=$(uname -m)
    case "$ARCH" in
        x86_64|amd64) ARCH="x86_64" ;;
        aarch64|arm64) ARCH="aarch64" ;;
        *) echo "  Unsupported architecture: $ARCH"; exit 1 ;;
    esac
    case "$OS" in
        linux) PLATFORM="${ARCH}-unknown-linux-gnu" ;;
        darwin) PLATFORM="${ARCH}-apple-darwin" ;;
        mingw*|msys*|cygwin*)
            echo ""
            echo "  For Windows, use PowerShell instead:"
            echo "    irm https://ainativelang.com/install.ps1 | iex"
            echo ""
            echo "  Or download the .msi desktop installer from:"
            echo "    https://ainativelang.com/armaraos"
            exit 1
            ;;
        *) echo "  Unsupported OS: $OS"; exit 1 ;;
    esac
}

detect_shell_rc() {
    local user_shell="${SHELL:-}"
    if [ -z "$user_shell" ] && command -v getent &>/dev/null; then
        user_shell=$(getent passwd "$(id -un)" 2>/dev/null | cut -d: -f7)
    fi
    if [ -z "$user_shell" ] && [ -f /etc/passwd ]; then
        user_shell=$(grep "^$(id -un):" /etc/passwd 2>/dev/null | cut -d: -f7)
    fi
    case "$user_shell" in
        */zsh)  SHELL_RC="$HOME/.zshrc" ;;
        */bash) SHELL_RC="$HOME/.bashrc" ;;
        */fish) SHELL_RC="$HOME/.config/fish/config.fish" ;;
    esac
    if [ -z "$SHELL_RC" ]; then
        if [ -f "$HOME/.bashrc" ]; then
            SHELL_RC="$HOME/.bashrc"
        elif [ -f "$HOME/.zshrc" ]; then
            SHELL_RC="$HOME/.zshrc"
        elif [ -f "$HOME/.config/fish/config.fish" ]; then
            SHELL_RC="$HOME/.config/fish/config.fish"
        fi
    fi
}

append_path_to_shell_rc() {
    local dir="$1"
    local marker="$2"
    [ -n "$SHELL_RC" ] || return 0
    if grep -q "$marker" "$SHELL_RC" 2>/dev/null; then
        return 0
    fi
    case "$SHELL_RC" in
        */config.fish)
            mkdir -p "$(dirname "$SHELL_RC")"
            echo "fish_add_path \"$dir\"" >> "$SHELL_RC"
            ;;
        *)
            echo "export PATH=\"$dir:\$PATH\"" >> "$SHELL_RC"
            ;;
    esac
    echo "  Added $dir to PATH in $SHELL_RC"
}

export_path_now() {
    export PATH="$1:$PATH"
}

print_path_hint() {
    local bin="${1:-$(armaraos_cli_bin 2>/dev/null || true)}"
    echo ""
    echo "  PATH note: curl | sh runs in a subshell — open a new terminal or run:"
    if [ -n "$SHELL_RC" ] && [ -f "$SHELL_RC" ]; then
        echo "    source \"$SHELL_RC\""
    else
        echo "    export PATH=\"$INSTALL_DIR:\$PATH\""
    fi
    if [ -n "$bin" ]; then
        echo "  Or use the full path: $bin dashboard"
    fi
    echo ""
}

# Emit manifest URL + checksum URL for this platform (stdout: two lines). No fallback here.
resolve_cli_download_from_manifest() {
    local platform="$1"
    local base="${DOWNLOAD_BASE%/}"
    local json

    json="$(curl -fsSL "${base}/latest.json" 2>/dev/null || true)"
    [ -n "$json" ] || return 1

    python3 -c "
import json, sys
data = json.load(sys.stdin)
platform = sys.argv[1]
base = (data.get('download_base') or sys.argv[2]).rstrip('/')
entry = (data.get('platforms') or {}).get(platform)
if not entry:
    sys.exit(1)
archive = entry.get('archive') or ''
url = entry.get('url') or (f'{base}/{archive}' if archive else '')
sha = entry.get('sha256_url') or (f'{url}.sha256' if url else '')
if not url:
    sys.exit(1)
print(url)
print(sha)
" "$platform" "$base" <<< "$json" 2>/dev/null
}

download_cli_archive() {
    local platform="$1"
    local archive_path="$2"
    local base="${DOWNLOAD_BASE%/}"
    local tried=()
    local url sha candidate lines

    lines="$(resolve_cli_download_from_manifest "$platform" 2>/dev/null || true)"
    if [ -n "$lines" ]; then
        url="$(printf '%s\n' "$lines" | sed -n '1p')"
        sha="$(printf '%s\n' "$lines" | sed -n '2p')"
        if [ -n "$url" ]; then
            tried+=("$url")
            if curl -fsSL "$url" -o "$archive_path" 2>/dev/null; then
                CLI_DOWNLOAD_URL="$url"
                CLI_CHECKSUM_URL="${sha:-${url}.sha256}"
                return 0
            fi
            echo "  Skipped $(basename "$url") (download failed)" >&2
        fi
    fi

    for candidate in \
        "${base}/armaraos-${platform}.tar.gz" \
        "${base}/openfang-${platform}.tar.gz"; do
        case " ${tried[*]} " in
            *" $candidate "*) continue ;;
        esac
        if curl -fsSL "$candidate" -o "$archive_path" 2>/dev/null; then
            CLI_DOWNLOAD_URL="$candidate"
            CLI_CHECKSUM_URL="${candidate}.sha256"
            return 0
        fi
        echo "  Skipped $(basename "$candidate") (not found)" >&2
    done
    return 1
}

finalize_cli_binary() {
    local install_dir="$1"
    if [ -f "${install_dir}/armaraos" ]; then
        chmod +x "${install_dir}/armaraos"
        if [ -f "${install_dir}/openfang" ]; then
            chmod +x "${install_dir}/openfang" 2>/dev/null || true
        fi
        return 0
    fi
    if [ -f "${install_dir}/openfang" ]; then
        chmod +x "${install_dir}/openfang"
        cat > "${install_dir}/armaraos" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$DIR/openfang" "$@"
EOF
        chmod +x "${install_dir}/armaraos"
        return 0
    fi
    return 1
}

macos_quarantine_fix() {
    local bin="$1"
    [ "$OS" = "darwin" ] || return 0
    if command -v xattr &>/dev/null; then
        xattr -cr "$bin" 2>/dev/null || true
    fi
    if command -v codesign &>/dev/null; then
        codesign --force --sign - "$bin" 2>/dev/null || \
            echo "  Warning: ad-hoc codesign failed — if the binary is killed, run: xattr -cr $bin && codesign --force --sign - $bin"
    fi
}

python_version_ok() {
    "$1" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null
}

python_display_version() {
    local py="$1"
    "$py" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))' 2>/dev/null || echo "unknown"
}

python_is_externally_managed() {
    local py="$1"
    "$py" -c 'import sysconfig, pathlib; p=pathlib.Path(sysconfig.get_path("stdlib"))/"EXTERNALLY-MANAGED"; raise SystemExit(0 if p.is_file() else 1)' 2>/dev/null
}

find_python() {
    local candidate="" path=""
    for candidate in python3.12 python3.11 python3.10 python3 python; do
        path="$(command -v "$candidate" 2>/dev/null || true)"
        if [ -n "$path" ] && python_version_ok "$path"; then
            echo "$path"
            return 0
        fi
    done
    # Homebrew keg-only python@3.12 / python@3.11 (common on macOS)
    if [ "$OS" = "darwin" ] && command -v brew >/dev/null 2>&1; then
        local brew_py
        for brew_py in \
            "$(brew --prefix python@3.12 2>/dev/null)/bin/python3" \
            "$(brew --prefix python@3.11 2>/dev/null)/bin/python3" \
            "$(brew --prefix python@3.10 2>/dev/null)/bin/python3"; do
            if [ -x "$brew_py" ] && python_version_ok "$brew_py"; then
                echo "$brew_py"
                return 0
            fi
        done
    fi
    return 1
}

try_install_python_mac() {
    [ "$OS" = "darwin" ] || return 1
    [ "${ARMARAOS_AUTO_PYTHON:-1}" != "0" ] || return 1
    command -v brew >/dev/null 2>&1 || return 1
    echo "  No Python 3.10+ on PATH — installing via Homebrew (one-time, ~1 min)..." >&2
    if brew install python@3.12 2>/dev/null || brew install python3; then
        local brew_py
        brew_py="$(brew --prefix python@3.12 2>/dev/null)/bin/python3"
        if [ -x "$brew_py" ] && python_version_ok "$brew_py"; then
            echo "$brew_py"
            return 0
        fi
        if command -v python3 >/dev/null 2>&1 && python_version_ok "$(command -v python3)"; then
            command -v python3
            return 0
        fi
    fi
    return 1
}

print_python_help() {
    echo ""
    echo "  Install incomplete: Python 3.10+ is required for AINL (ainativelang[mcp])."
    echo "  ArmaraOS requires AINL — finish setup after Python is ready, then re-run this installer."
    echo ""
    if [ "$OS" = "darwin" ]; then
        echo "  Easiest options on macOS:"
        echo "    • Desktop app (bundled Python): https://ainativelang.com/armaraos"
        echo "    • Homebrew: brew install python@3.12"
        echo "    • Official installer: https://www.python.org/downloads/"
    else
        echo "  Install Python 3.10+, then re-run this script:"
        echo "    Debian/Ubuntu: sudo apt install python3 python3-pip python3-venv"
        echo "    Fedora:        sudo dnf install python3 python3-pip"
        echo "    Or:            https://www.python.org/downloads/"
        echo ""
        echo "  On PEP 668 systems (externally managed), the installer auto-creates"
        echo "  ~/.armaraos/ainl-venv when pip --user is blocked."
    fi
    echo ""
    echo "  Re-run after Python is ready:"
    echo "    curl -sSfL https://ainativelang.com/install.sh | sh"
    echo ""
}

ensure_python() {
    local py=""
    if py="$(find_python)"; then
        echo "  Using existing Python $(python_display_version "$py") ($py)" >&2
        echo "$py"
        return 0
    fi
    if py="$(try_install_python_mac)"; then
        echo "  Using Python $(python_display_version "$py") ($py)" >&2
        echo "$py"
        return 0
    fi
    print_python_help
    return 1
}

ainl_venv_dir() {
    echo "${ARMARAOS_AINL_VENV:-$HOME/.armaraos/ainl-venv}"
}

pip_stderr_indicates_externally_managed() {
    local log="$1"
    grep -qi 'externally-managed-environment\|EXTERNALLY-MANAGED' "$log" 2>/dev/null
}

pip_install_ainl_user() {
    local python="$1"
    local log
    log="$(mktemp)"
    if "$python" -m pip install --user -q "ainativelang[mcp]" 2>"$log"; then
        rm -f "$log"
        return 0
    fi
    if pip_stderr_indicates_externally_managed "$log"; then
        rm -f "$log"
        return 2
    fi
    "$python" -m pip install --upgrade pip >/dev/null 2>&1 || true
    if "$python" -m pip install --user "ainativelang[mcp]" 2>"$log"; then
        rm -f "$log"
        return 0
    fi
    if pip_stderr_indicates_externally_managed "$log"; then
        rm -f "$log"
        return 2
    fi
    cat "$log" >&2
    rm -f "$log"
    return 1
}

install_ainl_via_venv() {
    local base_python="$1"
    local venv_dir pip_py ainl_bin
    venv_dir="$(ainl_venv_dir)"
    echo "  System Python is externally managed — using venv at $venv_dir"

    if ! "$base_python" -m venv --help >/dev/null 2>&1; then
        echo "  Error: 'python3 -m venv' is unavailable."
        if [ "$OS" = "linux" ]; then
            echo "  Install it, then re-run: sudo apt install python3-venv python3-pip   # Debian/Ubuntu"
            echo "                          sudo dnf install python3-pip               # Fedora"
        fi
        return 1
    fi

    if [ ! -x "$venv_dir/bin/python" ]; then
        echo "  Creating AINL virtualenv..."
        if ! "$base_python" -m venv "$venv_dir"; then
            echo "  Error: could not create venv at $venv_dir"
            return 1
        fi
    fi

    pip_py="$venv_dir/bin/python"
    echo "  Installing ainativelang[mcp] into venv..."
    if ! "$pip_py" -m pip install -q "ainativelang[mcp]"; then
        "$pip_py" -m pip install --upgrade pip >/dev/null 2>&1 || true
        "$pip_py" -m pip install "ainativelang[mcp]"
    fi

    ainl_bin="$venv_dir/bin/ainl"
    if [ ! -x "$ainl_bin" ]; then
        echo "  Error: AINL installed in venv but 'ainl' not found at $ainl_bin"
        return 1
    fi

    echo "  Registering AINL MCP server for ArmaraOS..."
    "$ainl_bin" install-mcp --host armaraos

    append_path_to_shell_rc "$venv_dir/bin" "ainl-venv"
    export_path_now "$venv_dir/bin"
    local arm_home="${ARMARAOS_HOME:-${OPENFANG_HOME:-$HOME/.armaraos}}"
    mkdir -p "$arm_home"
    printf '%s\n' "$ainl_bin" > "$arm_home/.armaraos-ainl-bin"
    echo "  AINL ready in venv ($( "$ainl_bin" --version 2>/dev/null | head -1 || echo ainl ))"
}

install_ainl() {
    local python="$1"
    local pip_rc user_base ainl_bin
    echo ""
    echo "  Installing AINL (ainativelang[mcp])..."

    if ! python_version_ok "$python"; then
        local ver
        ver="$(python_display_version "$python")"
        echo "  Error: Python $ver is too old — AINL needs 3.10+."
        print_python_help
        return 1
    fi

    if python_is_externally_managed "$python"; then
        install_ainl_via_venv "$python"
        return $?
    fi

    pip_rc=0
    pip_install_ainl_user "$python" || pip_rc=$?
    if [ "$pip_rc" -eq 2 ]; then
        install_ainl_via_venv "$python"
        return $?
    fi
    if [ "$pip_rc" -ne 0 ]; then
        return 1
    fi

    user_base="$("$python" -c 'import site; print(site.USER_BASE)')"
    ainl_bin="$user_base/bin/ainl"
    if [ ! -x "$ainl_bin" ]; then
        ainl_bin="$(command -v ainl 2>/dev/null || true)"
    fi
    if [ -z "${ainl_bin:-}" ] || [ ! -x "${ainl_bin:-/dev/null}" ]; then
        echo "  Error: AINL installed but could not find executable 'ainl'."
        echo "  Hint: export PATH=\"$user_base/bin:\$PATH\""
        return 1
    fi

    echo "  Registering AINL MCP server for ArmaraOS..."
    "$ainl_bin" install-mcp --host armaraos

    append_path_to_shell_rc "$user_base/bin" "ainl"
    export_path_now "$user_base/bin"
    echo "  AINL ready ($( "$ainl_bin" --version 2>/dev/null | head -1 || echo ainl ))"
}

config_api_listen_addr() {
    local config home listen
    home="$(armaraos_home_dir)"
    config="${home}/config.toml"
    listen=""
    if [ -f "$config" ]; then
        listen="$(grep -E '^[[:space:]]*api_listen[[:space:]]*=' "$config" 2>/dev/null | head -1 \
            | sed -E 's/.*=[[:space:]]*"([^"]+)".*/\1/' \
            | tr -d '\r')"
    fi
    if [ -z "$listen" ]; then
        # Match armaraos-types KernelConfig default (127.0.0.1:50051).
        listen="127.0.0.1:50051"
    fi
    printf '%s' "$listen" | sed 's/0\.0\.0\.0/127.0.0.1/g'
}

daemon_base_url() {
    local dj listen
    dj="$(armaraos_home_dir)/daemon.json"
    if [ -f "$dj" ]; then
        python3 -c "
import json, sys
try:
    d = json.load(open(sys.argv[1]))
    a = (d.get('listen_addr') or sys.argv[2]).replace('0.0.0.0', '127.0.0.1')
    print('http://' + a)
except Exception:
    print('http://' + sys.argv[2])
" "$dj" "$(config_api_listen_addr)" 2>/dev/null || echo "http://$(config_api_listen_addr)"
    else
        echo "http://$(config_api_listen_addr)"
    fi
}

daemon_start_timeout_sec() {
    local raw="${ARMARAOS_DAEMON_START_TIMEOUT:-45}"
    if [[ "$raw" =~ ^[0-9]+$ ]] && [ "$raw" -gt 0 ]; then
        echo "$raw"
    else
        echo 45
    fi
}

install_daemon_budget_sec() {
    local raw="${ARMARAOS_INSTALL_DAEMON_BUDGET:-120}"
    if [[ "$raw" =~ ^[0-9]+$ ]] && [ "$raw" -gt 0 ]; then
        echo "$raw"
    else
        echo 120
    fi
}

install_daemon_grace_sec() {
    local raw="${ARMARAOS_INSTALL_DAEMON_GRACE_SEC:-15}"
    if [[ "$raw" =~ ^[0-9]+$ ]] && [ "$raw" -ge 0 ]; then
        echo "$raw"
    else
        echo 15
    fi
}

armaraos_home_dir() {
    echo "${ARMARAOS_HOME:-${OPENFANG_HOME:-${HOME}/.armaraos}}"
}

daemon_listen_port() {
    local base="${1:-$(daemon_base_url)}"
    local port default_port
    port="$(printf '%s' "$base" | sed -n 's|.*:\([0-9][0-9]*\)/\?$|\1|p')"
    default_port="$(config_api_listen_addr | sed -n 's|.*:\([0-9][0-9]*\)$|\1|p')"
    if [ -n "$port" ]; then
        echo "$port"
    elif [ -n "$default_port" ]; then
        echo "$default_port"
    else
        echo 50051
    fi
}

armaraos_process_running() {
    if command -v pgrep >/dev/null 2>&1; then
        pgrep -x armaraos >/dev/null 2>&1 || pgrep -x openfang >/dev/null 2>&1
        return $?
    fi
    ps aux 2>/dev/null | grep -E '[a]rmaraos|[o]penfang' >/dev/null 2>&1
}

port_in_use() {
    local port="${1:-4200}"
    if command -v ss >/dev/null 2>&1; then
        ss -ltn 2>/dev/null | grep -q ":${port} "
        return $?
    fi
    if command -v lsof >/dev/null 2>&1; then
        lsof -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
        return $?
    fi
    if command -v netstat >/dev/null 2>&1; then
        netstat -an 2>/dev/null | grep -E "[\.:]${port}[[:space:]].*LISTEN" >/dev/null 2>&1
        return $?
    fi
    return 1
}

armaraos_log_tail() {
    local lines="${1:-6}"
    local home
    home="$(armaraos_home_dir)"
    local f
    for f in "$home/logs/daemon.log" "$home/logs/tui.log" "$home/tui.log"; do
        if [ -f "$f" ]; then
            tail -n "$lines" "$f" 2>/dev/null
            return 0
        fi
    done
    return 1
}

diagnose_daemon_launch() {
    local bin="$1"
    local base="${2:-$(daemon_base_url)}"
    local port log_tail pid

    port="$(daemon_listen_port "$base")"

    if [ -z "$bin" ] || [ ! -x "$bin" ]; then
        echo "FINDING: CLI binary not found at install path"
        echo "HINT: Re-run the installer; check permissions and antivirus"
        return 0
    fi

    if ! run_with_timeout 12 "$bin" --version >/dev/null 2>&1; then
        echo "FINDING: armaraos --version failed or timed out (antivirus may be scanning)"
        echo "HINT: Allow the install directory in antivirus, then run: armaraos --version"
    fi

    if daemon_healthy "$base"; then
        echo "FINDING: Daemon is healthy at ${base}"
        echo "HINT: Open dashboard: armaraos dashboard"
        return 0
    fi

    if armaraos_process_running; then
        echo "FINDING: ArmaraOS process is running but /api/health did not respond yet"
        echo "HINT: Wait a few seconds, then: armaraos status"
        echo "HINT: If stuck: armaraos stop && armaraos start --yolo --detach"
    elif port_in_use "$port"; then
        echo "FINDING: Port ${port} is in use by another program"
        echo "HINT: Stop the other service or change api_listen in ~/.armaraos/config.toml"
    else
        echo "FINDING: No armaraos process detected"
        echo "HINT: Start manually: armaraos start --yolo --detach"
        echo "HINT: If nothing starts: armaraos doctor --repair"
        echo "HINT: First boot can take 30-60s under antivirus scan"
    fi

    if [ -f "${HOME}/.armaraos/daemon.json" ]; then
        pid="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('pid',''))" "${HOME}/.armaraos/daemon.json" 2>/dev/null || true)"
        if [ -n "$pid" ] && ! kill -0 "$pid" 2>/dev/null; then
            echo "FINDING: Stale daemon.json (PID ${pid} is not running)"
            echo "HINT: Run: armaraos stop && armaraos start --yolo --detach"
        fi
    fi

    if log_tail="$(armaraos_log_tail 6)"; then
        echo "FINDING: Log file present under ~/.armaraos/logs/"
        printf '%s\n' "$log_tail" | while IFS= read -r line; do
            echo "LOG: $line"
        done
    else
        echo "FINDING: No daemon log yet — boot may not have started"
    fi
}

write_daemon_launch_report() {
    local status="$1"
    local bin="$2"
    local line kind text hint_header printed_hints

    echo ""
    echo "  ── Daemon launch ──"
    case "$status" in
        success)
            echo "  Status: RUNNING"
            echo "  Dashboard: $(daemon_base_url)/"
            ;;
        failed)
            echo "  Status: NOT READY (install finished — CLI + AINL are installed)"
            echo "  Detected:"
            hint_header=0
            printed_hints=0
            log_header=0
            while IFS= read -r line; do
                kind="${line%%:*}"
                text="${line#*: }"
                case "$kind" in
                    FINDING) echo "    • $text" ;;
                    HINT)
                        if [ "$hint_header" -eq 0 ]; then
                            echo "  Next steps:"
                            hint_header=1
                        fi
                        printed_hints=$((printed_hints + 1))
                        echo "    ${printed_hints}. $text"
                        ;;
                    LOG)
                        if [ "$log_header" -eq 0 ]; then
                            echo "  Recent log:"
                            log_header=1
                        fi
                        echo "    $text"
                        ;;
                esac
            done <<EOF
$(diagnose_daemon_launch "$bin" "$(daemon_base_url)" 2>/dev/null || true)
EOF
            echo "  Logs: $(armaraos_home_dir)/logs/daemon.log"
            ;;
        skipped)
            echo "  Status: SKIPPED (ARMARAOS_SKIP_AUTO_LAUNCH=1)"
            ;;
    esac
    echo ""
}

install_deadline_epoch() {
    echo $(( $(date +%s) + $(install_daemon_budget_sec) ))
}

remaining_budget_sec() {
    local deadline="$1"
    local now remain
    now=$(date +%s)
    remain=$(( deadline - now ))
    if [ "$remain" -lt 0 ]; then
        echo 0
    else
        echo "$remain"
    fi
}

run_with_timeout() {
    local timeout_sec="$1"
    shift
    if command -v timeout >/dev/null 2>&1; then
        timeout "$timeout_sec" "$@"
    elif command -v gtimeout >/dev/null 2>&1; then
        gtimeout "$timeout_sec" "$@"
    else
        perl -e 'alarm shift; exec @ARGV or exit 127' "$timeout_sec" "$@"
    fi
}

start_daemon_detached_process() {
    local bin="$1"
    # Do not wait on `armaraos start --detach` — it polls health internally for up to 45s.
    if command -v setsid >/dev/null 2>&1; then
        setsid "$bin" start --yolo --detach >/dev/null 2>&1 &
    else
        nohup "$bin" start --yolo --detach >/dev/null 2>&1 &
    fi
    disown 2>/dev/null || true
}

open_dashboard_url() {
    local base="$1"
    local url="${base%/}/"
    if command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$url" >/dev/null 2>&1 &
    elif command -v open >/dev/null 2>&1; then
        open "$url" >/dev/null 2>&1 &
    else
        return 1
    fi
    return 0
}

daemon_healthy() {
    local base="${1:-$(daemon_base_url)}"
    curl -sfS -m 3 "${base%/}/api/health" >/dev/null 2>&1
}

wait_daemon_healthy() {
    local base="$1"
    local timeout="${2:-45}"
    local deadline="${3:-}"
    local label="${4:-daemon}"
    local i=0 started now elapsed left last_progress=-5 check_base

    if [ -n "$deadline" ]; then
        started="$(date +%s)"
        while [ "$(date +%s)" -lt "$deadline" ]; do
            check_base="$(daemon_base_url)"
            if daemon_healthy "$check_base"; then
                elapsed=$(( $(date +%s) - started ))
                [ "$elapsed" -lt 1 ] && elapsed=1
                echo "  ${label} ready after ${elapsed}s ($check_base)" >&2
                return 0
            fi
            now="$(date +%s)"
            elapsed=$(( now - started ))
            left=$(( deadline - now ))
            [ "$left" -lt 0 ] && left=0
            if [ "$elapsed" -ge $(( last_progress + 5 )) ]; then
                last_progress=$elapsed
                echo "  Waiting for ${label}... ${elapsed}s elapsed (${left}s left, checking ${check_base%/}/api/health)" >&2
            fi
            sleep 1
        done
        check_base="$(daemon_base_url)"
        echo "  Timed out waiting for ${label} (${check_base%/}/api/health)" >&2
        return 1
    fi
    while [ "$i" -lt "$timeout" ]; do
        check_base="$(daemon_base_url)"
        if daemon_healthy "$check_base"; then
            return 0
        fi
        i=$((i + 1))
        sleep 1
    done
    return 1
}

repair_armaraos_install() {
    local bin="$1"
    local of_home="${HOME}/.armaraos"
    local sub config

    for sub in data agents logs; do
        mkdir -p "${of_home}/${sub}"
    done
    config="${of_home}/config.toml"
    if [ ! -f "$config" ]; then
        echo "  Repair: first-time setup (armaraos init --quick)..." >&2
        run_with_timeout 60 "$bin" init --quick || true
    fi
    repair_config_toml_windows_paths || true
    ARMARAOS_NONINTERACTIVE=1 run_with_timeout 60 "$bin" doctor --repair >/dev/null 2>&1 || {
        echo "  Warning: armaraos doctor --repair timed out or failed (continuing install)." >&2
    }
    run_with_timeout 15 "$bin" stop 2>/dev/null || true
    sleep 1
}

# Fix command = "C:\..." lines where backslashes break TOML (desktop AINL bootstrap on Windows).
repair_config_toml_windows_paths() {
    local config="${HOME}/.armaraos/config.toml"
    [ -f "$config" ] || return 0
    python3 - "$config" <<'PY' || return 1
import sys
from pathlib import Path

path = Path(sys.argv[1])
raw = path.read_text(encoding="utf-8")
keys = {"command", "path", "root", "cwd"}
ends_nl = raw.endswith("\n")
lines = raw.splitlines()
out = []
changed = False
for line in lines:
    trimmed = line.strip()
    if "=" not in trimmed or '"' not in trimmed:
        out.append(line)
        continue
    key = trimmed.split("=", 1)[0].strip()
    if key not in keys:
        out.append(line)
        continue
    eq = line.find("=")
    after = line[eq + 1 :].lstrip()
    if not after.startswith('"'):
        out.append(line)
        continue
    vs = line.find('"', eq)
    if vs < 0:
        out.append(line)
        continue
    er = line[vs + 1 :].rfind('"')
    if er < 0:
        out.append(line)
        continue
    inner = line[vs + 1 : vs + 1 + er]
    if "\\" not in inner:
        out.append(line)
        continue
    fixed = inner.replace("\\", "/")
    out.append(line[: vs + 1] + fixed + line[vs + 1 + er :])
    changed = True
if not changed:
    sys.exit(0)
text = "\n".join(out)
if ends_nl and not text.endswith("\n"):
    text += "\n"
path.write_text(text, encoding="utf-8")
print("  Repaired Windows path escaping in config.toml (MCP command paths)", file=sys.stderr)
PY
}

start_armaraos_daemon() {
    local bin="$1"
    local deadline="${2:-}"
    local base remaining grace diag_line

    if [ -z "$deadline" ]; then
        deadline=$(( $(date +%s) + $(install_daemon_budget_sec) ))
    fi

    base="$(daemon_base_url)"
    if daemon_healthy "$base"; then
        echo "  Daemon already healthy at $base" >&2
        return 0
    fi

    echo "" >&2
    echo "  Starting ArmaraOS daemon (background, non-blocking)..." >&2
    echo "  (First boot can take up to $(install_daemon_budget_sec)s — progress updates every 5s)" >&2
    start_daemon_detached_process "$bin"
    if wait_daemon_healthy "$base" 0 "$deadline" "daemon"; then
        return 0
    fi

    echo "  Quick check:" >&2
    diagnose_daemon_launch "$bin" "$base" 2>/dev/null | grep '^FINDING:' | head -3 | while IFS= read -r diag_line; do
        echo "    • ${diag_line#FINDING: }" >&2
    done

    if [ "${ARMARAOS_SKIP_INSTALL_REPAIR:-}" = "1" ]; then
        echo "  Repair skipped (ARMARAOS_SKIP_INSTALL_REPAIR=1)." >&2
        return 1
    fi

    remaining="$(remaining_budget_sec "$deadline")"
    if [ "$remaining" -lt 12 ]; then
        echo "  No time left for repair retry in this install window." >&2
        return 1
    fi

    echo "  Repairing install state and retrying (up to ${remaining}s left)..." >&2
    repair_armaraos_install "$bin"
    start_daemon_detached_process "$bin"
    wait_daemon_healthy "$(daemon_base_url)" 0 "$deadline" "daemon (retry)"
}

open_armaraos_dashboard() {
    local bin="$1"
    local deadline="${2:-}"
    local base remaining

    echo "" >&2
    echo "  Opening dashboard in your browser..." >&2
    base="$(daemon_base_url)"
    if daemon_healthy "$base"; then
        if open_dashboard_url "$base"; then
            return 0
        fi
        echo "  Browser did not open — visit: ${base%/}/" >&2
        return 1
    fi

    if [ -n "$deadline" ]; then
        remaining="$(remaining_budget_sec "$deadline")"
        [ "$remaining" -lt 5 ] && remaining=5
    else
        remaining=30
    fi
    if run_with_timeout "$remaining" "$bin" dashboard; then
        return 0
    fi
    base="$(daemon_base_url)"
    if daemon_healthy "$base"; then
        return 0
    fi
    echo "  Browser did not open — visit: ${base%/}/" >&2
    return 1
}

# Golden path (Mac/Linux + Windows install.ps1): start daemon, verify /api/health, repair + retry, open dashboard.
launch_armaraos_after_install() {
    if [ "${ARMARAOS_SKIP_AUTO_LAUNCH:-}" = "1" ]; then
        write_daemon_launch_report skipped ""
        printf '%s\n' "skipped"
        return 0
    fi

    local bin base deadline healthy grace grace_deadline
    bin="$(armaraos_cli_bin)"
    if [ -z "$bin" ]; then
        write_daemon_launch_report failed ""
        printf '%s\n' "failed"
        return 0
    fi

    deadline="$(install_deadline_epoch)"
    base="$(daemon_base_url)"
    healthy=0
    if daemon_healthy "$base"; then
        healthy=1
        echo "" >&2
        echo "  Daemon already running." >&2
    elif start_armaraos_daemon "$bin" "$deadline"; then
        healthy=1
        echo "  Daemon is running." >&2
    fi

    if [ "$healthy" -eq 0 ]; then
        grace="$(install_daemon_grace_sec)"
        if [ "$grace" -gt 0 ]; then
            echo "" >&2
            echo "  Final recheck (${grace}s) — daemon may still be starting..." >&2
            grace_deadline=$(( $(date +%s) + grace ))
            if wait_daemon_healthy "$(daemon_base_url)" 0 "$grace_deadline" "daemon (recheck)"; then
                healthy=1
            fi
        fi
    fi

    open_armaraos_dashboard "$bin" "$deadline" || true

    if [ "$healthy" -eq 0 ] && daemon_healthy "$(daemon_base_url)"; then
        healthy=1
        echo "  Daemon became healthy during dashboard open." >&2
    fi

    if [ "$healthy" -eq 1 ]; then
        write_daemon_launch_report success "$bin"
        printf '%s\n' "success"
        return 0
    fi
    write_daemon_launch_report failed "$bin"
    printf '%s\n' "failed"
    return 0
}

print_get_started() {
    local desktop_shortcut="${1:-}"
    local launch_result="${2:-skipped}"
    echo ""
    echo "  You're ready!"
    if [ "$launch_result" = "success" ]; then
        echo "  Your browser should show the dashboard (setup wizard on first visit)."
        echo "  You can close this terminal — the daemon keeps running."
    elif [ "$launch_result" = "failed" ]; then
        echo "  See the Daemon launch report above for detected issues and next steps."
        echo "  Quick retry: armaraos start --yolo --detach  then  armaraos dashboard"
    else
        echo "  Open the dashboard: armaraos dashboard"
        echo "  (starts the daemon if needed, then opens your browser)"
    fi
    if [ -n "$desktop_shortcut" ]; then
        echo "  Next time: double-click ArmaraOS Dashboard on your desktop."
    fi
    echo ""
    echo "  Verify anytime: armaraos doctor"
    echo "  Upgrade CLI:    armaraos update"
    echo ""
    if [ -n "$SHELL_RC" ]; then
        echo "  New terminals pick up PATH automatically. In an existing terminal:"
        case "$SHELL_RC" in
            */config.fish) echo "    source $SHELL_RC" ;;
            *) echo "    source $SHELL_RC   # or open a new terminal" ;;
        esac
        echo ""
    fi
}

armaraos_cli_bin() {
    if [ -x "$INSTALL_DIR/armaraos" ]; then
        echo "$INSTALL_DIR/armaraos"
    elif [ -x "$INSTALL_DIR/openfang" ]; then
        echo "$INSTALL_DIR/openfang"
    fi
}

initialize_armaraos_if_needed() {
    local bin config
    bin="$(armaraos_cli_bin)"
    [ -n "$bin" ] || return 0
    config="${HOME}/.armaraos/config.toml"
    [ -f "$config" ] && return 0
    echo ""
    echo "  First-time setup (armaraos init --quick)..."
    if ! run_with_timeout 60 "$bin" init --quick; then
        echo "  Warning: init --quick timed out or failed — run it manually before opening the dashboard."
    fi
}

install_dashboard_shortcut() {
    local bin desktop launcher
    bin="$(armaraos_cli_bin)"
    [ -n "$bin" ] || return 1

    desktop=""
    if [ "$OS" = "darwin" ]; then
        desktop="$HOME/Desktop"
    elif [ -n "${XDG_DESKTOP_DIR:-}" ] && [ -d "$XDG_DESKTOP_DIR" ]; then
        desktop="$XDG_DESKTOP_DIR"
    elif [ -d "$HOME/Desktop" ]; then
        desktop="$HOME/Desktop"
    fi
    [ -n "$desktop" ] || return 1

    launcher="$desktop/ArmaraOS Dashboard.command"
    cat > "$launcher" <<EOF
#!/usr/bin/env bash
exec "$bin" dashboard
EOF
    chmod +x "$launcher"
    echo "" >&2
    echo "  Created desktop shortcut: ArmaraOS Dashboard" >&2
    printf '%s\n' "$launcher"
}

install() {
    detect_platform
    detect_shell_rc

    echo ""
    echo "  ArmaraOS Installer"
    echo "  =================="
    echo ""

    if [ -n "${ARMARAOS_VERSION:-}" ]; then
        VERSION="$ARMARAOS_VERSION"
        echo "  Using specified version: $VERSION"
    elif [ -n "${OPENFANG_VERSION:-}" ]; then
        VERSION="$OPENFANG_VERSION"
        echo "  Using specified version: $VERSION"
    else
        echo "  Fetching latest release from ${DOWNLOAD_BASE%/}/latest.json ..."
        if ! VERSION="$(resolve_latest_tag)"; then
            echo "  Could not determine latest version from ${DOWNLOAD_BASE%/}/latest.json"
            echo "  Set ARMARAOS_VERSION=vX.Y.Z or try again after the next ArmaraOS release is published."
            exit 1
        fi
    fi

    if [ -z "$VERSION" ]; then
        echo "  Could not determine latest version."
        exit 1
    fi

    echo "  Installing ArmaraOS (CLI) $VERSION for $PLATFORM..."
    mkdir -p "$INSTALL_DIR"

    TMPDIR=$(mktemp -d)
    ARCHIVE="$TMPDIR/armaraos-cli.tar.gz"
    CHECKSUM_FILE="$TMPDIR/checksum.sha256"
    CLI_DOWNLOAD_URL=""
    CLI_CHECKSUM_URL=""
    cleanup() { rm -rf "$TMPDIR"; }
    trap cleanup EXIT

    if ! download_cli_archive "$PLATFORM" "$ARCHIVE"; then
        echo "  Download failed (tried latest.json + armaraos/openfang archives for $PLATFORM)."
        echo "  If this is a fresh release, wait a few minutes for ainativelang.com to sync CLI binaries."
        echo "  Or set ARMARAOS_VERSION=vX.Y.Z when a build exists at ${DOWNLOAD_BASE%/}/"
        exit 1
    fi
    echo "  Downloaded $(basename "$CLI_DOWNLOAD_URL")" 

    if curl -fsSL "$CLI_CHECKSUM_URL" -o "$CHECKSUM_FILE" 2>/dev/null; then
        EXPECTED=$(cut -d ' ' -f 1 < "$CHECKSUM_FILE")
        if command -v sha256sum &>/dev/null; then
            ACTUAL=$(sha256sum "$ARCHIVE" | cut -d ' ' -f 1)
        elif command -v shasum &>/dev/null; then
            ACTUAL=$(shasum -a 256 "$ARCHIVE" | cut -d ' ' -f 1)
        else
            ACTUAL=""
        fi
        if [ -n "$ACTUAL" ] && [ "$EXPECTED" != "$ACTUAL" ]; then
            echo "  Checksum verification FAILED!"
            exit 1
        fi
        echo "  Checksum verified."
    fi

    tar xzf "$ARCHIVE" -C "$INSTALL_DIR"
    if ! finalize_cli_binary "$INSTALL_DIR"; then
        echo "  Error: archive did not contain armaraos or openfang binary."
        exit 1
    fi

    CLI_BIN="$(armaraos_cli_bin || true)"
    if [ -z "$CLI_BIN" ]; then
        echo "  Error: could not locate installed CLI binary under $INSTALL_DIR"
        exit 1
    fi
    macos_quarantine_fix "$CLI_BIN"

    append_path_to_shell_rc "$INSTALL_DIR" "armaraos"
    export_path_now "$INSTALL_DIR"
    print_path_hint "$CLI_BIN"

    if "$CLI_BIN" --version >/dev/null 2>&1; then
        INSTALLED_VERSION=$("$CLI_BIN" --version 2>/dev/null || echo "$VERSION")
        echo ""
        echo "  ArmaraOS CLI installed ($INSTALLED_VERSION)"
    else
        echo ""
        echo "  ArmaraOS binary installed to $CLI_BIN"
    fi

    PYTHON=""
    if ! PYTHON="$(ensure_python)"; then
        exit 1
    fi

    if ! install_ainl "$PYTHON"; then
        exit 1
    fi

    initialize_armaraos_if_needed
    repair_config_toml_windows_paths || true
    if bin="$(armaraos_cli_bin)"; then
        ARMARAOS_NONINTERACTIVE=1 run_with_timeout 60 "$bin" doctor --repair >/dev/null 2>&1 || {
            echo "  Warning: armaraos doctor --repair timed out or failed (continuing install)." >&2
        }
    fi
    DESKTOP_SHORTCUT=""
    if launcher_path="$(install_dashboard_shortcut)"; then
        DESKTOP_SHORTCUT="$launcher_path"
    fi

    LAUNCH_RESULT="$(launch_armaraos_after_install)"
    print_get_started "$DESKTOP_SHORTCUT" "$LAUNCH_RESULT"
}

on_install_interrupt() {
    echo "" >&2
    echo "  Install interrupted." >&2
    print_path_hint "$(armaraos_cli_bin 2>/dev/null || true)"
    echo "  If the daemon was starting, try: $(armaraos_cli_bin 2>/dev/null || echo "$INSTALL_DIR/armaraos") start --yolo --detach" >&2
    exit 130
}

trap on_install_interrupt INT

install
