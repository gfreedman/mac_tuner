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
from mactuner.ui.theme import APP_NAME, COLOR_BRAND

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
            "  [dim]Press [bold white]↵[/bold white] to start your first scan  "
            "·  [bold white]Ctrl-C[/bold white] to exit[/dim]"
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
    table.add_column(justify="left")
    table.add_row(_build_left(info, display_name), _build_right())

    title = Text()
    title.append(APP_NAME, style="bold white")
    title.append(f"  v{__version__}", style="dim white")

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

    # Build "macOS Sequoia · Apple M2 · 16 GB" line
    identity_parts = [p for p in [macos_display, cpu] if p]
    if ram:
        identity_parts.append(f"{ram} GB")

    t = Text(justify="center")
    t.append(f"Welcome back, {display_name}!", style="bold white")
    t.append("\n\n")
    _append_beagle(t)
    t.append("\n")
    t.append("  ·  ".join(identity_parts), style="dim")
    t.append("\n")
    t.append(model, style="dim")
    t.append("\n")
    t.append(str(Path.cwd()), style="dim")
    t.append("\n")
    return t


# ── Right column ──────────────────────────────────────────────────────────────

def _build_right() -> Text:
    t = Text(justify="left")
    t.append("Quick start\n", style="bold white")
    t.append("\n")

    _CMD_W = 22
    cmds = [
        ("mactuner",           "Full system health scan"),
        ("mactuner --fix",     "Interactive fix mode — repair issues"),
        ("mactuner --only",    "Targeted scan  e.g.  --only security,disk"),
        ("mactuner --explain", "Deeper context for every finding"),
        ("mactuner --help",    "All options"),
    ]
    for cmd, desc in cmds:
        t.append("  ")
        t.append(cmd.ljust(_CMD_W), style="bold white")
        t.append(desc + "\n", style="dim white")

    t.append("\n")
    t.append("─" * 60 + "\n", style="dim white")
    t.append("\n")

    last = _load_last_scan()
    if last:
        t.append("Last scan\n", style="bold white")
        t.append("\n")
        _append_last_scan(t, last)
    else:
        t.append("No previous scan\n", style="dim white")

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
        score_style = "bold bright_green"
    elif score >= 70:
        score_style = "bold yellow"
    else:
        score_style = "bold bright_red"

    # Line 1: date · time
    t.append("  ", style="dim white")
    t.append(date_str + "\n", style="dim white")

    # Line 2: score + status badges
    t.append("  ", style="dim white")
    t.append(f"Score {score}", style=score_style)
    if critical:
        t.append(f"  ·  🔴 {critical} critical", style="bold bright_red")
    if warning:
        t.append(f"  ·  ⚠️  {warning} warnings", style="yellow")
    if not critical and not warning:
        t.append("  ·  ✨ all clear", style="bright_green")

    t.append("\n")
