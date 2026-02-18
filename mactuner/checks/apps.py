"""
App-level checks.

Checks:
  - AppStoreUpdatesCheck — outdated App Store apps (requires mas CLI)
  - iCloudStatusCheck    — iCloud account sign-in and Drive availability
  - LoginItemsCheck      — startup items count via launchctl
"""

from __future__ import annotations

import os

from mactuner.checks.base import BaseCheck, CheckResult


# ── App Store updates ─────────────────────────────────────────────────────────

class AppStoreUpdatesCheck(BaseCheck):
    id = "app_store_updates"
    name = "App Store Updates"
    category = "apps"
    category_icon = "🛍️ "

    requires_tool = "mas"

    scan_description = (
        "Checking for pending App Store updates via mas — "
        "apps don't always notify you, so outdated versions accumulate security "
        "vulnerabilities silently."
    )
    finding_explanation = (
        "Apps from the Mac App Store receive security and bug-fix updates regularly. "
        "Unlike Homebrew, App Store apps don't auto-update by default unless you "
        "enable automatic updates. Outdated apps can have unpatched vulnerabilities "
        "that attackers exploit — browsers and productivity apps are common targets."
    )
    recommendation = (
        "Run 'mas upgrade' to update all App Store apps at once, "
        "or open the App Store → Updates tab. "
        "Enable automatic updates: App Store → Settings → Automatic Updates."
    )

    fix_level = "auto"
    fix_description = "Update all outdated App Store apps via mas upgrade."
    fix_command = "mas upgrade"
    fix_reversible = False
    fix_time_estimate = "~5 minutes"

    def run(self) -> CheckResult:
        rc, out, err = self.shell(["mas", "outdated"], timeout=30)

        # mas exits 0 whether or not there are updates
        if rc != 0 and not out.strip():
            return self._info("Could not check App Store updates (try: mas list)")

        lines = [l.strip() for l in out.splitlines() if l.strip()]
        count = len(lines)

        if count == 0:
            return self._pass("All App Store apps are up to date")

        apps_preview = ", ".join(
            l.split(None, 2)[2].strip() if len(l.split(None, 2)) >= 3 else l
            for l in lines[:3]
        )
        suffix = f"  +{count - 3} more" if count > 3 else ""

        return self._warning(
            f"{count} App Store app{'s' if count != 1 else ''} need updates: "
            f"{apps_preview}{suffix}",
            data={"outdated": lines, "count": count},
        )


# ── iCloud status ─────────────────────────────────────────────────────────────

class iCloudStatusCheck(BaseCheck):
    id = "icloud_status"
    name = "iCloud Sign-in"
    category = "apps"
    category_icon = "☁️ "

    scan_description = (
        "Checking iCloud account status — "
        "iCloud sync failures are silent: data may not be backed up to the cloud "
        "even though the icon appears normal."
    )
    finding_explanation = (
        "iCloud keeps your documents, photos, and settings synced across Apple devices. "
        "If the account is missing or in a broken state, files in iCloud Drive may "
        "become unavailable on other devices and new data won't upload. "
        "This often happens after a macOS upgrade or password change."
    )
    recommendation = (
        "Open System Settings → Apple Account to verify iCloud status. "
        "If there's a yellow warning icon, sign out and sign back in. "
        "Check iCloud Drive sync: Finder → iCloud Drive — look for the sync spinner."
    )

    fix_level = "guided"
    fix_description = "Check iCloud status in System Settings → Apple Account."
    fix_url = "x-apple.systempreferences:com.apple.preferences.AppleIDPrefPane"
    fix_reversible = True
    fix_time_estimate = "~2 minutes"

    def run(self) -> CheckResult:
        # Check MobileMeAccounts preferences — present when iCloud account is configured
        rc, out, _ = self.shell(
            ["defaults", "read", "MobileMeAccounts", "Accounts"]
        )

        if rc != 0 or not out.strip() or out.strip() in ("()", "(\n)"):
            return self._info("No iCloud account configured on this Mac")

        # Check iCloud Drive directory presence as a proxy for active sync
        icloud_drive = os.path.expanduser("~/Library/Mobile Documents")
        if os.path.isdir(icloud_drive):
            try:
                count = len(os.listdir(icloud_drive))
                return self._pass(f"iCloud active — {count} apps syncing to Drive")
            except PermissionError:
                return self._info("iCloud configured (Drive access restricted)")

        return self._info("iCloud account configured")


# ── Login items (startup apps) ────────────────────────────────────────────────

class LoginItemsCheck(BaseCheck):
    id = "login_items"
    name = "Login Items"
    category = "apps"
    category_icon = "🚀"

    scan_description = (
        "Counting login items (apps that launch at startup) — "
        "each one adds to boot time and silently consumes RAM in the background."
    )
    finding_explanation = (
        "Login items are apps and agents that launch automatically when you log in. "
        "Many apps add themselves without obvious disclosure — Dropbox, Google Drive, "
        "Zoom, browser helpers, update daemons, and vendor software are common culprits. "
        "A Mac with 20+ login items can add 30–60 seconds to startup time."
    )
    recommendation = (
        "Review System Settings → General → Login Items & Extensions. "
        "Disable any you don't need running at startup — most can be launched on demand. "
        "Also check the 'Allow in Background' section for hidden agents."
    )

    fix_level = "guided"
    fix_description = "Review and disable unnecessary login items in System Settings."
    fix_url = "x-apple.systempreferences:com.apple.LoginItems-Settings.extension"
    fix_reversible = True
    fix_time_estimate = "~5 minutes"

    # Labels to exclude from the "third-party agent" count.
    # Only genuinely system/Apple-managed identifiers belong here.
    # "0x…" labels are anonymous numeric PIDs — not meaningful agent names.
    _SYSTEM_LABEL_PREFIXES = (
        "com.apple.",    # Apple system and app agents
        "com.openssh.",  # SSH daemon (part of the OS)
        "0x",            # Numeric/hex PIDs — not real agent labels
    )

    def run(self) -> CheckResult:
        rc, out, _ = self.shell(["launchctl", "list"])
        if rc != 0 or not out:
            return self._info("Could not enumerate background launch agents")

        third_party = []
        for line in out.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("PID"):
                continue
            # launchctl list format: PID  Status  Label
            parts = stripped.split(None, 2)
            if len(parts) < 3:
                continue
            label = parts[2]
            if not any(label.startswith(p) for p in self._SYSTEM_LABEL_PREFIXES):
                third_party.append(label)

        count = len(third_party)

        if count > 20:
            return self._warning(
                f"{count} third-party background agents at startup — review login items",
                data={"count": count},
            )
        if count > 12:
            return self._info(
                f"{count} third-party background agents",
                data={"count": count},
            )
        return self._pass(
            f"{count} background login agent{'s' if count != 1 else ''}",
            data={"count": count},
        )


# ── Export ────────────────────────────────────────────────────────────────────

ALL_CHECKS = [
    AppStoreUpdatesCheck,
    iCloudStatusCheck,
    LoginItemsCheck,
]
