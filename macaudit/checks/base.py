"""
Core data model for Mac Audit checks.

CheckResult — the contract every check must return.
BaseCheck   — abstract base class all checks inherit from.

This file is the single source of truth for the data shape.
Do not deviate from the field names or types defined here.
"""

import os
import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

from macaudit.system_info import IS_APPLE_SILICON, MACOS_VERSION


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class CheckResult:
    # Identity
    id: str                     # "homebrew_outdated"
    name: str                   # "Outdated Homebrew Packages"
    category: str               # "homebrew"
    category_icon: str          # "🍺"

    # Result
    status: Literal["pass", "warning", "critical", "info", "skip", "error"]
    message: str                # Short: "14 packages are out of date"

    # Educational layer — ALL THREE REQUIRED on every non-skip result
    scan_description: str       # Shown during scan (what + why)
    finding_explanation: str    # In report: why this matters
    recommendation: str         # What to do and why

    # Fix capability
    fix_level: Literal["auto", "auto_sudo", "guided", "instructions", "none"]
    fix_description: str        # Exactly what the fix does
    fix_command: str | None = None          # Shell command (AUTO fixes)
    fix_url: str | None = None              # Settings URL (GUIDED)
    fix_steps: list[str] | None = None     # Manual steps (INSTRUCTIONS)
    fix_reversible: bool = True             # Can it be undone?
    fix_time_estimate: str = "~30 seconds"
    requires_sudo: bool = False

    # Version & compatibility (required for every check)
    min_macos: tuple[int, int] = (13, 0)
    requires_tool: str | None = None       # 'brew', 'mas', 'docker', etc.
    apple_silicon_compatible: bool = True

    # Metadata
    data: dict[str, Any] = field(default_factory=dict)
    profile_tags: list[str] = field(
        default_factory=lambda: ["developer", "creative", "standard"]
    )


# ── Base class ────────────────────────────────────────────────────────────────

