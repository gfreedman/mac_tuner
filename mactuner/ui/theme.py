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
APP_VERSION = "1.0.0"


# ── Color palette ─────────────────────────────────────────────────────────────

COLOR_CRITICAL = "bright_red"       # Security risks, hardware failure
COLOR_WARNING = "yellow"            # Outdated, suboptimal, needs review
COLOR_PASS = "bright_green"         # All clear
COLOR_INFO = "cyan"                 # Neutral context
COLOR_BRAND = "magenta"             # Section headers, branding
COLOR_DIM = "dim white"             # Secondary text, explanations, commands
COLOR_HEADER_BG = "grey11"          # Panel background for header


# ── Rich styles ───────────────────────────────────────────────────────────────

STYLE_CRITICAL = Style(color="bright_red", bold=True)
STYLE_WARNING = Style(color="yellow", bold=True)
STYLE_PASS = Style(color="bright_green", bold=True)
STYLE_INFO = Style(color="cyan")
STYLE_BRAND = Style(color="magenta", bold=True)
STYLE_DIM = Style(color="white", dim=True)
STYLE_SECTION = Style(color="magenta", bold=True)
STYLE_COMMAND = Style(color="white", dim=True)

# Spinner style for live checks
STYLE_SPINNER = Style(color="cyan")


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
        "critical": COLOR_CRITICAL + " bold",
        "warning": COLOR_WARNING + " bold",
        "pass": COLOR_PASS + " bold",
        "info": COLOR_INFO,
        "brand": COLOR_BRAND + " bold",
        "dim": "dim white",
        "section": COLOR_BRAND + " bold",
        "command": "dim white",
    }
)


# ── Progress bar style ────────────────────────────────────────────────────────

PROGRESS_BAR_COLOR = "cyan"
PROGRESS_COMPLETE_COLOR = "bright_green"
