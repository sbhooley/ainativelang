#!/usr/bin/env bash
# Upgrade ArmaraOS CLI on macOS/Linux without a self-update-capable binary (legacy v0.8.2 and earlier).
# Usage: curl -sSfL https://ainativelang.com/downloads/armaraos/cli/upgrade-cli.sh | sh
#
# Env: ARMARAOS_VERSION, ARMARAOS_INSTALL_DIR (default ~/.armaraos/bin), ARMARAOS_DOWNLOAD_BASE

set -euo pipefail

DOWNLOAD_BASE="${ARMARAOS_DOWNLOAD_BASE:-https://raw.githubusercontent.com/sbhooley/ainativelang/main/downloads/armaraos/cli}"
INSTALL_DIR="${ARMARAOS_INSTALL_DIR:-${OPENFANG_INSTALL_DIR:-$HOME/.armaraos/bin}}"
ARM_HOME="${ARMARAOS_HOME:-${OPENFANG_HOME:-$HOME/.armaraos}}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"

resolve_latest_tag() {
    if [ -n "${ARMARAOS_VERSION:-}" ]; then
        echo "$ARMARAOS_VERSION"
        return 0
    fi
    local json tag
    json="$(curl -fsSL "${DOWNLOAD_BASE%/}/latest.json")"
    tag="$(printf '%s' "$json" | sed -n 's/.*"tag"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)"
    [ -n "$tag" ]
}

detect_archive_name() {
    local os arch
    os="$(uname -s | tr '[:upper:]' '[:lower:]')"
    arch="$(uname -m)"
    case "$os" in
        darwin)
            case "$arch" in
                arm64|aarch64) echo "armaraos-aarch64-apple-darwin.tar.gz" ;;
                *) echo "armaraos-x86_64-apple-darwin.tar.gz" ;;
            esac
            ;;
        linux)
            case "$arch" in
                aarch64|arm64) echo "armaraos-aarch64-unknown-linux-gnu.tar.gz" ;;
                *) echo "armaraos-x86_64-unknown-linux-gnu.tar.gz" ;;
            esac
            ;;
        *) echo "unsupported" ;;
    esac
}

stop_armaraos() {
    if [ -x "$INSTALL_DIR/armaraos" ]; then
        "$INSTALL_DIR/armaraos" stop >/dev/null 2>&1 || true
    elif [ -x "$INSTALL_DIR/openfang" ]; then
        "$INSTALL_DIR/openfang" stop >/dev/null 2>&1 || true
    fi
    pkill -x armaraos >/dev/null 2>&1 || true
    pkill -x openfang >/dev/null 2>&1 || true
    sleep 2
}

run_ainl_layout_repair() {
    if [ -f "$SCRIPT_DIR/ainl-layout-repair.sh" ]; then
        # shellcheck source=/dev/null
        . "$SCRIPT_DIR/ainl-layout-repair.sh"
        repair_ainl_layout || true
        return 0
    fi
    local repair_url="${DOWNLOAD_BASE%/}/ainl-layout-repair.sh"
    local tmp
    tmp="$(mktemp)"
    if curl -fsSL "$repair_url" -o "$tmp" 2>/dev/null; then
        # shellcheck source=/dev/null
        . "$tmp"
        repair_ainl_layout || true
        rm -f "$tmp"
    fi
}

main() {
    echo ""
    echo "  ArmaraOS CLI upgrade (Unix)"
    echo "  ==========================="
    echo ""

    mkdir -p "$INSTALL_DIR"
    local tag archive url sha_url tmpdir archive_path cli_bin
    tag="$(resolve_latest_tag)"
    archive="$(detect_archive_name)"
    if [ "$archive" = "unsupported" ]; then
        echo "  Error: unsupported OS for upgrade-cli.sh (use install.sh)" >&2
        exit 1
    fi

    url="${DOWNLOAD_BASE%/}/$archive"
    sha_url="${url}.sha256"
    tmpdir="$(mktemp -d)"
    archive_path="$tmpdir/$archive"

    echo "  Target:  $tag"
    echo "  Install: $INSTALL_DIR"
    echo ""

    stop_armaraos

    echo "  Downloading CLI archive..."
    curl -fsSL "$url" -o "$archive_path"

    if curl -fsSL "$sha_url" -o "$tmpdir/checksum" 2>/dev/null; then
        local expected actual
        expected="$(awk '{print $1}' "$tmpdir/checksum" | tr '[:upper:]' '[:lower:]')"
        if command -v shasum >/dev/null 2>&1; then
            actual="$(shasum -a 256 "$archive_path" | awk '{print $1}')"
        else
            actual="$(sha256sum "$archive_path" | awk '{print $1}')"
        fi
        if [ "$expected" != "$actual" ]; then
            echo "  Checksum verification FAILED!" >&2
            exit 1
        fi
        echo "  Checksum verified."
    fi

    tar xzf "$archive_path" -C "$tmpdir"
    cli_bin="$(find "$tmpdir" -maxdepth 3 -type f \( -name armaraos -o -name openfang \) -perm -111 2>/dev/null | head -1)"
    if [ -z "$cli_bin" ]; then
        cli_bin="$(find "$tmpdir" -maxdepth 3 -type f \( -name armaraos -o -name openfang \) 2>/dev/null | head -1)"
    fi
    if [ -z "$cli_bin" ]; then
        echo "  Error: armaraos binary not found in archive" >&2
        exit 1
    fi

    install -m 755 "$cli_bin" "$INSTALL_DIR/armaraos"
    if [ ! -x "$INSTALL_DIR/openfang" ]; then
        cp "$INSTALL_DIR/armaraos" "$INSTALL_DIR/openfang" 2>/dev/null || ln -sf armaraos "$INSTALL_DIR/openfang" 2>/dev/null || true
    fi

    echo ""
    echo "  Installed: $("$INSTALL_DIR/armaraos" --version 2>/dev/null || echo armaraos)"
    echo ""

    echo "  Post-upgrade: repairing AINL layout and config..."
    run_ainl_layout_repair
    ARMARAOS_NONINTERACTIVE=1 "$INSTALL_DIR/armaraos" doctor --repair >/dev/null 2>&1 || {
        echo "  Warning: doctor --repair timed out or failed (continuing)" >&2
    }
    "$INSTALL_DIR/armaraos" stop >/dev/null 2>&1 || true
    sleep 2
    "$INSTALL_DIR/armaraos" start --yolo --detach >/dev/null 2>&1 || {
        echo "  Warning: could not start daemon — run: $INSTALL_DIR/armaraos start --yolo --detach" >&2
    }
    "$INSTALL_DIR/armaraos" dashboard >/dev/null 2>&1 || true

    echo ""
    echo "  Upgrade complete."
    echo ""
    echo "  v0.8.3+ supports: armaraos update"
    echo ""
}

main "$@"
