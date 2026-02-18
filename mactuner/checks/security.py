"""
Security hardening checks.

Covers auto-login, SSH keys, launch agents, /etc/hosts,
sharing services, Activation Lock, MDM profiles.
"""

import plistlib
import re
from pathlib import Path

from mactuner.checks.base import BaseCheck, CheckResult

HOME = Path.home()

# Standard /etc/hosts entries — not suspicious
_STANDARD_HOSTS = {
    "localhost", "broadcasthost", "ip6-localhost",
    "ip6-loopback", "local",
}
_LOOPBACK_PREFIXES = ("127.", "::1", "0.0.0.0", "255.")

# Launch agent paths to scan (order: user → system)
_LAUNCH_AGENT_DIRS = [
    HOME / "Library" / "LaunchAgents",
    HOME / "Library" / "LaunchDaemons",   # should be empty for normal users
    Path("/Library/LaunchAgents"),
    Path("/Library/LaunchDaemons"),
]

# SSH config paths
_SSH_DIR = HOME / ".ssh"
_AUTHORIZED_KEYS = _SSH_DIR / "authorized_keys"


# ── Checks ────────────────────────────────────────────────────────────────────

class AutoLoginCheck(BaseCheck):
    id = "auto_login"
    name = "Auto-Login"
    category = "security"
    category_icon = "🛡️ "

    scan_description = (
        "Checking if auto-login is enabled — with auto-login on, anyone who "
        "picks up your Mac gets instant access without a password."
    )
    finding_explanation = (
        "Auto-login bypasses the login screen entirely. If your Mac is lost "
        "or stolen, the finder gets instant access to everything on it — "
        "files, browser sessions, passwords stored in apps."
    )
    recommendation = (
        "Disable auto-login in System Settings → General → Login Items & Extensions "
        "→ Login Options (or System Preferences → Security → disable auto-login)."
    )
    fix_level = "guided"
    fix_description = "Opens Login Items settings"
    fix_url = "x-apple.systempreferences:com.apple.LoginItems-Settings.Extension"
    fix_reversible = True
    fix_time_estimate = "~30 seconds"

    def run(self) -> CheckResult:
        rc, stdout, _ = self.shell(
            [
                "defaults",
                "read",
                "/Library/Preferences/com.apple.loginwindow",
                "autoLoginUser",
            ]
        )

        if rc != 0:
            # Key missing → auto-login is disabled (normal/good)
            return self._pass("Auto-login is disabled")

        username = stdout.strip()
        if username:
            return self._critical(
                f"Auto-login is enabled for user '{username}'",
                data={"auto_login_user": username},
            )

        return self._pass("Auto-login is disabled")


class SSHAuthorizedKeysCheck(BaseCheck):
    id = "ssh_authorized_keys"
    name = "SSH Authorized Keys"
    category = "security"
    category_icon = "🛡️ "

    scan_description = (
        "Checking ~/.ssh/authorized_keys — old or forgotten SSH keys in this "
        "file give their holders permanent passwordless access to your Mac."
    )
    finding_explanation = (
        "Every key in authorized_keys grants its holder SSH access without a "
        "password. Old keys from previous employers, old computers, or "
        "developers you no longer work with are permanent backdoors."
    )
    recommendation = (
        "Review ~/.ssh/authorized_keys and remove any keys you don't recognize "
        "or that belong to people/machines no longer trusted."
    )
    fix_level = "instructions"
    fix_description = "Review and remove untrusted public keys"
    fix_steps = [
        "Open Terminal and run: cat ~/.ssh/authorized_keys",
        "For each key, check the comment at the end (usually user@host)",
        "Remove lines for machines or people you no longer trust",
        "Save the file",
    ]
    fix_reversible = True
    fix_time_estimate = "~5 minutes"

    def run(self) -> CheckResult:
        # Also check if Remote Login (SSH server) is even running
        rc_ssh, ssh_out, _ = self.shell(
            ["systemsetup", "-getremotelogin"], timeout=5
        )
        ssh_on = rc_ssh == 0 and "on" in ssh_out.lower()

        if not _AUTHORIZED_KEYS.exists():
            if ssh_on:
                return self._pass(
                    "SSH is on, but no authorized_keys file exists"
                )
            return self._pass("No authorized_keys file (SSH server is off)")

        try:
            content = _AUTHORIZED_KEYS.read_text(errors="replace")
        except OSError as e:
            return self._error(f"Could not read authorized_keys: {e}")

        keys = [
            ln.strip()
            for ln in content.splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]

        if not keys:
            return self._pass("authorized_keys is empty")

        n = len(keys)
        msg = f"{n} authorized SSH key{'s' if n != 1 else ''} found"

        if n > 5:
            return self._warning(
                f"{msg} — review for old or untrusted entries",
                data={"key_count": n},
            )

        return self._info(
            f"{msg} — verify all are still trusted",
            data={"key_count": n},
        )


