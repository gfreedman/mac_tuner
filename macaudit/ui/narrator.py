"""
ScanNarrator — live narrated scan UI (parallel mode).

Wraps rich.live.Live to show two layers:

  1. Completed checks — printed above (scroll naturally, in input order)
  2. Progress area    — spinner + "Running checks…" + progress bar (live)

Usage:
    with ScanNarrator(console, total=len(checks)) as narrator:
        narrator.print_scan_header()
        # ... submit checks to ThreadPoolExecutor ...
        # on each completion:
        narrator.increment()
        narrator.print_result(result)  # call in input order
"""

from rich.console import Console, Group
from rich.live import Live
from rich.padding import Padding
from rich.spinner import Spinner
from rich.text import Text

from macaudit.checks.base import CheckResult
from macaudit.ui.progress import render_progress
from macaudit.ui.theme import CATEGORY_ICONS, COLOR_DIM, COLOR_TEXT, STATUS_ICONS, STATUS_STYLES


class ScanNarrator:
    """
    Context manager for live scan feedback during parallel execution.

    Completed results are printed in input order above the live area.
    The live area shows a spinner + progress bar while checks run.
    """

    def __init__(self, console: Console, total: int) -> None:
        self.console = console
        self.total = total
        self.completed = 0
        self._last_category: str | None = None

        self._live = Live(
            console=console,
            refresh_per_second=12,
            transient=False,
        )

    # ── Context manager ───────────────────────────────────────────────────────

    def __enter__(self) -> "ScanNarrator":
        self._live.__enter__()
        self._live.update(self._render_parallel())
        return self

    def __exit__(self, *args) -> None:
        # Replace live area with final progress bar (100% if all ran)
        self._live.update(_idle_bar(self.completed, self.total))
        self._live.__exit__(*args)
        self.console.print()  # breathing room after last check

    # ── Public API ────────────────────────────────────────────────────────────

    def increment(self) -> None:
        """Bump completed count and refresh the live progress area."""
        self.completed += 1
        self._live.update(self._render_parallel())

    def print_result(self, result: CheckResult) -> None:
        """Print a completed check result above the live area, with category headers."""
        if result.category != self._last_category:
            if self._last_category is not None:
                self._live.console.print()  # spacing between categories
            self._live.console.print(_format_category_header(result.category, self.console.width))
            self._last_category = result.category
        self._live.console.print(_format_result(result))

    def print_scan_header(self) -> None:
        """Print a 'Scanning…' label before the first check."""
        self._live.console.print()
        label = Text()
        label.append("  Scanning", style="bold magenta")
        label.append("  —  ", style=COLOR_DIM)
        label.append("checks run in parallel", style=COLOR_DIM)
        self._live.console.print(label)
        self._live.console.print()

    # ── Internal rendering ────────────────────────────────────────────────────

    def _render_parallel(self) -> Group:
        """
        Live area while checks run in parallel:

          ⠋  Running checks…

          [████████░░░░░░░░░░░░░░] 34%  ·  8 of 23 checks
        """
        spinner = Spinner(
            "dots",
            text=Text("  Running checks…", style=COLOR_DIM),
            style="cyan",
        )
        spinner_indented = Padding(spinner, pad=(0, 0, 0, 4))

        progress = Padding(
            render_progress(self.completed, self.total),
            pad=(1, 0, 0, 0),
        )

        return Group(spinner_indented, progress)


# ── Module-level helpers ──────────────────────────────────────────────────────


def _idle_bar(completed: int, total: int) -> Padding:
    """Progress bar with blank line above (shown between checks)."""
    return Padding(render_progress(completed, total), pad=(1, 0, 0, 0))


def _format_category_header(category: str, console_width: int = 80) -> Group:
    """Bold category header with thin underline: e.g. '  💻  System'"""
    icon = CATEGORY_ICONS.get(category, "  ")
    name = category.replace("_", " ").title()
    header = Text()
    header.append(f"  {icon}  ", style="bold")
    header.append(name, style=f"bold {COLOR_TEXT}")
    rule_width = min(44, console_width - 6)
    rule = Text("  " + "─" * rule_width, style=COLOR_DIM)
    return Group(header, rule)


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
    line.append(result.name.ljust(38), style=str(style))
    line.append(f"  {result.message}", style=COLOR_DIM)

    return line
