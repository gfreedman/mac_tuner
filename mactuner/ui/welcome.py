"""
Welcome screen.

Displayed on first run (before ~/.config/mactuner/.welcomed exists)
or with --welcome. Provides orientation, system identity, and a quick-start
command guide. Optionally shows the last scan summary if one exists.

Layout:
  header bar   mactuner v1.2.0 · Mac System Health Inspector
  greeting     Welcome, Geoff!                           [bright green]
  ident        beagle art left | macOS · CPU · model · RAM right
               cwd line
  divider
  quick start  aligned command → description table
  divider      (only if last_scan exists)
  last scan    date · score · counts
"""

import getpass
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from mactuner import __version__
from mactuner.system_info import get_system_info
from mactuner.ui.header import _append_beagle
from mactuner.ui.theme import APP_NAME, APP_TAGLINE, COLOR_BRAND


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
        console.print()
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
    # ── Header bar ────────────────────────────────────────────────────────────
    hdr = Text()
    hdr.append(f" {APP_NAME} ", style="bold white")
    hdr.append(f"v{__version__}", style="dim white")
    hdr.append("  ·  ", style="dim white")
    hdr.append(APP_TAGLINE, style="dim white")
    hdr.append(" ")
    console.print(Panel(hdr, border_style=COLOR_BRAND, padding=(0, 1)))
    console.print()

    # ── Greeting ──────────────────────────────────────────────────────────────
    console.print(
        f"  [bold bright_green]Welcome, {display_name}![/bold bright_green]"
    )

    # ── Beagle + system identity (tight side-by-side) ─────────────────────────
    beagle = Text(justify="left")
    _append_beagle(beagle)

    macos_name = info.get("macos_name", "")
    macos_ver  = info.get("macos_version", "")
    macos_str  = (
        f"macOS {macos_name} {macos_ver}"
        if macos_name and not macos_name.isdigit()
        else f"macOS {macos_ver}"
    )
    cpu   = info.get("cpu_brand", "") or info.get("architecture", "")
    model = info.get("model_name", "Mac")
    ram   = info.get("ram_gb", 0)

    chip_parts = [p for p in [macos_str, cpu, model] if p]
    if ram:
        chip_parts.append(f"{ram} GB")

    # Right column: blank line 1 aligns info with body (line 2), cwd with belly (line 3)
    right = Text(justify="left")
    right.append("\n")
    right.append("  ·  ".join(chip_parts) + "\n", style="dim white")
    right.append(str(Path.cwd()), style="dim white")

    # padding=(0, 2): 2-char gap on left/right of each cell — keeps art and info tight
    ident = Table(box=None, show_header=False, padding=(0, 2), expand=False)
    ident.add_column(width=16, justify="left")   # exactly fits 16-char wide art
    ident.add_column(justify="left")
    ident.add_row(beagle, right)
    console.print()
    console.print(ident)
    console.print()

    # ── Divider ───────────────────────────────────────────────────────────────
    console.print("  " + "─" * 52, style="dim white")
    console.print()

    # ── Quick start ───────────────────────────────────────────────────────────
    console.print("  [bold white]Quick start[/bold white]")
    console.print()

    cmds = [
        ("mactuner",           "Full system health scan"),
        ("mactuner --fix",     "Interactive fix mode — repair issues"),
        ("mactuner --only",    "Targeted scan  e.g.  --only security,disk"),
        ("mactuner --explain", "Deeper context for every finding"),
        ("mactuner --help",    "All options"),
    ]
    cmd_tbl = Table(box=None, show_header=False, padding=(0, 0), expand=False)
    cmd_tbl.add_column(width=30, no_wrap=True)
    cmd_tbl.add_column(justify="left")
    for cmd, desc in cmds:
        name = Text()
        name.append("    ")
        name.append(cmd, style="bold white")
        cmd_tbl.add_row(name, Text(desc, style="dim white"))
    console.print(cmd_tbl)
    console.print()

    # ── Last scan ─────────────────────────────────────────────────────────────
    last = _load_last_scan()
    if last:
        console.print("  " + "─" * 52, style="dim white")
        console.print()
        _render_last_scan(console, last)
        console.print()


# ── Last scan helpers ─────────────────────────────────────────────────────────

def _load_last_scan() -> Optional[dict]:
    try:
        data = json.loads(_LAST_SCAN.read_text())
        if "score" in data and "date" in data:
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return None


def _render_last_scan(console: Console, data: dict) -> None:
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

    # Line 1: label + date
    line1 = Text()
    line1.append("  Last scan  ", style="dim white")
    line1.append(date_str, style="dim white")
    console.print(line1)

    # Line 2: score + issue counts (indented to align under date)
    line2 = Text()
    line2.append("  Score ", style="dim white")
    line2.append(str(score), style=score_style)

    if critical:
        line2.append(f"  ·  🔴 {critical} critical", style="bold bright_red")
    if warning:
        line2.append(f"  ·  ⚠️  {warning} warnings", style="yellow")
    if not critical and not warning:
        line2.append("  ·  ✨ all clear", style="bright_green")

    console.print(line2)
