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

from rich.console import Console, Group
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from macaudit.checks.base import CheckResult, calculate_health_score
from macaudit.enums import CheckStatus, FixLevel
from macaudit.ui.progress import BAR_WIDTH
from macaudit.ui.theme import (
    BORDER_CRITICAL,
    BORDER_DIM,
    BORDER_NEUTRAL,
    BORDER_PASS,
    BORDER_WARNING,
    CATEGORY_ICONS,
    COLOR_CRITICAL,
    COLOR_DIM,
    COLOR_PASS,
    COLOR_TEXT,
    FIX_LEVEL_LABELS,
    ICON_MDM,
    MDM_CHECK_IDS,
    STATUS_ICONS,
    STATUS_STYLES,
    score_color,
)


# ── Constants ─────────────────────────────────────────────────────────────────

# Render order for category panels (matches canonical section flow in the report)
_CATEGORY_ORDER = [
    "system", "security", "privacy",
    "homebrew", "disk", "hardware",
    "memory", "network", "dev_env", "apps",
]

_ISSUE_STATUSES: frozenset[CheckStatus] = frozenset((
    CheckStatus.CRITICAL,
    CheckStatus.WARNING,
    CheckStatus.ERROR,
))

# Indentation for explanation / recommendation / fix lines
_INDENT = 8

_FIXABLE_LEVELS: frozenset[FixLevel] = frozenset((
    FixLevel.AUTO,
    FixLevel.AUTO_SUDO,
    FixLevel.GUIDED,
    FixLevel.INSTRUCTIONS,
))

# Sort keys for severity-descending ordering of issue results
_ISSUE_SEVERITY_ORDER: dict[CheckStatus, int] = {
    CheckStatus.CRITICAL: 0,
    CheckStatus.WARNING:  1,
    CheckStatus.ERROR:    2,
}


# ── Public API ────────────────────────────────────────────────────────────────

