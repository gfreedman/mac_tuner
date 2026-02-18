"""
MacTuner header banner.

Two-column Claude Code-style panel:
  Left  — welcome greeting, beagle character art, system identity
  Right — tips for getting started, last scan info
"""

import getpass

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from mactuner.system_info import get_system_info
from mactuner.ui.theme import COLOR_BRAND, MACTUNER_THEME


def build_header() -> Panel:
    """
    Return a two-column Rich Panel (Claude Code style).

    Left column : greeting + beagle art + system identity
    Right column: tips for getting started + last scan info
    """
    info = get_system_info()

    table = Table(box=None, show_header=False, padding=(0, 2), expand=True)
    table.add_column(width=28, justify="center")
    table.add_column(justify="left")

    table.add_row(_build_left(info), _build_right())

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


def _build_right() -> Text:
    """Right column: tips for getting started + last scan info."""
    t = Text(justify="left")
    t.append("\n")
    t.append("Tips for getting started", style="bold white")
    t.append("\n\n")

    tips = [
        ("--fix",             " after the scan to repair issues interactively"),
        ("--only",            " security,disk  for a targeted category scan"),
        ("--explain",         "  adds deeper context to every finding"),
        ("--show-completion", "  to enable tab completion"),
    ]
    for flag, desc in tips:
        t.append("  • mactuner ", style="dim white")
        t.append(flag, style="bold white")
        t.append(desc + "\n", style="dim white")

    t.append("\n")
    t.append("  " + "─" * 32 + "\n", style="dim white")
    t.append("\n")
    t.append("  Last scan\n", style="bold white")
    t.append("  No recent scans\n", style="dim white")
    return t


def print_header(console: Console | None = None) -> None:
    """Render the header to the given Console (or create a themed one)."""
    if console is None:
        console = Console(theme=MACTUNER_THEME)
    console.print(build_header())
