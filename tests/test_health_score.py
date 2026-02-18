"""
Tests for calculate_health_score().

Verifies the algorithm from CLAUDE.md:
  - Critical: -10 base (-15 for security/privacy/system)
  - Warning:  -3  base (-3  for security/privacy/system — int(3*1.2)=3)
  - Info / Pass / Skip / Error: 0
  - Clamped to [0, 100]
"""

import pytest

from mactuner.checks.base import CheckResult, calculate_health_score


def _r(status: str, category: str = "disk") -> CheckResult:
    """Build a minimal CheckResult with the given status and category."""
    return CheckResult(
        id="t", name="T", category=category, category_icon="✅",
        status=status, message="",
        scan_description="", finding_explanation="", recommendation="",
        fix_level="none", fix_description="",
    )


class TestCalculateHealthScore:
    def test_empty_list_returns_100(self):
        assert calculate_health_score([]) == 100

    def test_all_pass_returns_100(self):
        assert calculate_health_score([_r("pass")] * 10) == 100

    def test_all_info_returns_100(self):
        assert calculate_health_score([_r("info")] * 5) == 100

    def test_all_skip_returns_100(self):
        assert calculate_health_score([_r("skip")] * 5) == 100

    def test_all_error_returns_100(self):
        assert calculate_health_score([_r("error")] * 5) == 100

    # ── Critical deductions ───────────────────────────────────────────────────

    def test_single_critical_non_security_deducts_10(self):
        assert calculate_health_score([_r("critical", "disk")]) == 90

    def test_single_critical_security_deducts_15(self):
        assert calculate_health_score([_r("critical", "security")]) == 85

    def test_single_critical_privacy_deducts_15(self):
        assert calculate_health_score([_r("critical", "privacy")]) == 85

    def test_single_critical_system_deducts_15(self):
        assert calculate_health_score([_r("critical", "system")]) == 85

    def test_two_criticals_non_security(self):
        assert calculate_health_score([_r("critical", "disk")] * 2) == 80

    def test_two_criticals_security(self):
        assert calculate_health_score([_r("critical", "security")] * 2) == 70

    # ── Warning deductions ────────────────────────────────────────────────────

    def test_single_warning_non_security_deducts_3(self):
        assert calculate_health_score([_r("warning", "disk")]) == 97

    def test_single_warning_security_deducts_3(self):
        # int(3 * 1.2) = int(3.6) = 3 — truncates, not rounds
        assert calculate_health_score([_r("warning", "security")]) == 97

    def test_single_warning_privacy_deducts_3(self):
        assert calculate_health_score([_r("warning", "privacy")]) == 97

    def test_five_warnings_non_security(self):
        assert calculate_health_score([_r("warning", "disk")] * 5) == 85

    # ── Mixed scenarios ───────────────────────────────────────────────────────

    def test_critical_plus_warnings(self):
        results = [
            _r("critical", "security"),   # -15
            _r("warning", "disk"),        # -3
            _r("warning", "disk"),        # -3
            _r("pass", "disk"),           # 0
            _r("info", "disk"),           # 0
        ]
        assert calculate_health_score(results) == 100 - 15 - 3 - 3  # 79

    def test_mixed_categories(self):
        results = [
            _r("critical", "disk"),       # -10
            _r("critical", "system"),     # -15
            _r("warning", "homebrew"),    # -3
            _r("pass", "security"),       # 0
        ]
        assert calculate_health_score(results) == 100 - 10 - 15 - 3  # 72

    # ── Clamping ──────────────────────────────────────────────────────────────

    def test_clamps_to_zero_on_many_criticals(self):
        results = [_r("critical", "security")] * 20  # 20 × 15 = 300 deducted
        assert calculate_health_score(results) == 0

    def test_never_below_zero(self):
        results = [_r("critical")] * 100
        assert calculate_health_score(results) >= 0

    def test_never_above_100(self):
        # Just passes — should stay at 100
        assert calculate_health_score([_r("pass")] * 50) == 100
