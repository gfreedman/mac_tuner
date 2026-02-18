"""
Fix session orchestrator.

Presents an interactive checkbox menu of fixable issues (using questionary),
handles per-fix confirmation, and routes each fix to the correct executor.

Fix level behaviour in the menu:
  auto         — pre-selected if reversible and no sudo
  auto_sudo    — not pre-selected (requires password)
  guided       — not pre-selected (opens System Settings)
  instructions — not pre-selected (just prints steps)

--auto mode bypasses the menu and applies all safe AUTO fixes directly.
"""

from __future__ import annotations

from rich.console import Console
from rich.padding import Padding
from rich.text import Text

from mactuner.checks.base import CheckResult
from mactuner.fixer.executor import (
    run_auto_fix,
    run_auto_sudo_fix,
    run_guided_fix,
    run_instructions_fix,
)


# ── Constants ─────────────────────────────────────────────────────────────────

_FIXABLE_STATUSES = frozenset(("warning", "critical", "error"))
_FIXABLE_LEVELS   = frozenset(("auto", "auto_sudo", "guided", "instructions"))

_SEVERITY_ORDER = {"critical": 0, "warning": 1, "error": 2}

_LEVEL_EMOJI = {
    "auto":          "🤖",
    "auto_sudo":     "🤖🔐",
    "guided":        "👆",
    "instructions":  "📋",
}

_LEVEL_LABEL = {
    "auto":          "Automatic",
    "auto_sudo":     "Requires password",
    "guided":        "Opens Settings",
    "instructions":  "Step-by-step",
}


# ── Public API ────────────────────────────────────────────────────────────────

def run_fix_session(
    results: list[CheckResult],
    console: Console,
    auto: bool = False,
) -> None:
    """
    Run the interactive fix session.

    Args:
        results: All check results from the scan.
        console: Rich Console (shared with rest of tool).
        auto:    If True, apply reversible AUTO fixes without prompting.
    """
    fixable = _get_fixable(results)

    console.print()
    console.rule("[bold]Fix Mode[/bold]", style="dim")
    console.print()

    if not fixable:
        console.print(
            "  [bright_green]✨  Nothing to fix — your system looks healthy![/bright_green]"
        )
        console.print()
        return

    if auto:
        _run_auto_mode(fixable, console)
    else:
        _run_interactive_mode(fixable, console)


# ── Interactive mode ──────────────────────────────────────────────────────────

def _run_interactive_mode(fixable: list[CheckResult], console: Console) -> None:
    """Show questionary checkbox, confirm each fix, execute."""
    try:
        import questionary
    except ImportError:
        console.print(
            "[red]questionary not installed — run: pip install questionary[/red]\n"
        )
        return

    _print_fix_legend(console)
    _print_fixable_summary(fixable, console)

    choices = _build_choices(fixable, questionary)

    try:
        selected = questionary.checkbox(
            "Select fixes to apply  (Space to toggle, Enter to confirm):",
            choices=choices,
            style=_questionary_style(questionary),
        ).ask()
    except KeyboardInterrupt:
        console.print("\n  [dim]Fix mode cancelled.[/dim]\n")
        return

    if selected is None or len(selected) == 0:
        console.print("\n  [dim]No fixes selected — exiting fix mode.[/dim]\n")
        return

    console.print()
    _execute_fixes(selected, console, confirm_each=True)


# ── Auto mode ─────────────────────────────────────────────────────────────────

def _run_auto_mode(fixable: list[CheckResult], console: Console) -> None:
    """Apply all safe AUTO fixes without interactive menu or per-fix prompts."""
    safe = [
        r for r in fixable
        if r.fix_level == "auto"
        and r.fix_reversible
        and not r.requires_sudo
    ]

    if not safe:
        console.print(
            "  [dim]No safe AUTO fixes available.\n"
            "  Run without --auto to see all fixable issues interactively.[/dim]\n"
        )
        return

    console.print(
        f"  Applying [bold]{len(safe)}[/bold] safe, reversible "
        f"AUTO fix{'es' if len(safe) != 1 else ''}…"
    )
    console.print()

    _execute_fixes(safe, console, confirm_each=False)


# ── Execution loop ────────────────────────────────────────────────────────────

def _execute_fixes(
    selected: list[CheckResult],
    console: Console,
    confirm_each: bool,
) -> None:
    """Iterate selected fixes: optionally confirm, then dispatch."""
    applied = 0
    skipped = 0

    for idx, result in enumerate(selected, 1):
        _print_fix_header(console, result, idx, len(selected))

        if confirm_each:
            try:
                import questionary
                confirmed = questionary.confirm(
                    "  Apply this fix?",
                    default=False,
                ).ask()
            except (ImportError, KeyboardInterrupt):
                confirmed = False

            if not confirmed:
                console.print("  [dim]Skipped.[/dim]\n")
                skipped += 1
                continue

        success = _dispatch(result, console)
        if success:
            applied += 1
        else:
            skipped += 1

    _print_session_summary(console, applied, skipped, len(selected))


