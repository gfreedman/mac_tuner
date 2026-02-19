"""
MacTuner header banner.

Two-column Claude Code-style panel:
  Left  — welcome greeting, beagle character art, system identity
  Right — mode chips + contextual tips per mode
"""

import getpass
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from mactuner.system_info import get_system_info
from mactuner.ui.theme import COLOR_BRAND, MACTUNER_THEME


def build_header(mode: str = "scan", only_cats: Optional[set] = None) -> Panel:
    """
    Return a two-column Rich Panel (Claude Code style).

    Left column : greeting + beagle art + system identity
    Right column: mode chips + contextual tips for the active mode
    """
    info = get_system_info()

    table = Table(box=None, show_header=False, padding=(0, 2), expand=True)
    table.add_column(width=28, justify="center")
    table.add_column(justify="left")

    table.add_row(_build_left(info), _build_right(mode, only_cats))

    return Panel(table, border_style=COLOR_BRAND)


def _build_left(info: dict) -> Text:
    """Left column: greeting + beagle art + macOS/hardware identity."""
    username_raw = getpass.getuser()
    display_name = username_raw.replace("_", " ").replace(".", " ").split()[0].capitalize()

    macos_name = info.get("macos_name", "")
    macos_ver  = info.get("macos_version", "")
    if macos_name and not macos_name.isdigit():
        macos_display = f"macOS {macos_name} {macos_ver}"
    else:
        macos_display = f"macOS {macos_ver}"

    model = info.get("model_name", "Mac")

    t = Text(justify="center")
    t.append("\n")
    t.append(f"Welcome back, {display_name}!", style="bold white")
    t.append("\n\n")
    _append_beagle(t)
    t.append("\n")
    t.append(macos_display, style="dim")
    t.append("\n")
    t.append(model, style="dim")
    t.append("\n")
    return t


def _append_beagle(t: Text) -> None:
    """Append beagle block-character art with Rich color spans."""
    E = "#4A2800"   # ears  — dark brown
    H = "#9B6B3A"   # head  — medium brown
    I = "#F0F0F0"   # eyes  — near-white
    N = "#2C1500"   # nose  — near-black
    B = "#C48B4A"   # body  — golden tan
    L = "#9B6B3A"   # legs  — same as head

    def row(*spans: tuple[str, str]) -> None:
        for color, chars in spans:
            t.append(chars, style=color)
        t.append("\n")

    row((E, "  ▖         ▗"))
    row((E, "  ▐         ▌"))
    row((E, "  ▐"), (H, "  ▄▄▄▄▄"), (E, "  ▌"))
    row((H, "  ▀██████████▀"))
    row((H, "     "), (I, "◉"), (H, "   "), (I, "◉"))
    row((H, "      "), (N, "▾▾▾"))
    row((B, "     ▄████▄"))
    row((L, "   ▗▌      ▌▖"))
    row((L, "   ▀▘      ▝▀"))


def _build_right(mode: str = "scan", only_cats: Optional[set] = None) -> Text:
    """Right column: mode chips + contextual tips for the active mode."""
    t = Text(justify="left")
    t.append("\n")
    t.append("  Modes\n", style=f"bold {COLOR_BRAND}")
    t.append("\n")

    # ── Mode chips ────────────────────────────────────────────────────────────
    modes = [
        ("scan",     "🔍", "cyan",    "mactuner",        "Full system audit (read-only)"),
        ("fix",      "🔧", "magenta", "mactuner --fix",   "Apply fixes interactively"),
        ("targeted", "🎯", "yellow",  "mactuner --only …","Targeted category scan"),
    ]

    for m_id, icon, color, cmd, desc in modes:
        if m_id == mode:
            # Active mode — full brightness with ← active label
            if m_id == "targeted" and only_cats:
                cats_str = ",".join(sorted(only_cats))
                cmd = f"mactuner --only {cats_str}"
            t.append(f"  {icon} ", style=f"bold {color}")
            t.append(f"{cmd}", style=f"bold {color}")
            t.append("   ← active\n", style=f"dim {color}")
            t.append(f"     {desc}\n", style=color)
        else:
            # Inactive — dim
            t.append(f"  ·  {icon} {cmd}", style="dim white")
            t.append(f"  {desc}\n", style="dim white")

    # ── Divider ───────────────────────────────────────────────────────────────
    t.append("\n")
    t.append("  " + "─" * 34 + "\n", style="dim white")
    t.append("\n")

    # ── Contextual tips ───────────────────────────────────────────────────────
    if mode == "scan":
        t.append("  Scan mode tips\n", style=f"bold {COLOR_BRAND}")
        t.append("\n")
        tips = [
            ("mactuner --fix",     "after scan to repair issues"),
            ("mactuner --only",    "security,disk  targeted scan"),
            ("mactuner --explain", "deeper context per finding"),
            ("mactuner -y",        "skip pre-scan prompt"),
        ]
    elif mode == "fix":
        t.append("  Fix mode tips\n", style=f"bold {COLOR_BRAND}")
        t.append("\n")
        tips = [
            ("mactuner --auto",    "apply safe fixes without prompting"),
            ("mactuner --only",    "security  fix one category only"),
            ("mactuner -y",        "skip pre-scan prompt"),
            ("mactuner --explain", "see deeper context first"),
        ]
    else:  # targeted
        t.append("  Targeted mode tips\n", style=f"bold {COLOR_BRAND}")
        t.append("\n")
        tips = [
            ("mactuner --fix",     "add to apply fixes after scan"),
            ("mactuner --explain", "deeper context per finding"),
            ("mactuner --only",    "combine categories e.g. security,disk"),
            ("mactuner -y",        "skip pre-scan prompt"),
        ]

    for flag, desc in tips:
        t.append(f"  • ", style="dim white")
        t.append(flag, style="bold white")
        t.append(f"  {desc}\n", style="dim white")

    return t


def print_header(
    console: Optional[Console] = None,
    mode: str = "scan",
    only_cats: Optional[set] = None,
) -> None:
    """Render the header to the given Console (or create a themed one)."""
    if console is None:
        console = Console(theme=MACTUNER_THEME)
    console.print(build_header(mode=mode, only_cats=only_cats))
