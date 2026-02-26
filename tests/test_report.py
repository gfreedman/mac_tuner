"""
Tests for ui/report.py.

Covers:
  - MDM inline badges:    _render_issue and _compact_table with mdm_enrolled flag
  - Contextual verdicts:  _score_verdict with 0, 1, 2, and 3+ criticals
"""

from io import StringIO

from rich.console import Console

from macaudit.checks.base import CheckResult
from macaudit.ui.report import (
    _compact_table,
    _render_issue,
    _score_verdict,
    build_summary_panel,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _console() -> tuple[Console, StringIO]:
    """Return a Console that captures output in a StringIO buffer."""
    buf = StringIO()
    con = Console(file=buf, highlight=False, no_color=True)
    return con, buf


def _result(**kwargs) -> CheckResult:
    """Build a minimal CheckResult; kwargs override any field."""
    defaults = dict(
        id="test_check",
        name="Test Check",
        category="system",
        category_icon="🖥️",
        status="warning",
        message="something is off",
        scan_description="",
        finding_explanation="",
        recommendation="",
        fix_level="none",
        fix_description="",
    )
    defaults.update(kwargs)
    return CheckResult(**defaults)


def _render_to_text(renderables: list) -> str:
    """Render a list of Rich renderables to plain text."""
    con, buf = _console()
    for r in renderables:
        con.print(r)
    return buf.getvalue()


# ── MDM inline badges: _render_issue ─────────────────────────────────────────

class TestRenderIssueMDM:
    def test_mdm_badge_shown_for_mdm_check(self):
        """MDM-relevant check shows badge when mdm_enrolled=True."""
        r = _result(id="filevault", name="FileVault", status="critical",
                     message="Disk encryption is disabled")
        parts = _render_issue(r, mdm_enrolled=True)
        text = _render_to_text(parts)
        assert "may be managed by your org" in text

    def test_mdm_badge_hidden_when_not_enrolled(self):
        """MDM-relevant check does NOT show badge when mdm_enrolled=False."""
        r = _result(id="filevault", name="FileVault", status="critical",
                     message="Disk encryption is disabled")
        parts = _render_issue(r, mdm_enrolled=False)
        text = _render_to_text(parts)
        assert "may be managed by your org" not in text

    def test_mdm_badge_hidden_for_non_mdm_check(self):
        """Non-MDM check never shows badge even when mdm_enrolled=True."""
        r = _result(id="disk_space", name="Disk Space", status="warning",
                     message="14 GB free")
        parts = _render_issue(r, mdm_enrolled=True)
        text = _render_to_text(parts)
        assert "may be managed by your org" not in text

    def test_all_mdm_check_ids_show_badge(self):
        """Every check ID in MDM_CHECK_IDS produces a badge."""
        from macaudit.ui.theme import MDM_CHECK_IDS
        for check_id in MDM_CHECK_IDS:
            r = _result(id=check_id, status="warning", message="test")
            parts = _render_issue(r, mdm_enrolled=True)
            text = _render_to_text(parts)
            assert "may be managed by your org" in text, (
                f"MDM badge missing for check ID '{check_id}'"
            )


# ── MDM inline badges: _compact_table ────────────────────────────────────────

class TestCompactTableMDM:
    def test_mdm_managed_tag_shown_for_mdm_check(self):
        """Compact table appends 'managed' tag for MDM checks when enrolled."""
        r = _result(id="firewall", name="Firewall", status="pass",
                     message="Firewall is enabled")
        con, buf = _console()
        table = _compact_table([r], mdm_enrolled=True)
        con.print(table)
        assert "managed" in buf.getvalue()

    def test_mdm_managed_tag_hidden_when_not_enrolled(self):
        """Compact table does NOT append 'managed' tag when not enrolled."""
        r = _result(id="firewall", name="Firewall", status="pass",
                     message="Firewall is enabled")
        con, buf = _console()
        table = _compact_table([r], mdm_enrolled=False)
        con.print(table)
        assert "managed" not in buf.getvalue()

    def test_mdm_managed_tag_hidden_for_non_mdm_check(self):
        """Compact table does NOT append 'managed' for non-MDM checks."""
        r = _result(id="battery", name="Battery", status="info",
                     message="342 cycles")
        con, buf = _console()
        table = _compact_table([r], mdm_enrolled=True)
        con.print(table)
        assert "managed" not in buf.getvalue()


# ── Contextual verdicts: _score_verdict ──────────────────────────────────────

class TestScoreVerdict:
    def test_one_critical_names_the_finding(self):
        """With 1 critical, verdict names the specific finding."""
        r = _result(id="filevault", name="FileVault Disk Encryption",
                     status="critical", message="Disk encryption is disabled")
        verdict = _score_verdict(70, 1, 0, critical_results=[r])
        assert "FileVault Disk Encryption" in verdict
        assert "disk encryption is disabled" in verdict
        assert "Address this first" in verdict

    def test_two_criticals_names_both(self):
        """With 2 criticals, verdict names both findings."""
        r1 = _result(id="filevault", name="FileVault", status="critical",
                      message="Disabled")
        r2 = _result(id="firewall", name="Firewall", status="critical",
                      message="Disabled")
        verdict = _score_verdict(60, 2, 0, critical_results=[r1, r2])
        assert "FileVault" in verdict
        assert "Firewall" in verdict
        assert "2 critical issues" in verdict

    def test_three_criticals_uses_generic_count(self):
        """With 3+ criticals, verdict uses generic count, not names."""
        rs = [
            _result(id="a", name="Check A", status="critical", message="bad"),
            _result(id="b", name="Check B", status="critical", message="bad"),
            _result(id="c", name="Check C", status="critical", message="bad"),
        ]
        verdict = _score_verdict(40, 3, 0, critical_results=rs)
        assert "3 critical issues detected" in verdict
        assert "Check A" not in verdict

    def test_zero_criticals_high_score(self):
        """With no criticals and high score, verdict is positive."""
        verdict = _score_verdict(96, 0, 0)
        assert "Excellent" in verdict

    def test_zero_criticals_mid_score(self):
        """With no criticals and mid score, verdict reflects warnings."""
        verdict = _score_verdict(80, 0, 3)
        assert "Good" in verdict

    def test_one_critical_strips_trailing_period(self):
        """Message with trailing period is stripped in the verdict."""
        r = _result(id="x", name="Some Check", status="critical",
                     message="Something is wrong.")
        verdict = _score_verdict(70, 1, 0, critical_results=[r])
        # Should not have double period: "wrong.. Address"
        assert ".." not in verdict
        assert "something is wrong. Address" in verdict

    def test_one_critical_lowercases_message(self):
        """Message is lowercased in the contextual verdict."""
        r = _result(id="x", name="Check", status="critical",
                     message="DISK ENCRYPTION IS OFF")
        verdict = _score_verdict(70, 1, 0, critical_results=[r])
        assert "disk encryption is off" in verdict

    def test_backward_compat_without_critical_results(self):
        """Calling without critical_results still works (generic message)."""
        verdict = _score_verdict(40, 4, 0)
        assert "4 critical issues detected" in verdict


# ── Contextual verdicts: build_summary_panel integration ─────────────────────

class TestSummaryPanelVerdict:
    def test_summary_panel_includes_critical_name(self):
        """build_summary_panel verdict names the critical finding."""
        r_crit = _result(id="firewall", name="Firewall", status="critical",
                          message="Firewall is disabled")
        r_pass = _result(id="sip", name="SIP", status="pass",
                          message="Enabled")
        con, buf = _console()
        panel = build_summary_panel([r_crit, r_pass])
        con.print(panel)
        output = buf.getvalue()
        assert "Firewall" in output
        assert "firewall is disabled" in output
