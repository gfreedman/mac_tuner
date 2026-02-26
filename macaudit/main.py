"""
Mac Audit — entry point and orchestrator.

CLI flags, scan loop, result collection, report dispatch.
"""

import shutil
import time
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from macaudit import __version__
from macaudit.checks.base import BaseCheck, CheckResult, calculate_health_score
from macaudit.ui.header import print_header
from macaudit.ui.theme import COLOR_DIM, COLOR_TEXT, MACTUNER_THEME


# ── Console (shared across the tool) ─────────────────────────────────────────

console = Console(theme=MACTUNER_THEME)


# ── MDM flag ─────────────────────────────────────────────────────────────────

_MDM_FLAG = Path.home() / ".config" / "macaudit" / ".mdm_warned"


# ── CLI ───────────────────────────────────────────────────────────────────────

@click.command(name="macaudit", context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, "-V", "--version", prog_name="macaudit")
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
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="With --fix: walk through the fix flow without executing any changes.",
)
# Skip prompts
@click.option("--yes", "-y", is_flag=True, default=False,
              help="Skip the pre-scan confirmation prompt.")
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
# Shell completion
@click.option(
    "--show-completion",
    is_flag=True,
    default=False,
    help="Print shell completion setup instructions and exit.",
)
# Welcome screen
@click.option(
    "--welcome",
    is_flag=True,
    default=False,
    help="Show the welcome screen and exit.",
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
    dry_run: bool,
    yes: bool,
    fail_on_critical: bool,
    check_shell_secrets: bool,
    show_completion: bool,
    welcome: bool,
) -> None:
    """Mac System Health Inspector & Tuner.

    Run a full narrated audit of your Mac. Explains every finding.
    Safe, read-only by default — use --fix to apply changes.

    \b
    Environment variables:
      NO_COLOR=1   Disable all colour output (ANSI-stripped plain text).
      TERM=dumb    Alternative way to suppress colour in some terminals.
    """
    # ── Shell completion ──────────────────────────────────────────────────────
    if show_completion:
        _print_completion_help(console)
        return

    # ── Welcome flag ──────────────────────────────────────────────────────────
    if welcome:
        if not quiet and not as_json:
            from macaudit.ui.welcome import show_welcome
            show_welcome(console, first_run=False)
        return

    # ── Validate --dry-run requires --fix ─────────────────────────────────────
    if dry_run and not fix:
        console.print("[red]Error:[/red] --dry-run requires --fix.")
        raise SystemExit(1)

    # ── Resolve category filters (needed for mode before header) ──────────────
    only_cats = {c.strip().lower() for c in only.split(",")} if only else None
    skip_cats = {c.strip().lower() for c in skip.split(",")} if skip else set()

    # ── Header / first-run welcome ────────────────────────────────────────────
    _first_run = False
    _mdm_enrolled = False
    if not quiet and not as_json:
        from macaudit.ui.welcome import is_first_run, show_welcome
        _mdm_enrolled = _is_mdm_enrolled()
        if is_first_run():
            _first_run = True
            ok = show_welcome(console, first_run=True)
            if not ok:
                return
            _warn_if_mdm_enrolled(console)
        else:
            print_header(console, mode=_resolve_mode(fix, only, skip), only_cats=only_cats)
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

    # ── Pre-scan prompt ───────────────────────────────────────────────────────
    if not quiet and not as_json and not yes and not _first_run:
        n = len(all_checks)
        console.print(f"  [dim]Ready to run [bold text]{n}[/bold text] checks.[/dim]")
        console.print()
        console.print(
            "  [dim]Press [bold text]↵ \\[ENTER][/bold text] to begin  "
            "·  [bold text]Ctrl-C[/bold text] to cancel[/dim]"
        )
        try:
            input()
        except (KeyboardInterrupt, EOFError):
            console.print("\n  [dim]Cancelled.[/dim]\n")
            return
        console.print()

    # ── Run checks (narrated) ─────────────────────────────────────────────────
    _scan_start = time.monotonic()
    results = _run_checks(all_checks, quiet=quiet, as_json=as_json)
    _scan_elapsed = time.monotonic() - _scan_start

    # ── Persist last-scan summary for welcome screen ──────────────────────────
    if not as_json:
        from macaudit.ui.welcome import save_last_scan
        _counts: dict[str, int] = {}
        for r in results:
            _counts[r.status] = _counts.get(r.status, 0) + 1
        save_last_scan(calculate_health_score(results), _counts)

    # ── Output ────────────────────────────────────────────────────────────────
    if as_json:
        _output_json(results)
        return

    score = calculate_health_score(results)

    if quiet:
        criticals = sum(1 for r in results if r.status == "critical")
        console.print(f"Health score: {score}/100  |  Critical: {criticals}")
        return

    from macaudit.ui.report import print_report
    print_report(results, console, issues_only=issues_only, explain=explain,
                 scan_duration=_scan_elapsed, mode=_resolve_mode(fix, only, skip),
                 mdm_enrolled=_mdm_enrolled)

    # ── Fix mode ──────────────────────────────────────────────────────────────
    if fix:
        from macaudit.fixer.runner import run_fix_session
        run_fix_session(results, console, auto=auto, dry_run=dry_run)

    # ── Exit code contract ────────────────────────────────────────────────────
    if fail_on_critical:
        criticals = sum(1 for r in results if r.status == "critical")
        if criticals:
            raise SystemExit(2)


# ── Mode resolution ───────────────────────────────────────────────────────────

def _resolve_mode(fix: bool, only: Optional[str], skip: Optional[str]) -> str:
    """Return the active mode string ('fix', 'targeted', or 'scan') based on CLI flags."""
    if fix:
        return "fix"
    if only or skip:
        return "targeted"
    return "scan"


