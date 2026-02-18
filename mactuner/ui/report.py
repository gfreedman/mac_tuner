"""
Phase 4 — Report renderer.

Renders the post-scan output:
  1. Summary panel  — health score + bar + status counts + verdict
  2. Category panels — one Rich Panel per category

Failing checks (critical / warning / error): 4 lines
  • Line 1: status icon + name + short message
  • Line 2: finding explanation  (why it matters)
  • Line 3: recommendation       (what to do)
  • Line 4: fix info             (muted, how to fix)

Passing checks: 1 line
Info checks: 1–2 lines
Skipped checks: 1 line (very dim)
"""

from collections import defaultdict
from typing import Optional

from rich.console import Console, Group
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from mactuner.checks.base import CheckResult, calculate_health_score
from mactuner.ui.theme import (
    CATEGORY_ICONS,
    FIX_LEVEL_LABELS,
    MACTUNER_THEME,
    STATUS_ICONS,
    STATUS_STYLES,
)


# ── Constants ─────────────────────────────────────────────────────────────────

# Render order for category panels
_CATEGORY_ORDER = [
    "system", "security", "privacy",
    "homebrew", "disk", "hardware",
    "memory", "network", "dev_env", "apps",
]

_ISSUE_STATUSES = frozenset(("critical", "warning", "error"))

# Indentation for explanation / recommendation / fix lines
_INDENT = 8


# ── Public API ────────────────────────────────────────────────────────────────

def print_report(
    results: list[CheckResult],
    console: Console,
    issues_only: bool = False,
    explain: bool = False,
) -> None:
    """
    Render the complete post-scan report to the console.

    Args:
        results:     All CheckResult objects from the scan.
        console:     Rich Console to print to.
        issues_only: If True, show only panels that have warnings/criticals.
        explain:     If True, show extra context for info/pass checks too.
    """
    if not results:
        console.print("[dim]  No results to display.[/dim]")
        return

    console.print()
    console.print(build_summary_panel(results))

    for panel in build_category_panels(results, issues_only=issues_only, explain=explain):
        console.print(panel)

    console.print()


def build_summary_panel(results: list[CheckResult]) -> Panel:
    """Return the top-level Summary Panel."""
    score = calculate_health_score(results)

    counts: dict[str, int] = defaultdict(int)
    for r in results:
        counts[r.status] += 1

    critical = counts["critical"]
    warnings = counts["warning"]
    passed   = counts["pass"]
    info     = counts["info"]
    errors   = counts["error"]

    # Score colour
    if score >= 90:
        score_color = "bright_green"
    elif score >= 75:
        score_color = "green"
    elif score >= 55:
        score_color = "yellow"
    else:
        score_color = "bright_red"

    # Score bar (22 chars wide)
    bar_width = 22
    filled = round(bar_width * score / 100)
    empty  = bar_width - filled

    # ── Line 1: score ─────────────────────────────────────────────────────────
    score_line = Text()
    score_line.append("   Health Score  ", style="bold white")
    score_line.append(f"{score:>3}", style=f"bold {score_color}")
    score_line.append("  [", style="dim white")
    score_line.append("█" * filled, style=score_color)
    score_line.append("░" * empty,  style="dim white")
    score_line.append("]", style="dim white")
    score_line.append(f"  / 100", style="dim white")

    # ── Line 2: status counts ─────────────────────────────────────────────────
    counts_line = Text()
    counts_line.append("\n   ")

    def _count_chip(icon: str, n: int, label: str, active_style: str) -> None:
        counts_line.append(icon + " ", style="bold")
        style = active_style if n > 0 else "dim white"
        counts_line.append(f"{n}  {label}", style=style)
        counts_line.append("    ")

    _count_chip("🔴", critical, "Critical", "bold bright_red")
    _count_chip("⚠️ ", warnings, "Warnings", "bold yellow")
    _count_chip("✅", passed,   "Passed",   "bold bright_green")
    _count_chip("ℹ️ ", info,    "Info",     "cyan")
    if errors:
        _count_chip("❌", errors, "Errors", "bold bright_red")

    # ── Line 3: verdict ───────────────────────────────────────────────────────
    verdict_line = Text()
    verdict_line.append(
        f"\n   {_score_verdict(score, critical, warnings)}",
        style="dim white",
    )

    content = Group(score_line, counts_line, verdict_line)

    # Panel border follows worst status
    border = (
        "bright_red" if critical or errors
        else "yellow"   if warnings
        else "bright_green"
    )

    return Panel(
        content,
        title="[bold]Summary[/bold]",
        border_style=border,
        padding=(1, 2),
    )


def build_category_panels(
    results: list[CheckResult],
    issues_only: bool = False,
    explain: bool = False,
) -> list[Panel]:
    """Return one Panel per category that has results worth showing."""
    # Group by category, preserving original order
    by_cat: dict[str, list[CheckResult]] = {}
    for r in results:
        by_cat.setdefault(r.category, []).append(r)

    # Render in spec-defined order, then any extra categories
    order = _CATEGORY_ORDER + [c for c in by_cat if c not in _CATEGORY_ORDER]

    panels = []
    for cat in order:
        if cat not in by_cat:
            continue
        panel = _build_category_panel(cat, by_cat[cat], issues_only, explain)
        if panel is not None:
            panels.append(panel)

    return panels


# ── Internal: category panel ──────────────────────────────────────────────────

