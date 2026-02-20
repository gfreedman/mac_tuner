"""
System health checks.

Covers macOS version, software updates, SIP, FileVault, Firewall,
Gatekeeper, Time Machine, auto-update config, screen lock,
Rosetta 2, and Secure Boot.
"""

import subprocess
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from macaudit.checks.base import BaseCheck, CheckResult
from macaudit.system_info import IS_APPLE_SILICON, MACOS_VERSION

_FIREWALL = "/usr/libexec/ApplicationFirewall/socketfilterfw"


# ── Shared network call (cached) ──────────────────────────────────────────────

@lru_cache(maxsize=1)
def _fetch_software_updates() -> tuple[int, str]:
    """
    Run `softwareupdate -l` once; cache result.

    Returns (returncode, combined_output).
    Timeout is 30 s because this is a network call.
    """
    try:
        r = subprocess.run(
            ["softwareupdate", "-l"],
            capture_output=True, text=True, timeout=30, check=False,
        )
        return r.returncode, r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        return -1, "TIMEOUT: softwareupdate took too long"
    except FileNotFoundError:
        return -1, "NOTFOUND: softwareupdate not available"
    except Exception as e:
        return -1, f"ERROR: {e}"


def _parse_update_lines(output: str) -> list[str]:
    """Return lines that describe available update items (start with * or -)."""
    return [
        ln.strip()
        for ln in output.splitlines()
        if ln.strip().startswith(("*", "-")) and ln.strip() != "-"
    ]


# ── Checks ────────────────────────────────────────────────────────────────────

class MacOSVersionCheck(BaseCheck):
    id = "macos_version"
    name = "macOS Version"
    category = "system"
    category_icon = "🖥️ "

    scan_description = (
        "Checking your macOS version — Apple releases security patches in every "
        "update. Running an old version leaves known vulnerabilities unpatched."
    )
    finding_explanation = (
        "macOS updates include security patches for vulnerabilities attackers "
        "actively exploit. Running an old major version means you receive no "
        "future security fixes for the base OS."
    )
    recommendation = (
        "Open System Settings → General → Software Update to install available "
        "macOS updates."
    )
    fix_level = "guided"
    fix_description = "Opens Software Update in System Settings"
    fix_url = "x-apple.systempreferences:com.apple.preferences.softwareupdate"
    fix_reversible = False
    fix_time_estimate = "20–60 minutes"

    def run(self) -> CheckResult:
        from macaudit.system_info import MACOS_VERSION_STRING

        rc, output = _fetch_software_updates()

        if rc == -1:
            # Network/timeout — just report current version
            return self._info(
                f"macOS {MACOS_VERSION_STRING} "
                f"(could not check for updates — {output[:60]})",
                data={"version": MACOS_VERSION_STRING},
            )

        update_lines = _parse_update_lines(output)
        macos_update = any(
            "macos" in ln.lower() or "os x" in ln.lower()
            for ln in update_lines
        )

        if macos_update:
            return self._warning(
                f"macOS update available (running {MACOS_VERSION_STRING})",
                data={"version": MACOS_VERSION_STRING, "update_available": True},
            )

        # Sanity: flag very old major version even if softwareupdate thinks it's fine
        if MACOS_VERSION[0] < 13:
            return self._warning(
                f"macOS {MACOS_VERSION_STRING} is no longer supported by Apple",
                data={"version": MACOS_VERSION_STRING},
            )

        return self._pass(
            f"macOS {MACOS_VERSION_STRING} is current",
            data={"version": MACOS_VERSION_STRING},
        )