class SSHKeyStrengthCheck(BaseCheck):
    id = "ssh_key_strength"
    name = "SSH Key Strength"
    category = "security"
    category_icon = "🛡️ "

    scan_description = (
        "Checking SSH key types — DSA keys are broken, and old RSA keys may be "
        "too weak. Ed25519 or ECDSA are the modern standard."
    )
    finding_explanation = (
        "DSA keys are cryptographically broken and should never be used. "
        "RSA keys need to be at least 2048 bits (4096 recommended). "
        "Ed25519 is the modern default and far more secure."
    )
    recommendation = (
        "Generate a new Ed25519 key: ssh-keygen -t ed25519 -C 'your@email'. "
        "Then update authorized_keys on any remote servers."
    )
    fix_level = "instructions"
    fix_description = "Generate a new strong SSH key"
    fix_steps = [
        "Run: ssh-keygen -t ed25519 -C 'your@email.com'",
        "Copy new public key to servers: ssh-copy-id user@host",
        "Remove old weak keys from ~/.ssh/ once new ones are working",
    ]
    fix_reversible = True
    fix_time_estimate = "~10 minutes"

    def run(self) -> CheckResult:
        if not _SSH_DIR.exists():
            return self._skip("No ~/.ssh directory found")

        weak_keys: list[str] = []
        rsa_keys: list[str] = []

        # Check public key files
        for pub in _SSH_DIR.glob("*.pub"):
            try:
                text = pub.read_text(errors="replace").strip()
                if text.startswith("ssh-dss"):
                    weak_keys.append(f"{pub.name} (DSA — broken)")
                elif text.startswith("ssh-rsa"):
                    rsa_keys.append(pub.name)
            except OSError:
                continue

        # Also scan authorized_keys for weak types
        if _AUTHORIZED_KEYS.exists():
            try:
                for ln in _AUTHORIZED_KEYS.read_text(errors="replace").splitlines():
                    ln = ln.strip()
                    if ln.startswith("ssh-dss"):
                        weak_keys.append("authorized_keys entry (DSA — broken)")
            except OSError:
                pass

        if weak_keys:
            return self._warning(
                f"Weak SSH keys found: {', '.join(weak_keys[:3])}",
                data={"weak_keys": weak_keys},
            )

        if rsa_keys:
            # RSA might be fine (≥2048) but flag for awareness
            return self._info(
                f"RSA key(s) found: {', '.join(rsa_keys)} — consider upgrading to Ed25519",
                data={"rsa_keys": rsa_keys},
            )

        # Check if any modern keys exist
        modern = list(_SSH_DIR.glob("id_ed25519.pub")) + list(_SSH_DIR.glob("id_ecdsa*.pub"))
        if modern:
            return self._pass(
                f"Strong key(s) found: {', '.join(p.name for p in modern[:3])}"
            )

        if list(_SSH_DIR.glob("*.pub")):
            return self._info("SSH keys present — types appear acceptable")

        return self._pass("No local SSH keys found")


class LaunchAgentsCheck(BaseCheck):
    id = "launch_agents"
    name = "Launch Agents & Daemons"
    category = "security"
    category_icon = "🛡️ "

    scan_description = (
        "Scanning launch agent directories — malware and adware use launch "
        "agents to persist across reboots without your knowledge."
    )
    finding_explanation = (
        "Launch agents are programs that run automatically when you log in. "
        "Legitimate software uses them, but so does adware and malware — "
        "it's a primary persistence mechanism. ~/Library/LaunchDaemons/ "
        "should be empty for normal users; its presence is a red flag."
    )
    recommendation = (
        "Review any non-Apple launch agents. If you don't recognize who made "
        "it or why it's running, research it before removing."
    )
    fix_level = "instructions"
    fix_description = "Review and remove suspicious launch agents"
    fix_steps = [
        "Open Terminal and run: ls ~/Library/LaunchAgents/",
        "Research any plists you don't recognize",
        "To disable: launchctl unload ~/Library/LaunchAgents/<name>.plist",
        "To remove: rm ~/Library/LaunchAgents/<name>.plist",
    ]
    fix_reversible = True
    fix_time_estimate = "10–30 minutes"

    def run(self) -> CheckResult:
        non_apple: list[str] = []
        suspicious: list[str] = []  # in places they shouldn't be

        for directory in _LAUNCH_AGENT_DIRS:
            if not directory.exists():
                continue

            in_user_daemons = "LaunchDaemons" in str(directory) and str(directory).startswith(str(HOME))

            for plist in directory.glob("*.plist"):
                name = plist.name

                if in_user_daemons:
                    # ~/Library/LaunchDaemons/ should not exist / be empty
                    suspicious.append(f"{name} (in ~/Library/LaunchDaemons/ — abnormal)")
                    continue

                # Flag non-Apple plists for awareness
                if not name.startswith("com.apple.") and not name.startswith("com.Apple."):
                    non_apple.append(f"{name} ({directory.name})")

        all_issues = suspicious + non_apple

        if suspicious:
            return self._critical(
                f"Suspicious entries in ~/Library/LaunchDaemons/: "
                f"{', '.join(suspicious[:3])}",
                data={"suspicious": suspicious, "non_apple": non_apple},
            )

        if len(non_apple) > 10:
            return self._warning(
                f"{len(non_apple)} third-party launch agents — review for unwanted entries",
                data={"non_apple": non_apple},
            )

        if non_apple:
            return self._info(
                f"{len(non_apple)} third-party launch agent(s) — verify all are intentional",
                data={"non_apple": non_apple},
            )

        return self._pass("No unexpected launch agents or daemons found")


