"""
Scan history — persist full scan snapshots for diffing.

Stores JSON snapshots in ~/.config/macaudit/history/, one file per scan.
Keeps the newest _MAX_SCANS files and prunes older ones automatically.
"""

import dataclasses
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from macaudit import __version__
from macaudit.checks.base import CheckResult, calculate_health_score


# ── Constants ────────────────────────────────────────────────────────────────

_HISTORY_DIR = Path.home() / ".config" / "macaudit" / "history"
_MAX_SCANS = 10


# ── Public API ───────────────────────────────────────────────────────────────

def save_scan(results: list[CheckResult]) -> Optional[Path]:
    """
    Persist a full scan snapshot to the history directory.

    Returns the path of the written file, or None on failure.
    """
    payload = _build_payload(results)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    path = _HISTORY_DIR / f"{ts}.json"

    try:
        _HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2))
    except OSError:
        return None

    prune_history()
    return path


def load_previous_scan() -> Optional[dict]:
    """
    Return the parsed JSON of the most recent history file, or None.

    Catches JSONDecodeError and OSError gracefully.
    """
    try:
        files = sorted(_HISTORY_DIR.glob("*.json"))
    except OSError:
        return None

    if not files:
        return None

    try:
        return json.loads(files[-1].read_text())
    except (json.JSONDecodeError, OSError):
        return None


def prune_history() -> None:
    """Keep only the newest _MAX_SCANS history files, delete the rest."""
    try:
        files = sorted(_HISTORY_DIR.glob("*.json"))
    except OSError:
        return

    for old in files[:-_MAX_SCANS]:
        try:
            old.unlink()
        except OSError:
            pass


# ── Internal ─────────────────────────────────────────────────────────────────

def _build_payload(results: list[CheckResult]) -> dict:
    """
    Build the full scan payload dict (same shape as _output_json).

    Reuses the dataclasses.asdict() pattern from main._output_json.
    """
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

    return {
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
