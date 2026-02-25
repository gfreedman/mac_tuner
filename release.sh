#!/usr/bin/env bash
#
# release.sh — single-command release for macaudit
#
# Runs every step of a release in order:
#   1. Preflight  — clean tree, correct branch, tools present, tests green
#   2. Version    — bump pyproject.toml, validate semver
#   3. Changelog  — abort if no human-written entry for this version
#   4. Git        — commit, tag, push (idempotent: skips if tag exists)
#   5. GitHub     — create release with changelog body (skips if exists)
#   6. Homebrew   — full formula regeneration from PyPI (not sed-patching)
#   7. Summary    — print what happened
#
# Usage:
#   ./release.sh 1.7.0            # full release
#   ./release.sh --preflight-only  # just run checks, don't touch anything
#
set -euo pipefail

# ── Colours / helpers ────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'
BOLD='\033[1m'; RESET='\033[0m'

info()  { printf "${BLUE}▸${RESET} %s\n" "$*"; }
ok()    { printf "${GREEN}✓${RESET} %s\n" "$*"; }
warn()  { printf "${YELLOW}⚠${RESET} %s\n" "$*"; }
die()   { printf "${RED}✗${RESET} %s\n" "$*" >&2; exit 1; }
phase() { printf "\n${BOLD}── Phase %s ──${RESET}\n" "$1"; }

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_ROOT"

# Prefer the project venv's python — it has pytest and project deps installed.
# Homebrew's bare `python3` may point at a different version without them.
if [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
else
  PYTHON="python3"
fi

# ── Parse CLI args ───────────────────────────────────────────────────────────
PREFLIGHT_ONLY=false
VERSION=""

for arg in "$@"; do
  case "$arg" in
    --preflight-only) PREFLIGHT_ONLY=true ;;
    --help|-h)
      echo "Usage: ./release.sh [--preflight-only] [VERSION]"
      echo ""
      echo "  VERSION           Semver X.Y.Z (e.g. 1.7.0)"
      echo "  --preflight-only  Run preflight checks only, then exit"
      exit 0
      ;;
    *) VERSION="$arg" ;;
  esac
done

# ─────────────────────────────────────────────────────────────────────────────
# Phase 1 — Preflight
# ─────────────────────────────────────────────────────────────────────────────
phase "1 — Preflight"

# Bail on uncommitted or staged changes — we're about to modify pyproject.toml
if ! git diff --quiet || ! git diff --cached --quiet; then
  die "Working tree has uncommitted changes. Commit or stash first."
fi
if [ -n "$(git ls-files --others --exclude-standard)" ]; then
  die "Working tree has untracked files. Clean up first."
fi
ok "Clean working tree"

BRANCH=$(git branch --show-current)
if [ "$BRANCH" != "main" ]; then
  die "Must be on 'main' branch (currently on '$BRANCH')."
fi
ok "On main branch"

for cmd in git python3 gh curl shasum; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    die "Required tool '$cmd' not found in PATH."
  fi
done
ok "All required tools available"

info "Running tests…"
if ! $PYTHON -m pytest --tb=short -q 2>&1; then
  die "Tests failed. Fix them before releasing."
fi
ok "Tests pass"

if $PREFLIGHT_ONLY; then
  ok "Preflight complete (--preflight-only mode)."
  exit 0
fi

# ─────────────────────────────────────────────────────────────────────────────
# Phase 2 — Version
# ─────────────────────────────────────────────────────────────────────────────
phase "2 — Version"

