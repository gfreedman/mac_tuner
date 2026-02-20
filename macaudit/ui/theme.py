"""
Mac Audit visual design system.

All colors, styles, and icons as named constants.
Import from here — never hardcode markup strings in other modules.

Color palette is selected at import time based on macOS appearance.
Dark and light palettes are both 24-bit hex for consistent rendering
across Terminal.app, iTerm2, Warp, Alacritty, etc.
"""

import subprocess

from rich.style import Style
from rich.theme import Theme


# ── Brand ─────────────────────────────────────────────────────────────────────

from macaudit import __version__

APP_NAME = "macaudit"
APP_TAGLINE = "Mac System Health Inspector"
APP_VERSION = __version__


# ── Dark/light detection ──────────────────────────────────────────────────────

def _is_dark_mode() -> bool:
    """
    Detect macOS system appearance.

    Returns True for dark mode, False for light.
    Falls back to True (dark palette) on any error — the dark palette
    is readable in the vast majority of terminal configurations.
    """
    try:
        r = subprocess.run(
            ["defaults", "read", "-g", "AppleInterfaceStyle"],
            capture_output=True, text=True, timeout=2, check=False,
        )
        # exit 0 + "Dark" → dark mode
        # exit 1 (key absent) → light mode
        if r.returncode == 0:
            return "Dark" in r.stdout
        if r.returncode == 1:
            return False
    except Exception:
        pass
    return True  # safe default


DARK_MODE: bool = _is_dark_mode()


# ── Color palette ─────────────────────────────────────────────────────────────
# Two complete palettes — selected at import time.

if DARK_MODE:
    # ── Dark palette (light text on dark background) ─────────────────────────
    COLOR_CRITICAL = "#E05252"      # Warm severity red
    COLOR_WARNING  = "#D4870A"      # Amber
    COLOR_PASS     = "#4DBD74"      # Calm sage-green
    COLOR_INFO     = "#5BA3C9"      # Slate blue
    COLOR_BRAND    = "#7B9FD4"      # Periwinkle blue
    COLOR_DIM      = "#787878"      # Medium gray
    COLOR_COMMAND  = "#C0C0C0"      # Light silver — commands stand out from dim text
    COLOR_TEXT     = "#F0F0F0"      # Primary text — near-white
    COLOR_HEADER_BG = "grey11"

    COLOR_SCORE_HIGH = "#4DBD74"    # ≥ 90
    COLOR_SCORE_MID  = "#7EC67E"    # 75–89
    COLOR_SCORE_LOW  = "#D4870A"    # 55–74
    COLOR_SCORE_POOR = "#E05252"    # < 55

    PROGRESS_BAR_COLOR      = "#7B9FD4"
    PROGRESS_COMPLETE_COLOR = "#4DBD74"

else:
    # ── Light palette (dark text on light/white background) ──────────────────
    # All values chosen for WCAG AA contrast (≥ 4.5:1) on white backgrounds.
    COLOR_CRITICAL = "#B91C1C"      # Deep red         (contrast 6.5:1 on white)
    COLOR_WARNING  = "#92400E"      # Dark amber        (7.2:1)
    COLOR_PASS     = "#166534"      # Deep green        (7.5:1)
    COLOR_INFO     = "#0369A1"      # Deep sky blue     (5.9:1)
    COLOR_BRAND    = "#1D4ED8"      # Deep blue         (6.2:1)
    COLOR_DIM      = "#4B5563"      # Dark gray         (7.9:1)
    COLOR_COMMAND  = "#1F2937"      # Near-black        (15.8:1)
    COLOR_TEXT     = "#0F172A"      # Primary text — near-black (18.1:1)
    COLOR_HEADER_BG = "grey93"

    COLOR_SCORE_HIGH = "#166534"    # ≥ 90
    COLOR_SCORE_MID  = "#15803D"    # 75–89
    COLOR_SCORE_LOW  = "#92400E"    # 55–74
    COLOR_SCORE_POOR = "#B91C1C"    # < 55

    PROGRESS_BAR_COLOR      = "#1D4ED8"
    PROGRESS_COMPLETE_COLOR = "#166534"


# ── Rich styles ───────────────────────────────────────────────────────────────

STYLE_CRITICAL = Style(color=COLOR_CRITICAL, bold=True)
STYLE_WARNING  = Style(color=COLOR_WARNING,  bold=True)
STYLE_PASS     = Style(color=COLOR_PASS,     bold=True)
STYLE_INFO     = Style(color=COLOR_INFO)
STYLE_BRAND    = Style(color=COLOR_BRAND,    bold=True)
STYLE_DIM      = Style(color=COLOR_DIM)
STYLE_SECTION  = Style(color=COLOR_BRAND,    bold=True)
STYLE_COMMAND  = Style(color=COLOR_COMMAND)
STYLE_SPINNER  = Style(color=COLOR_BRAND)


# ── Status icons ──────────────────────────────────────────────────────────────

ICON_PASS = "✅"
ICON_WARNING = "⚠️ "
ICON_CRITICAL = "🔴"
ICON_INFO = "ℹ️ "
ICON_SKIP = "⏭️ "
ICON_ERROR = "❌"
ICON_FIX = "🔧"
ICON_LOCK = "🔐"
ICON_GUIDED = "👆"
ICON_STEPS = "📋"

STATUS_ICONS: dict[str, str] = {
    "pass": ICON_PASS,
    "warning": ICON_WARNING,
    "critical": ICON_CRITICAL,
    "info": ICON_INFO,
    "skip": ICON_SKIP,
    "error": ICON_ERROR,
}

STATUS_STYLES: dict[str, Style] = {
    "pass": STYLE_PASS,
    "warning": STYLE_WARNING,
    "critical": STYLE_CRITICAL,
    "info": STYLE_INFO,
    "skip": STYLE_DIM,
    "error": STYLE_CRITICAL,
}


# ── Category icons ────────────────────────────────────────────────────────────

CATEGORY_ICONS: dict[str, str] = {
    "system": "🖥️ ",
    "privacy": "🔏",
    "security": "🛡️ ",
    "homebrew": "🍺",
    "disk": "💽",
    "hardware": "🔋",
    "memory": "🧠",
    "network": "🌐",
    "dev_env": "🧑‍💻",
    "apps": "📱",
}


# ── Fix level labels ──────────────────────────────────────────────────────────

FIX_LEVEL_LABELS: dict[str, str] = {
    "auto": f"{ICON_FIX} Automatic",
    "auto_sudo": f"{ICON_FIX}{ICON_LOCK} Requires password",
    "guided": f"{ICON_GUIDED} Opens Settings",
    "instructions": f"{ICON_STEPS} Step-by-step",
    "none": "📊 Info only",
}


# ── Rich Theme ────────────────────────────────────────────────────────────────

MACTUNER_THEME = Theme(
    {
        "critical": f"{COLOR_CRITICAL} bold",
        "warning":  f"{COLOR_WARNING} bold",
        "pass":     f"{COLOR_PASS} bold",
        "info":     COLOR_INFO,
        "brand":    f"{COLOR_BRAND} bold",
        "dim":      COLOR_DIM,
        "section":  f"{COLOR_BRAND} bold",
        "command":  COLOR_COMMAND,
        "text":     COLOR_TEXT,        # primary text — use instead of hardcoded "white"
    }
)