# ── Shell completion help ─────────────────────────────────────────────────────

def _print_completion_help(console: Console) -> None:
    """Print shell completion setup instructions and exit."""
    import os
    from rich.panel import Panel
    from rich.text import Text
    from macaudit.ui.theme import COLOR_BRAND

    shell = os.environ.get("SHELL", "").split("/")[-1]

    t = Text()
    t.append("\n  Shell completion for macaudit\n\n", style=f"bold {COLOR_TEXT}")

    # Primary shell (detected)
    if shell in ("zsh", ""):
        primary, primary_rc   = "zsh",  "~/.zshrc"
        secondary, secondary_rc = "bash", "~/.bash_profile"
    elif shell == "bash":
        primary, primary_rc   = "bash", "~/.bash_profile"
        secondary, secondary_rc = "zsh",  "~/.zshrc"
    else:
        primary, primary_rc   = shell, f"~/.{shell}rc"
        secondary, secondary_rc = "zsh", "~/.zshrc"

    t.append(f"  Add this to your {primary_rc}:\n", style=COLOR_TEXT)
    t.append(
        f'    eval "$(_MACAUDIT_COMPLETE={primary}_source macaudit)"\n\n',
        style=COLOR_DIM,
    )
    t.append(f"  For {secondary}, add to {secondary_rc}:\n", style=COLOR_DIM)
    t.append(
        f'    eval "$(_MACAUDIT_COMPLETE={secondary}_source macaudit)"\n\n',
        style=COLOR_DIM,
    )
    t.append(f"  Then restart your terminal or run: source {primary_rc}\n", style=COLOR_DIM)

    console.print(Panel(t, border_style=COLOR_BRAND))


# ── MDM enrollment advisory ───────────────────────────────────────────────────

def _is_mdm_enrolled() -> bool:
    """Return True if this Mac is MDM-enrolled (profiles enrollment check)."""
    import subprocess
    try:
        r = subprocess.run(
            ["profiles", "status", "-type", "enrollment"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        output = (r.stdout + r.stderr).lower()
        return "enrolled via dep" in output or "mdm enrollment: yes" in output
    except Exception:
        return False


def _warn_if_mdm_enrolled(console: Console) -> None:
    """
    Print a brief MDM advisory if the Mac is managed.

    The warning is shown at most once (flagged by ~/.config/macaudit/.mdm_warned).
    """
    if _MDM_FLAG.exists():
        return

    if not _is_mdm_enrolled():
        return

    from rich.panel import Panel
    from rich.text import Text
    note = Text()
    note.append("  This Mac appears to be MDM-enrolled.\n", style="bold yellow")
    note.append(
        "  Some settings (FileVault, auto-updates, profiles, sharing) may be\n"
        "  enforced by your organization. Warnings about these may reflect IT\n"
        "  policy rather than security issues — check with your administrator.\n",
        style=COLOR_DIM,
    )
    note.append("  This notice will not appear again.", style=COLOR_DIM)
    console.print(
        Panel(note, title="[yellow]Managed Device[/yellow]", border_style="yellow")
    )
    console.print()
    try:
        _MDM_FLAG.parent.mkdir(parents=True, exist_ok=True)
        _MDM_FLAG.touch()
    except OSError:
        pass


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
    from macaudit.checks.apps import ALL_CHECKS as APPS
    from macaudit.checks.dev_env import ALL_CHECKS as DEV_ENV
    from macaudit.checks.disk import ALL_CHECKS as DISK
    from macaudit.checks.hardware import ALL_CHECKS as HARDWARE
    from macaudit.checks.homebrew import ALL_CHECKS as HOMEBREW
    from macaudit.checks.memory import ALL_CHECKS as MEMORY
    from macaudit.checks.network import ALL_CHECKS as NETWORK
    from macaudit.checks.privacy import ALL_CHECKS as PRIVACY
    from macaudit.checks.security import ALL_CHECKS as SECURITY
    from macaudit.checks.system import ALL_CHECKS as SYSTEM

    # Ordered for logical report flow (matches category panel order in report.py)
    all_classes = (
        SYSTEM + SECURITY + PRIVACY
        + HOMEBREW + DISK + HARDWARE
        + MEMORY + NETWORK + DEV_ENV + APPS
    )

    # Opt-in checks appended after standard suite
    if check_shell_secrets:
        from macaudit.checks.secrets import ALL_CHECKS as SECRETS
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
    In narrated mode, checks run in parallel via ThreadPoolExecutor(max_workers=8)
    and results are printed in input order for deterministic output.
    """
    import concurrent.futures

    from macaudit.ui.narrator import ScanNarrator

    if quiet or as_json:
        return [check.execute() for check in checks]

    results: list[CheckResult | None] = [None] * len(checks)
    with ScanNarrator(console, total=len(checks)) as narrator:
        narrator.print_scan_header()
        next_to_print = 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            future_to_idx = {
                pool.submit(check.execute): i
                for i, check in enumerate(checks)
            }
            for future in concurrent.futures.as_completed(future_to_idx):
                idx = future_to_idx[future]
                results[idx] = future.result()
                narrator.increment()
                # Flush contiguous completed results in input order
                while next_to_print < len(results) and results[next_to_print] is not None:
                    narrator.print_result(results[next_to_print])
                    next_to_print += 1

    return results




# ── JSON output ───────────────────────────────────────────────────────────────

def _output_json(results: list[CheckResult]) -> None:
    """Serialize all CheckResults plus system info and health score to JSON on stdout."""
    import dataclasses
    import json
    from datetime import datetime, timezone

    from macaudit.system_info import get_system_info

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
        "macaudit_version": __version__,
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
