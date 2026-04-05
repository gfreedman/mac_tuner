"""
Shared enumerations for macaudit's core vocabulary.

These enums replace bare string literals scattered across the codebase,
giving every status, fix-level, and category value a single authoritative
name.  All three inherit from both ``str`` and ``Enum``, which means:

  - They are backwards-compatible with plain-string comparisons
    (``CheckStatus.CRITICAL == "critical"`` is ``True``).
  - Dict lookups on enum-keyed dicts work with plain-string keys and
    vice versa, because ``str, Enum`` members share the ``str`` hash.
  - JSON serialisation via ``dataclasses.asdict()`` continues to produce
    plain strings, not enum reprs.

Attributes:
    CheckStatus: Valid values for ``CheckResult.status``.
    FixLevel: Valid values for ``CheckResult.fix_level``.
    CheckCategory: Valid values for ``CheckResult.category``.
"""

from enum import Enum


class CheckStatus(str, Enum):
    """Result status returned by every check.

    Ordered from best to worst for severity comparisons.

    Attributes:
        PASS:     Check found no issue; nothing for the user to do.
        INFO:     Informational finding; no action required.
        SKIP:     Check was not applicable or was suppressed by config.
        WARNING:  Potential issue; action recommended.
        ERROR:    Unexpected exception during check execution.
        CRITICAL: Serious issue; action strongly required.
    """

    PASS     = "pass"
    INFO     = "info"
    SKIP     = "skip"
    WARNING  = "warning"
    ERROR    = "error"
    CRITICAL = "critical"


class FixLevel(str, Enum):
    """Automated-fix capability tier for a check result.

    Attributes:
        AUTO:         Safe shell command; no privileges required.
        AUTO_SUDO:    Shell command requiring admin privileges, presented
                      via a native macOS password dialog.
        GUIDED:       Opens the relevant System Settings pane.
        INSTRUCTIONS: Prints numbered manual steps; no commands executed.
        NONE:         No automated fix available.
    """

    AUTO         = "auto"
    AUTO_SUDO    = "auto_sudo"
    GUIDED       = "guided"
    INSTRUCTIONS = "instructions"
    NONE         = "none"


class CheckCategory(str, Enum):
    """Category slugs used to group checks in the report.

    Attributes:
        SYSTEM:   macOS version, updates, screen lock, Gatekeeper.
        SECURITY: FileVault, firewall, SIP, profiles.
        PRIVACY:  TCC permissions, Location Services, Sharing.
        MALWARE:  ClamAV, Objective-See tools, persistence directories.
        HOMEBREW: Outdated formulae, Homebrew health, cache.
        DISK:     Free space, snapshots, caches, Trash.
        HARDWARE: Battery, SMART, thermal, kernel panics.
        MEMORY:   Swap, top CPU/memory consumers.
        NETWORK:  AirDrop, firewall stealth, open ports, DNS.
        DEV_ENV:  Git, Python, Node, Docker, Xcode CLT.
        APPS:     App Store updates, login items, iCloud.
    """

    SYSTEM   = "system"
    SECURITY = "security"
    PRIVACY  = "privacy"
    MALWARE  = "malware"
    HOMEBREW = "homebrew"
    DISK     = "disk"
    HARDWARE = "hardware"
    MEMORY   = "memory"
    NETWORK  = "network"
    DEV_ENV  = "dev_env"
    APPS     = "apps"
