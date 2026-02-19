"""
Welcome screen.

Displayed on first run (before ~/.config/mactuner/.welcomed exists)
or with --welcome. Provides orientation, system identity, and a quick-start
command guide. Optionally shows the last scan summary if one exists.

Layout (plain stacked text — no panels, no tables):
  mactuner v1.2.0  ·  Mac System Health Inspector
  ──────────────────────────────────────────────

  Welcome, Geoff!

  [beagle art]

  macOS 26.3  ·  Apple M2  ·  MacBook Air  ·  16 GB
  /Users/geoff/path

  ──────────────────────────────────────────────
  Quick start

    mactuner              Full system health scan
    mactuner --fix        Interactive fix mode
    ...

  ──────────────────────────────────────────────
  Last scan  ·  18 Feb 2026  ·  22:06  ·  Score 94
"""

import getpass
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.text import Text

from mactuner import __version__
from mactuner.system_info import get_system_info
from mactuner.ui.header import _append_beagle
from mactuner.ui.theme import APP_NAME, APP_TAGLINE


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

_DIV = "  " + "─" * 52  # reused divider line


def _render(console: Console, info: dict, display_name: str) -> None:
    # ── Version line + underline (no Panel box) ───────────────────────────────
    hdr = Text()
    hdr.append("  ")
    hdr.append(APP_NAME, style="bold white")
    hdr.append(f"  v{__version__}", style="dim white")
    hdr.append("  ·  ", style="dim white")
    hdr.append(APP_TAGLINE, style="dim white")
    console.print(hdr)
    console.print(_DIV, style="dim white")
    console.print()

    # ── Greeting ──────────────────────────────────────────────────────────────
    console.print(f"  [bold bright_green]Welcome, {display_name}![/bold bright_green]")
    console.print()

    # ── Beagle (printed directly — no table wrapper) ──────────────────────────
    beagle = Text(justify="left")
    _append_beagle(beagle)
    console.print(beagle)

    # ── System identity ───────────────────────────────────────────────────────
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

    console.print("  " + "  ·  ".join(chip_parts), style="dim white")
    console.print("  " + str(Path.cwd()), style="dim white")
    console.print()

    # ── Quick start ───────────────────────────────────────────────────────────
    console.print(_DIV, style="dim white")
    console.print()
    console.print("  [bold white]Quick start[/bold white]")
    console.print()

    # ljust pads command to fixed width so descriptions line up — no Table needed
    _CMD_W = 22   # len("mactuner --explain") = 18, +4 breathing room
    cmds = [
        ("mactuner",           "Full system health scan"),
        ("mactuner --fix",     "Interactive fix mode — repair issues"),
        ("mactuner --only",    "Targeted scan  e.g.  --only security,disk"),
        ("mactuner --explain", "Deeper context for every finding"),
        ("mactuner --help",    "All options"),
    ]
    for cmd, desc in cmds:
        row = Text()
        row.append("    ")
        row.append(cmd.ljust(_CMD_W), style="bold white")
        row.append(desc, style="dim white")
        console.print(row)
    console.print()

    # ── Last scan ─────────────────────────────────────────────────────────────
    last = _load_last_scan()
    if last:
        console.print(_DIV, style="dim white")
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

    line = Text()
    line.append("  Last scan  ·  ", style="dim white")
    line.append(date_str, style="dim white")
    line.append("  ·  ", style="dim white")
    line.append(f"Score {score}", style=score_style)

    if critical:
        line.append(f"  ·  🔴 {critical} critical", style="bold bright_red")
    if warning:
        line.append(f"  ·  ⚠️  {warning} warnings", style="yellow")
    if not critical and not warning:
        line.append("  ·  ✨ all clear", style="bright_green")

    console.print(line)
