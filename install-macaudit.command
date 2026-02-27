#!/usr/bin/env bash
#
# install-macaudit.command — double-click installer for Mac Audit
#
# Double-click this file in Finder (or run it in Terminal) to install
# Mac Audit via Homebrew. Installs Homebrew first if it isn't present.
#
set -euo pipefail

# ── Colours / helpers ────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'
BOLD='\033[1m'; RESET='\033[0m'

info()  { printf "${BLUE}▸${RESET} %s\n" "$*"; }
ok()    { printf "${GREEN}✓${RESET} %s\n" "$*"; }
warn()  { printf "${YELLOW}⚠${RESET} %s\n" "$*"; }
die()   { printf "${RED}✗${RESET} %s\n" "$*" >&2; exit 1; }

# ── Header ───────────────────────────────────────────────────────────────────
printf "\n"
printf "${BOLD}── Mac Audit — Installer ──${RESET}\n"
printf "\n"

# ── Check macOS version (require Ventura 13+) ────────────────────────────────
MACOS_MAJOR=$(sw_vers -productVersion | cut -d. -f1)
if [ "$MACOS_MAJOR" -lt 13 ]; then
  die "Mac Audit requires macOS 13 Ventura or later (you have $(sw_vers -productVersion))."
fi
ok "macOS $(sw_vers -productVersion)"

# ── Homebrew ─────────────────────────────────────────────────────────────────
if command -v brew >/dev/null 2>&1; then
  ok "Homebrew found"
else
  info "Homebrew not found — installing…"
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

  # Add Homebrew to PATH for the rest of this session
  if [ -x /opt/homebrew/bin/brew ]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  elif [ -x /usr/local/bin/brew ]; then
    eval "$(/usr/local/bin/brew shellenv)"
  fi

  if ! command -v brew >/dev/null 2>&1; then
    die "Homebrew install finished but 'brew' is not in PATH. Open a new terminal and re-run."
  fi
  ok "Homebrew installed"
fi

# ── Install or upgrade macaudit ──────────────────────────────────────────────
if brew ls --versions macaudit >/dev/null 2>&1; then
  info "macaudit is already installed — upgrading…"
  brew upgrade gfreedman/macaudit/macaudit || ok "Already on latest version"
else
  info "Installing macaudit…"
  brew install gfreedman/macaudit/macaudit
fi

# ── Verify ───────────────────────────────────────────────────────────────────
if command -v macaudit >/dev/null 2>&1; then
  ok "macaudit $(macaudit --version) installed successfully"
else
  die "Installation finished but 'macaudit' is not in PATH."
fi

# ── Done ─────────────────────────────────────────────────────────────────────
printf "\n"
printf "${GREEN}${BOLD}All done!${RESET}\n"
printf "\n"
printf "  Run a scan:       ${BOLD}macaudit${RESET}\n"
printf "  Fix issues:       ${BOLD}macaudit --fix${RESET}\n"
printf "\n"

read -p "Press Enter to close…"
