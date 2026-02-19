"""
Welcome screen.

Displayed on first run (before ~/.config/mactuner/.welcomed exists)
or with --welcome. Mirrors the Claude Code two-column Panel layout:

  ╭─── MacTuner  v1.2.0 ─────────────────────────────────────────────╮
  │                             │ Quick start                          │
  │     Welcome back, Geoff!    │   mactuner           Full scan       │
  │                             │   mactuner --fix     Fix mode        │
  │           beagle            │ ──────────────────────────────────── │
  │                             │ Last scan                            │
  │   macOS 26.3 · MacBook Air  │   18 Feb 2026 · 22:06 · Score 94    │
  │    /Users/geoff_freedman    │                                      │
  ╰──────────────────────────────────────────────────────────────────╯
"""

import getpass
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.box import Box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from mactuner import __version__
from mactuner.system_info import get_system_info
from mactuner.ui.header import _append_beagle
from mactuner.ui.theme import (
    APP_NAME, COLOR_BRAND, COLOR_DIM, COLOR_TEXT,
    COLOR_CRITICAL, COLOR_WARNING, COLOR_PASS,
    COLOR_SCORE_HIGH, COLOR_SCORE_MID, COLOR_SCORE_LOW, COLOR_SCORE_POOR,
)

# Box that renders only a │ column separator — no outer borders, no row rules.
# Each 4-char line: left_border, fill, col_separator, right_border
_VBAR = Box("    \n  │ \n    \n  │ \n    \n    \n  │ \n    \n")


# ── Persistent state paths ────────────────────────────────────────────────────

_CONFIG_DIR   = Path.home() / ".config" / "mactuner"
_WELCOME_FLAG = _CONFIG_DIR / ".welcomed"
_LAST_SCAN    = _CONFIG_DIR / "last_scan.json"


# ── Public API ────────────────────────────────────────────────────────────────

def is_first_run() -> bool:
    """True when mactuner has never been run on this machine."""
    return not _WELCOME_FLAG.exists()


def mark_welcomed() -> None:
    """Create the first-run flag so the welcome screen is not shown again."""
    try:
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        _WELCOME_FLAG.touch()
    except OSError:
        pass


def save_last_scan(score: int, counts: dict) -> None:
    """
    Persist a lightweight scan summary after every run.

    Written to ~/.config/mactuner/last_scan.json.
    """
    record = {
        "date":     datetime.now().isoformat(timespec="seconds"),
        "score":    score,
        "critical": counts.get("critical", 0),
        "warning":  counts.get("warning",  0),
        "pass":     counts.get("pass",     0),
        "info":     counts.get("info",     0),
    }
    try:
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        _LAST_SCAN.write_text(json.dumps(record))
    except OSError:
        pass


def show_welcome(console: Console, first_run: bool = False) -> bool:
    """
    Render the welcome screen.

    Args:
        console:   Shared Rich Console.
        first_run: If True, prompt "↵ to start scan". Returns True when the
                   user continues, False on Ctrl-C / EOF. Calls mark_welcomed()
                   on confirm.
                   If False (--welcome flag), just display; always returns False.
    """
    info         = get_system_info()
    username_raw = getpass.getuser()
    display_name = (
        username_raw.replace("_", " ").replace(".", " ").split()[0].capitalize()
    )

    _render(console, info, display_name)

    if first_run:
        console.print(
            "  [dim]Press [bold text]↵[/bold text] to start your first scan  "
            "·  [bold text]Ctrl-C[/bold text] to exit[/dim]"
        )
        try:
            input()
        except (KeyboardInterrupt, EOFError):
            console.print("\n  [dim]Cancelled.[/dim]\n")
            return False
        console.print()
        mark_welcomed()
        return True

    return False


# ── Renderer ──────────────────────────────────────────────────────────────────

def _render(console: Console, info: dict, display_name: str) -> None:
    table = Table(
        box=_VBAR, show_header=False, show_edge=False, show_lines=False,
        border_style=COLOR_BRAND, padding=(0, 2), expand=True,
    )
    table.add_column(width=28, justify="center")
    table.add_column(justify="left", overflow="fold")
    # Right column content width:
    #   terminal(W) - panel_borders(2) - panel_padding(2) - left_col_total(32) - separator(1) - right_col_padding(4)
    right_w = max(10, console.width - 41)
    table.add_row(_build_left(info, display_name), _build_right(right_w))

    title = Text()
    title.append(APP_NAME, style=f"bold {COLOR_TEXT}")
    title.append(f"  v{__version__}", style=COLOR_DIM)

    console.print(Panel(table, title=title, title_align="left", border_style=COLOR_BRAND))