def print_report(
    results: list[CheckResult],
    console: Console,
    issues_only: bool = False,
    explain: bool = False,
    scan_duration: float = 0.0,
    mode: str = "scan",
    mdm_enrolled: bool = False,
    diff: dict | None = None,
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
        mdm_enrolled:  If True, show inline MDM badges on relevant findings.
        diff:          Structured diff dict from compute_diff(), or None.
    """
    if not results:
        console.print("[dim]  No results to display.[/dim]")
        return

    console.print()
    console.print(build_summary_panel(results, scan_duration=scan_duration))

    if diff is not None:
        console.print(build_diff_panel(diff))

    for panel in build_category_panels(results, issues_only=issues_only, explain=explain,
                                       mdm_enrolled=mdm_enrolled):
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

    critical = counts[CheckStatus.CRITICAL]
    warnings = counts[CheckStatus.WARNING]
    passed   = counts[CheckStatus.PASS]
    info     = counts[CheckStatus.INFO]
    errors   = counts[CheckStatus.ERROR]

    # Score colour
    sc = score_color(score)

    # Score bar
    bar_width = BAR_WIDTH
    filled = round(bar_width * score / 100)
    empty  = bar_width - filled

    # ── Line 1: score ─────────────────────────────────────────────────────────
    score_line = Text()
    score_line.append("   Health Score  ", style=f"bold {COLOR_TEXT}")
    score_line.append(f"{score:>3}", style=f"bold {sc}")
    score_line.append("  [", style=COLOR_DIM)
    score_line.append("█" * filled, style=sc)
    score_line.append("░" * empty,  style=COLOR_DIM)
    score_line.append("]", style=COLOR_DIM)
    score_line.append("  / 100", style=COLOR_DIM)

    # ── Line 2: status counts ─────────────────────────────────────────────────
    counts_line = Text()
    counts_line.append("\n   ")

    def _count_chip(icon: str, n: int, label: str, active_style: str) -> None:
        counts_line.append(icon + " ", style="bold")
        style = active_style if n > 0 else COLOR_DIM
        counts_line.append(f"{n}  {label}", style=style)
        counts_line.append("    ")

    _count_chip(STATUS_ICONS["critical"], critical, "Critical", "bold bright_red")
    _count_chip(STATUS_ICONS["warning"], warnings, "Warnings", "bold yellow")
    _count_chip(STATUS_ICONS["pass"],    passed,   "Passed",   "bold bright_green")
    _count_chip(STATUS_ICONS["info"],    info,     "Info",     "cyan")
    if errors:
        _count_chip(STATUS_ICONS["error"], errors, "Errors", "bold bright_red")

    # ── Line 3: verdict ───────────────────────────────────────────────────────
    crit_results = [r for r in results if r.status == CheckStatus.CRITICAL]
    verdict_line = Text()
    verdict_line.append(
        f"\n   {_score_verdict(score, critical, warnings, critical_results=crit_results)}",
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
        BORDER_CRITICAL if critical or errors
        else BORDER_WARNING if warnings
        else BORDER_PASS
    )

    return Panel(
        content,
        title="[bold]Summary[/bold]",
        border_style=border,
        padding=(1, 2),
    )


def build_diff_panel(diff: dict) -> Panel:
    """
    Build the "Changes Since Last Scan" panel from a structured diff dict.

    Shows score delta, previous scan time, and improved/regressed/new/removed
    sections. Sections with no items are omitted entirely.
    """
    parts: list = []

    # ── Score line ────────────────────────────────────────────────────────────
    score_before = diff.get("score_before", 0)
    score_after = diff.get("score_after", 0)
    score_delta = diff.get("score_delta", 0)

    score_line = Text()
    score_line.append("   Score  ", style=f"bold {COLOR_TEXT}")
    score_line.append(str(score_before), style=COLOR_DIM)
    score_line.append(" → ", style=COLOR_DIM)
    score_line.append(str(score_after), style=f"bold {score_color(score_after)}")
    score_line.append("  ", style=COLOR_DIM)

    if score_delta > 0:
        score_line.append(f"(+{score_delta})", style=f"bold {COLOR_PASS}")
    elif score_delta < 0:
        score_line.append(f"({score_delta})", style=f"bold {COLOR_CRITICAL}")
    else:
        score_line.append("(±0)", style=COLOR_DIM)

    parts.append(score_line)

    # ── Previous scan time ────────────────────────────────────────────────────
    prev_time = diff.get("previous_scan_time", "")
    if prev_time:
        from datetime import datetime
        try:
            dt = datetime.fromisoformat(prev_time)
            time_str = f"{dt.day} {dt.strftime('%b %Y')}  ·  {dt.strftime('%H:%M')}"
        except (ValueError, TypeError):
            time_str = prev_time
        time_line = Text()
        time_line.append(f"   Previous scan: {time_str}", style=COLOR_DIM)
        parts.append(time_line)

    # ── Improved section ──────────────────────────────────────────────────────
    improved = diff.get("improved", [])
    if improved:
        parts.append(Text(""))
        header = Text()
        header.append("   Improved", style=f"bold {COLOR_PASS}")
        parts.append(header)
        for item in improved:
            line = Text()
            line.append(f"   {STATUS_ICONS['pass']}  ", style=COLOR_PASS)
            line.append(item.get("name", ""), style="bold")
            before = item.get("before_status", "")
            after = item.get("after_status", "")
            line.append(f"   {before} → {after}", style=COLOR_DIM)
            msg = item.get("message", "")
            if msg:
                line.append(f"   {msg}", style=COLOR_DIM)
            parts.append(line)

    # ── Regressed section ─────────────────────────────────────────────────────
    regressed = diff.get("regressed", [])
    if regressed:
        parts.append(Text(""))
        header = Text()
        header.append("   Regressed", style=f"bold {COLOR_CRITICAL}")
        parts.append(header)
        for item in regressed:
            line = Text()
            line.append(f"   {STATUS_ICONS['critical']}  ", style=COLOR_CRITICAL)
            line.append(item.get("name", ""), style="bold")
            before = item.get("before_status", "")
            after = item.get("after_status", "")
            line.append(f"   {before} → {after}", style=COLOR_DIM)
            msg = item.get("message", "")
            if msg:
                line.append(f"   {msg}", style=COLOR_DIM)
            parts.append(line)

    # ── New checks section ────────────────────────────────────────────────────
    new_checks = diff.get("new_checks", [])
    if new_checks:
        parts.append(Text(""))
        header = Text()
        header.append("   New checks", style=f"bold {COLOR_TEXT}")
        parts.append(header)
        for item in new_checks:
            icon = STATUS_ICONS.get(item.get("status", "info"), STATUS_ICONS["info"])
            line = Text()
            line.append(f"   {icon}  ", style=COLOR_DIM)
            line.append(item.get("name", ""), style="bold")
            msg = item.get("message", "")
            if msg:
                line.append(f"   {msg}", style=COLOR_DIM)
            parts.append(line)

    # ── Removed checks section ────────────────────────────────────────────────
    removed_checks = diff.get("removed_checks", [])
    if removed_checks:
        parts.append(Text(""))
        header = Text()
        header.append("   Removed checks", style=f"bold {COLOR_DIM}")
        parts.append(header)
        for item in removed_checks:
            line = Text()
            line.append("   ─  ", style=COLOR_DIM)
            line.append(item.get("name", ""), style=COLOR_DIM)
            parts.append(line)

    # ── Border color ──────────────────────────────────────────────────────────
    has_regressions = bool(regressed)
    if score_delta > 0 and not has_regressions:
        border = COLOR_PASS
    elif score_delta < 0:
        border = COLOR_CRITICAL
    else:
        border = BORDER_NEUTRAL

    return Panel(
        Group(*parts),
        title="[bold]Changes Since Last Scan[/bold]",
        border_style=border,
        padding=(1, 2),
    )


def build_category_panels(
    results: list[CheckResult],
    issues_only: bool = False,
    explain: bool = False,
    mdm_enrolled: bool = False,
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
        panel = _build_category_panel(cat, by_cat[cat], issues_only, explain,
                                      mdm_enrolled=mdm_enrolled)
        if panel is not None:
            panels.append(panel)

    return panels


def build_recommendations_panel(
    results: list[CheckResult],
    mode: str = "scan",
) -> Panel | None:
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
        if r.status == CheckStatus.INFO and r.fix_level in _FIXABLE_LEVELS
    ]
    all_fixable = actionable + info_fixable
    total = len(all_fixable)

    if total == 0:
        # Nothing to fix — show a healthy system message
        body = Text()
        body.append("\n  ✨  Nothing actionable — your Mac looks healthy.\n", style="bold bright_green")
        return Panel(body, title="[bold]Recommendations[/bold]", border_style="bright_green", padding=(0, 1))

    all_fixable_sorted = sorted(
        all_fixable,
        key=lambda r: _ISSUE_SEVERITY_ORDER.get(r.status, 9),
    )

    # Show up to 6 items
    shown = all_fixable_sorted[:6]
    remainder = total - len(shown)

    parts: list = []

    # Leading total-count line
    lede = Text()
    lede.append(f"  {total} fixable item{'s' if total != 1 else ''}", style=f"bold {COLOR_TEXT}")
    lede.append(" — top issues:", style=COLOR_DIM)
    parts.append(lede)
    parts.append(Text(""))

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
    has_critical = any(r.status == CheckStatus.CRITICAL for r in all_fixable)
    has_warning  = any(r.status == CheckStatus.WARNING  for r in all_fixable)
    border = BORDER_CRITICAL if has_critical else BORDER_WARNING if has_warning else BORDER_DIM

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
    mdm_enrolled: bool = False,
) -> Panel | None:
    """Build one category panel; returns None if there is nothing to show."""
    issues  = [r for r in results if r.status in _ISSUE_STATUSES]
    infos   = [r for r in results if r.status == "info"]
    passes  = [r for r in results if r.status == "pass"]
    skips   = [r for r in results if r.status == "skip"]

    if issues_only and not issues:
        return None

    parts: list = []

    # ── Issues (critical → warning → error) ───────────────────────────────────
    for r in sorted(issues, key=lambda r: _ISSUE_SEVERITY_ORDER.get(r.status, 9)):
        parts.extend(_render_issue(r, mdm_enrolled=mdm_enrolled))
        parts.append(Text(""))  # blank line between issues

    # ── Info + Pass + Skip — rendered in one aligned table ───────────────────
    if not issues_only:
        compact = infos + passes + skips
        if compact:
            if issues:
                pass  # already have a blank line from the issue loop
            parts.append(_compact_table(compact, explain, mdm_enrolled=mdm_enrolled))

    if not parts:
        return None

    icon     = CATEGORY_ICONS.get(category, "  ")
    cat_name = category.replace("_", " ").title()
    title    = f"{icon} {cat_name}"

    # Border: worst status in the category
    if any(r.status == CheckStatus.CRITICAL for r in results):
        border = BORDER_CRITICAL
    elif any(r.status in (CheckStatus.WARNING, CheckStatus.ERROR) for r in results):
        border = BORDER_WARNING
    else:
        border = COLOR_PASS

    return Panel(
        Group(*parts),
        title=f"[bold]{title}[/bold]",
        border_style=border,
        padding=(0, 1),
    )


# ── Internal: individual check renderers ──────────────────────────────────────

def _render_issue(result: CheckResult, mdm_enrolled: bool = False) -> list:
    """
    Critical / warning / error — up to 5 lines.

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
    if result.fix_level != FixLevel.NONE:
        fix_label = FIX_LEVEL_LABELS.get(result.fix_level, result.fix_level)
        fix_text = Text()
        fix_text.append(f"· {fix_label}", style="dim cyan")
        if result.fix_description:
            fix_text.append(f"  —  {result.fix_description}", style=COLOR_DIM)
        if result.fix_reversible is False:
            fix_text.append("  [irreversible]", style="dim red")
        parts.append(Padding(fix_text, (0, 2, 0, _INDENT)))

    # Line 5: MDM badge (muted)
    if mdm_enrolled and result.id in MDM_CHECK_IDS:
        mdm_line = Text()
        mdm_line.append(f"{ICON_MDM} may be managed by your org", style=COLOR_DIM)
        parts.append(Padding(mdm_line, (0, 2, 0, _INDENT)))

    return parts


def _compact_table(results: list[CheckResult], explain: bool = False, mdm_enrolled: bool = False) -> Table:
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

        if r.status == CheckStatus.PASS:
            name_style = "dim"
            msg_style  = "dim"
            icon_style = "bright_green"
        elif r.status == CheckStatus.SKIP:
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
        if mdm_enrolled and r.id in MDM_CHECK_IDS:
            msg_cell.append(f"  {ICON_MDM} managed", style=COLOR_DIM)

        table.add_row(name_cell, msg_cell)

        # Explain mode: add recommendation below in a second indented row
        if explain and r.recommendation and r.status in (CheckStatus.INFO, CheckStatus.PASS):
            blank   = Text("")
            rec     = Text(f"  → {r.recommendation}", style=COLOR_DIM)
            table.add_row(blank, rec)

    return table


# ── Verdict copy ──────────────────────────────────────────────────────────────

def _score_verdict(
    score: int,
    critical: int,
    warnings: int,
    critical_results: list[CheckResult] = (),
) -> str:
    """Return an emoji + one-line verdict string based on health score and critical/warning counts."""
    if critical == 1 and critical_results:
        r = critical_results[0]
        return f"🚨  {r.name} — {r.message.lower().rstrip('.')}. Address this first."
    if critical == 2 and critical_results:
        names = " and ".join(r.name for r in critical_results[:2])
        return f"🚨  {names} — 2 critical issues. Address these first."
    if critical >= 3:
        return f"🚨  {critical} critical issues detected — review the red items immediately."
    if score >= 95:
        return "✨  Excellent — your Mac is well configured and up to date."
    if score >= 85:
        return "👍  Very good — a few things worth tuning."
    if score >= 70:
        return "📋  Good — some settings could be tightened for better security."
    if score >= 55:
        return "⚠️   Fair — several issues should be addressed soon."
    return "🚨  Poor — significant security gaps detected. Start with the red items."