# Read current version from pyproject.toml
CURRENT_VERSION=$($PYTHON -c "
import re, pathlib
m = re.search(r'version\s*=\s*\"([^\"]+)\"', pathlib.Path('pyproject.toml').read_text())
print(m.group(1))
")
info "Current version: $CURRENT_VERSION"

# Prompt interactively if not passed as an argument
if [ -z "$VERSION" ]; then
  printf "Enter new version (X.Y.Z): "
  read -r VERSION
fi

if ! echo "$VERSION" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$'; then
  die "Invalid version '$VERSION'. Must be semver X.Y.Z."
fi

# If version already matches, this is a re-run — skip the bump.
# Otherwise ensure the new version is strictly higher.
if [ "$VERSION" = "$CURRENT_VERSION" ]; then
  ok "pyproject.toml already at $VERSION (re-run)"
else
  HIGHER=$($PYTHON -c "
from packaging.version import Version
import sys
try:
    result = Version('$VERSION') > Version('$CURRENT_VERSION')
except Exception:
    new = tuple(int(x) for x in '$VERSION'.split('.'))
    cur = tuple(int(x) for x in '$CURRENT_VERSION'.split('.'))
    result = new > cur
print('yes' if result else 'no')
")
  if [ "$HIGHER" != "yes" ]; then
    die "New version $VERSION must be greater than current $CURRENT_VERSION."
  fi

  sed -i '' "s/^version = \".*\"/version = \"$VERSION\"/" pyproject.toml
  ok "Updated pyproject.toml to $VERSION"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Phase 3 — Changelog gate
# Changelogs are human-written, never auto-generated. If there's no entry
# for the new version we abort so the author writes one first.
# ─────────────────────────────────────────────────────────────────────────────
phase "3 — Changelog gate"

if ! grep -qF "## [$VERSION]" CHANGELOG.md; then
  # Revert the version bump so the working tree stays clean for next run
  git checkout pyproject.toml 2>/dev/null || true
  die "CHANGELOG.md has no entry for [$VERSION]. Write one before releasing."
fi
ok "Changelog entry found for $VERSION"

# ─────────────────────────────────────────────────────────────────────────────
# Phase 4 — Commit, tag, push
# Idempotent: if the tag already exists we skip everything.
# ─────────────────────────────────────────────────────────────────────────────
phase "4 — Commit, tag, push"

TAG="v$VERSION"

if git rev-parse "$TAG" >/dev/null 2>&1; then
  warn "Tag $TAG already exists — skipping commit/tag/push."
else
  git add pyproject.toml
  git commit -m "Bump version to $VERSION"
  git tag "$TAG"
  ok "Created commit and tag $TAG"

  info "Pushing to origin…"
  git push origin main
  git push origin "$TAG"
  ok "Pushed main and $TAG"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Phase 5 — GitHub Release
# Uses the changelog section as the release body so GitHub shows the same
# human-written notes. Falls back to --generate-notes if extraction fails.
# ─────────────────────────────────────────────────────────────────────────────
phase "5 — GitHub Release"

if gh release view "$TAG" --repo gfreedman/mac_audit >/dev/null 2>&1; then
  warn "GitHub release $TAG already exists — skipping."
else
  # Extract everything between this version's ## heading and the next one
  NOTES=$(awk -v ver="$VERSION" '
    /^## \[/ { if (found) exit; if (index($0, "[" ver "]")) found=1; next }
    found { print }
  ' CHANGELOG.md)

  if [ -z "$NOTES" ]; then
    warn "Could not extract changelog notes — using --generate-notes."
    gh release create "$TAG" \
      --repo gfreedman/mac_audit \
      --title "Mac Audit $TAG" \
      --generate-notes
  else
    gh release create "$TAG" \
      --repo gfreedman/mac_audit \
      --title "Mac Audit $TAG" \
      --notes "$NOTES"
  fi
  ok "Created GitHub release $TAG"
fi

RELEASE_URL="https://github.com/gfreedman/mac_audit/releases/tag/$TAG"

# ─────────────────────────────────────────────────────────────────────────────
# Phase 6 — Homebrew formula (full regeneration)
#
# Why regenerate instead of sed-patching?
# A sed patch can only update the tarball URL + sha256. When dependencies
# change (added, removed, or upgraded) the resource blocks go stale.
# Full regeneration fetches the current dependency tree from PyPI and
# writes every resource block from scratch — always correct.
# ─────────────────────────────────────────────────────────────────────────────
phase "6 — Homebrew formula"

TAP_DIR="/tmp/homebrew-macaudit"
FORMULA="$TAP_DIR/Formula/macaudit.rb"

# Use git rev-parse to verify the clone is intact (survives /tmp partial cleanup)
if git -C "$TAP_DIR" rev-parse --git-dir >/dev/null 2>&1; then
  info "Updating existing tap clone…"
  git -C "$TAP_DIR" pull --ff-only origin main
else
  info "Cloning tap repo…"
  rm -rf "$TAP_DIR"
  gh repo clone gfreedman/homebrew-macaudit "$TAP_DIR"
fi

# Download the release tarball and compute its sha256.
# The tarball may not be available immediately after tag push, so we retry
# up to 10 times with a 5s delay. We detect an empty/missing tarball by
# comparing against the sha256 of zero bytes.
TARBALL_URL="https://github.com/gfreedman/mac_audit/archive/refs/tags/$TAG.tar.gz"
EMPTY_SHA="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
TARBALL_SHA=""
info "Waiting for tarball…"
for attempt in $(seq 1 10); do
  TARBALL_SHA=$(curl -sfL "$TARBALL_URL" | shasum -a 256 | awk '{print $1}')
  if [ -n "$TARBALL_SHA" ] && [ "$TARBALL_SHA" != "$EMPTY_SHA" ]; then
    break
  fi
  warn "Attempt $attempt: tarball not ready, retrying in 5s…"
  sleep 5
  TARBALL_SHA=""
done
if [ -z "$TARBALL_SHA" ]; then
  die "Failed to download tarball after 10 attempts."
fi
ok "Tarball SHA256: $TARBALL_SHA"

# Parse direct dependencies from pyproject.toml's dependencies array.
# We split on version-specifier characters (>=, <=, ~=, !=, etc.) to
# extract just the bare package name.
DIRECT_DEPS=$($PYTHON -c "
import re, pathlib
text = pathlib.Path('pyproject.toml').read_text()
m = re.search(r'dependencies\s*=\s*\[(.*?)\]', text, re.DOTALL)
for dep in re.findall(r'\"([^\"]+)\"', m.group(1)):
    # Strip version specifiers: >=, <=, ~=, !=, ==, etc.
    name = re.split(r'[><=!~;]', dep)[0].strip()
    print(name)
")
info "Direct deps: $(echo $DIRECT_DEPS | tr '\n' ' ')"

# BFS-resolve the full dependency tree via PyPI's JSON API.
#
# Starting from the direct deps above, we fetch each package's metadata,
# grab its sdist URL + sha256, then enqueue any transitive dependencies.
# We skip deps that only apply to extras (e.g. dev/test) or Windows.
#
# Output: Homebrew `resource` blocks, one per dependency, sorted by name.
info "Resolving dependency tree via PyPI…"
RESOURCE_BLOCKS=$($PYTHON << 'PYEOF'
import json, re, sys, urllib.request, urllib.error

def normalize(name):
    """PEP 503 normalize: rich_text -> rich-text, Rich -> rich."""
    return re.sub(r'[-_.]+', '-', name).lower()

def fetch_pypi(pkg):
    """Fetch package metadata from https://pypi.org/pypi/{name}/json."""
    url = f"https://pypi.org/pypi/{normalize(pkg)}/json"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"  WARNING: PyPI lookup failed for {pkg}: {e}", file=sys.stderr)
        return None

def parse_requires(requires_dist):
    """Return unconditional, non-extras, non-Windows dependency names.

    PyPI's requires_dist entries look like:
      'mdurl ~=0.1'                       -> mdurl  (keep)
      'pygments >=2.13.0,<3.0.0'         -> pygments (keep)
      'foo ; extra == "jupyter"'          -> skip (extras-only)
      'bar ; sys_platform == "win32"'     -> skip (Windows-only)
    """
    deps = []
    if not requires_dist:
        return deps
    for req in requires_dist:
        if 'extra ==' in req or 'extra==' in req:
            continue
        if 'sys_platform == "win32"' in req or "sys_platform == 'win32'" in req:
            continue
        if 'platform_system == "Windows"' in req or "platform_system == 'Windows'" in req:
            continue
        # Split on whitespace or version operators to get the bare name.
        # The ~ handles PEP 440 compatible-release (~=) specifiers.
        name = re.split(r'[\s><=!~;\[]', req)[0].strip()
        if name:
            deps.append(name)
    return deps

def get_sdist(data):
    """Return (url, sha256) for the sdist archive, or (None, None)."""
    for url_info in data.get("urls", []):
        if url_info.get("packagetype") == "sdist":
            return url_info["url"], url_info["digests"]["sha256"]
    return None, None

# --- Main: BFS from direct deps ------------------------------------------

import pathlib
text = pathlib.Path("pyproject.toml").read_text()
m = re.search(r'dependencies\s*=\s*\[(.*?)\]', text, re.DOTALL)
direct = []
for dep in re.findall(r'"([^"]+)"', m.group(1)):
    # Strip version specifiers (>=, ~=, etc.) to get bare package name
    name = re.split(r'[><=!~;]', dep)[0].strip()
    direct.append(name)

seen = set()                # normalized names we've already visited
queue = list(direct)        # BFS frontier
resources = {}              # norm_name -> (name, sdist_url, sdist_sha256)

while queue:
    pkg = queue.pop(0)
    norm = normalize(pkg)
    if norm in seen:
        continue
    seen.add(norm)

    data = fetch_pypi(pkg)
    if not data:
        continue

    sdist_url, sdist_sha = get_sdist(data)
    if not sdist_url:
        print(f"  WARNING: No sdist for {pkg}, skipping", file=sys.stderr)
        continue

    resources[norm] = (norm, sdist_url, sdist_sha)

    # Enqueue transitive dependencies for the next BFS iteration
    requires = data.get("info", {}).get("requires_dist") or []
    for child in parse_requires(requires):
        child_norm = normalize(child)
        if child_norm not in seen:
            queue.append(child)

# Print Homebrew resource blocks, sorted alphabetically
for norm in sorted(resources):
    name, url, sha = resources[norm]
    print(f'  resource "{name}" do')
    print(f'    url "{url}"')
    print(f'    sha256 "{sha}"')
    print(f'  end')
    print()
PYEOF
)

if [ -z "$RESOURCE_BLOCKS" ]; then
  die "Failed to resolve any dependencies."
fi
ok "Resolved dependency tree"

# Write the complete formula from a template (not patching the old one).
info "Writing formula…"
cat > "$FORMULA" << FORMULA_EOF
class Macaudit < Formula
  include Language::Python::Virtualenv

  desc "Mac System Health Inspector & Auditor"
  homepage "https://github.com/gfreedman/mac_audit"
  url "$TARBALL_URL"
  sha256 "$TARBALL_SHA"
  license "MIT"
  head "https://github.com/gfreedman/mac_audit.git", branch: "main"

  depends_on "python@3.12"

$RESOURCE_BLOCKS
  def install
    virtualenv_install_with_resources
  end

  def caveats
    <<~EOS
      To enable shell completion, add to your ~/.zshrc:
        eval "\$(_MACAUDIT_COMPLETE=zsh_source macaudit)"

      For bash, add to ~/.bash_profile:
        eval "\$(_MACAUDIT_COMPLETE=bash_source macaudit)"

      Then restart your terminal or run: source ~/.zshrc
    EOS
  end

  test do
    assert_match version.to_s, shell_output("\#{bin}/macaudit --version")
  end
end
FORMULA_EOF

ok "Formula written to $FORMULA"

# Commit and push — skip if the formula didn't actually change (idempotent)
cd "$TAP_DIR"
if git diff --quiet Formula/macaudit.rb; then
  warn "Formula unchanged — skipping commit."
else
  git add Formula/macaudit.rb
  git commit -m "macaudit $VERSION"
  git push origin main
  ok "Formula committed and pushed"
fi
cd "$REPO_ROOT"

# ─────────────────────────────────────────────────────────────────────────────
# Phase 7 — Summary
# ─────────────────────────────────────────────────────────────────────────────
phase "7 — Summary"

printf "\n"
printf "${GREEN}${BOLD}Release $VERSION complete!${RESET}\n"
printf "\n"
printf "  Version:  %s\n" "$VERSION"
printf "  Tag:      %s\n" "$TAG"
printf "  Release:  %s\n" "$RELEASE_URL"
printf "  Formula:  %s\n" "$FORMULA"
printf "\n"
printf "  brew install gfreedman/macaudit/macaudit\n"
printf "\n"