def _build_category_panel(
    category: str,
    results: list[CheckResult],
    issues_only: bool,
    explain: bool,
) -> Optional[Panel]:
    """Build one category panel; returns None if there is nothing to show."""
    issues  = [r for r in results if r.status in _ISSUE_STATUSES]
    infos   = [r for r in results if r.status == "info"]
    passes  = [r for r in results if r.status == "pass"]
    skips   = [r for r in results if r.status == "skip"]

    if issues_only and not issues:
        return None

    parts: list = []

    # ── Issues (critical → warning → error) ───────────────────────────────────
    for r in sorted(issues, key=lambda r: {"critical": 0, "warning": 1, "error": 2}.get(r.status, 9)):
        parts.extend(_render_issue(r))
        parts.append(Text(""))  # blank line between issues

    # ── Info + Pass + Skip — rendered in one aligned table ───────────────────
    if not issues_only:
        compact = infos + passes + skips
        if compact:
            if issues:
                pass  # already have a blank line from the issue loop
            parts.append(_compact_table(compact, explain))

    if not parts:
        return None

    icon     = CATEGORY_ICONS.get(category, "  ")
    cat_name = category.replace("_", " ").title()
    title    = f"{icon} {cat_name}"

    # Border: worst status in the category
    if any(r.status == "critical" for r in results):
        border = "bright_red"
    elif any(r.status in ("warning", "error") for r in results):
        border = "yellow"
    else:
        border = "dim"

    return Panel(
        Group(*parts),
        title=f"[bold]{title}[/bold]",
        border_style=border,
        padding=(0, 1),
    )


# ── Internal: individual check renderers ──────────────────────────────────────

def _render_issue(result: CheckResult) -> list:
    """
    Critical / warning / error — up to 4 lines.

    Returns a list of renderables (Text + Padding objects).
    """
    icon  = STATUS_ICONS.get(result.status, "?")
    style = STATUS_STYLES.get(result.status)

    parts: list = []

    # Line 1: icon + name + message
    line1 = Text()
    line1.append(f"  {icon}  ", style=str(style))
    line1.append(result.name, style=f"bold")
    line1.append(f"   {result.message}", style=str(style))
    parts.append(line1)

    # Line 2: finding explanation (indented, wraps correctly)
    if result.finding_explanation:
        parts.append(
            Padding(
                Text(result.finding_explanation, style="dim white"),
                (0, 2, 0, _INDENT),
            )
        )

    # Line 3: recommendation
    if result.recommendation:
        rec = Text()
        rec.append("→ ", style="white bold")
        rec.append(result.recommendation, style="white")
        parts.append(Padding(rec, (0, 2, 0, _INDENT)))

    # Line 4: fix info (muted)
    if result.fix_level != "none":
        fix_label = FIX_LEVEL_LABELS.get(result.fix_level, result.fix_level)
        fix_text = Text()
        fix_text.append(f"· {fix_label}", style="dim cyan")
        if result.fix_description:
            fix_text.append(f"  —  {result.fix_description}", style="dim white")
        if result.fix_reversible is False:
            fix_text.append("  [irreversible]", style="dim red")
        parts.append(Padding(fix_text, (0, 2, 0, _INDENT)))

    return parts


def _compact_table(results: list[CheckResult], explain: bool = False) -> Table:
    """
    Render info / pass / skip checks as a two-column aligned table.

    Column 1 (fixed): icon + name
    Column 2 (flex):  message — wraps independently so continuation lines
                      stay under the message, not reset to column 0.
    """
    table = Table(
        show_header=False,
        show_edge=False,
        show_lines=False,
        box=None,
        padding=(0, 0),
        expand=False,
    )
    # Name column: icon (~6) + name (up to 36) = ~42 chars.
    # no_wrap=True + max_width prevent squeezing the message column on narrow terms.
    table.add_column("name", no_wrap=True, min_width=40, max_width=44)
    # Message column: fills remaining panel width
    table.add_column("message", ratio=1)

    for r in results:
        icon  = STATUS_ICONS.get(r.status, "?")
        style = STATUS_STYLES.get(r.status)

        if r.status == "pass":
            name_style = "dim"
            msg_style  = "dim"
            icon_style = "bright_green"
        elif r.status == "skip":
            name_style = "dim"
            msg_style  = "dim"
            icon_style = "dim"
        else:  # info
            name_style = "white"
            msg_style  = "dim white"
            icon_style = "cyan"

        name_cell = Text()
        name_cell.append(f"  {icon}  ", style=icon_style)
        name_cell.append(r.name, style=name_style)

        msg_cell = Text(f"  {r.message}", style=msg_style)

        table.add_row(name_cell, msg_cell)

        # Explain mode: add recommendation below in a second indented row
        if explain and r.recommendation and r.status in ("info", "pass"):
            blank   = Text("")
            rec     = Text(f"  → {r.recommendation}", style="dim white")
            table.add_row(blank, rec)

    return table


# ── Verdict copy ──────────────────────────────────────────────────────────────

def _score_verdict(score: int, critical: int, warnings: int) -> str:
    if critical >= 3:
        return f"🚨  {critical} critical issues detected — review the red items immediately."
    if critical > 0:
        return f"🚨  {critical} critical issue{'s' if critical > 1 else ''} detected — address these first."
    if score >= 95:
        return "✨  Excellent — your Mac is well configured and up to date."
    if score >= 85:
        return "👍  Very good — a few things worth tuning."
    if score >= 70:
        return "📋  Good — some settings could be tightened for better security."
    if score >= 55:
        return "⚠️   Fair — several issues should be addressed soon."
    return "🚨  Poor — significant security gaps detected. Start with the red items."
