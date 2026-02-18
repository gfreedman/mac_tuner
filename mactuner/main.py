"""
MacTuner — entry point and orchestrator.

CLI flags, scan loop, result collection, report dispatch.
"""

import time
from typing import Optional

import click
from rich.console import Console

from mactuner import __version__
from mactuner.checks.base import BaseCheck, CheckResult, calculate_health_score
from mactuner.ui.header import print_header
from mactuner.ui.theme import MACTUNER_THEME


# ── Console (shared across the tool) ─────────────────────────────────────────

console = Console(theme=MACTUNER_THEME)


# ── CLI ───────────────────────────────────────────────────────────────────────

@click.command(name="mactuner", context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, "-V", "--version", prog_name="mactuner")
# Profiles
@click.option(
    "--profile",
    type=click.Choice(["developer", "creative", "standard"], case_sensitive=False),
    default=None,
    help="Force a profile (auto-detected by default).",
)
# Category filters
@click.option(
    "--only",
    metavar="CATS",
    default=None,
    help="Comma-separated categories to run, e.g. homebrew,disk,security",
)
@click.option(
    "--skip",
    metavar="CATS",
    default=None,
    help="Comma-separated categories to skip.",
)
# Output modes
@click.option("--issues-only", is_flag=True, default=False, help="Show only warnings and criticals.")
@click.option("--explain", is_flag=True, default=False, help="Extra educational context for every finding.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output results as JSON.")
@click.option("--quiet", is_flag=True, default=False, help="Print only health score and critical count.")
# Fix modes
@click.option("--fix", is_flag=True, default=False, help="Enter interactive fix mode after scan.")
@click.option(
    "--auto",
    is_flag=True,
    default=False,
    help="With --fix: automatically apply all safe AUTO fixes without prompting for each one.",
)
# Exit code contract
@click.option(
    "--fail-on-critical",
    is_flag=True,
    default=False,
    help="Exit with code 2 if any critical issues are found (useful in scripts and CI).",
)
# Opt-in checks
@click.option(
    "--check-shell-secrets",
    is_flag=True,
    default=False,
    help="Scan shell config files for accidentally committed credentials.",
)
def cli(
    profile: Optional[str],
    only: Optional[str],
    skip: Optional[str],
    issues_only: bool,
    explain: bool,
    as_json: bool,
    quiet: bool,
    fix: bool,
    auto: bool,
    fail_on_critical: bool,
    check_shell_secrets: bool,
) -> None:
    """Mac System Health Inspector & Tuner.

    Run a full narrated audit of your Mac. Explains every finding.
    Safe, read-only by default — use --fix to apply changes.

    \b
    Environment variables:
      NO_COLOR=1   Disable all colour output (ANSI-stripped plain text).
      TERM=dumb    Alternative way to suppress colour in some terminals.
    """
    # ── Header ────────────────────────────────────────────────────────────────
    if not quiet and not as_json:
        print_header(console)
        console.print()
        _warn_if_mdm_enrolled(console)

    # ── Warn: --check-shell-secrets + --json exposes redacted credential hints ──
    if check_shell_secrets and as_json:
        import sys
        print(
            "Warning: --check-shell-secrets with --json includes redacted credential "
            "hints in the JSON output. Treat the output file as sensitive.",
            file=sys.stderr,
        )

    # ── Resolve profile ───────────────────────────────────────────────────────
    resolved_profile = _resolve_profile(profile)

    # ── Resolve category filters ──────────────────────────────────────────────
    only_cats = {c.strip().lower() for c in only.split(",")} if only else None
    skip_cats = {c.strip().lower() for c in skip.split(",")} if skip else set()

    # ── Collect checks ────────────────────────────────────────────────────────
    all_checks = _collect_checks(
        profile=resolved_profile,
        only_cats=only_cats,
        skip_cats=skip_cats,
        check_shell_secrets=check_shell_secrets,
    )

    if not all_checks:
        console.print("[dim]No checks match the specified filters.[/dim]")
        console.print()
        return

    # ── Run checks (narrated) ─────────────────────────────────────────────────
    _scan_start = time.monotonic()
    results = _run_checks(all_checks, quiet=quiet, as_json=as_json)
    _scan_elapsed = time.monotonic() - _scan_start

    # ── Output ────────────────────────────────────────────────────────────────
    if as_json:
        _output_json(results)
        return

    score = calculate_health_score(results)

    if quiet:
        criticals = sum(1 for r in results if r.status == "critical")
        console.print(f"Health score: {score}/100  |  Critical: {criticals}")
        return

    from mactuner.ui.report import print_report
    print_report(results, console, issues_only=issues_only, explain=explain, scan_duration=_scan_elapsed)

    # ── Fix mode ──────────────────────────────────────────────────────────────
    if fix:
        from mactuner.fixer.runner import run_fix_session
        run_fix_session(results, console, auto=auto)

    # ── Exit code contract ────────────────────────────────────────────────────
    if fail_on_critical:
        criticals = sum(1 for r in results if r.status == "critical")
        if criticals:
            raise SystemExit(2)


# ── MDM enrollment advisory ───────────────────────────────────────────────────