class BaseCheck(ABC):
    """
    Abstract base class for all Mac Audit checks.

    Subclasses must:
      1. Set class attributes (id, name, category, …)
      2. Override run() to return a CheckResult

    run() is guaranteed to be called only when:
      - macOS version >= min_macos
      - required tool exists (if requires_tool is set)
      - architecture is compatible

    run() must handle ALL exceptions internally and return a
    CheckResult with status='error' rather than letting exceptions
    propagate to the caller.
    """

    # Subclasses override these as class attributes
    id: str = "base_check"
    name: str = "Base Check"
    category: str = "system"
    category_icon: str = "🖥️ "

    scan_description: str = "Running check..."
    finding_explanation: str = ""
    recommendation: str = ""

    fix_level: Literal["auto", "auto_sudo", "guided", "instructions", "none"] = "none"
    fix_description: str = "No fix available"
    fix_command: str | None = None
    fix_url: str | None = None
    fix_steps: list[str] | None = None
    fix_reversible: bool = True
    fix_time_estimate: str = "~30 seconds"
    requires_sudo: bool = False

    min_macos: tuple[int, int] = (13, 0)
    requires_tool: str | None = None
    apple_silicon_compatible: bool = True

    # Immutable tuple prevents accidental mutation of the shared class attribute.
    # Subclasses that target specific profiles override this with a smaller tuple,
    # e.g. `profile_tags = ("developer",)` for developer-only checks.
    profile_tags: tuple[str, ...] = ("developer", "creative", "standard")

    # ── Public API ────────────────────────────────────────────────────────────

    def execute(self) -> CheckResult:
        """
        Gate-check then delegate to run().

        Call this from the orchestrator — not run() directly.
        """
        # macOS version gate
        if MACOS_VERSION < self.min_macos:
            return self._skip(
                f"Requires macOS {self.min_macos[0]}.{self.min_macos[1]}+"
            )

        # Tool availability gate
        if self.requires_tool and not self.has_tool(self.requires_tool):
            return self._skip(f"{self.requires_tool} not installed")

        # Architecture gate
        if not self.apple_silicon_compatible and IS_APPLE_SILICON:
            return self._skip("Not compatible with Apple Silicon")

        # Safety net — one bad check must never crash the whole scan
        try:
            return self.run()
        except Exception as e:
            return self._error(f"Unexpected error in {self.id}: {e}")

    @abstractmethod
    def run(self) -> CheckResult:
        """
        Implement the actual check here.

        Must:
        - Wrap subprocess calls in try/except with timeout=10
        - Return a CheckResult on every code path (no bare exceptions)
        - Never output to stdout/stderr directly
        """

    # ── Helper methods ────────────────────────────────────────────────────────

    def has_tool(self, tool: str) -> bool:
        """Return True if tool is available in PATH."""
        return shutil.which(tool) is not None

    def shell(
        self,
        cmd: list[str],
        timeout: int = 10,
    ) -> tuple[int, str, str]:
        """
        Run a subprocess safely and return its output.

        Args:
            cmd:     Argument list, e.g. ["sw_vers", "-productVersion"].
                     Never constructed from user-supplied data.
            timeout: Maximum seconds to wait before aborting (default 10).

        Returns:
            (returncode, stdout, stderr) — all strings, never None.
            On timeout or missing binary, returncode is -1 and stderr
            contains a human-readable error description.
        """
        # Force C locale so command output is always English, regardless of
        # the user's system language. Without this, string matching breaks on
        # non-English macOS (e.g. "Enabled" vs "Activé" in French).
        _env = {**os.environ, "LANG": "C", "LC_ALL": "C"}
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                env=_env,
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"Command timed out after {timeout}s: {' '.join(cmd)}"
        except FileNotFoundError:
            return -1, "", f"Command not found: {cmd[0]}"
        except Exception as e:
            return -1, "", str(e)

    def _result(
        self,
        status: Literal["pass", "warning", "critical", "info", "skip", "error"],
        message: str,
        data: dict[str, Any] | None = None,
    ) -> CheckResult:
        """Convenience builder — fills class-level defaults into a CheckResult."""
        return CheckResult(
            id=self.id,
            name=self.name,
            category=self.category,
            category_icon=self.category_icon,
            status=status,
            message=message,
            scan_description=self.scan_description,
            finding_explanation=self.finding_explanation,
            recommendation=self.recommendation,
            fix_level=self.fix_level,
            fix_description=self.fix_description,
            fix_command=self.fix_command,
            fix_url=self.fix_url,
            fix_steps=self.fix_steps,
            fix_reversible=self.fix_reversible,
            fix_time_estimate=self.fix_time_estimate,
            requires_sudo=self.requires_sudo,
            min_macos=self.min_macos,
            requires_tool=self.requires_tool,
            apple_silicon_compatible=self.apple_silicon_compatible,
            data=data or {},
            # Convert to list so the resulting CheckResult is mutable/serialisable,
            # and so that subclass tuple overrides are correctly propagated.
            profile_tags=list(self.profile_tags),
        )

    def _skip(self, reason: str) -> CheckResult:
        return self._result("skip", reason)

    def _error(self, message: str) -> CheckResult:
        return self._result("error", message)

    def _pass(self, message: str, data: dict[str, Any] | None = None) -> CheckResult:
        return self._result("pass", message, data=data)

    def _warning(
        self,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> CheckResult:
        return self._result("warning", message, data=data)

    def _critical(
        self,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> CheckResult:
        return self._result("critical", message, data=data)

    def _info(self, message: str, data: dict[str, Any] | None = None) -> CheckResult:
        return self._result("info", message, data=data)


# ── Health score ──────────────────────────────────────────────────────────────

_SECURITY_CATEGORIES = {"system", "privacy", "security"}


def calculate_health_score(checks: list[CheckResult]) -> int:
    """
    Calculate health score 0–100 from a list of completed check results.

    Args:
        checks: All CheckResult objects returned by a scan run.

    Returns:
        Integer in [0, 100].  Higher is healthier.

    Algorithm (from CLAUDE.md):
      Start at 100.
      Critical: -10 pts base (×1.5 for security/privacy/system → 15 pts)
      Warning:  -3 pts base  (×1.2 for security/privacy/system → ~4 pts)
      Info / Pass / Skip / Error: 0 pts
      Clamp result to [0, 100].
    """
    score = 100

    for check in checks:
        if check.status == "critical":
            points = 10
            if check.category in _SECURITY_CATEGORIES:
                points = int(points * 1.5)  # 15
        elif check.status == "warning":
            points = 3
            if check.category in _SECURITY_CATEGORIES:
                points = int(points * 1.2)  # ~4 (rounds to 3 or 4)
        else:
            points = 0

        score -= points

    return max(0, min(100, score))
