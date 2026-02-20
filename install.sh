#!/usr/bin/env bash
# Mac Audit installer
# Installs macaudit globally using pipx (recommended) or pip.
#
# Usage:
#   curl -sSf https://raw.githubusercontent.com/gfreedman/mac_audit/main/install.sh | bash
#   — or —
#   bash install.sh

set -euo pipefail

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
DIM='\033[2m'
RESET='\033[0m'

PACKAGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log()    { echo -e "${DIM}  $*${RESET}"; }
ok()     { echo -e "${GREEN}  ✅  $*${RESET}"; }
warn()   { echo -e "${YELLOW}  ⚠️   $*${RESET}"; }
error()  { echo -e "${RED}  ❌  $*${RESET}" >&2; exit 1; }
header() { echo -e "\n${BOLD}$*${RESET}"; }

# ── Check macOS ──────────────────────────────────────────────────────────────

if [[ "$(uname)" != "Darwin" ]]; then
    error "Mac Audit only runs on macOS."
fi

MACOS_MAJOR=$(sw_vers -productVersion | cut -d. -f1)
if (( MACOS_MAJOR < 13 )); then
    error "Mac Audit requires macOS 13 Ventura or later (you have $(sw_vers -productVersion))."
fi

# ── Check Python ─────────────────────────────────────────────────────────────

header "Checking Python…"

if ! command -v python3 &>/dev/null; then
    warn "python3 not found."
    echo ""
    echo "  Install Xcode Command Line Tools to get Python 3:"
    echo "    xcode-select --install"
    echo ""
    error "Python 3.10+ is required."
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if (( PYTHON_MAJOR < 3 || (PYTHON_MAJOR == 3 && PYTHON_MINOR < 10) )); then
    error "Python 3.10+ required (you have $PYTHON_VERSION). Install via: brew install python@3.12"
fi

ok "Python $PYTHON_VERSION"

# ── Install via pipx (recommended) ───────────────────────────────────────────

header "Installing Mac Audit…"

if command -v pipx &>/dev/null; then
    log "Using pipx (recommended)…"

    # If installing from the repo directory
    if [[ -f "$PACKAGE_DIR/pyproject.toml" ]]; then
        pipx install "$PACKAGE_DIR" --force
    else
        pipx install macaudit
    fi

    ok "Installed via pipx"
    INSTALLED_VIA="pipx"

elif command -v pip3 &>/dev/null; then
    warn "pipx not found — falling back to pip3 --user."
    warn "pipx is recommended for global CLI tools: pip3 install pipx"
    echo ""

    if [[ -f "$PACKAGE_DIR/pyproject.toml" ]]; then
        pip3 install --user "$PACKAGE_DIR"
    else
        pip3 install --user macaudit
    fi

    ok "Installed via pip3 --user"
    INSTALLED_VIA="pip"

else
    error "Neither pipx nor pip3 found. Install Python 3.10+: brew install python@3.12"
fi

# ── Verify install ────────────────────────────────────────────────────────────

header "Verifying…"

if command -v macaudit &>/dev/null; then
    VERSION=$(macaudit --version 2>&1 | head -1)
    ok "$VERSION — ready to use"
else
    warn "macaudit not found in PATH after install."
    if [[ "$INSTALLED_VIA" == "pip" ]]; then
        echo ""
        echo "  Add this to your ~/.zshrc or ~/.bashrc:"
        echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
        echo ""
        echo "  Then reload your shell: exec \$SHELL"
    elif [[ "$INSTALLED_VIA" == "pipx" ]]; then
        echo ""
        echo "  Run: pipx ensurepath"
        echo "  Then reload your shell: exec \$SHELL"
    fi
fi

# ── Done ─────────────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}  Mac Audit installed!${RESET}"
echo ""
echo "  Run a full system audit:"
echo -e "    ${BOLD}macaudit${RESET}"
echo ""
echo "  Show only warnings and criticals:"
echo -e "    ${BOLD}macaudit --issues-only${RESET}"
echo ""
echo "  Enter fix mode:"
echo -e "    ${BOLD}macaudit --fix${RESET}"
echo ""
