"""
Network and sharing checks.

Checks:
  - AirDropCheck       — AirDrop discoverability (Everyone = risky on public Wi-Fi)
  - RemoteLoginCheck   — SSH remote login enabled
  - ScreenSharingCheck — Screen Sharing / Remote Desktop enabled
  - FileSharingCheck   — File Sharing (SMB/AFP) enabled
  - DNSCheck           — Custom or suspicious DNS servers
  - ProxyCheck         — HTTP/HTTPS proxy configured
  - SavedWifiCheck     — Number of saved Wi-Fi networks
"""

from __future__ import annotations

import re
import shutil

from mactuner.checks.base import BaseCheck, CheckResult


# ── AirDrop ───────────────────────────────────────────────────────────────────

class AirDropCheck(BaseCheck):
    id = "airdrop_visibility"
    name = "AirDrop Visibility"
    category = "network"
    category_icon = "📡"

    scan_description = (
        "Checking AirDrop discoverability setting — "
        "being visible to Everyone on a public network lets strangers send you files."
    )
    finding_explanation = (
        "AirDrop set to 'Everyone' means any nearby Apple device can see your Mac and "
        "attempt to send files. On public Wi-Fi (cafés, airports) this is a privacy risk. "
        "'Contacts Only' limits this to people in your contacts."
    )
    recommendation = (
        "Change AirDrop to 'Contacts Only' or 'No One' in Control Center → AirDrop. "
        "You can always temporarily enable 'Everyone' when you need it."
    )

    fix_level = "guided"
    fix_description = "Change AirDrop to Contacts Only in Control Center."
    fix_url = "x-apple.systempreferences:com.apple.preference.sharing"
    fix_reversible = True
    fix_time_estimate = "~30 seconds"

    def run(self) -> CheckResult:
        rc, out, _ = self.shell(
            ["defaults", "read", "com.apple.sharingd", "DiscoverableMode"]
        )
        if rc != 0:
            return self._info("AirDrop discoverability setting not found (may be Contacts Only)")

        mode = out.strip()
        if mode == "Everyone":
            return self._warning(
                "AirDrop visible to Everyone — change to Contacts Only"
            )
        if mode in ("Contacts Only",):
            return self._pass("AirDrop: Contacts Only")
        if mode == "Off":
            return self._pass("AirDrop: Off")
        return self._info(f"AirDrop mode: {mode}")


# ── Remote Login (SSH) ────────────────────────────────────────────────────────

class RemoteLoginCheck(BaseCheck):
    id = "remote_login"
    name = "Remote Login (SSH)"
    category = "network"
    category_icon = "🔑"

    scan_description = (
        "Checking if SSH remote login is enabled — "
        "an open SSH server on public Wi-Fi is a significant attack surface."
    )
    finding_explanation = (
        "Remote Login enables SSH access to your Mac from any device on the network. "
        "If enabled on a public or shared network, it exposes your Mac to login attempts "
        "from anyone on that network. Disable it when not actively in use."
    )
    recommendation = (
        "Disable Remote Login in System Settings → General → Sharing → Remote Login "
        "when not needed. Only enable it temporarily when you actually need SSH access."
    )

    fix_level = "guided"
    fix_description = "Disable Remote Login in System Settings → Sharing."
    fix_url = "x-apple.systempreferences:com.apple.preference.sharing"
    fix_reversible = True
    fix_time_estimate = "~30 seconds"

    def run(self) -> CheckResult:
        rc, out, _ = self.shell(["systemsetup", "-getremotelogin"])
        if rc != 0:
            # systemsetup may require sudo — try launchctl
            rc2, out2, _ = self.shell(
                ["launchctl", "list", "com.openssh.sshd"]
            )
            if rc2 == 0:
                return self._warning("Remote Login (SSH) appears to be enabled")
            return self._pass("Remote Login (SSH) is Off")

        out_lower = out.lower()
        if "on" in out_lower:
            return self._warning(
                "Remote Login is On — SSH access is open"
            )
        return self._pass("Remote Login (SSH) is Off")


# ── Screen Sharing ────────────────────────────────────────────────────────────

class ScreenSharingCheck(BaseCheck):
    id = "screen_sharing"
    name = "Screen Sharing"
    category = "network"
    category_icon = "🖥️ "

    scan_description = (
        "Checking if Screen Sharing is enabled — "
        "an open screen sharing session lets others see and control your display remotely."
    )
    finding_explanation = (
        "Screen Sharing (VNC) allows remote control of your Mac. If left on and accessible "
        "from a network, it's a serious privacy risk. Always disable when not actively in use."
    )
    recommendation = (
        "Disable Screen Sharing in System Settings → General → Sharing. "
        "Enable only when you need it, then disable immediately after."
    )

    fix_level = "guided"
    fix_description = "Disable Screen Sharing in System Settings → Sharing."
    fix_url = "x-apple.systempreferences:com.apple.preference.sharing"
    fix_reversible = True
    fix_time_estimate = "~30 seconds"

    def run(self) -> CheckResult:
        rc, out, _ = self.shell(
            ["launchctl", "list", "com.apple.screensharing"]
        )
        if rc == 0:
            return self._warning("Screen Sharing is enabled")

        # Also check via sharing command
        rc2, out2, _ = self.shell(["sharing", "-l"])
        if rc2 == 0 and "screen" in out2.lower():
            return self._warning("Screen Sharing appears to be enabled")

        return self._pass("Screen Sharing is Off")


