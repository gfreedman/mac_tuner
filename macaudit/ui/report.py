"""
Phase 4 — Report renderer.

Renders the post-scan output:
  1. Summary panel  — health score + bar + status counts + verdict
  2. Category panels — one Rich Panel per category
  3. Recommendations panel — what to fix next (scan/targeted modes only)

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

from macaudit.checks.base import CheckResult, calculate_health_score
from macaudit.ui.theme import (
    CATEGORY_ICONS,
    COLOR_DIM,
    COLOR_TEXT,
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

_FIXABLE_LEVELS = frozenset(("auto", "auto_sudo", "guided", "instructions"))


# ── Public API ────────────────────────────────────────────────────────────────

def print_report(
    results: list[CheckResult],
    console: Console,
    issues_only: bool = False,
    explain: bool = False,
    scan_duration: float = 0.0,
    mode: str = "scan",
) -> None:
    """
    Render the complete post-scan report to the console.

    Args:
        results:       All CheckResult objects from the scan.
        console:       Rich Console to print to.
        issues_only:   If True, show only panels that have warnings/criticals.
        explain:       If True, show extra context for info/pass checks too.
        scan_duration: Wall-clock seconds the scan took (0 = not tracked).
        mode:          Active mode — "scan", "fix", or "targeted".
    """
    if not results:
        console.print("[dim]  No results to display.[/dim]")
        return

    console.print()
    console.print(build_summary_panel(results, scan_duration=scan_duration))

    for panel in build_category_panels(results, issues_only=issues_only, explain=explain):
        console.print(panel)

    recs = build_recommendations_panel(results, mode=mode)
    if recs is not None:
        console.print(recs)

    console.print()


def build_summary_panel(results: list[CheckResult], scan_duration: float = 0.0) -> Panel:
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
    score_line.append("   Health Score  ", style=f"bold {COLOR_TEXT}")
    score_line.append(f"{score:>3}", style=f"bold {score_color}")
    score_line.append("  [", style=COLOR_DIM)
    score_line.append("█" * filled, style=score_color)
    score_line.append("░" * empty,  style=COLOR_DIM)
    score_line.append("]", style=COLOR_DIM)
    score_line.append(f"  / 100", style=COLOR_DIM)

    # ── Line 2: status counts ─────────────────────────────────────────────────
    counts_line = Text()
    counts_line.append("\n   ")

    def _count_chip(icon: str, n: int, label: str, active_style: str) -> None:
        counts_line.append(icon + " ", style="bold")
        style = active_style if n > 0 else COLOR_DIM
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
        style=COLOR_DIM,
    )

    # ── Line 4: scan duration (optional) ─────────────────────────────────────
    duration_line = Text()
    if scan_duration > 0:
        n = len(results)
        dur_str = (
            f"{scan_duration:.0f}s" if scan_duration >= 10
            else f"{scan_duration:.1f}s"
        )
        duration_line.append(
            f"\n   {n} checks completed in {dur_str}",
            style=COLOR_DIM,
        )

    content = Group(score_line, counts_line, verdict_line, duration_line)

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


def build_recommendations_panel(
    results: list[CheckResult],
    mode: str = "scan",
) -> Optional[Panel]:
    """
    Build a "What to do next" panel summarising fixable items.

    Returns None when mode == "fix" (fix flow IS the next step).
    Returns None when there is nothing actionable.
    """
    if mode == "fix":
        return None

    # Collect actionable items
    actionable = [
        r for r in results
        if r.status in _ISSUE_STATUSES and r.fix_level in _FIXABLE_LEVELS
    ]
    info_fixable = [
        r for r in results
        if r.status == "info" and r.fix_level in _FIXABLE_LEVELS
    ]
    all_fixable = actionable + info_fixable
    total = len(all_fixable)

    if total == 0:
        # Nothing to fix — show a healthy system message
        body = Text()
        body.append("\n  ✨  Nothing actionable — your Mac looks healthy.\n", style="bold bright_green")
        return Panel(body, title="[bold]Recommendations[/bold]", border_style="bright_green", padding=(0, 1))

    # Sort: critical=0, warning=1, error=2, info=3
    _order = {"critical": 0, "warning": 1, "error": 2, "info": 3}
    all_fixable_sorted = sorted(all_fixable, key=lambda r: _order.get(r.status, 9))

    # Show up to 6 items
    shown = all_fixable_sorted[:6]
    remainder = total - len(shown)

    parts: list = []

    for r in shown:
        icon = STATUS_ICONS.get(r.status, "?")
        style = STATUS_STYLES.get(r.status)
        fix_label = FIX_LEVEL_LABELS.get(r.fix_level, r.fix_level)

        line1 = Text()
        line1.append(f"  {icon}  ", style=str(style))
        line1.append(r.name, style="bold")
        line1.append(f"   {r.message}", style=str(style))
        parts.append(line1)

        if r.fix_description:
            fix_text = Text()
            fix_text.append(f"· {fix_label}", style="dim cyan")
            fix_text.append(f"  —  {r.fix_description}", style=COLOR_DIM)
            parts.append(Padding(fix_text, (0, 2, 0, _INDENT)))

        parts.append(Text(""))

    if remainder > 0:
        more = Text()
        more.append(f"  … and {remainder} more fixable item{'s' if remainder != 1 else ''}", style=COLOR_DIM)
        parts.append(more)
        parts.append(Text(""))

    # CTA footer
    parts.append(Text("  " + "─" * 50, style=COLOR_DIM))
    cta = Text()
    cta.append("\n  Run  ", style=COLOR_DIM)
    cta.append("macaudit --fix", style=f"bold {COLOR_TEXT}")
    cta.append(f"  to step through {total} fixable item{'s' if total != 1 else ''} interactively.\n", style=COLOR_DIM)
    cta.append("  Add  ", style=COLOR_DIM)
    cta.append("--auto", style=f"bold {COLOR_TEXT}")
    cta.append("  to apply safe automatic fixes without prompting.\n", style=COLOR_DIM)
    parts.append(cta)

    # Border: bright_red if any critical, yellow if any warning, cyan otherwise
    has_critical = any(r.status == "critical" for r in all_fixable)
    has_warning  = any(r.status == "warning"  for r in all_fixable)
    border = "bright_red" if has_critical else "yellow" if has_warning else "cyan"

    return Panel(
        Group(*parts),
        title="[bold]Recommendations[/bold]",
        border_style=border,
        padding=(0, 1),
    )


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
                Text(result.finding_explanation, style=COLOR_DIM),
                (0, 2, 0, _INDENT),
            )
        )

    # Line 3: recommendation
    if result.recommendation:
        rec = Text()
        rec.append("→ ", style=f"bold {COLOR_TEXT}")
        rec.append(result.recommendation, style=COLOR_TEXT)
        parts.append(Padding(rec, (0, 2, 0, _INDENT)))

    # Line 4: fix info (muted)
    if result.fix_level != "none":
        fix_label = FIX_LEVEL_LABELS.get(result.fix_level, result.fix_level)
        fix_text = Text()
        fix_text.append(f"· {fix_label}", style="dim cyan")
        if result.fix_description:
            fix_text.append(f"  —  {result.fix_description}", style=COLOR_DIM)
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
            name_style = COLOR_TEXT
            msg_style  = COLOR_DIM
            icon_style = "cyan"

        name_cell = Text()
        name_cell.append(f"  {icon}  ", style=icon_style)
        name_cell.append(r.name, style=name_style)

        msg_cell = Text(f"  {r.message}", style=msg_style)

        table.add_row(name_cell, msg_cell)

        # Explain mode: add recommendation below in a second indented row
        if explain and r.recommendation and r.status in ("info", "pass"):
            blank   = Text("")
            rec     = Text(f"  → {r.recommendation}", style=COLOR_DIM)
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