class PendingUpdatesCheck(BaseCheck):
    id = "pending_updates"
    name = "Pending Software Updates"
    category = "system"
    category_icon = "🖥️ "

    scan_description = (
        "Checking for pending software updates — uninstalled updates may include "
        "security patches that protect against known exploits."
    )
    finding_explanation = (
        "Pending updates often contain security patches. Each day they sit "
        "uninstalled is a day your system is exposed to patched vulnerabilities."
    )
    recommendation = (
        "Run System Settings → General → Software Update to install all pending updates."
    )
    fix_level = "guided"
    fix_description = "Opens Software Update in System Settings"
    fix_url = "x-apple.systempreferences:com.apple.preferences.softwareupdate"
    fix_reversible = False
    fix_time_estimate = "5–60 minutes depending on updates"

    def run(self) -> CheckResult:
        rc, output = _fetch_software_updates()

        if rc == -1:
            return self._info(
                f"Could not check for updates: {output[:80]}",
            )

        if "no new software available" in output.lower():
            return self._pass("All software is up to date")

        update_lines = _parse_update_lines(output)
        n = len(update_lines)

        if n == 0:
            return self._pass("No pending updates found")

        # Flag critical/security updates specially
        has_security = any(
            "security" in ln.lower() or "recommended: yes" in ln.lower()
            for ln in output.splitlines()
        )

        msg = f"{n} update{'s' if n != 1 else ''} pending"
        if has_security:
            msg += " (includes recommended updates)"
            return self._warning(msg, data={"count": n})

        return self._warning(msg, data={"count": n})


class SIPCheck(BaseCheck):
    id = "sip_status"
    name = "System Integrity Protection (SIP)"
    category = "system"
    category_icon = "🖥️ "

    scan_description = (
        "Checking System Integrity Protection — SIP prevents malware from "
        "modifying core system files and system processes, even with root access."
    )
    finding_explanation = (
        "SIP restricts what even root can do: it protects system directories, "
        "prevents runtime injection into system processes, and stops kernel "
        "extensions from loading unsigned. Disabled SIP is a common target for "
        "malware that needs to persist through reboots."
    )
    recommendation = (
        "SIP should be enabled. If you disabled it for a specific reason "
        "(e.g. kernel extensions), ensure you understand the implications. "
        "Re-enable by booting to Recovery and running: csrutil enable"
    )
    fix_level = "instructions"
    fix_description = "Re-enabling SIP requires booting to Recovery Mode"
    fix_steps = [
        "Restart and hold Power (Apple Silicon) or Cmd+R (Intel) to enter Recovery",
        "Open Terminal from the Utilities menu",
        "Run: csrutil enable",
        "Restart your Mac",
    ]
    fix_reversible = True
    fix_time_estimate = "~5 minutes"

    def run(self) -> CheckResult:
        rc, stdout, stderr = self.shell(["csrutil", "status"])

        if rc != 0 or not stdout:
            return self._info(f"Could not determine SIP status: {stderr[:80]}")

        out = stdout.strip().lower()

        # Full SIP enabled: "system integrity protection status: enabled."
        # Must not match "enabled (custom configuration)" — that's partial.
        if "status: enabled." in out and "custom" not in out:
            return self._pass("System Integrity Protection is enabled")

        # Partial: SIP enabled with specific flags removed
        if "enabled" in out and "custom" in out:
            return self._warning(
                "SIP is partially disabled (custom configuration — some protections removed)",
                data={"sip_status": stdout.strip()[:120]},
            )

        if "disabled" in out:
            return self._warning(
                "System Integrity Protection is disabled",
                data={"sip_enabled": False},
            )

        return self._info(f"SIP status: {stdout.strip()[:80]}")


class FileVaultCheck(BaseCheck):
    id = "filevault"
    name = "FileVault Disk Encryption"
    category = "system"
    category_icon = "🖥️ "

    scan_description = (
        "Checking if FileVault disk encryption is enabled — without it, anyone "
        "with physical access to your Mac can read all your files, even without "
        "knowing your password."
    )
    finding_explanation = (
        "FileVault encrypts your entire disk. Without it, someone who steals "
        "your Mac can plug it into another computer and read every file—no "
        "login password required. This is especially important for laptops."
    )
    recommendation = (
        "Enable FileVault in System Settings → Privacy & Security → FileVault. "
        "Encryption runs in the background and doesn't slow down normal use."
    )
    fix_level = "guided"
    fix_description = "Opens Privacy & Security where you can enable FileVault"
    fix_url = "x-apple.systempreferences:com.apple.preference.security?FileVault"
    fix_reversible = True
    fix_time_estimate = "Hours to encrypt (runs in background)"

    def run(self) -> CheckResult:
        rc, stdout, stderr = self.shell(["fdesetup", "status"])

        if rc != 0:
            return self._error(f"Could not check FileVault: {stderr[:80]}")

        out = stdout.lower()

        if "is on" in out:
            if "converting" in out:
                return self._info(
                    "FileVault is encrypting (conversion in progress)",
                    data={"converting": True},
                )
            return self._pass("Disk encryption is enabled")

        if "is off" in out:
            return self._critical(
                "Disk encryption is disabled — physical access = data access",
                data={"filevault_enabled": False},
            )

        return self._info(f"FileVault status unclear: {stdout.strip()[:80]}")


