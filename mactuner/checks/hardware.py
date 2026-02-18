"""
Hardware health checks.

Checks:
  - BatteryCheck         — cycle count, condition, max capacity
  - SMARTStatusCheck     — disk SMART health
  - KernelPanicCheck     — recent kernel panics in DiagnosticReports
  - ThermalCheck         — CPU thermal throttling state
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta
from functools import lru_cache

from mactuner.checks.base import BaseCheck, CheckResult
from mactuner.system_info import IS_APPLE_SILICON


# ── Shared data fetcher ────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _get_power_data() -> str:
    """Run system_profiler SPPowerDataType once and cache."""
    import subprocess
    try:
        r = subprocess.run(
            ["system_profiler", "SPPowerDataType"],
            capture_output=True, text=True, timeout=15, check=False,
        )
        return r.stdout
    except Exception:
        return ""


# ── Battery ───────────────────────────────────────────────────────────────────

class BatteryCheck(BaseCheck):
    id = "battery_health"
    name = "Battery Health"
    category = "hardware"
    category_icon = "🔋"

    scan_description = (
        "Checking battery cycle count and condition — "
        "a degraded battery causes unexpected shutdowns, throttling, and poor performance."
    )
    finding_explanation = (
        "Mac batteries are rated for ~1000 charge cycles. Beyond that, maximum capacity "
        "degrades significantly. A battery in 'Service Recommended' state may cause random "
        "shutdowns and CPU throttling to protect the system."
    )
    recommendation = (
        "If condition is 'Service Recommended', consider battery replacement through "
        "Apple or an authorised service provider. Check battery stats in "
        "System Settings → Battery."
    )

    fix_level = "instructions"
    fix_description = "Open System Settings → Battery to see detailed health info."
    fix_steps = [
        "Open System Settings → Battery",
        "Click 'Battery Health…' for full details",
        "If 'Service Recommended', schedule a Genius Bar appointment",
    ]
    fix_reversible = True
    fix_time_estimate = "N/A"

    def run(self) -> CheckResult:
        raw = _get_power_data()
        if not raw:
            return self._info("Could not read power data")

        # Check if this is a desktop Mac (no battery section)
        if "Battery Information" not in raw and "Charge Information" not in raw:
            return self._info("No battery detected (desktop Mac)")

        condition = ""
        cycle_count = None
        max_capacity = None

        for line in raw.splitlines():
            line = line.strip()
            if "Condition:" in line:
                condition = line.split(":", 1)[-1].strip()
            elif "Cycle Count:" in line:
                m = re.search(r"\d+", line)
                if m:
                    cycle_count = int(m.group())
            elif "Maximum Capacity:" in line:
                m = re.search(r"(\d+)%?", line)
                if m:
                    max_capacity = int(m.group(1))

        parts = []
        if cycle_count is not None:
            parts.append(f"{cycle_count} cycles")
        if max_capacity is not None:
            parts.append(f"{max_capacity}% capacity")
        if condition:
            parts.append(condition)

        msg = "  ·  ".join(parts) if parts else "Battery info available"

        if condition.lower() in ("service recommended", "replace now", "replace soon"):
            return self._critical(msg)
        if cycle_count and cycle_count >= 900:
            return self._warning(msg)
        if max_capacity is not None and max_capacity < 80:
            return self._warning(msg)
        return self._info(msg)


# ── SMART status ──────────────────────────────────────────────────────────────

class SMARTStatusCheck(BaseCheck):
    id = "smart_status"
    name = "Disk SMART Status"
    category = "hardware"
    category_icon = "💾"

    scan_description = (
        "Checking disk SMART (Self-Monitoring, Analysis and Reporting Technology) status — "
        "early warning system for drive failure before you lose data."
    )
    finding_explanation = (
        "SMART monitors disk health indicators like reallocated sectors and read errors. "
        "A 'Failing' or 'Not Supported' status on a primary drive is a serious early-warning "
        "sign that the disk may be about to fail."
    )
    recommendation = (
        "Back up immediately if status is Failing. Replace the drive soon. "
        "Consider running Apple Diagnostics (hold D at startup) for additional hardware tests."
    )

    fix_level = "instructions"
    fix_description = "Immediate backup recommended if status is Failing."
    fix_steps = [
        "Back up with Time Machine or another backup solution immediately",
        "Run Apple Diagnostics: restart and hold D key",
        "Schedule a Genius Bar appointment for drive replacement",
    ]
    fix_reversible = False
    fix_time_estimate = "N/A"

    def run(self) -> CheckResult:
        # Use "/" to resolve the boot volume dynamically — avoids hardcoding
        # disk0 which breaks on external boot drives and Fusion Drive setups.
        rc, out, _ = self.shell(["diskutil", "info", "/"])
        if rc != 0 or not out:
            return self._info("Could not read disk SMART status")

        smart_status = ""
        for line in out.splitlines():
            if "SMART Status" in line:
                smart_status = line.split(":", 1)[-1].strip()
                break

        if not smart_status:
            return self._info("SMART status not reported for this disk")

        if smart_status.lower() in ("verified", "not applicable"):
            return self._pass(f"SMART: {smart_status}")
        if "fail" in smart_status.lower():
            return self._critical(f"SMART: {smart_status} — back up immediately")
        # "Not Supported" is common for external drives / Apple SSDs
        return self._info(f"SMART: {smart_status}")


# ── Kernel panics ─────────────────────────────────────────────────────────────

class KernelPanicCheck(BaseCheck):
    id = "kernel_panics"
    name = "Kernel Panics (7 days)"
    category = "hardware"
    category_icon = "💥"

    scan_description = (
        "Checking for kernel panics in the last 7 days — "
        "repeated panics indicate hardware or driver problems that need investigation."
    )
    finding_explanation = (
        "A kernel panic is a macOS crash where the OS detects an unrecoverable error. "
        "One occasional panic may be normal. Multiple panics in a week indicate a pattern "
        "that could be defective RAM, a bad GPU, a problematic kernel extension, or a "
        "failing drive."
    )
    recommendation = (
        "For repeated panics: run Apple Diagnostics (restart + hold D), check for third-party "
        "kernel extensions with 'kextstat', and consider a RAM test. Report to Apple Support "
        "if the problem persists."
    )

    fix_level = "instructions"
    fix_description = "Run Apple Diagnostics and check logs for panic cause."
    fix_steps = [
        "Restart Mac, hold D to boot into Apple Diagnostics",
        "Check panic report: Console.app → Crash Reports → Kernel",
        "If third-party kexts listed, update or remove them",
    ]
    fix_reversible = True
    fix_time_estimate = "~20 minutes"

    _PANIC_DIR = "/Library/Logs/DiagnosticReports"

    def run(self) -> CheckResult:
        try:
            cutoff = datetime.now() - timedelta(days=7)
            panic_files = []

            if not os.path.isdir(self._PANIC_DIR):
                return self._info("Diagnostic reports directory not found")

            for fname in os.listdir(self._PANIC_DIR):
                if "Panic" not in fname and "panic" not in fname:
                    continue
                fpath = os.path.join(self._PANIC_DIR, fname)
                try:
                    mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                    if mtime >= cutoff:
                        panic_files.append(fname)
                except OSError:
                    continue

            count = len(panic_files)
            if count == 0:
                return self._pass("No kernel panics in the last 7 days")
            if count == 1:
                return self._warning(f"1 kernel panic in the last 7 days")
            if count >= 3:
                return self._critical(f"{count} kernel panics in the last 7 days")
            return self._warning(f"{count} kernel panics in the last 7 days")

        except PermissionError:
            return self._info(
                "Cannot read diagnostic reports — Full Disk Access needed"
            )
        except Exception as e:
            return self._error(f"Could not check kernel panics: {e}")


# ── Thermal throttling ────────────────────────────────────────────────────────

class ThermalCheck(BaseCheck):
    id = "thermal_state"
    name = "CPU Thermal State"
    category = "hardware"
    category_icon = "🌡️ "

    scan_description = (
        "Checking CPU thermal state — excessive heat causes macOS to throttle CPU speed, "
        "making everything feel sluggish even when performance should be good."
    )
    finding_explanation = (
        "When a Mac runs too hot, macOS reduces CPU and GPU clock speeds to prevent damage. "
        "This 'thermal throttling' can reduce performance by 30–50%. Common causes: "
        "blocked vents, demanding workloads, or a failing fan."
    )
    recommendation = (
        "If throttling: ensure Mac vents are unobstructed, clean fans if accessible, "
        "quit demanding background apps. Apple Silicon Macs: check Activity Monitor → "
        "Energy for highest consumers."
    )

    fix_level = "instructions"
    fix_description = "Check Activity Monitor for CPU-intensive processes causing heat."
    fix_steps = [
        "Open Activity Monitor → Energy tab",
        "Identify high-impact processes and quit unnecessary ones",
        "Ensure Mac is on a hard flat surface with vents unobstructed",
        "For Intel Macs: consider SMC reset if problem persists",
    ]
    fix_reversible = True
    fix_time_estimate = "~5 minutes"

    def run(self) -> CheckResult:
        # pmset -g thermlog shows current thermal state
        rc, out, _ = self.shell(["pmset", "-g", "thermlog"])
        if rc != 0 or not out:
            return self._info("Could not read thermal state")

        # Look for CPU_Speed_Limit or Thermal_Level
        throttled = False
        for line in out.splitlines():
            line_lower = line.lower()
            if "cpu_speed_limit" in line_lower:
                m = re.search(r"=\s*(\d+)", line)
                if m and int(m.group(1)) < 100:
                    throttled = True
                    break
            # "No Thermal Pressure" is the good state
            if "no thermal pressure" in line_lower:
                return self._pass("No thermal throttling detected")
            if "thermal pressure" in line_lower and "no" not in line_lower:
                throttled = True

        # Try powermetrics as a fallback (may need sudo — skip if unavailable)
        if not throttled:
            # Check sysctl for thermal level on Apple Silicon
            rc2, out2, _ = self.shell(
                ["sysctl", "-n", "machdep.xcpm.cpu_thermal_level"]
            )
            if rc2 == 0 and out2.strip():
                try:
                    level = int(out2.strip())
                    if level > 0:
                        throttled = True
                except ValueError:
                    pass

        if throttled:
            return self._warning(
                "CPU is being thermally throttled — performance is reduced"
            )
        return self._pass("No thermal throttling detected")


# ── Export ────────────────────────────────────────────────────────────────────

ALL_CHECKS = [
    BatteryCheck,
    SMARTStatusCheck,
    KernelPanicCheck,
    ThermalCheck,
]