class EtcHostsCheck(BaseCheck):
    id = "etc_hosts"
    name = "/etc/hosts Entries"
    category = "security"
    category_icon = "🛡️ "

    scan_description = (
        "Checking /etc/hosts for unusual entries — malware sometimes adds "
        "entries here to redirect legitimate sites to malicious servers."
    )
    finding_explanation = (
        "/etc/hosts maps hostnames to IP addresses before DNS is consulted. "
        "An entry redirecting 'apple.com' to a malicious IP means visiting "
        "apple.com in a browser goes to the attacker's server instead."
    )
    recommendation = (
        "Review /etc/hosts and remove any entries you didn't add yourself. "
        "Run: sudo nano /etc/hosts"
    )
    fix_level = "instructions"
    fix_description = "Review /etc/hosts for rogue entries"
    fix_steps = [
        "Run: cat /etc/hosts",
        "Standard entries only: 127.0.0.1 localhost, ::1 localhost",
        "Remove any entries for well-known domains (google.com, apple.com, etc.)",
        "Edit with: sudo nano /etc/hosts",
    ]
    fix_reversible = True
    fix_time_estimate = "~5 minutes"

    def run(self) -> CheckResult:
        hosts_path = Path("/etc/hosts")
        if not hosts_path.exists():
            return self._info("/etc/hosts not found")

        try:
            content = hosts_path.read_text(errors="replace")
        except OSError as e:
            return self._error(f"Could not read /etc/hosts: {e}")

        unusual: list[str] = []
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split()
            if len(parts) < 2:
                continue

            ip, *hostnames = parts

            # Skip loopback / standard addresses
            if any(ip.startswith(p) for p in _LOOPBACK_PREFIXES):
                continue

            # Any non-loopback entry is worth flagging
            for host in hostnames:
                if host not in _STANDARD_HOSTS:
                    unusual.append(f"{ip} → {host}")

        if not unusual:
            return self._pass("No unusual entries in /etc/hosts")

        n = len(unusual)
        examples = unusual[:3]
        return self._warning(
            f"{n} non-standard /etc/hosts entr{'ies' if n != 1 else 'y'}: "
            f"{', '.join(examples)}{'…' if n > 3 else ''}",
            data={"unusual_entries": unusual},
        )


class SharingServicesCheck(BaseCheck):
    id = "sharing_services"
    name = "Sharing Services"
    category = "security"
    category_icon = "🛡️ "

    scan_description = (
        "Checking active sharing services — each enabled service (Screen Sharing, "
        "Remote Login, File Sharing) is an open port that attackers can probe."
    )
    finding_explanation = (
        "Services like Screen Sharing, Remote Login (SSH), and File Sharing "
        "open network ports on your Mac. On public Wi-Fi, these are immediately "
        "visible to other users on the network. Only enable what you actively use."
    )
    recommendation = (
        "Disable unused services in System Settings → General → Sharing."
    )
    fix_level = "guided"
    fix_description = "Opens Sharing settings"
    fix_url = "x-apple.systempreferences:com.apple.preferences.sharing"
    fix_reversible = True
    fix_time_estimate = "~30 seconds"

    def run(self) -> CheckResult:
        active: list[str] = []

        # Remote Login (SSH)
        rc, stdout, _ = self.shell(["systemsetup", "-getremotelogin"], timeout=5)
        if rc == 0 and "on" in stdout.lower():
            active.append("Remote Login (SSH)")

        # Screen Sharing / VNC
        rc2, stdout2, _ = self.shell(
            ["launchctl", "list", "com.apple.screensharing"]
        )
        if rc2 == 0 and stdout2.strip() and "Could not find" not in stdout2:
            active.append("Screen Sharing")

        # File Sharing (AFP/SMB)
        rc3, stdout3, _ = self.shell(
            ["launchctl", "list", "com.apple.smbd"]
        )
        if rc3 == 0 and stdout3.strip() and "Could not find" not in stdout3:
            active.append("File Sharing (SMB)")

        if not active:
            return self._pass("No sharing services are active")

        n = len(active)
        return self._info(
            f"{n} sharing service{'s' if n != 1 else ''} active: {', '.join(active)}",
            data={"active_services": active},
        )


