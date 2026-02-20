"""
Homebrew package manager checks.

ALL checks gracefully skip if Homebrew is not installed.
MacPorts detection is noted but not checked in depth.
"""

from macaudit.checks.base import BaseCheck, CheckResult

# Single shared check for brew existence (used by all subclasses)
_BREW_MISSING_MSG = "Homebrew is not installed — skipping package checks"


class _HomebrewBase(BaseCheck):
    """All Homebrew checks inherit from this — skips if brew absent."""
    category = "homebrew"
    category_icon = "🍺"
    requires_tool = "brew"
    profile_tags = ["developer", "creative", "standard"]


class HomebrewDoctorCheck(_HomebrewBase):
    id = "homebrew_doctor"
    name = "Homebrew Health (brew doctor)"

    scan_description = (
        "Running 'brew doctor' — checks for common Homebrew issues like "
        "broken symlinks, PATH conflicts, and stale installation state."
    )
    finding_explanation = (
        "Homebrew issues cause 'command not found' errors, broken installs, "
        "and conflicts between package versions. brew doctor is the canonical "
        "way to surface them."
    )
    recommendation = (
        "Follow the instructions from 'brew doctor' to fix each issue. "
        "Most fixes are one-liners it prints for you."
    )
    fix_level = "auto"
    fix_description = "Runs 'brew doctor' and follows its suggestions"
    fix_command = ["brew", "doctor"]
    fix_reversible = True
    fix_time_estimate = "~30 seconds"

    def run(self) -> CheckResult:
        rc, stdout, stderr = self.shell(["brew", "doctor"], timeout=30)

        output = (stdout + stderr).strip()

        if rc == 0 or "ready to brew" in output.lower():
            return self._pass("Homebrew is healthy")

        # Collect warning lines
        warnings = [
            ln.strip()
            for ln in output.splitlines()
            if ln.strip().startswith("Warning:")
        ]

        if warnings:
            n = len(warnings)
            return self._warning(
                f"{n} Homebrew issue{'s' if n != 1 else ''} found — run 'brew doctor'",
                data={"warnings": warnings},
            )

        return self._warning(
            "brew doctor reported issues",
            data={"output_preview": output[:300]},
        )


class HomebrewOutdatedCheck(_HomebrewBase):
    id = "homebrew_outdated"
    name = "Outdated Homebrew Formulae"

    scan_description = (
        "Checking for outdated Homebrew formulae — outdated packages may contain "
        "security vulnerabilities that have been patched in newer versions."
    )
    finding_explanation = (
        "CVEs in CLI tools and libraries are patched in package updates. "
        "Running old versions of git, curl, OpenSSL, or any networked tool "
        "leaves known vulnerabilities exploitable."
    )
    recommendation = (
        "Run 'brew upgrade' to update all outdated formulae. "
        "Or 'brew upgrade <name>' to update specific packages."
    )
    fix_level = "auto"
    fix_description = "Runs 'brew upgrade' to update all outdated formulae"
    fix_command = ["brew", "upgrade"]
    fix_reversible = False
    fix_time_estimate = "Varies — could be seconds or minutes"

    def run(self) -> CheckResult:
        rc, stdout, stderr = self.shell(["brew", "outdated"], timeout=30)

        if rc != 0:
            return self._error(f"brew outdated failed: {(stdout + stderr)[:80]}")

        packages = [ln.strip() for ln in stdout.splitlines() if ln.strip()]

        if not packages:
            return self._pass("All Homebrew formulae are up to date")

        n = len(packages)
        names = ", ".join(p.split()[0] for p in packages[:4])
        suffix = "…" if n > 4 else ""
        return self._warning(
            f"{n} outdated formula{'e' if n != 1 else ''}: {names}{suffix}",
            data={"outdated": packages},
        )


class HomebrewOutdatedCasksCheck(_HomebrewBase):
    id = "homebrew_outdated_casks"
    name = "Outdated Homebrew Casks"

    scan_description = (
        "Checking for outdated Homebrew casks (GUI apps) — cask updates "
        "include security patches for apps like browsers and media players."
    )
    finding_explanation = (
        "Casks are GUI apps managed by Homebrew (e.g. Firefox, VS Code, Slack). "
        "Like formulae, outdated casks may have known security vulnerabilities."
    )
    recommendation = (
        "Run 'brew upgrade --cask' to update all outdated casks. "
        "Some casks self-update; 'brew outdated --cask' shows which don't."
    )
    fix_level = "auto"
    fix_description = "Runs 'brew upgrade --cask'"
    fix_command = ["brew", "upgrade", "--cask"]
    fix_reversible = False
    fix_time_estimate = "Varies — could be minutes"

    def run(self) -> CheckResult:
        rc, stdout, stderr = self.shell(
            ["brew", "outdated", "--cask"], timeout=30
        )

        if rc != 0:
            return self._error(f"brew outdated --cask failed: {(stdout + stderr)[:80]}")

        casks = [ln.strip() for ln in stdout.splitlines() if ln.strip()]

        if not casks:
            return self._pass("All Homebrew casks are up to date")

        n = len(casks)
        names = ", ".join(c.split()[0] for c in casks[:4])
        suffix = "…" if n > 4 else ""
        return self._warning(
            f"{n} outdated cask{'s' if n != 1 else ''}: {names}{suffix}",
            data={"outdated_casks": casks},
        )


