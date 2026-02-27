"""
Scan diffing — compare two scan payloads and return structured changes.

Pure logic, no I/O. Takes two dicts (same shape as --json output)
and returns a diff dict describing what improved, regressed, appeared,
or disappeared between scans.
"""

from typing import Optional


# ── Status severity ranking ──────────────────────────────────────────────────

_STATUS_SEVERITY: dict[str, int] = {
    "pass": 0,
    "info": 1,
    "skip": 2,
    "warning": 3,
    "error": 4,
    "critical": 5,
}


# ── Public API ───────────────────────────────────────────────────────────────

def compute_diff(current: dict, previous: dict) -> Optional[dict]:
    """
    Compare two scan payloads and return a structured diff.

    Returns None if:
      - schema_version mismatch (payloads from incompatible versions)
      - nothing changed (identical scores and check statuses)

    Args:
        current:  The just-completed scan payload.
        previous: The most recent historical scan payload.

    Returns:
        A diff dict or None.
    """
    if current.get("schema_version") != previous.get("schema_version"):
        return None

    score_before = previous.get("score", 0)
    score_after = current.get("score", 0)
    score_delta = score_after - score_before

    # Index checks by ID
    prev_by_id: dict[str, dict] = {
        r["id"]: r for r in previous.get("results", [])
    }
    curr_by_id: dict[str, dict] = {
        r["id"]: r for r in current.get("results", [])
    }

    improved: list[dict] = []
    regressed: list[dict] = []
    new_checks: list[dict] = []
    removed_checks: list[dict] = []

    # Checks present in both scans
    common_ids = set(prev_by_id) & set(curr_by_id)
    for check_id in common_ids:
        prev_r = prev_by_id[check_id]
        curr_r = curr_by_id[check_id]

        prev_sev = _STATUS_SEVERITY.get(prev_r.get("status", ""), 0)
        curr_sev = _STATUS_SEVERITY.get(curr_r.get("status", ""), 0)

        if curr_sev < prev_sev:
            improved.append({
                "id": check_id,
                "name": curr_r.get("name", ""),
                "category": curr_r.get("category", ""),
                "before_status": prev_r.get("status", ""),
                "after_status": curr_r.get("status", ""),
                "message": curr_r.get("message", ""),
            })
        elif curr_sev > prev_sev:
            regressed.append({
                "id": check_id,
                "name": curr_r.get("name", ""),
                "category": curr_r.get("category", ""),
                "before_status": prev_r.get("status", ""),
                "after_status": curr_r.get("status", ""),
                "message": curr_r.get("message", ""),
            })

    # New checks (in current but not previous)
    for check_id in set(curr_by_id) - set(prev_by_id):
        r = curr_by_id[check_id]
        new_checks.append({
            "id": check_id,
            "name": r.get("name", ""),
            "category": r.get("category", ""),
            "status": r.get("status", ""),
            "message": r.get("message", ""),
        })

    # Removed checks (in previous but not current)
    for check_id in set(prev_by_id) - set(curr_by_id):
        r = prev_by_id[check_id]
        removed_checks.append({
            "id": check_id,
            "name": r.get("name", ""),
            "category": r.get("category", ""),
            "status": r.get("status", ""),
            "message": r.get("message", ""),
        })

    # Sort for deterministic output
    improved.sort(key=lambda d: d["id"])
    regressed.sort(key=lambda d: d["id"])
    new_checks.sort(key=lambda d: d["id"])
    removed_checks.sort(key=lambda d: d["id"])

    diff = {
        "previous_scan_time": previous.get("scan_time", ""),
        "score_before": score_before,
        "score_after": score_after,
        "score_delta": score_delta,
        "improved": improved,
        "regressed": regressed,
        "new_checks": new_checks,
        "removed_checks": removed_checks,
    }

    # Filter mismatch suppression: if >50% of total checks are new/removed,
    # it's likely a --only/--skip filter difference, not real changes.
    total_checks = max(len(prev_by_id), len(curr_by_id), 1)
    filter_ratio = (len(new_checks) + len(removed_checks)) / total_checks
    if filter_ratio > 0.5:
        diff["new_checks"] = []
        diff["removed_checks"] = []

    if is_empty_diff(diff):
        return None

    return diff


def is_empty_diff(diff: dict) -> bool:
    """Return True if the diff has no meaningful changes."""
    return (
        diff.get("score_delta", 0) == 0
        and not diff.get("improved")
        and not diff.get("regressed")
        and not diff.get("new_checks")
        and not diff.get("removed_checks")
    )