def _warn_if_mdm_enrolled(console: Console) -> None:
    """
    Detect MDM enrollment and print a brief advisory if the Mac is managed.

    On MDM-enrolled Macs, IT policy enforces many settings that mactuner
    may flag (FileVault, profiles, auto-updates, sharing). Alerting the user
    prevents false-alarm panic over findings they cannot and should not change.
    """
    import subprocess
    try:
        r = subprocess.run(
            ["profiles", "status", "-type", "enrollment"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        output = (r.stdout + r.stderr).lower()
        enrolled = "enrolled via dep" in output or "mdm enrollment: yes" in output
    except Exception:
        return

    if enrolled:
        from rich.panel import Panel
        from rich.text import Text
        note = Text()
        note.append("  This Mac appears to be MDM-enrolled.\n", style="bold yellow")
        note.append(
            "  Some settings (FileVault, auto-updates, profiles, sharing) may be\n"
            "  enforced by your organization. Warnings about these may reflect IT\n"
            "  policy rather than security issues — check with your administrator.",
            style="dim white",
        )
        console.print(
            Panel(note, title="[yellow]Managed Device[/yellow]", border_style="yellow")
        )
        console.print()


# ── Profile resolution ────────────────────────────────────────────────────────

def _resolve_profile(requested: Optional[str]) -> str:
    """
    Auto-detect profile if not specified.

    developer  — Homebrew is installed
    standard   — no Homebrew / MacPorts
    creative   — force with --profile creative
    """
    if requested:
        return requested.lower()

    import shutil
    if shutil.which("brew"):
        return "developer"
    return "standard"


# ── Check registry ────────────────────────────────────────────────────────────

def _collect_checks(
    profile: str,
    only_cats: Optional[set],
    skip_cats: set,
    check_shell_secrets: bool,
) -> list[BaseCheck]:
    """
    Return instantiated check objects to run, in display order.

    Category order matches the report sections:
      system → security → homebrew → disk
    """
    from mactuner.checks.apps import ALL_CHECKS as APPS
    from mactuner.checks.dev_env import ALL_CHECKS as DEV_ENV
    from mactuner.checks.disk import ALL_CHECKS as DISK
    from mactuner.checks.hardware import ALL_CHECKS as HARDWARE
    from mactuner.checks.homebrew import ALL_CHECKS as HOMEBREW
    from mactuner.checks.memory import ALL_CHECKS as MEMORY
    from mactuner.checks.network import ALL_CHECKS as NETWORK
    from mactuner.checks.privacy import ALL_CHECKS as PRIVACY
    from mactuner.checks.security import ALL_CHECKS as SECURITY
    from mactuner.checks.system import ALL_CHECKS as SYSTEM

    # Ordered for logical report flow (matches category panel order in report.py)
    all_classes = (
        SYSTEM + SECURITY + PRIVACY
        + HOMEBREW + DISK + HARDWARE
        + MEMORY + NETWORK + DEV_ENV + APPS
    )

    # Opt-in checks appended after standard suite
    if check_shell_secrets:
        from mactuner.checks.secrets import ALL_CHECKS as SECRETS
        all_classes = all_classes + SECRETS

    checks = [cls() for cls in all_classes]

    # Category filters
    if only_cats:
        checks = [c for c in checks if c.category in only_cats]
    if skip_cats:
        checks = [c for c in checks if c.category not in skip_cats]

    # Profile filter
    checks = [
        c for c in checks
        if profile in getattr(c, "profile_tags", [profile])
    ]

    return checks


# ── Scan loop ─────────────────────────────────────────────────────────────────

def _run_checks(checks: list, quiet: bool, as_json: bool) -> list[CheckResult]:
    """
    Execute every check with live narration and progress bar.

    In quiet/JSON mode the narrator is bypassed and checks run silently.
    """
    from mactuner.ui.narrator import ScanNarrator

    results: list[CheckResult] = []

    if quiet or as_json:
        for check in checks:
            results.append(check.execute())
        return results

    with ScanNarrator(console, total=len(checks)) as narrator:
        narrator.print_scan_header()
        for check in checks:
            narrator.start_check(check)
            result = check.execute()
            narrator.finish_check(result)
            results.append(result)

    return results




# ── JSON output ───────────────────────────────────────────────────────────────

def _output_json(results: list[CheckResult]) -> None:
    import dataclasses
    import json
    from datetime import datetime, timezone

    from mactuner.system_info import get_system_info

    info = get_system_info()

    counts: dict[str, int] = {}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1

    serialised = []
    for r in results:
        d = dataclasses.asdict(r)
        d["min_macos"] = list(d["min_macos"])  # tuple → list for JSON
        serialised.append(d)

    payload = {
        "schema_version": 1,
        "mactuner_version": __version__,
        "scan_time": datetime.now(timezone.utc).isoformat(),
        "system": {
            "macos_version": info["macos_version"],
            "architecture": info["architecture"],
            "model": info["model_name"],
        },
        "score": calculate_health_score(results),
        "summary": counts,
        "results": serialised,
    }

    click.echo(json.dumps(payload, indent=2))


# ── Entry ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cli()