# ── Left column ───────────────────────────────────────────────────────────────

def _build_left(info: dict, display_name: str) -> Text:
    macos_name = info.get("macos_name", "")
    macos_ver  = info.get("macos_version", "")
    macos_display = (
        f"macOS {macos_name} {macos_ver}"
        if macos_name and not macos_name.isdigit()
        else f"macOS {macos_ver}"
    )
    model = info.get("model_name", "Mac")
    ram   = info.get("ram_gb", 0)
    cpu   = info.get("cpu_brand", "") or info.get("architecture", "")

    # Each info line must fit within the 28-char left column content width.
    # Split chip/ram/model onto separate lines rather than one long joined string.
    cpu_ram = "  ·  ".join([p for p in [cpu, f"{ram} GB" if ram else ""] if p])

    t = Text(justify="center")
    t.append("\n")
    t.append(f"Welcome back, {display_name}!", style=f"bold {COLOR_TEXT}")
    t.append("\n\n")
    _append_beagle(t)
    t.append("\n")
    t.append(macos_display + "\n", style="dim")
    if cpu_ram:
        t.append(cpu_ram + "\n", style="dim")
    t.append(model + "\n", style="dim")
    t.append(str(Path.cwd()) + "\n", style="dim")
    return t


# ── Right column ──────────────────────────────────────────────────────────────

def _build_right(right_w: int = 55) -> Text:
    t = Text(justify="left")
    t.append("\n")
    t.append("Quick start\n", style=f"bold {COLOR_BRAND}")
    t.append("\n")

    _CMD_W = 20   # len("mactuner --explain") = 18, +2 breathing room
    cmds = [
        ("mactuner",           "Full system health scan"),
        ("mactuner --fix",     "Interactive fix mode"),
        ("mactuner --only",    "Target specific categories"),
        ("mactuner --explain", "Verbose context per finding"),
        ("mactuner --help",    "All options"),
    ]
    for cmd, desc in cmds:
        t.append("  ")
        t.append(cmd.ljust(_CMD_W), style=f"bold {COLOR_TEXT}")
        t.append(desc + "\n", style=COLOR_DIM)

    t.append("\n")
    t.append("─" * right_w + "\n", style=COLOR_DIM)
    t.append("\n")

    last = _load_last_scan()
    if last:
        t.append("Last scan\n", style=f"bold {COLOR_BRAND}")
        t.append("\n")
        _append_last_scan(t, last)
    else:
        t.append("No previous scan\n", style=COLOR_DIM)

    return t


# ── Last scan helpers ─────────────────────────────────────────────────────────

def _load_last_scan() -> Optional[dict]:
    try:
        data = json.loads(_LAST_SCAN.read_text())
        if "score" in data and "date" in data:
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return None


def _append_last_scan(t: Text, data: dict) -> None:
    try:
        dt = datetime.fromisoformat(data["date"])
        date_str = f"{dt.day} {dt.strftime('%b %Y')}  ·  {dt.strftime('%H:%M')}"
    except (ValueError, KeyError):
        date_str = str(data.get("date", ""))

    score    = data.get("score",    0)
    critical = data.get("critical", 0)
    warning  = data.get("warning",  0)

    if score >= 90:
        score_style = f"bold {COLOR_SCORE_HIGH}"
    elif score >= 75:
        score_style = f"bold {COLOR_SCORE_MID}"
    elif score >= 55:
        score_style = f"bold {COLOR_SCORE_LOW}"
    else:
        score_style = f"bold {COLOR_SCORE_POOR}"

    # Line 1: date · time
    t.append("  ", style=COLOR_DIM)
    t.append(date_str + "\n", style=COLOR_DIM)

    # Line 2: score + status badges
    t.append("  ", style=COLOR_DIM)
    t.append(f"Score {score}", style=score_style)
    if critical:
        t.append(f"  ·  {critical} critical", style=f"bold {COLOR_CRITICAL}")
    if warning:
        t.append(f"  ·  {warning} warnings", style=COLOR_WARNING)
    if not critical and not warning:
        t.append("  ·  all clear", style=COLOR_PASS)

    t.append("\n")