class ActivationLockCheck(BaseCheck):
    id = "activation_lock"
    name = "Activation Lock"
    category = "security"
    category_icon = "🛡️ "

    scan_description = (
        "Checking Activation Lock status — on a used/secondhand Mac, if a "
        "previous owner's Activation Lock is still on, they can remotely "
        "wipe or lock your device."
    )
    finding_explanation = (
        "Activation Lock ties a Mac to an Apple ID. If a previous owner's "
        "lock is still active and you don't have their credentials, you could "
        "lose access to the machine remotely."
    )
    recommendation = (
        "If this is a secondhand Mac, confirm the previous owner signed out of "
        "iCloud (System Settings → Apple ID → Sign Out) before handing it over."
    )
    fix_level = "instructions"
    fix_description = "Contact previous owner to remove their Activation Lock"
    fix_steps = [
        "Ask the previous owner to visit appleid.apple.com",
        "Sign in and go to Devices",
        "Select this Mac and choose 'Remove from Account'",
        "Or: erase and restore the Mac with original owner present",
    ]
    fix_reversible = False
    fix_time_estimate = "Varies"

    def run(self) -> CheckResult:
        # nvram fmm-mobileme-token-FMM — non-empty = Find My is configured
        rc, stdout, _ = self.shell(
            ["nvram", "fmm-mobileme-token-FMM"], timeout=5
        )

        if rc != 0 or not stdout.strip():
            return self._info(
                "Activation Lock: Find My token not found in NVRAM — "
                "may not be configured or may not be readable"
            )

        token = stdout.strip()
        # A very long token means Find My is set up
        if len(token) > 40:
            return self._pass(
                "Activation Lock is active (Find My is configured)",
                data={"find_my_configured": True},
            )

        return self._info(
            "Activation Lock token present but minimal — verify in System Settings → Apple ID",
            data={"token_length": len(token)},
        )


class MDMProfilesCheck(BaseCheck):
    id = "mdm_profiles"
    name = "MDM / Configuration Profiles"
    category = "security"
    category_icon = "🛡️ "

    scan_description = (
        "Checking for MDM and configuration profiles — a rogue profile can "
        "reroute DNS, inject certificates, and bypass security settings without "
        "your knowledge."
    )
    finding_explanation = (
        "Configuration profiles can change DNS servers (redirecting all traffic), "
        "install root certificates (decrypting all HTTPS), and alter security "
        "policies. Corporate devices legitimately have them, but a profile you "
        "didn't intentionally install is a serious red flag."
    )
    recommendation = (
        "Review profiles in System Settings → Privacy & Security → Profiles. "
        "Remove any you don't recognize or didn't intentionally install."
    )
    fix_level = "guided"
    fix_description = "Opens Privacy & Security → Profiles"
    fix_url = "x-apple.systempreferences:com.apple.preference.security"
    fix_reversible = True
    fix_time_estimate = "~5 minutes"

    def run(self) -> CheckResult:
        rc, stdout, stderr = self.shell(["profiles", "list"], timeout=8)

        if rc != 0:
            if "permission" in stderr.lower() or "not permitted" in stderr.lower():
                return self._info(
                    "Could not read profiles — run as admin to see all profiles"
                )
            if "There are no" in stdout or "There are no" in stderr:
                return self._pass("No configuration profiles installed")
            return self._info(f"Could not check profiles: {stderr[:80]}")

        if not stdout.strip() or "There are no" in stdout:
            return self._pass("No configuration profiles installed")

        # Count profile entries (lines with "attribute")
        profile_lines = [
            ln for ln in stdout.splitlines()
            if "_computerlevel" in ln or "profileIdentifier" in ln.lower()
        ]
        n = max(len(profile_lines), 1)  # at least 1 if there's output

        return self._warning(
            f"{n} configuration profile{'s' if n != 1 else ''} installed — verify they're intentional",
            data={"profile_count": n, "output_preview": stdout[:200]},
        )


# ── Public list for main.py ───────────────────────────────────────────────────

ALL_CHECKS: list[type[BaseCheck]] = [
    AutoLoginCheck,
    SSHAuthorizedKeysCheck,
    SSHKeyStrengthCheck,
    LaunchAgentsCheck,
    EtcHostsCheck,
    SharingServicesCheck,
    ActivationLockCheck,
    MDMProfilesCheck,
]