class FirewallCheck(BaseCheck):
    id = "firewall"
    name = "Application Firewall"
    category = "system"
    category_icon = "🖥️ "

    scan_description = (
        "Checking if the macOS application firewall is enabled — it blocks "
        "unexpected incoming connections to your Mac."
    )
    finding_explanation = (
        "The macOS Application Firewall (ALF) controls which apps can accept "
        "incoming network connections. Note: it is inbound-only — it does not "
        "filter outbound traffic. With ALF disabled, any running app can receive "
        "unsolicited inbound data from the network, which is a significant risk on "
        "public Wi-Fi. For outbound traffic control, a third-party tool such as "
        "Little Snitch or Lulu is needed."
    )
    recommendation = (
        "Enable the firewall in System Settings → Network → Firewall. "
        "For outbound traffic filtering, consider Little Snitch or Lulu (free)."
    )
    fix_level = "auto_sudo"
    fix_description = "Enables the application firewall"
    fix_command = f"{_FIREWALL} --setglobalstate on"
    fix_reversible = True
    fix_time_estimate = "~5 seconds"
    requires_sudo = True

    def run(self) -> CheckResult:
        if not Path(_FIREWALL).exists():
            return self._skip("socketfilterfw not found")

        rc, stdout, stderr = self.shell([_FIREWALL, "--getglobalstate"])

        if rc != 0:
            return self._info(f"Could not check firewall: {stderr[:80]}")

        out = stdout.lower()

        if "enabled" in out or "state = 1" in out:
            return self._pass("Application firewall is enabled")

        if "disabled" in out or "state = 0" in out:
            return self._warning(
                "Application firewall is disabled",
                data={"firewall_enabled": False},
            )

        return self._info(f"Firewall status unclear: {stdout.strip()[:80]}")


class FirewallStealthCheck(BaseCheck):
    id = "firewall_stealth"
    name = "Firewall Stealth Mode"
    category = "system"
    category_icon = "🖥️ "

    scan_description = (
        "Checking firewall stealth mode — this prevents your Mac from responding "
        "to network probing, making it harder for attackers to detect."
    )
    finding_explanation = (
        "Stealth mode makes your Mac ignore unsolicited ICMP ping requests and "
        "connection attempts from closed ports. Without it, network scanners "
        "can confirm your Mac exists on the network."
    )
    recommendation = (
        "Enable stealth mode in System Settings → Network → Firewall → Options."
    )
    fix_level = "auto_sudo"
    fix_description = "Enables firewall stealth mode"
    fix_command = f"{_FIREWALL} --setstealthmode on"
    fix_reversible = True
    fix_time_estimate = "~5 seconds"
    requires_sudo = True

    def run(self) -> CheckResult:
        if not Path(_FIREWALL).exists():
            return self._skip("socketfilterfw not found")

        rc, stdout, stderr = self.shell([_FIREWALL, "--getstealthmode"])

        if rc != 0:
            return self._info(f"Could not check stealth mode: {stderr[:80]}")

        out = stdout.lower()

        # Output format: "Firewall stealth mode is on" / "Firewall stealth mode is off"
        # Older format: "Stealth mode enabled" / "Stealth mode disabled"
        if "enabled" in out or " is on" in out:
            return self._pass("Stealth mode is enabled")

        if "disabled" in out or " is off" in out:
            return self._info(
                "Stealth mode is disabled — Mac responds to network probes",
                data={"stealth_enabled": False},
            )

        return self._info(f"Stealth mode status: {stdout.strip()[:80]}")


