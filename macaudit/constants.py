"""
Named constants for all tuneable thresholds in macaudit checks.

Every magic number used in a severity decision lives here.  Check modules
import from this file rather than embedding bare integers, making thresholds
easy to find, adjust, and keep in sync with their documentation.

Usage::

    from macaudit.constants import DISK_CRITICAL_GB, BATTERY_HEALTH_THRESHOLD

Attributes:
    CRITICAL_PENALTY (int): Base health-score deduction per critical result.
    WARNING_PENALTY (int): Base health-score deduction per warning result.
    SECURITY_CRITICAL_MULTIPLIER (float): Extra weight for critical results in
        security-related categories (system, privacy, security).
    SECURITY_WARNING_MULTIPLIER (float): Extra weight for warning results in
        security-related categories.

    DISK_CRITICAL_GB (int): Free-disk threshold below which a critical is raised.
    DISK_WARNING_GB (int): Free-disk threshold below which a warning is raised.
    DISK_INFO_GB (int): Free-disk threshold below which an info is raised.
    XCODE_CACHE_WARNING_GB (int): DerivedData size above which a warning is raised.
    XCODE_CACHE_INFO_GB (int): DerivedData size above which an info is raised.
    DOCKER_WARNING_GB (int): Container-runtime disk use above which a warning is raised.
    TRASH_WARNING_MB (int): Trash size above which a warning is raised.
    APP_CACHES_WARNING_GB (int): ~/Library/Caches size above which a warning is raised.
    APP_CACHES_INFO_GB (int): ~/Library/Caches size above which an info is raised.

    SWAP_CRITICAL_GB (int): Swap usage above which a critical is raised.
    SWAP_WARNING_GB (int): Swap usage above which a warning is raised.
    SWAP_INFO_GB (int): Swap usage above which an info is raised.
    CPU_RUNAWAY_THRESHOLD (int): CPU% above which the top process is flagged as runaway.

    BATTERY_HEALTH_THRESHOLD (int): Max-capacity % below which battery is degraded.
    CPU_SPEED_LIMIT_FULL (int): CPU speed-limit % at which no throttling is active.
    KERNEL_PANIC_CRITICAL (int): Panic count in 7 days that triggers a critical.
    KERNEL_PANIC_WARNING (int): Panic count in 7 days that triggers a warning.

    SCREEN_LOCK_PASS_SECONDS (int): Password delay (seconds) considered acceptable.
    SCREEN_LOCK_WARNING_SECONDS (int): Password delay (seconds) that triggers a warning.

    BREW_CACHE_WARNING_MB (int): Homebrew reclaimable cache size that triggers a warning.

    MIN_SUPPORTED_MACOS_MAJOR (int): Oldest supported macOS major version.
"""


# ── Health-score penalties ────────────────────────────────────────────────────

CRITICAL_PENALTY              = 10     # points deducted per critical result
WARNING_PENALTY               = 3      # points deducted per warning result

# Security, privacy, and system results carry extra weight because they
# directly expose the user to external threats.
SECURITY_CRITICAL_MULTIPLIER  = 1.5   # → 15 points deducted
SECURITY_WARNING_MULTIPLIER   = 1.2   # → 3 or 4 points deducted (int-truncated)


# ── Disk thresholds ───────────────────────────────────────────────────────────

DISK_CRITICAL_GB        = 5    # GB free — critical: macOS may become unstable
DISK_WARNING_GB         = 10   # GB free — warning: headroom is getting low
DISK_INFO_GB            = 20   # GB free — info: adequate but worth monitoring

XCODE_CACHE_WARNING_GB  = 10   # GB — DerivedData is large enough to warrant cleanup
XCODE_CACHE_INFO_GB     = 2    # GB — DerivedData is present but not yet a concern

DOCKER_WARNING_GB       = 20   # GB — container runtime storage is consuming significant space
TRASH_WARNING_MB        = 500  # MB — Trash is large enough that emptying is worthwhile

APP_CACHES_WARNING_GB   = 10   # GB — ~/Library/Caches is unusually large
APP_CACHES_INFO_GB      = 3    # GB — ~/Library/Caches is noteworthy but not alarming


# ── Memory / CPU thresholds ───────────────────────────────────────────────────

SWAP_CRITICAL_GB        = 8    # GB swap used — suggests severe memory pressure
SWAP_WARNING_GB         = 4    # GB swap used — notable pressure
SWAP_INFO_GB            = 1    # GB swap used — worth surfacing

# A single process above this CPU% is likely spinning in a tight bug loop.
# Chosen below 100% because macOS reports pcpu as a rolling average that
# rarely reaches the theoretical maximum even on a fully loaded core.
CPU_RUNAWAY_THRESHOLD   = 90   # % CPU usage


# ── Hardware thresholds ───────────────────────────────────────────────────────

# Apple's documented threshold for "battery health is degraded".
BATTERY_HEALTH_THRESHOLD = 80  # % max capacity

# A CPU speed limit below 100% means the OS is reducing clock frequency
# to manage thermal output (active throttling).
CPU_SPEED_LIMIT_FULL    = 100  # % — at or above this means no throttling

KERNEL_PANIC_CRITICAL   = 3    # panics in 7-day window → critical
KERNEL_PANIC_WARNING    = 1    # panics in 7-day window → warning (any non-zero)


# ── Screen lock thresholds ────────────────────────────────────────────────────

SCREEN_LOCK_PASS_SECONDS    = 5   * 60   # 5 min — acceptable password delay
SCREEN_LOCK_WARNING_SECONDS = 60  * 60   # 60 min — password delay is too long


# ── Homebrew thresholds ───────────────────────────────────────────────────────

BREW_CACHE_WARNING_MB   = 500  # MB — enough reclaimable space to warrant cleanup


# ── macOS version ─────────────────────────────────────────────────────────────

# Oldest macOS major version explicitly supported.  Checks that target
# Ventura-specific APIs set min_macos = (MIN_SUPPORTED_MACOS_MAJOR, 0).
MIN_SUPPORTED_MACOS_MAJOR = 13   # macOS Ventura