# ── File Sharing ──────────────────────────────────────────────────────────────

class FileSharingCheck(BaseCheck):
    id = "file_sharing"
    name = "File Sharing"
    category = "network"
    category_icon = "📂"

    scan_description = (
        "Checking if File Sharing (SMB/AFP) is enabled — "
        "active file sharing broadcasts your Mac's presence on the network."
    )
    finding_explanation = (
        "File Sharing makes shared folders accessible to other devices on the network. "
        "On public Wi-Fi, this broadcasts that your Mac has shared folders and anyone "
        "on the network can attempt to access them."
    )
    recommendation = (
        "Disable File Sharing in System Settings → General → Sharing when not in use. "
        "Enable only temporarily when transferring files."
    )

    fix_level = "guided"
    fix_description = "Disable File Sharing in System Settings → Sharing."
    fix_url = "x-apple.systempreferences:com.apple.preference.sharing"
    fix_reversible = True
    fix_time_estimate = "~30 seconds"

    def run(self) -> CheckResult:
        # Check if smbd is running
        rc, out, _ = self.shell(["launchctl", "list", "com.apple.smbd"])
        if rc == 0:
            return self._warning("File Sharing (SMB) is enabled")

        rc2, out2, _ = self.shell(["launchctl", "list", "com.apple.AppleFileServer"])
        if rc2 == 0:
            return self._warning("File Sharing (AFP) is enabled")

        return self._pass("File Sharing is Off")


# ── DNS check ─────────────────────────────────────────────────────────────────

_KNOWN_GOOD_DNS = {
    # Apple
    "17.0.0.0/8",
    # Google
    "8.8.8.8", "8.8.4.4",
    # Cloudflare
    "1.1.1.1", "1.0.0.1",
    # OpenDNS
    "208.67.222.222", "208.67.220.220",
    # Quad9
    "9.9.9.9", "149.112.112.112",
    # Common ISP / DHCP ranges (192.168.x.x, 10.x.x.x, 172.16–31.x.x)
}

_PRIVATE_PREFIXES = ("192.168.", "10.", "172.16.", "172.17.", "172.18.",
                     "172.19.", "172.2", "172.30.", "172.31.", "127.")


class DNSCheck(BaseCheck):
    id = "dns_settings"
    name = "DNS Configuration"
    category = "network"
    category_icon = "🌐"

    scan_description = (
        "Checking DNS server configuration — "
        "modified DNS settings can silently redirect you to fake websites even "
        "when you type the right address."
    )
    finding_explanation = (
        "DNS translates website names (google.com) to IP addresses. If DNS is set to "
        "an unexpected server, every website lookup could be intercepted and redirected. "
        "This is a common attack from malicious software and rogue Wi-Fi hotspots."
    )
    recommendation = (
        "If you see unfamiliar DNS servers, check System Settings → Network → your "
        "connection → DNS. Reset to automatic or set known-safe servers (1.1.1.1, 8.8.8.8). "
        "Run 'scutil --dns' to see full configuration."
    )

    fix_level = "guided"
    fix_description = "Review DNS servers in System Settings → Network."
    fix_url = "x-apple.systempreferences:com.apple.Network-Settings.extension"
    fix_reversible = True
    fix_time_estimate = "~2 minutes"

    def run(self) -> CheckResult:
        rc, out, _ = self.shell(["scutil", "--dns"])
        if rc != 0 or not out:
            return self._info("Could not read DNS configuration")

        servers = re.findall(r"nameserver\[[\d]+\]\s*:\s*([\d.a-f:]+)", out)
        if not servers:
            return self._info("No DNS servers found in scutil output")

        # De-duplicate
        unique = list(dict.fromkeys(servers))

        # IPv6 addresses are commonly assigned by ISP routers — only flag IPv4 as suspicious
        def _is_suspicious_ipv4(addr: str) -> bool:
            if ":" in addr:  # IPv6 — skip; ISP router DNS is normal
                return False
            return (
                not any(addr.startswith(p) for p in _PRIVATE_PREFIXES)
                and addr not in _KNOWN_GOOD_DNS
            )

        suspicious = [s for s in unique if _is_suspicious_ipv4(s)]

        if suspicious:
            return self._warning(
                f"Custom IPv4 DNS: {', '.join(suspicious[:3])} — verify these are intentional",
                data={"dns_servers": unique, "suspicious": suspicious},
            )
        return self._info(
            f"DNS: {', '.join(unique[:3])}",
            data={"dns_servers": unique},
        )


