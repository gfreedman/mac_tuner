"""
Privacy checks.

macOS does not provide a public API to enumerate TCC (Transparency, Consent and
Control) permissions programmatically. Attempting to read TCC.db directly would
require Full Disk Access and is unreliable across macOS versions.

Instead, this module guides the user to review the most critical permissions
manually in System Settings → Privacy & Security.

Checks:
  - TCCPermissionAuditCheck — guided review of Full Disk Access, Screen
                              Recording, and Accessibility grants
"""

from __future__ import annotations

import os

from macaudit.checks.base import BaseCheck, CheckResult


class TCCPermissionAuditCheck(BaseCheck):
    """
    Guided TCC permission review.

    Always returns 'info' — the real value is in the educational text and the
    'guided' fix that opens the correct System Settings pane.
    """

    id = "tcc_permission_audit"
    name = "Privacy Permissions"
    category = "privacy"
    category_icon = "🔒"

    scan_description = (
        "Reviewing privacy & security permissions — "
        "macOS doesn't expose a public API to enumerate all app permissions, "
        "so we'll guide you through the most critical ones to review manually."
    )
    finding_explanation = (
        "Apps with Full Disk Access can read every file on your Mac — "
        "including password databases, private documents, and saved credentials. "
        "Apps with Screen Recording can silently capture everything on screen "
        "(passwords, messages, banking info). "
        "Apps with Accessibility can control your Mac, simulate keystrokes, and "
        "log everything you type. These three permissions should be reviewed regularly."
    )
    recommendation = (
        "Open System Settings → Privacy & Security and audit: "
        "Full Disk Access (only Terminal, backup apps, and essential system tools); "
        "Screen Recording (only screen-sharing apps you actively use); "
        "Accessibility (only automation tools you explicitly trust and recognise)."
    )

    fix_level = "guided"
    fix_description = "Opens Privacy & Security in System Settings for manual review."
    fix_url = "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles"
    fix_reversible = True
    fix_time_estimate = "~5 minutes"

    def run(self) -> CheckResult:
        """Check for TCC.db visibility as a proxy for Full Disk Access; always returns info."""
        # Check if we can see the TCC database path at all (proxy for FDA state)
        # We intentionally do NOT read it — just note whether macaudit has FDA.
        tcc_path = os.path.expanduser(
            "~/Library/Application Support/com.apple.TCC/TCC.db"
        )
        has_fda = os.path.exists(tcc_path)

        if has_fda:
            return self._info(
                "macaudit has Full Disk Access — review app permissions in System Settings"
            )

        return self._info(
            "Review Full Disk Access, Screen Recording & Accessibility in System Settings"
        )


# ── Export ────────────────────────────────────────────────────────────────────

ALL_CHECKS = [
    TCCPermissionAuditCheck,
]