class GatekeeperCheck(BaseCheck):
    id = "gatekeeper"
    name = "Gatekeeper"
    category = "system"
    category_icon = "🖥️ "

    scan_description = (
        "Checking Gatekeeper — it verifies that apps are from identified developers "
        "and haven't been tampered with before allowing them to run."
    )
    finding_explanation = (
        "Gatekeeper is macOS's first line of defense against malicious apps. "
        "It checks code signatures and notarization before running any app. "
        "Disabled Gatekeeper means any unsigned app, including malware, runs "
        "without any verification."
    )
    recommendation = (
        "Re-enable Gatekeeper by running: sudo spctl --master-enable"
    )
    fix_level = "auto_sudo"
    fix_description = "Re-enables Gatekeeper app verification"
    fix_command = "spctl --master-enable"
    fix_reversible = True
    fix_time_estimate = "~5 seconds"
    requires_sudo = True

    def run(self) -> CheckResult:
        rc, stdout, stderr = self.shell(["spctl", "--status"])

        if rc != 0 and not stdout:
            return self._info(f"Could not check Gatekeeper: {stderr[:80]}")

        out = stdout.lower()

        if "enabled" in out:
            return self._pass("Gatekeeper is enabled — apps are verified before running")

        if "disabled" in out:
            return self._critical(
                "Gatekeeper is disabled — apps run without any verification",
                data={"gatekeeper_enabled": False},
            )

        return self._info(f"Gatekeeper status: {stdout.strip()[:80]}")


class TimeMachineCheck(BaseCheck):
    id = "time_machine"
    name = "Time Machine Backup"
    category = "system"
    category_icon = "🖥️ "

    scan_description = (
        "Checking when your last Time Machine backup ran — a backup you didn't "
        "make is a backup you'll desperately wish you had."
    )
    finding_explanation = (
        "Time Machine is your safety net for accidental deletion, drive failure, "
        "and ransomware. If the last backup is more than 7 days old — or "
        "there's never been one — you're at real risk of permanent data loss."
    )
    recommendation = (
        "Connect your Time Machine drive or configure a network backup. "
        "Aim for daily automatic backups."
    )
    fix_level = "guided"
    fix_description = "Opens Time Machine settings"
    fix_url = "x-apple.systempreferences:com.apple.TimeMachine"
    fix_reversible = True
    fix_time_estimate = "Varies — depends on backup size"

    def run(self) -> CheckResult:
        rc, stdout, stderr = self.shell(["tmutil", "latestbackup"])

        if rc != 0 or not stdout.strip():
            return self._warning(
                "No Time Machine backup found",
                data={"backup_found": False},
            )

        backup_path = stdout.strip()

        # Parse date from path component like "2024-02-10-143052"
        try:
            folder = Path(backup_path).name  # e.g. "2024-02-10-143052"
            dt = datetime.strptime(folder[:15], "%Y-%m-%d-%H%M%S")
            dt = dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            age_days = (now - dt).days
            age_str = (
                f"{age_days} day{'s' if age_days != 1 else ''} ago"
                if age_days > 0
                else "today"
            )

            if age_days > 7:
                return self._warning(
                    f"Last backup was {age_str}",
                    data={"backup_age_days": age_days},
                )
            if age_days > 1:
                return self._info(
                    f"Last backup was {age_str}",
                    data={"backup_age_days": age_days},
                )
            return self._pass(
                f"Last backup was {age_str}",
                data={"backup_age_days": age_days},
            )

        except (ValueError, IndexError):
            return self._info(f"Last backup: {backup_path[-50:]}")