# ── Proxy check ───────────────────────────────────────────────────────────────

class ProxyCheck(BaseCheck):
    id = "proxy_settings"
    name = "HTTP/HTTPS Proxy"
    category = "network"
    category_icon = "🔀"

    scan_description = (
        "Checking for HTTP/HTTPS proxy configuration — "
        "an unexpected proxy routes all your web traffic through another server."
    )
    finding_explanation = (
        "A proxy server intercepts all your web traffic before it reaches its destination. "
        "If a proxy is configured that you didn't set, it could be logging or modifying "
        "your traffic. This can be set by malware or a misconfigured MDM profile."
    )
    recommendation = (
        "If you see an unexpected proxy: check System Settings → Network → your connection "
        "→ Proxies. Remove any proxies you did not configure. Also check for MDM profiles "
        "in System Settings → Privacy & Security → Profiles."
    )

    fix_level = "guided"
    fix_description = "Review proxy settings in System Settings → Network."
    fix_url = "x-apple.systempreferences:com.apple.Network-Settings.extension"
    fix_reversible = True
    fix_time_estimate = "~2 minutes"

    def run(self) -> CheckResult:
        # Detect active network interface
        rc, route_out, _ = self.shell(["route", "get", "default"])
        iface = "Wi-Fi"  # Default fallback
        if rc == 0:
            for line in route_out.splitlines():
                if "interface:" in line:
                    raw = line.split(":")[-1].strip()
                    # Map bsd interface name to networksetup name
                    if raw.startswith("en0"):
                        iface = "Wi-Fi"
                    elif raw.startswith("en"):
                        iface = "Ethernet"
                    break

        rc, out, _ = self.shell(
            ["networksetup", "-getwebproxy", iface]
        )
        https_rc, https_out, _ = self.shell(
            ["networksetup", "-getsecurewebproxy", iface]
        )

        proxies_found = []
        for label, text in [("HTTP", out), ("HTTPS", https_out)]:
            if not text:
                continue
            enabled = False
            server = ""
            port = ""
            for line in text.splitlines():
                if line.startswith("Enabled:") and "Yes" in line:
                    enabled = True
                if line.startswith("Server:"):
                    server = line.split(":", 1)[-1].strip()
                if line.startswith("Port:"):
                    port = line.split(":", 1)[-1].strip()
            if enabled and server:
                proxies_found.append(f"{label}: {server}:{port}")

        if proxies_found:
            return self._warning(
                f"Proxy active — {'; '.join(proxies_found)}",
                data={"proxies": proxies_found},
            )
        return self._pass("No HTTP/HTTPS proxy configured")


# ── Saved Wi-Fi networks ──────────────────────────────────────────────────────

class SavedWifiCheck(BaseCheck):
    id = "saved_wifi"
    name = "Saved Wi-Fi Networks"
    category = "network"
    category_icon = "📶"

    scan_description = (
        "Counting saved Wi-Fi networks — "
        "too many saved networks causes auto-join to rogue hotspots with common names."
    )
    finding_explanation = (
        "macOS auto-joins the first known network it finds. Attackers create hotspots named "
        "'Starbucks', 'Airport Wi-Fi', or 'xfinitywifi' knowing many devices will "
        "auto-connect. Pruning old networks reduces this exposure."
    )
    recommendation = (
        "Remove old Wi-Fi networks you no longer use in System Settings → Wi-Fi → "
        "click the info (ⓘ) button next to a network → Forget. Keep only current locations."
    )

    fix_level = "guided"
    fix_description = "Review and remove old Wi-Fi networks in System Settings → Wi-Fi."
    fix_url = "x-apple.systempreferences:com.apple.wifi-settings-extension"
    fix_reversible = True
    fix_time_estimate = "~5 minutes"

    def run(self) -> CheckResult:
        # Try en0 first, then en1
        for iface in ("en0", "en1"):
            rc, out, _ = self.shell(
                ["networksetup", "-listpreferredwirelessnetworks", iface]
            )
            if rc == 0 and out and "Error" not in out:
                break
        else:
            return self._info("Could not list saved Wi-Fi networks")

        lines = [
            l.strip() for l in out.splitlines()
            if l.strip() and "Preferred networks" not in l
        ]
        count = len(lines)

        if count == 0:
            return self._info("No saved Wi-Fi networks found")
        if count > 30:
            return self._warning(
                f"{count} saved Wi-Fi networks — prune old ones to reduce auto-join risk",
                data={"count": count},
            )
        if count > 20:
            return self._warning(
                f"{count} saved networks — consider removing old ones",
                data={"count": count},
            )
        return self._info(
            f"{count} saved Wi-Fi network{'s' if count != 1 else ''}",
            data={"count": count},
        )


# ── Export ────────────────────────────────────────────────────────────────────

ALL_CHECKS = [
    AirDropCheck,
    RemoteLoginCheck,
    ScreenSharingCheck,
    FileSharingCheck,
    DNSCheck,
    ProxyCheck,
    SavedWifiCheck,
]
