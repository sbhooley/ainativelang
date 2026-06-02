#!/usr/bin/env bash
# ArmaraOS installer — works on Linux, macOS, WSL
# Usage: curl -sSfL https://ainativelang.com/install.sh | sh
#
# Environment variables:
#   ARMARAOS_INSTALL_DIR  — custom install directory (default: ~/.armaraos/bin)
#   ARMARAOS_VERSION      — install a specific version tag (default: latest)
#   ARMARAOS_AUTO_PYTHON  — set to 0 to skip auto-installing Python (macOS: brew; default: 1)
#   ARMARAOS_AINL_VENV       — AINL virtualenv when system Python is PEP 668 (default: ~/.armaraos/ainl-venv)
#   ARMARAOS_DOWNLOAD_BASE — CLI mirror base (default: raw.githubusercontent.com/.../downloads/armaraos/cli)
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
    echo "  Python 3.10+ is required for AINL (ainativelang[mcp])."
    echo "  The ArmaraOS CLI is already installed — finish AINL after Python is ready."
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
    echo "  Skip AINL for now (CLI only): ARMARAOS_SKIP_AINL=1 curl -sSfL https://ainativelang.com/install.sh | sh"
    echo "  Re-run full install:            curl -sSfL https://ainativelang.com/install.sh | sh"
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

print_get_started() {
    echo ""
    echo "  You're ready — run these now (PATH updated for this shell):"
    echo "    armaraos init --quick"
    echo "    armaraos start --detach"
    echo "    armaraos dashboard"
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

    URL="${DOWNLOAD_BASE%/}/openfang-$PLATFORM.tar.gz"
    CHECKSUM_URL="${URL}.sha256"

    echo "  Installing ArmaraOS (CLI) $VERSION for $PLATFORM..."
    mkdir -p "$INSTALL_DIR"

    TMPDIR=$(mktemp -d)
    ARCHIVE="$TMPDIR/openfang.tar.gz"
    CHECKSUM_FILE="$TMPDIR/checksum.sha256"
    cleanup() { rm -rf "$TMPDIR"; }
    trap cleanup EXIT

    if ! curl -fsSL "$URL" -o "$ARCHIVE" 2>/dev/null; then
        echo "  Download failed: $URL"
        echo "  If this is a fresh release, wait a few minutes for ainativelang.com to sync CLI binaries."
        echo "  Or set ARMARAOS_VERSION=vX.Y.Z when a build exists at ${DOWNLOAD_BASE%/}/"
        exit 1
    fi

    if curl -fsSL "$CHECKSUM_URL" -o "$CHECKSUM_FILE" 2>/dev/null; then
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
    chmod +x "$INSTALL_DIR/openfang"

    cat > "$INSTALL_DIR/armaraos" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$DIR/openfang" "$@"
EOF
    chmod +x "$INSTALL_DIR/armaraos"

    if [ "$OS" = "darwin" ]; then
        if command -v xattr &>/dev/null; then
            xattr -cr "$INSTALL_DIR/openfang" 2>/dev/null || true
        fi
        if command -v codesign &>/dev/null; then
            codesign --force --sign - "$INSTALL_DIR/openfang" 2>/dev/null || \
                echo "  Warning: ad-hoc codesign failed — if the binary is killed, run: xattr -cr $INSTALL_DIR/openfang && codesign --force --sign - $INSTALL_DIR/openfang"
        fi
    fi

    append_path_to_shell_rc "$INSTALL_DIR" "openfang"
    export_path_now "$INSTALL_DIR"

    if "$INSTALL_DIR/openfang" --version >/dev/null 2>&1; then
        INSTALLED_VERSION=$("$INSTALL_DIR/openfang" --version 2>/dev/null || echo "$VERSION")
        echo ""
        echo "  ArmaraOS CLI installed ($INSTALLED_VERSION)"
    else
        echo ""
        echo "  ArmaraOS binary installed to $INSTALL_DIR"
    fi

    if [ "${ARMARAOS_SKIP_AINL:-0}" = "1" ]; then
        echo ""
        echo "  Skipped AINL (ARMARAOS_SKIP_AINL=1). Add later: curl -sSfL https://ainativelang.com/install.sh | sh"
        print_get_started
        return 0
    fi

    PYTHON=""
    if ! PYTHON="$(ensure_python)"; then
        exit 1
    fi

    if ! install_ainl "$PYTHON"; then
        exit 1
    fi

    print_get_started
}

install
