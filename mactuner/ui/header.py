"""
MacTuner header banner.

Renders a rich Panel with system identity:
  - Tool name + tagline + version
  - Mac model + macOS version + architecture
  - Scan start timestamp
"""

from datetime import datetime

from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from mactuner.system_info import get_system_info
from mactuner.ui.theme import (
    APP_NAME,
    APP_TAGLINE,
    APP_VERSION,
    COLOR_BRAND,
    COLOR_DIM,
    COLOR_INFO,
    MACTUNER_THEME,
)


def build_header() -> Panel:
    """
    Return a rich Panel for the top of the scan.

    Example output:
    ╭──────────────────────────────────────────────────────────────╮
    │         mactuner  ·  Mac System Health Inspector  ·  v1.0   │
    │         MacBook Pro (M3 Max)  ·  macOS Sequoia 15.3.1       │
    │         Scan started: Monday 17 Feb 2026  ·  10:41 AM       │
    ╰──────────────────────────────────────────────────────────────╯
    """
    info = get_system_info()
    now = datetime.now()
    timestamp = now.strftime("%A %d %b %Y  ·  %I:%M %p").lstrip("0")

    # Line 1 — tool identity
    title_text = Text()
    title_text.append(f"  {APP_NAME}  ", style=f"bold {COLOR_BRAND}")
    title_text.append("·", style=COLOR_DIM)
    title_text.append(f"  {APP_TAGLINE}  ", style="bold white")
    title_text.append("·", style=COLOR_DIM)
    title_text.append(f"  v{APP_VERSION}", style=COLOR_DIM)

    # Line 2 — hardware identity
    macos_line = Text()
    model = info["model_name"]
    arch = info["architecture"]
    macos_ver = info["macos_version"]
    macos_name = info["macos_name"]
    ram = info["ram_gb"]

    # Build "macOS Sequoia 15.3" or just "macOS 26.3" for unknown names
    if macos_name and not macos_name.isdigit():
        macos_display = f"macOS {macos_name} {macos_ver}"
    else:
        macos_display = f"macOS {macos_ver}"

    macos_line.append(f"  {model}", style="bold white")
    macos_line.append("  ·  ", style=COLOR_DIM)
    macos_line.append(macos_display, style=f"bold {COLOR_INFO}")
    macos_line.append("  ·  ", style=COLOR_DIM)
    macos_line.append(f"{arch}", style=COLOR_DIM)
    if ram:
        macos_line.append(f"  ·  {ram} GB RAM", style=COLOR_DIM)

    # Line 3 — timestamp
    time_text = Text()
    time_text.append(f"  Scan started: {timestamp}  ", style=COLOR_DIM)

    body = Text.assemble(
        title_text, "\n",
        macos_line, "\n",
        time_text,
    )

    return Panel(
        Align.center(body),
        border_style=COLOR_BRAND,
        padding=(0, 2),
    )


def print_header(console: Console | None = None) -> None:
    """Render the header to the given Console (or create a themed one)."""
    if console is None:
        console = Console(theme=MACTUNER_THEME)
    console.print(build_header())