def _dispatch(result: CheckResult, console: Console) -> bool:
    """Route to the correct executor."""
    dispatch_map = {
        "auto":         run_auto_fix,
        "auto_sudo":    run_auto_sudo_fix,
        "guided":       run_guided_fix,
        "instructions": run_instructions_fix,
    }
    fn = dispatch_map.get(result.fix_level)
    if fn is None:
        console.print("  [dim]No executor for this fix level.[/dim]\n")
        return False
    return fn(result, console)


# ── UI helpers ────────────────────────────────────────────────────────────────

def _get_fixable(results: list[CheckResult]) -> list[CheckResult]:
    """Return fixable results sorted by severity (critical first)."""
    fixable = [
        r for r in results
        if r.status in _FIXABLE_STATUSES
        and r.fix_level in _FIXABLE_LEVELS
    ]
    return sorted(fixable, key=lambda r: _SEVERITY_ORDER.get(r.status, 9))


def _build_choices(fixable: list[CheckResult], questionary) -> list:
    """Build questionary Choice objects, pre-selecting safe AUTO fixes."""
    choices = []
    for r in fixable:
        emoji = _LEVEL_EMOJI.get(r.fix_level, "·")
        irreversible = "  [irreversible]" if not r.fix_reversible else ""
        label = f"  {emoji}  {r.name}  —  {r.message}{irreversible}"

        preselected = (
            r.fix_level == "auto"
            and r.fix_reversible
            and not r.requires_sudo
        )

        choices.append(
            questionary.Choice(title=label, value=r, checked=preselected)
        )
    return choices


def _questionary_style(questionary):
    """Consistent colour style for the questionary prompt."""
    return questionary.Style([
        ("qmark",       "fg:#61afef bold"),
        ("question",    "bold"),
        ("pointer",     "fg:#61afef bold"),
        ("highlighted", "fg:#61afef bold"),
        ("selected",    "fg:#98c379"),
        ("separator",   "fg:#586e75"),
        ("instruction", "fg:#586e75 italic"),
        ("answer",      "fg:#f8f8f2 bg:#282c34"),
    ])


def _print_fix_legend(console: Console) -> None:
    legend = Text("  ")
    for level, emoji in _LEVEL_EMOJI.items():
        legend.append(f"{emoji} {_LEVEL_LABEL[level]}    ", style="dim")
    console.print(legend)
    console.print()


def _print_fixable_summary(fixable: list[CheckResult], console: Console) -> None:
    counts: dict[str, int] = {}
    for r in fixable:
        counts[r.fix_level] = counts.get(r.fix_level, 0) + 1

    parts = []
    for level in ("auto", "auto_sudo", "guided", "instructions"):
        n = counts.get(level, 0)
        if n:
            parts.append(
                f"[bold]{n}[/bold] {_LEVEL_EMOJI[level]} {_LEVEL_LABEL[level]}"
            )

    console.print(f"  Found {len(fixable)} fixable issues:  " + "    ".join(parts))
    console.print(
        "  [dim](Pre-selected: safe AUTO fixes. "
        "Use Space to toggle, Enter to confirm.)[/dim]"
    )
    console.print()


def _print_fix_header(
    console: Console,
    result: CheckResult,
    index: int,
    total: int,
) -> None:
    emoji = _LEVEL_EMOJI.get(result.fix_level, "·")
    label = _LEVEL_LABEL.get(result.fix_level, result.fix_level)

    console.print(
        f"  [dim][{index}/{total}][/dim]  "
        f"[bold]{result.name}[/bold]  "
        f"[dim]{emoji} {label}[/dim]"
    )
    console.print(f"  [dim]{result.fix_description}[/dim]")

    if not result.fix_reversible:
        console.print("  [bold red]  ⚠️   This action cannot be undone[/bold red]")

    if result.fix_time_estimate and result.fix_time_estimate != "N/A":
        console.print(f"  [dim]Estimated time: {result.fix_time_estimate}[/dim]")

    console.print()


def _print_session_summary(
    console: Console,
    applied: int,
    skipped: int,
    total: int,
) -> None:
    console.rule(style="dim")
    console.print()

    if applied == 0:
        console.print("  [dim]No fixes were applied.[/dim]")
    else:
        s = "es" if applied != 1 else ""
        console.print(
            f"  [bright_green]✅  {applied} fix{s} applied[/bright_green]"
            + (f"  [dim]({skipped} skipped)[/dim]" if skipped else "")
        )

    console.print()
