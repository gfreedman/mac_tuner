"""
Security hardening checks.

Covers auto-login, SSH keys, launch agents, /etc/hosts,
sharing services, Activation Lock, MDM profiles.
"""

import plistlib
import re
from pathlib import Path

from macaudit.checks.base import BaseCheck, CheckResult

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
    """Detect if auto-login is enabled, bypassing the login screen."""

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
        """Read com.apple.loginwindow autoLoginUser via defaults; missing key means disabled."""
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
    """Check for SSH authorized keys that grant passwordless remote access."""

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
        """Query systemsetup for SSH status, then read ~/.ssh/authorized_keys.

        Counts non-comment key lines; warns if more than 5 keys are present.
        Returns pass if the file is missing or empty.
        """
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
    """Verify that local SSH keys use strong algorithms (Ed25519/ECDSA, not DSA)."""

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
        """Scan ~/.ssh/*.pub and authorized_keys for DSA keys; flag RSA as upgrade candidates."""
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
    """Scan launch agent directories for non-Apple and suspicious persistence entries."""

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
        """Glob *.plist in user and system LaunchAgent/Daemon dirs; flag non-Apple entries."""
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
    """Check /etc/hosts for non-standard entries that could redirect traffic."""

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
        """Parse /etc/hosts; flag entries with non-loopback IPs pointing to non-standard hostnames."""
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
    """Detect active sharing services (SSH, Screen Sharing, File Sharing)."""

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
        """Query systemsetup and launchctl to detect SSH, Screen Sharing, and SMB services."""
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
    """Check whether Find My / Activation Lock is configured via NVRAM token."""

    id = "activation_lock"
    name = "Activation Lock"
    category = "security"
    category_icon = "🛡️ "

    scan_description = (
        "Checking if Find My / Activation Lock is configured — on a secondhand Mac, "
        "a previous owner's lock still active means they can remotely wipe or lock it."
    )
    finding_explanation = (
        "Activation Lock ties a Mac to an Apple ID via Find My. If a previous owner's "
        "lock is still active and you don't have their credentials, you could lose access "
        "to the machine remotely. Note: on MDM-enrolled devices this NVRAM token may not "
        "accurately reflect Activation Lock status — check with your IT administrator."
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
        """Read nvram fmm-mobileme-token-FMM; a long token indicates Find My is active."""
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
        # A long token indicates Find My is configured, which implies Activation Lock
        # is likely active. We can't confirm definitively from NVRAM alone.
        if len(token) > 40:
            return self._pass(
                "Find My is configured — Activation Lock is likely active",
                data={"find_my_configured": True},
            )

        return self._info(
            "Find My token present but minimal — verify in System Settings → Apple ID",
            data={"token_length": len(token)},
        )


class MDMProfilesCheck(BaseCheck):
    """Detect installed MDM and configuration profiles that may alter security settings."""

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
        """Run profiles list; count profile entries and warn if any are installed."""
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


class SystemRootCACheck(BaseCheck):
    """Audit System keychain for unexpected root CAs or traffic-inspection certificates."""

    id = "system_root_cas"
    name = "System Root Certificates"
    category = "security"
    category_icon = "🛡️ "

    scan_description = (
        "Checking the System keychain for unexpected root certificates — "
        "a rogue root CA lets an attacker silently decrypt all HTTPS traffic."
    )
    finding_explanation = (
        "Root certificates in the System keychain are trusted to verify any website's "
        "HTTPS certificate. Enterprise tools (Zscaler, Cisco Umbrella, Palo Alto) and "
        "some malware install root CAs here to inspect or forge encrypted traffic. "
        "On a personal Mac, any unexpected root CA is a serious concern."
    )
    recommendation = (
        "Review certificates in Keychain Access → System keychain → Certificates. "
        "Remove any you don't recognize or didn't intentionally install. "
        "Or run: security find-certificate -a /Library/Keychains/System.keychain"
    )
    fix_level = "instructions"
    fix_description = "Audit system root certificates via Keychain Access"
    fix_steps = [
        "Open Keychain Access (search Spotlight)",
        "Select 'System' in the left sidebar, then click 'Certificates'",
        "Look for certificates with unknown issuers or blue trust overrides",
        "Delete certificates you don't recognize (requires admin password)",
    ]
    fix_reversible = True
    fix_time_estimate = "~10 minutes"

    # Known enterprise MITM / traffic inspection tool indicators
    _MITM_INDICATORS = [
        "zscaler", "cisco umbrella", "palo alto", "forcepoint",
        "charles proxy", "burp suite", "fiddler", "mitmproxy",
        "netskope", "iboss", "lightspeed", "smoothwall", "squid",
    ]

    def run(self) -> CheckResult:
        """Run security find-certificate on System.keychain; match cert names against known MITM indicators."""
        rc, out, _ = self.shell(
            ["security", "find-certificate", "-a", "/Library/Keychains/System.keychain"]
        )

        if rc != 0 or not out.strip():
            return self._info(
                "Could not read System keychain certificates "
                "(may require Full Disk Access)"
            )

        # Extract certificate common names from "alis" attribute lines
        # Format: "alis"<blob>="Certificate Name"
        names: list[str] = []
        for line in out.splitlines():
            line = line.strip()
            if '"alis"<blob>=' in line:
                try:
                    name = line.split('="', 1)[1].rstrip('"')
                    names.append(name)
                except IndexError:
                    continue

        if not names:
            return self._info("System keychain present (could not parse certificate names)")

        # Check for known traffic inspection / MITM tool certificates
        mitm_found: list[str] = []
        for name in names:
            name_lower = name.lower()
            for indicator in self._MITM_INDICATORS:
                if indicator in name_lower:
                    mitm_found.append(name)
                    break

        count = len(names)

        if mitm_found:
            return self._warning(
                f"Traffic inspection certificate detected: "
                f"{', '.join(mitm_found[:2])} — HTTPS traffic may be monitored",
                data={"cert_count": count, "mitm_certs": mitm_found},
            )

        # macOS ships with ~170 root CAs; flag notably higher counts for awareness
        if count > 200:
            return self._info(
                f"{count} root certificates in System keychain "
                f"(~{count - 170} beyond typical Apple defaults — review if unexpected)",
                data={"cert_count": count},
            )

        return self._pass(
            f"{count} root certificate{'s' if count != 1 else ''} in System keychain (appears normal)",
            data={"cert_count": count},
        )


class GuestAccountCheck(BaseCheck):
    """Detect if the macOS Guest account is enabled."""

    id = "guest_account"
    name = "Guest Account"
    category = "security"
    category_icon = "🛡️ "

    scan_description = (
        "Checking if the Guest account is enabled — an enabled Guest account "
        "gives anyone who picks up your Mac a login with filesystem access."
    )
    finding_explanation = (
        "The macOS Guest account lets anyone log in without a password. "
        "While Guest sessions are sandboxed, Guest users can browse the web, "
        "use apps, and access iCloud-enabled services. "
        "It is also a common first step in local privilege-escalation research."
    )
    recommendation = (
        "Disable the Guest account in System Settings → General → Users & Groups → Guest User."
    )
    fix_level = "guided"
    fix_description = "Opens Users & Groups to disable the Guest account"
    fix_url = "x-apple.systempreferences:com.apple.preferences.users"
    fix_reversible = True
    fix_time_estimate = "~30 seconds"

    def run(self) -> CheckResult:
        """Read GuestEnabled from com.apple.loginwindow via defaults."""
        rc, out, _ = self.shell(
            ["defaults", "read", "/Library/Preferences/com.apple.loginwindow", "GuestEnabled"]
        )
        if rc == 0 and out.strip() == "1":
            return self._warning(
                "Guest account is enabled — anyone can log in without a password",
                data={"guest_enabled": True},
            )
        return self._pass("Guest account is disabled")


class LoginHooksCheck(BaseCheck):
    """Detect legacy login/logout hooks that run scripts as root at session events."""

    id = "login_hooks"
    name = "Login/Logout Hooks"
    category = "security"
    category_icon = "🛡️ "

    scan_description = (
        "Checking for login and logout hooks — these run arbitrary scripts as root "
        "at every login and logout event, a technique used by malware to persist."
    )
    finding_explanation = (
        "Login hooks run a script as root every time any user logs in. "
        "Logout hooks run at logout. They are a legacy persistence mechanism "
        "rarely needed by legitimate software today — their presence on a "
        "personal Mac is highly suspicious."
    )
    recommendation = (
        "If you did not set these hooks intentionally, remove them: "
        "sudo defaults delete com.apple.loginwindow LoginHook"
    )
    fix_level = "instructions"
    fix_description = "Remove unrecognised login/logout hooks"
    fix_steps = [
        "Check current hooks: defaults read com.apple.loginwindow LoginHook",
        "To remove login hook:  sudo defaults delete com.apple.loginwindow LoginHook",
        "To remove logout hook: sudo defaults delete com.apple.loginwindow LogoutHook",
        "Investigate the script path before removing to understand what it was doing",
    ]
    fix_reversible = True
    fix_time_estimate = "~5 minutes"

    def run(self) -> CheckResult:
        """Read LoginHook and LogoutHook from com.apple.loginwindow via defaults."""
        found: list[str] = []
        for key in ("LoginHook", "LogoutHook"):
            rc, out, _ = self.shell(
                ["defaults", "read", "com.apple.loginwindow", key]
            )
            if rc == 0 and out.strip():
                found.append(f"{key}: {out.strip()[:60]}")

        if found:
            return self._warning(
                f"Login/logout hook{'s' if len(found) > 1 else ''} detected: "
                f"{'; '.join(found)}",
                data={"hooks": found},
            )
        return self._pass("No login or logout hooks configured")


class SSHConfigCheck(BaseCheck):
    """Check sshd_config for risky settings like password auth and root login."""

    id = "ssh_config"
    name = "SSH Server Config"
    category = "security"
    category_icon = "🛡️ "

    scan_description = (
        "Checking sshd_config for risky settings — password authentication and "
        "root login over SSH are among the most exploited server misconfigurations."
    )
    finding_explanation = (
        "SSH with password authentication enabled is constantly brute-forced on the "
        "internet. PermitRootLogin exposes the most privileged account. "
        "If Remote Login is enabled, these settings directly affect your Mac's "
        "exposure — key-only auth is the strong default."
    )
    recommendation = (
        "In /etc/ssh/sshd_config: set 'PasswordAuthentication no' and "
        "'PermitRootLogin no'. Restart SSH: sudo launchctl kickstart -k system/com.openssh.sshd"
    )
    fix_level = "instructions"
    fix_description = "Harden sshd_config to disable password auth and root login"
    fix_steps = [
        "Open: sudo nano /etc/ssh/sshd_config",
        "Set: PasswordAuthentication no",
        "Set: PermitRootLogin no",
        "Save and restart SSH: sudo launchctl kickstart -k system/com.openssh.sshd",
    ]
    fix_reversible = True
    fix_time_estimate = "~5 minutes"

    def run(self) -> CheckResult:
        """Parse /etc/ssh/sshd_config for PasswordAuthentication yes and PermitRootLogin; skip if SSH is off."""
        config_path = Path("/etc/ssh/sshd_config")
        if not config_path.exists():
            return self._skip("sshd_config not found")

        # First check if SSH server is actually running — skip if not
        rc_ssh, ssh_out, _ = self.shell(["systemsetup", "-getremotelogin"], timeout=5)
        if rc_ssh == 0 and "off" in ssh_out.lower():
            return self._pass("Remote Login (SSH) is off — sshd_config not applicable")

        try:
            content = config_path.read_text(errors="replace")
        except PermissionError:
            return self._info(
                "Could not read /etc/ssh/sshd_config — run macaudit with sudo to check"
            )

        issues: list[str] = []
        for line in content.splitlines():
            stripped = line.strip().lower()
            if stripped.startswith("#"):
                continue
            if stripped.startswith("passwordauthentication") and "yes" in stripped:
                issues.append("PasswordAuthentication yes (enables password brute-force)")
            if stripped.startswith("permitrootlogin") and "no" not in stripped and "prohibit" not in stripped:
                issues.append("PermitRootLogin is not 'no' (root login permitted)")

        if issues:
            return self._warning(
                f"Risky SSH config: {'; '.join(issues)}",
                data={"issues": issues},
            )
        return self._pass("SSH server config looks secure")


class SystemExtensionsCheck(BaseCheck):
    """List active system extensions and flag for review."""

    id = "system_extensions"
    name = "System Extensions"
    category = "security"
    category_icon = "🛡️ "

    scan_description = (
        "Checking installed system extensions — these run as kernel-adjacent "
        "privileged code. Unexpected extensions can be left by uninstalled apps "
        "or indicate compromise."
    )
    finding_explanation = (
        "System extensions (DriverKit, Network Extensions, Endpoint Security) "
        "run at the highest privilege level below the kernel. "
        "Legitimate apps like antivirus, VPNs, and virtualization tools use them. "
        "Extensions that remain after app uninstall continue running indefinitely."
    )
    recommendation = (
        "Review in System Settings → Privacy & Security → Security → System Extensions. "
        "Or run: systemextensionsctl list"
    )
    fix_level = "guided"
    fix_description = "Review system extensions in System Settings → Privacy & Security"
    fix_url = "x-apple.systempreferences:com.apple.preference.security"
    fix_reversible = True
    fix_time_estimate = "~5 minutes"

    def run(self) -> CheckResult:
        """Run systemextensionsctl list; count active/enabled extensions."""
        rc, out, _ = self.shell(["systemextensionsctl", "list"], timeout=10)
        if rc != 0 or not out.strip():
            return self._info("Could not list system extensions")

        extensions: list[str] = []
        for line in out.splitlines():
            # Active extension lines have [activated enabled] or similar
            if "[" in line and ("enabled" in line.lower() or "activated" in line.lower()):
                parts = line.strip().split()
                if len(parts) >= 2:
                    extensions.append(line.strip()[:80])

        n = len(extensions)
        if n == 0:
            return self._pass("No active system extensions found")
        return self._info(
            f"{n} system extension{'s' if n != 1 else ''} active — verify all are from apps you installed",
            data={"extensions": extensions, "count": n},
        )


class CronJobsCheck(BaseCheck):
    """Detect user cron jobs that could indicate unwanted persistence."""

    id = "cron_jobs"
    name = "Cron Jobs"
    category = "security"
    category_icon = "🛡️ "

    scan_description = (
        "Checking for cron jobs — scheduled tasks are a classic persistence "
        "mechanism used by malware to survive reboots and re-infect after cleanup."
    )
    finding_explanation = (
        "Cron jobs execute commands on a schedule. Legitimate developers sometimes "
        "use them, but on a typical Mac user's system they're rare. "
        "Malware uses cron to periodically re-download payloads or exfiltrate data. "
        "Any unexpected cron entry warrants close inspection."
    )
    recommendation = (
        "Review your crontab with: crontab -l\n"
        "Remove unexpected entries with: crontab -e\n"
        "Also check /etc/cron.d/ and /var/at/tabs/ for system-level crons."
    )
    fix_level = "instructions"
    fix_description = "Review and remove unexpected cron entries"
    fix_steps = [
        "List current crons: crontab -l",
        "Edit crontab: crontab -e  (remove suspicious lines and save)",
        "Check system crons: ls /etc/cron.d/ (if it exists)",
    ]
    fix_reversible = True
    fix_time_estimate = "~5 minutes"

    def run(self) -> CheckResult:
        """Run crontab -l and count non-comment job lines."""
        rc, out, _ = self.shell(["crontab", "-l"])
        if rc != 0 or not out.strip():
            return self._pass("No cron jobs configured for this user")

        jobs = [
            ln.strip()
            for ln in out.splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]
        if not jobs:
            return self._pass("No active cron jobs configured")

        n = len(jobs)
        return self._warning(
            f"{n} cron job{'s' if n != 1 else ''} found — verify each is intentional",
            data={"jobs": jobs, "count": n},
        )


class XProtectCheck(BaseCheck):
    """Check that XProtect malware signatures are recent (updated within 30 days)."""

    id = "xprotect_freshness"
    name = "XProtect Signatures"
    category = "security"
    category_icon = "🛡️ "

    scan_description = (
        "Checking XProtect signature freshness — stale signatures leave your Mac "
        "unprotected against malware families Apple has already detected and catalogued."
    )
    finding_explanation = (
        "XProtect is macOS's built-in malware scanner. It relies on a signature "
        "database that Apple updates silently in the background. If auto-updates "
        "are disabled or a proxy blocks downloads, signatures become stale and "
        "won't detect newer malware variants."
    )
    recommendation = (
        "Ensure 'Install System Data Files and Security Updates' is enabled in "
        "System Settings → General → Software Update → Automatic Updates."
    )
    fix_level = "guided"
    fix_description = "Enable automatic XProtect updates via Software Update settings"
    fix_url = "x-apple.systempreferences:com.apple.preferences.softwareupdate"
    fix_reversible = True
    fix_time_estimate = "~30 seconds"

    def run(self) -> CheckResult:
        """Query pkgutil for XProtect package install date; warn if older than 30 days."""
        import time as _time

        rc, out, _ = self.shell(
            ["pkgutil", "--pkg-info", "com.apple.pkg.XProtectPlistConfigData"],
            timeout=5,
        )

        if rc != 0 or not out.strip():
            # Fallback: check the XProtect bundle directly
            bundle = Path(
                "/Library/Apple/System/Library/CoreServices/XProtect.bundle"
            )
            if bundle.exists():
                return self._info("XProtect is present (version unreadable via pkgutil)")
            return self._info("XProtect bundle not found — may be part of System volume")

        version = ""
        install_time = 0
        for line in out.splitlines():
            if line.startswith("version:"):
                version = line.split(":", 1)[1].strip()
            elif line.startswith("install-time:"):
                try:
                    install_time = int(line.split(":", 1)[1].strip())
                except ValueError:
                    pass

        if install_time:
            age_days = int((_time.time() - install_time) / 86400)
            age_str = f"{age_days} day{'s' if age_days != 1 else ''} ago"
            ver_str = f" (v{version})" if version else ""

            if age_days > 30:
                return self._warning(
                    f"XProtect signatures are {age_days} days old{ver_str} — "
                    "signatures may be stale",
                    data={"version": version, "age_days": age_days},
                )
            return self._pass(
                f"XProtect signatures updated {age_str}{ver_str}",
                data={"version": version, "age_days": age_days},
            )

        if version:
            return self._info(
                f"XProtect present (v{version} — install date unavailable)",
                data={"version": version},
            )
        return self._info("XProtect present (details unavailable)")


# ── Public list for main.py ───────────────────────────────────────────────────

ALL_CHECKS: list[type[BaseCheck]] = [
    AutoLoginCheck,
    GuestAccountCheck,
    SSHAuthorizedKeysCheck,
    SSHKeyStrengthCheck,
    SSHConfigCheck,
    LaunchAgentsCheck,
    LoginHooksCheck,
    CronJobsCheck,
    EtcHostsCheck,
    SharingServicesCheck,
    ActivationLockCheck,
    MDMProfilesCheck,
    SystemRootCACheck,
    SystemExtensionsCheck,
    XProtectCheck,
]