class AutoUpdateCheck(BaseCheck):
    id = "auto_update"
    name = "Automatic Security Updates"
    category = "system"
    category_icon = "🖥️ "

    scan_description = (
        "Checking automatic update settings — security response updates and "
        "XProtect signature updates protect against new malware automatically."
    )
    finding_explanation = (
        "macOS has three critical auto-update toggles. If 'Install Security "
        "Responses and System Files' is off, your Mac won't automatically receive "
        "Apple's Rapid Security Responses — fast patches for active zero-day attacks."
    )
    recommendation = (
        "Enable all automatic update options in System Settings → "
        "General → Software Update → Automatic Updates."
    )
    fix_level = "guided"
    fix_description = "Opens Software Update settings"
    fix_url = "x-apple.systempreferences:com.apple.preferences.softwareupdate"
    fix_reversible = True
    fix_time_estimate = "~30 seconds"

    _PREF_DOMAIN = "/Library/Preferences/com.apple.SoftwareUpdate"

    def run(self) -> CheckResult:
        issues = []

        for key, label in [
            ("AutomaticCheckEnabled",  "Check for updates"),
            ("CriticalUpdateInstall",  "Install security responses"),
            ("ConfigDataInstall",      "Install XProtect/MRT updates"),
        ]:
            rc, stdout, _ = self.shell(
                ["defaults", "read", self._PREF_DOMAIN, key]
            )
            if rc == 0 and stdout.strip() == "0":
                issues.append(label)
            # rc != 0 → key missing (defaults to on) → no issue

        if not issues:
            return self._pass("Automatic security updates are enabled")

        return self._warning(
            f"Auto-updates partially disabled: {', '.join(issues)}",
            data={"disabled_keys": issues},
        )


class ScreenLockCheck(BaseCheck):
    id = "screen_lock"
    name = "Screen Lock After Sleep"
    category = "system"
    category_icon = "🖥️ "

    scan_description = (
        "Checking if your Mac requires a password quickly after sleep or "
        "screensaver — this prevents someone from accessing it if you step away."
    )
    finding_explanation = (
        "FileVault protects your data when the Mac is off. A screen lock "
        "protects it when it's sleeping — and you. Without a prompt delay of "
        "nearly zero, anyone near your unlocked Mac has full access."
    )
    recommendation = (
        "Set your Mac to require a password immediately after sleep in "
        "System Settings → Lock Screen → Require password after screen saver begins."
    )
    fix_level = "guided"
    fix_description = "Opens Lock Screen settings"
    fix_url = "x-apple.systempreferences:com.apple.preference.security?General"
    fix_reversible = True
    fix_time_estimate = "~30 seconds"

    def run(self) -> CheckResult:
        # Check if password is required at all
        rc_req, req_out, _ = self.shell(
            ["defaults", "read", "com.apple.screensaver", "askForPassword"]
        )
        if rc_req == 0 and req_out.strip() == "0":
            return self._warning(
                "Password not required after sleep or screensaver",
                data={"password_required": False},
            )

        # Check delay
        rc, stdout, _ = self.shell(
            ["defaults", "read", "com.apple.screensaver", "askForPasswordDelay"]
        )
        if rc != 0 or not stdout.strip():
            # Key absent → system default is 0 (immediate) — safe
            return self._pass("Password required immediately after sleep (system default)")

        try:
            delay = int(float(stdout.strip()))
        except ValueError:
            return self._info(f"Screen lock delay unreadable: {stdout.strip()[:40]}")

        if delay == 0:
            return self._pass("Password required immediately after sleep")
        if delay <= 5:
            return self._pass(
                f"Password required after {delay}s (acceptable)",
                data={"delay_seconds": delay},
            )
        if delay <= 60:
            return self._warning(
                f"Password delay is {delay}s — consider setting to immediate",
                data={"delay_seconds": delay},
            )

        return self._warning(
            f"Password delay is {delay}s — Mac is unlocked for too long after sleep",
            data={"delay_seconds": delay},
        )


class RosettaCheck(BaseCheck):
    id = "rosetta"
    name = "Rosetta 2"
    category = "system"
    category_icon = "🖥️ "

    scan_description = (
        "Checking if Rosetta 2 is installed — it's required to run apps built "
        "for Intel processors on Apple Silicon Macs."
    )
    finding_explanation = (
        "Many apps (particularly older or niche software) still distribute "
        "Intel-only binaries. Without Rosetta 2, they won't launch at all. "
        "On Apple Silicon, having Rosetta installed avoids surprise 'app can't "
        "be opened' errors."
    )
    recommendation = (
        "Install Rosetta 2 by running: softwareupdate --install-rosetta --agree-to-license"
    )
    fix_level = "auto_sudo"
    fix_description = "Installs Rosetta 2 for Intel app compatibility"
    fix_command = "softwareupdate --install-rosetta --agree-to-license"
    fix_reversible = False
    fix_time_estimate = "~2 minutes"

    def run(self) -> CheckResult:
        if not IS_APPLE_SILICON:
            return self._skip("Rosetta 2 only applies to Apple Silicon Macs")

        # Check if Rosetta translation runtime is present
        rosetta_path = Path("/usr/libexec/rosetta/rosetta")
        oah_path = Path("/usr/libexec/oah/translate")  # alternate indicator

        if rosetta_path.exists() or oah_path.exists():
            return self._pass("Rosetta 2 is installed (Intel app compatibility ready)")

        # Double-check: try running an x86_64 command
        rc, _, _ = self.shell(["arch", "-arch", "x86_64", "true"])
        if rc == 0:
            return self._pass("Rosetta 2 is installed")

        return self._info(
            "Rosetta 2 is not installed — Intel-only apps will not run",
            data={"rosetta_installed": False},
        )


