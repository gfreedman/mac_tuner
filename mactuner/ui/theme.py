"""
MacTuner visual design system.

All colors, styles, and icons as named constants.
Import from here — never hardcode markup strings in other modules.
"""

from rich.style import Style
from rich.theme import Theme


# ── Brand ─────────────────────────────────────────────────────────────────────

APP_NAME = "mactuner"
APP_TAGLINE = "Mac System Health Inspector"
APP_VERSION = "1.2.0"


# ── Color palette ─────────────────────────────────────────────────────────────

COLOR_CRITICAL = "#E05252"      # Warm severity red — intentional, not ANSI alarm
COLOR_WARNING  = "#D4870A"      # Amber — reliable across all 24-bit terminals
COLOR_PASS     = "#4DBD74"      # Calm sage-green — readable, not neon lime
COLOR_INFO     = "#5BA3C9"      # Slate blue — neutral informational
COLOR_BRAND    = "#7B9FD4"      # Periwinkle blue — trustworthy, frames without shouting
COLOR_DIM      = "#787878"      # Medium gray — consistent across terminals
COLOR_COMMAND  = "#C0C0C0"      # Light silver — commands stand out from secondary text
COLOR_HEADER_BG = "grey11"      # Panel background for header

# Score color bands
COLOR_SCORE_HIGH = "#4DBD74"    # ≥ 90
COLOR_SCORE_MID  = "#7EC67E"    # 75–89 (optimistic green — room to improve)
COLOR_SCORE_LOW  = "#D4870A"    # 55–74
COLOR_SCORE_POOR = "#E05252"    # < 55


# ── Rich styles ───────────────────────────────────────────────────────────────

STYLE_CRITICAL = Style(color="#E05252", bold=True)
STYLE_WARNING  = Style(color="#D4870A", bold=True)
STYLE_PASS     = Style(color="#4DBD74", bold=True)
STYLE_INFO     = Style(color="#5BA3C9")
STYLE_BRAND    = Style(color="#7B9FD4", bold=True)
STYLE_DIM      = Style(color="#787878")
STYLE_SECTION  = Style(color="#7B9FD4", bold=True)
STYLE_COMMAND  = Style(color="#C0C0C0")

# Spinner style for live checks — brand color: spinner is brand-motion
STYLE_SPINNER  = Style(color="#7B9FD4")


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

# Map status → icon
STATUS_ICONS: dict[str, str] = {
    "pass": ICON_PASS,
    "warning": ICON_WARNING,
    "critical": ICON_CRITICAL,
    "info": ICON_INFO,
    "skip": ICON_SKIP,
    "error": ICON_ERROR,
}

# Map status → style
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


# ── Rich Theme (registered with Console) ─────────────────────────────────────

MACTUNER_THEME = Theme(
    {
        "critical": "#E05252 bold",
        "warning":  "#D4870A bold",
        "pass":     "#4DBD74 bold",
        "info":     "#5BA3C9",
        "brand":    "#7B9FD4 bold",
        "dim":      "#787878",
        "section":  "#7B9FD4 bold",
        "command":  "#C0C0C0",
    }
)


# ── Progress bar style ────────────────────────────────────────────────────────

PROGRESS_BAR_COLOR      = "#7B9FD4"   # Brand — spinner and bar are both motion UI
PROGRESS_COMPLETE_COLOR = "#4DBD74"   # Same as PASS — completion = success