class HomebrewAutoremoveCheck(_HomebrewBase):
    id = "homebrew_autoremove"
    name = "Homebrew Orphaned Dependencies"

    scan_description = (
        "Checking for Homebrew packages that were installed as dependencies "
        "but are no longer needed by anything — safe to remove."
    )
    finding_explanation = (
        "When you uninstall a Homebrew formula, its dependencies may be left "
        "behind. Over time these orphaned packages accumulate, wasting disk "
        "space and cluttering your Homebrew installation."
    )
    recommendation = (
        "Run 'brew autoremove' to remove orphaned dependencies. "
        "This is safe — Homebrew only removes packages nothing else depends on."
    )
    fix_level = "auto"
    fix_description = "Runs 'brew autoremove' to remove orphaned dependencies"
    fix_command = ["brew", "autoremove"]
    fix_reversible = False
    fix_time_estimate = "~30 seconds"

    def run(self) -> CheckResult:
        rc, stdout, stderr = self.shell(
            ["brew", "autoremove", "--dry-run"], timeout=20
        )

        if rc != 0:
            return self._error(f"brew autoremove failed: {(stdout + stderr)[:80]}")

        lines = [ln.strip() for ln in stdout.splitlines() if ln.strip()]

        # Filter out header lines
        packages = [
            ln for ln in lines
            if not ln.startswith("==>") and not ln.lower().startswith("would")
        ]

        if not packages:
            return self._pass("No orphaned dependencies found")

        n = len(packages)
        return self._info(
            f"{n} orphaned dependenc{'ies' if n != 1 else 'y'} can be removed with 'brew autoremove'",
            data={"removable": packages},
        )


class HomebrewCleanupCheck(_HomebrewBase):
    id = "homebrew_cleanup"
    name = "Homebrew Cache Cleanup"

    scan_description = (
        "Checking how much disk space Homebrew's cached downloads are using — "
        "old package downloads accumulate silently over time."
    )
    finding_explanation = (
        "Homebrew keeps previous package downloads in its cache indefinitely. "
        "Over time this can grow to gigabytes of stale installers and bottles "
        "you'll never need again."
    )
    recommendation = (
        "Run 'brew cleanup' to remove stale downloads. "
        "Homebrew will only keep the most recent version of each formula."
    )
    fix_level = "auto"
    fix_description = "Runs 'brew cleanup' to remove stale package downloads"
    fix_command = ["brew", "cleanup"]
    fix_reversible = False
    fix_time_estimate = "~30 seconds"

    def run(self) -> CheckResult:
        rc, stdout, stderr = self.shell(
            ["brew", "cleanup", "--dry-run"], timeout=20
        )

        if rc != 0:
            return self._error(f"brew cleanup check failed: {(stdout + stderr)[:80]}")

        output = stdout + stderr

        # Parse "This operation would free X.XGB of disk space."
        import re
        match = re.search(
            r"would free (\d+(?:\.\d+)?)\s*(B|KB|MB|GB|TB)",
            output,
            re.IGNORECASE,
        )
        if match:
            size = f"{match.group(1)} {match.group(2)}"
            # Convert to MB to decide severity
            n = float(match.group(1))
            unit = match.group(2).upper()
            mb = {"B": n / 1e6, "KB": n / 1e3, "MB": n, "GB": n * 1e3, "TB": n * 1e6}.get(unit, 0)

            if mb >= 500:
                return self._warning(
                    f"Homebrew cache can free {size} — run 'brew cleanup'",
                    data={"reclaimable": size},
                )
            return self._info(
                f"Homebrew cache can free {size} — run 'brew cleanup'",
                data={"reclaimable": size},
            )

        # Check if output is empty (nothing to clean)
        if not output.strip() or "nothing" in output.lower():
            return self._pass("Homebrew cache is already clean")

        return self._info("Old Homebrew downloads found — run 'brew cleanup'")


class HomebrewMissingCheck(_HomebrewBase):
    id = "homebrew_missing"
    name = "Homebrew Missing Dependencies"

    scan_description = (
        "Checking for Homebrew formulae with missing dependencies — broken "
        "links cause 'command not found' errors that are hard to diagnose."
    )
    finding_explanation = (
        "If a formula's dependencies were removed or not properly linked, "
        "the formula itself may fail silently or produce confusing errors "
        "like 'library not found' or 'dyld: Library not loaded'."
    )
    recommendation = (
        "Run 'brew missing' to see what's broken, then "
        "'brew install <missing-dep>' or 'brew reinstall <formula>'."
    )
    fix_level = "auto"
    fix_description = "Runs 'brew missing' to identify, then reinstalls broken formulae"
    fix_command = ["brew", "missing"]
    fix_reversible = False
    fix_time_estimate = "~30 seconds"

    def run(self) -> CheckResult:
        rc, stdout, stderr = self.shell(["brew", "missing"], timeout=30)

        if rc != 0 and not stdout.strip():
            return self._error(f"brew missing failed: {(stdout + stderr)[:80]}")

        lines = [ln.strip() for ln in stdout.splitlines() if ln.strip()]

        if not lines:
            return self._pass("No missing Homebrew dependencies")

        n = len(lines)
        return self._warning(
            f"{n} formula{'e' if n != 1 else ''} with missing dependencies",
            data={"missing": lines},
        )


# ── Public list for main.py ───────────────────────────────────────────────────

ALL_CHECKS: list[type[BaseCheck]] = [
    HomebrewDoctorCheck,
    HomebrewOutdatedCheck,
    HomebrewOutdatedCasksCheck,
    HomebrewAutoremoveCheck,
    HomebrewCleanupCheck,
    HomebrewMissingCheck,
]