class SecureBootCheck(BaseCheck):
    id = "secure_boot"
    name = "Secure Boot"
    category = "system"
    category_icon = "🖥️ "

    scan_description = (
        "Checking Secure Boot policy — it ensures only trusted, Apple-signed "
        "software loads during startup, blocking rootkits and bootkits."
    )
    finding_explanation = (
        "Secure Boot at Full Security validates every piece of software in the "
        "boot chain. Reduced or Permissive Security allows unsigned kernel "
        "extensions and bootloaders — a favorite target for persistent malware."
    )
    recommendation = (
        "Set Secure Boot to Full Security in Startup Security Utility "
        "(boot to Recovery → Utilities → Startup Security Utility)."
    )
    fix_level = "instructions"
    fix_description = "Requires Recovery Mode to change Secure Boot policy"
    fix_steps = [
        "Restart and hold the Power button (Apple Silicon) or Cmd+R (Intel)",
        "Open Utilities → Startup Security Utility",
        "Select 'Full Security'",
        "Restart",
    ]
    fix_reversible = True
    fix_time_estimate = "~5 minutes"

    def run(self) -> CheckResult:
        if not IS_APPLE_SILICON:
            # For Intel with T2: system_profiler SPiBridgeDataType
            rc, stdout, _ = self.shell(
                ["system_profiler", "SPiBridgeDataType"], timeout=8
            )
            if rc != 0 or not stdout:
                return self._skip("Secure Boot check requires T2 chip or Apple Silicon")

            for line in stdout.splitlines():
                if "secure boot" in line.lower():
                    val = line.split(":", 1)[-1].strip()
                    if "full" in val.lower():
                        return self._pass(f"Secure Boot: {val}")
                    return self._info(f"Secure Boot: {val}")

            return self._skip("Secure Boot info not available on this Mac")

        # Apple Silicon: nvram AppleSecureBootPolicy
        rc, stdout, _ = self.shell(["nvram", "AppleSecureBootPolicy"])

        if rc != 0 or not stdout:
            # On some Apple Silicon builds the key name differs or requires
            # elevated access — return info rather than error
            return self._info(
                "Secure Boot policy not readable from NVRAM "
                "(may require System Integrity Protection to be enabled)"
            )

        # The value is hex-encoded; %02 = Full Security (mode 2)
        if "%02" in stdout:
            return self._pass("Secure Boot: Full Security (maximum protection)")
        if "%01" in stdout:
            return self._info(
                "Secure Boot: Reduced Security (unsigned kernel extensions allowed)",
                data={"secure_boot_level": 1},
            )
        if "%00" in stdout:
            return self._warning(
                "Secure Boot: Permissive Security (minimal boot protection)",
                data={"secure_boot_level": 0},
            )

        return self._info(f"Secure Boot policy: {stdout.strip()[:60]}")


# ── Public list for main.py ───────────────────────────────────────────────────

ALL_CHECKS: list[type[BaseCheck]] = [
    MacOSVersionCheck,
    PendingUpdatesCheck,
    SIPCheck,
    FileVaultCheck,
    FirewallCheck,
    FirewallStealthCheck,
    GatekeeperCheck,
    TimeMachineCheck,
    AutoUpdateCheck,
    ScreenLockCheck,
    RosettaCheck,
    SecureBootCheck,
]
