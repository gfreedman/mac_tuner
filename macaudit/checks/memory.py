"""
Memory and performance checks.

Checks:
  - MemoryPressureCheck — system memory pressure level (green/yellow/red)
  - SwapUsageCheck      — swap file usage
  - TopCPUCheck         — top 5 CPU-consuming processes
  - TopMemoryCheck      — top 5 memory-consuming processes
"""

from __future__ import annotations

import re

from macaudit.checks.base import BaseCheck, CheckResult


# ── Memory pressure ───────────────────────────────────────────────────────────

class MemoryPressureCheck(BaseCheck):
    """Report macOS memory pressure level (green/yellow/red) via the memory_pressure CLI."""

    id = "memory_pressure"
    name = "Memory Pressure"
    category = "memory"
    category_icon = "🧠"

    scan_description = (
        "Checking system memory pressure — macOS grades RAM usage as Green, Yellow, or Red. "
        "Red pressure means the system is actively struggling for RAM."
    )
    finding_explanation = (
        "macOS reports memory pressure as green (healthy), yellow (managed but limited), "
        "or red (critical — swapping heavily to disk). Red pressure causes freezes, "
        "long app launch times, and system instability."
    )
    recommendation = (
        "If pressure is red or yellow: quit unused apps, especially browsers with many tabs "
        "and Electron-based apps (Slack, Discord, VS Code). Consider upgrading RAM if this "
        "is a recurring pattern."
    )

    fix_level = "instructions"
    fix_description = "Quit RAM-heavy apps and check Activity Monitor → Memory tab."
    fix_steps = [
        "Open Activity Monitor → Memory tab",
        "Sort by 'Memory' column to find top consumers",
        "Quit apps you don't need right now",
        "Check the Memory Pressure graph at the bottom for trend",
    ]
    fix_reversible = True
    fix_time_estimate = "~2 minutes"

    def run(self) -> CheckResult:
        """Run `memory_pressure` and parse the output for Normal/Warning/Critical level."""
        rc, out, _ = self.shell(["memory_pressure"])
        if rc != 0 or not out:
            return self._info("Could not read memory pressure")

        out_lower = out.lower()

        # memory_pressure output format is undocumented and varies by macOS release.
        # macOS 13–14: includes a line like "System memory pressure level: Normal"
        # macOS 15+:   may output colour words like "green"/"yellow"/"red" directly.
        # We check for the structured line first, then fall back to colour words.
        level = "unknown"
        for line in out.splitlines():
            line_l = line.lower()
            if "system memory pressure" in line_l:
                if "critical" in line_l:
                    level = "critical"
                elif "warn" in line_l:
                    level = "warn"
                elif "normal" in line_l or "ok" in line_l:
                    level = "normal"
                break

        # Fallback: look for colour words
        if level == "unknown":
            if "red" in out_lower:
                level = "critical"
            elif "yellow" in out_lower:
                level = "warn"
            elif "green" in out_lower or "normal" in out_lower:
                level = "normal"

        if level == "critical":
            return self._critical("Memory pressure is RED — system is actively swapping")
        if level == "warn":
            return self._warning("Memory pressure is YELLOW — RAM is running low")
        if level == "normal":
            return self._pass("Memory pressure is normal (Green)")
        return self._info(f"Memory pressure: {out.strip()[:80]}")


# ── Swap usage ────────────────────────────────────────────────────────────────

class SwapUsageCheck(BaseCheck):
    """Check virtual memory swap usage via sysctl vm.swapusage."""

    id = "swap_usage"
    name = "Swap Usage"
    category = "memory"
    category_icon = "💽"

    scan_description = (
        "Checking swap file usage — heavy swap means macOS is using your SSD as slow RAM, "
        "which both slows performance and adds unnecessary wear to the drive."
    )
    finding_explanation = (
        "Swap (virtual memory) is disk space used as overflow RAM. While Apple Silicon "
        "Macs handle swap better than Intel, heavy swap still degrades responsiveness. "
        "Swap > 4 GB is a sign that RAM is insufficient for your typical workload."
    )
    recommendation = (
        "If swap is high: quit memory-heavy apps and restart if comfortable. "
        "If this is consistently high, your workload may need more RAM. "
        "Check Activity Monitor → Memory for the swap number."
    )

    fix_level = "instructions"
    fix_description = "Quit heavy apps, restart if needed."
    fix_reversible = True
    fix_time_estimate = "~1 minute"

    def run(self) -> CheckResult:
        """Parse `sysctl vm.swapusage` for the 'used' value; threshold at 1/4/8 GB."""
        rc, out, _ = self.shell(["sysctl", "-n", "vm.swapusage"])
        if rc != 0 or not out:
            return self._info("Could not read swap usage")

        # Output: "total = 3072.00M  used = 1536.00M  free = 1536.00M  (encrypted)"
        m = re.search(r"used\s*=\s*([\d.]+)([MG])", out)
        if not m:
            return self._info(f"Swap: {out.strip()[:60]}")

        value = float(m.group(1))
        unit  = m.group(2)
        gb = value / 1024 if unit == "M" else value
        msg = f"{value:.1f} {unit}B used"

        if gb >= 8:
            return self._critical(msg)
        if gb >= 4:
            return self._warning(msg)
        if gb >= 1:
            return self._info(msg)
        return self._pass(f"Minimal swap ({msg})")


