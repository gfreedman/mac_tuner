"""
macOS system detection — version, architecture, hardware model.
Every check module imports from here. Must be rock-solid.
"""

import platform
import subprocess
import shutil
from functools import lru_cache
from typing import Any


# Module-level constants — imported by every check
MACOS_VERSION: tuple[int, int] = tuple(
    map(int, platform.mac_ver()[0].split(".")[:2])
)  # e.g. (15, 3)

IS_APPLE_SILICON: bool = platform.machine() == "arm64"

MACOS_VERSION_STRING: str = platform.mac_ver()[0]  # e.g. "15.3.1"


def _run(cmd: list[str], timeout: int = 5) -> str:
    """Run a command and return stdout. Returns '' on any error."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return result.stdout.strip()
    except Exception:
        return ""


@lru_cache(maxsize=1)
def get_system_info() -> dict[str, Any]:
    """
    Return a dict describing this Mac.

    Keys:
        macos_version       "15.3.1"
        macos_version_tuple (15, 3)
        macos_name          "Sequoia"  (or "Unknown")
        architecture        "Apple Silicon" | "Intel"
        machine             "arm64" | "x86_64"
        hostname            "Geoffs-MacBook-Pro.local"
        model_name          "MacBook Pro (M3 Max)" | "Mac mini (2023)"
        cpu_brand           "Apple M3 Max" | "Intel Core i9"
        ram_gb              32
        has_brew            True | False
        has_macports        True | False
    """
    macos_name = _macos_name(MACOS_VERSION[0])
    model_name = _model_name()
    cpu_brand = _cpu_brand()
    ram_gb = _ram_gb()

    return {
        "macos_version": MACOS_VERSION_STRING,
        "macos_version_tuple": MACOS_VERSION,
        "macos_name": macos_name,
        "architecture": "Apple Silicon" if IS_APPLE_SILICON else "Intel",
        "machine": platform.machine(),
        "hostname": platform.node(),
        "model_name": model_name,
        "cpu_brand": cpu_brand,
        "ram_gb": ram_gb,
        "has_brew": shutil.which("brew") is not None,
        "has_macports": shutil.which("port") is not None,
    }


# ── Internal helpers ──────────────────────────────────────────────────────────

_MACOS_NAMES: dict[int, str] = {
    13: "Ventura",
    14: "Sonoma",
    15: "Sequoia",
    16: "Tahoe",
}


def _macos_name(major: int) -> str:
    """Map a macOS major version number to its marketing name (e.g. 15 → 'Sequoia')."""
    # Known names first; for future versions fall back gracefully
    name = _MACOS_NAMES.get(major)
    if name:
        return name
    if major >= 16:
        return str(major)  # e.g. "26" — header already prepends "macOS"
    return "Unknown"


def _model_name() -> str:
    """Return human-readable Mac model, e.g. 'MacBook Pro (M3 Max)'."""
    # system_profiler is slow; try sysctl first (fast, machine-readable)
    brand = _run(["sysctl", "-n", "hw.model"])  # e.g. "MacBookPro18,3"
    if not brand:
        return "Mac"

    # Try system_profiler for the marketing name (slower, nicer)
    sp = _run(
        ["system_profiler", "SPHardwareDataType"],
        timeout=5,
    )
    for line in sp.splitlines():
        if "Model Name" in line:
            return line.split(":", 1)[-1].strip()  # "MacBook Pro"

    return brand  # fallback to sysctl identifier


def _cpu_brand() -> str:
    """Return CPU description, e.g. 'Apple M3 Max' or 'Intel Core i9'."""
    brand = _run(["sysctl", "-n", "machdep.cpu.brand_string"])
    if brand:
        return brand

    # Apple Silicon: brand_string not available; build from chip class
    chip = _run(["sysctl", "-n", "hw.model"])
    return f"Apple Silicon ({chip})" if chip else "Unknown CPU"


def _ram_gb() -> int:
    """Return total physical RAM in GB."""
    mem_bytes_str = _run(["sysctl", "-n", "hw.memsize"])
    try:
        return int(mem_bytes_str) // (1024 ** 3)
    except (ValueError, TypeError):
        return 0
