"""
ScanNarrator — live narrated scan UI.

Wraps rich.live.Live to show three layers:

  1. Completed checks — printed above (scroll naturally)
  2. Current check   — category icon + name + description + spinner (live)
  3. Progress bar    — always at bottom (live)

Usage:
    with ScanNarrator(console, total=len(checks)) as narrator:
        for check in checks:
            narrator.start_check(check)
            result = check.execute()
            narrator.finish_check(result)
"""

from rich.console import Console, Group
from rich.live import Live
from rich.padding import Padding
from rich.spinner import Spinner
from rich.text import Text

from mactuner.checks.base import BaseCheck, CheckResult
from mactuner.ui.progress import render_progress
from mactuner.ui.theme import CATEGORY_ICONS, COLOR_TEXT, STATUS_ICONS, STATUS_STYLES


class ScanNarrator:
    """
    Context manager for live narrated scan feedback.

    Each check gets:
      • A "what we're checking and why" panel (dim, wraps naturally)
      • An animated spinner while running
      • A one-line result when done (printed and kept in scroll history)
      • A progress bar that advances at the bottom
    """

    def __init__(self, console: Console, total: int) -> None:
        self.console = console
        self.total = total
        self.completed = 0

        # State for the currently-running check
        self._current_name: str = ""
        self._current_icon: str = ""
        self._current_description: str = ""

        # Shared spinner — Live refreshes it at refresh_per_second
        self._spinner = Spinner("dots", style="cyan")

        self._live = Live(
            console=console,
            refresh_per_second=12,
            transient=False,
        )

    # ── Context manager ───────────────────────────────────────────────────────

    def __enter__(self) -> "ScanNarrator":
        self._live.__enter__()
        # Show idle progress bar immediately so the terminal isn't blank
        self._live.update(_idle_bar(self.completed, self.total))
        return self

    def __exit__(self, *args) -> None:
        # Replace live area with final progress bar (100% if all ran)
        self._live.update(_idle_bar(self.completed, self.total))
        self._live.__exit__(*args)
        self.console.print()  # breathing room after last check

    # ── Public API ────────────────────────────────────────────────────────────

    def start_check(self, check: BaseCheck) -> None:
        """Call immediately before check.execute()."""
        self._current_name = check.name
        self._current_icon = CATEGORY_ICONS.get(check.category, "  ")
        self._current_description = check.scan_description
        self._live.update(self._render_running())

    def finish_check(self, result: CheckResult) -> None:
        """Call immediately after check.execute() returns a result."""
        self.completed += 1
        # Print the completed line above the live area (scrolls up naturally)
        self._live.console.print(_format_result(result))
        # Update progress bar
        self._live.update(_idle_bar(self.completed, self.total))

    def print_scan_header(self) -> None:
        """Print a 'Scanning…' label before the first check."""
        self._live.console.print()
        label = Text()
        label.append("  Scanning", style="bold magenta")
        label.append("  —  ", style="dim white")
        label.append("every check is explained as it runs", style="dim white")
        self._live.console.print(label)
        self._live.console.print()

    # ── Internal rendering ────────────────────────────────────────────────────

    def _render_running(self) -> Group:
        """
        Live panel shown while a check is in progress:

          🖥️  macOS Version Check
               Checking if macOS is current — security updates patch known
               vulnerabilities that attackers actively exploit.
          ⠋  Running…

          [████████░░░░░░░░░░░░░░] 34%  ·  8 of 23 checks
        """
        # Line 1: category icon + check name
        title = Text()
        title.append(f"\n  {self._current_icon} ", style=f"bold {COLOR_TEXT}")
        title.append(self._current_name, style=f"bold {COLOR_TEXT}")

        # Line 2: description (rich wraps long lines automatically)
        description = Text(
            f"     {self._current_description}", style="dim white"
        )

        # Spinner line — Spinner(text=…) renders "⠋ Running…" on one line
        spinner = Spinner(
            "dots",
            text=Text("  Running…", style="dim white"),
            style="cyan",
        )
        spinner_indented = Padding(spinner, pad=(0, 0, 0, 4))

        # Progress bar with a blank line above it
        progress = Padding(
            render_progress(self.completed, self.total),
            pad=(1, 0, 0, 0),
        )

        return Group(title, description, spinner_indented, progress)


# ── Module-level helpers ──────────────────────────────────────────────────────


def _idle_bar(completed: int, total: int) -> Padding:
    """Progress bar with blank line above (shown between checks)."""
    return Padding(render_progress(completed, total), pad=(1, 0, 0, 0))


def _format_result(result: CheckResult) -> Text:
    """
    One-line completed result:
      ✅  macOS Version Check              macOS 15.3 is current
      ⚠️   FileVault                        Disk encryption is disabled
    """
    icon = STATUS_ICONS.get(result.status, "?")
    style = STATUS_STYLES.get(result.status)

    line = Text()
    line.append(f"  {icon}  ", style=str(style))
    line.append(result.name.ljust(36), style=str(style))
    line.append(f"  {result.message}", style="dim white")

    return line