# ── Top CPU consumers ─────────────────────────────────────────────────────────

class TopCPUCheck(BaseCheck):
    """List the top 5 CPU-consuming processes and flag any above 90%."""

    id = "top_cpu"
    name = "Top CPU Consumers"
    category = "memory"
    category_icon = "⚡"

    scan_description = (
        "Checking which processes are consuming the most CPU — "
        "runaway processes can make your Mac hot, drain battery, and slow everything down."
    )
    finding_explanation = (
        "A process consuming >80% CPU for an extended time is usually a bug, infinite loop, "
        "or a poorly written app. This drains battery, generates heat, and steals resources "
        "from the apps you're actually using."
    )
    recommendation = (
        "If a process is unexpectedly consuming high CPU: check Activity Monitor → CPU tab. "
        "Consider quitting or force-quitting it. Check for updates for the offending app."
    )

    fix_level = "instructions"
    fix_description = "Use Activity Monitor to identify and quit runaway processes."
    fix_steps = [
        "Open Activity Monitor → CPU tab",
        "Sort by '%CPU' column",
        "Identify unexpected high-CPU processes",
        "Double-click → Quit or Force Quit if needed",
    ]
    fix_reversible = True
    fix_time_estimate = "~2 minutes"

    def run(self) -> CheckResult:
        """Run `ps -eo pid,pcpu,pmem,comm`, sort by CPU%, and warn if top process >=90%."""
        rc, out, _ = self.shell(
            ["ps", "-eo", "pid,pcpu,pmem,comm"],
            timeout=10,
        )
        if rc != 0 or not out:
            return self._info("Could not read process list")

        procs = _parse_ps(out)
        procs.sort(key=lambda p: p["cpu"], reverse=True)
        top = procs[:5]

        if not top:
            return self._info("No process data available")

        top_cpu = top[0]["cpu"]
        top_name = _short_name(top[0]["comm"])

        summary = "  ".join(
            f"{_short_name(p['comm'])} {p['cpu']:.0f}%" for p in top[:3]
        )

        if top_cpu >= 90:
            return self._warning(
                f"High CPU: {top_name} at {top_cpu:.0f}%  —  {summary}",
                data={"top_processes": top},
            )
        return self._pass(
            f"Top process: {top_name} at {top_cpu:.0f}%  —  {summary}",
            data={"top_processes": top},
        )


# ── Top memory consumers ──────────────────────────────────────────────────────

class TopMemoryCheck(BaseCheck):
    """List the top 5 memory-consuming processes for visibility into RAM usage."""

    id = "top_memory"
    name = "Top Memory Consumers"
    category = "memory"
    category_icon = "📊"

    scan_description = (
        "Checking which processes are using the most RAM — "
        "identifying memory hogs helps explain slow performance and high swap usage."
    )
    finding_explanation = (
        "Electron-based apps (Slack, Discord, VS Code, Zoom), browsers with many tabs, "
        "and some media apps routinely consume 1–3 GB each. Knowing the top consumers "
        "lets you make informed decisions about what to quit."
    )
    recommendation = (
        "Consider quitting apps you're not actively using. Browsers: close unused tabs "
        "or use tab suspension extensions. Slack/Discord: quit rather than hide when "
        "not in use."
    )

    fix_level = "instructions"
    fix_description = "Quit memory-heavy apps you don't need right now."
    fix_steps = [
        "Open Activity Monitor → Memory tab",
        "Sort by 'Memory' column",
        "Quit apps consuming large memory that you don't need",
    ]
    fix_reversible = True
    fix_time_estimate = "~2 minutes"

    def run(self) -> CheckResult:
        """Run `ps -eo pid,pcpu,pmem,comm`, sort by memory%, and report the top 3."""
        rc, out, _ = self.shell(
            ["ps", "-eo", "pid,pcpu,pmem,comm"],
            timeout=10,
        )
        if rc != 0 or not out:
            return self._info("Could not read process list")

        procs = _parse_ps(out)
        procs.sort(key=lambda p: p["mem"], reverse=True)
        top = procs[:5]

        if not top:
            return self._info("No process data available")

        summary = "  ".join(
            f"{_short_name(p['comm'])} {p['mem']:.1f}%" for p in top[:3]
        )

        return self._info(
            f"Top memory consumers: {summary}",
            data={"top_processes": top},
        )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_ps(output: str) -> list[dict]:
    """Parse `ps -eo pid,pcpu,pmem,comm` output into list of dicts."""
    procs = []
    for line in output.splitlines()[1:]:  # skip header
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        try:
            procs.append({
                "pid":  int(parts[0]),
                "cpu":  float(parts[1]),
                "mem":  float(parts[2]),
                "comm": parts[3].strip(),
            })
        except ValueError:
            continue
    return procs


def _short_name(comm: str) -> str:
    """Shorten a process command path to just the filename."""
    return comm.rsplit("/", 1)[-1][:24]


# ── Export ────────────────────────────────────────────────────────────────────

ALL_CHECKS = [
    MemoryPressureCheck,
    SwapUsageCheck,
    TopCPUCheck,
    TopMemoryCheck,
]
