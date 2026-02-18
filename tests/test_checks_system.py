"""
Smoke tests for checks/system.py.

Tests the parser helpers (pure functions, no mocking needed) and verifies
that the execute() gating layer works correctly for system checks.
The underlying `run()` methods call real macOS commands and are not
unit-tested here — they are covered by manual integration testing on the
macOS version matrix (13/14/15 × Intel/ARM).
"""

from unittest.mock import patch

import pytest

from mactuner.checks.system import (
    MacOSVersionCheck,
    _parse_update_lines,
)


# ── _parse_update_lines() — pure parser, no subprocess ───────────────────────

class TestParseUpdateLines:
    def test_asterisk_prefixed_lines_included(self):
        output = "Software Update Tool\n* macOS 15.4\n* Safari 18.0\n"
        lines = _parse_update_lines(output)
        assert len(lines) == 2

    def test_asterisk_lines_stripped(self):
        output = "  * macOS 15.4 (Label: macOS15.4)\n"
        lines = _parse_update_lines(output)
        assert lines[0].startswith("*")

    def test_dash_lines_included(self):
        output = "- Label: macOS 15.4\n"
        lines = _parse_update_lines(output)
        assert any("macOS 15.4" in l for l in lines)

    def test_bare_dash_excluded(self):
        # A line that is just "-" (separator) must be filtered out
        output = "- \n* macOS 15.4\n"
        lines = _parse_update_lines(output)
        assert "-" not in lines  # the bare "-" stripped line

    def test_no_updates_returns_empty(self):
        output = "No new software available.\n"
        assert _parse_update_lines(output) == []

    def test_empty_output_returns_empty(self):
        assert _parse_update_lines("") == []

    def test_multiple_updates_all_captured(self):
        output = (
            "* macOS 15.4 Sequoia\n"
            "* Safari 18.3\n"
            "* XProtect Remediator 1.2.3\n"
        )
        assert len(_parse_update_lines(output)) == 3


# ── MacOSVersionCheck.execute() — gate layer ─────────────────────────────────

class TestMacOSVersionCheck:
    def test_has_expected_metadata(self):
        check = MacOSVersionCheck()
        assert check.category == "system"
        assert check.id == "macos_version"
        assert check.scan_description  # non-empty
        assert check.finding_explanation
        assert check.recommendation

    def test_has_all_three_profile_tags(self):
        check = MacOSVersionCheck()
        assert "developer" in check.profile_tags
        assert "creative" in check.profile_tags
        assert "standard" in check.profile_tags

    def test_min_macos_is_13(self):
        # Should run on macOS 13+
        check = MacOSVersionCheck()
        assert check.min_macos[0] <= 13

    def test_does_not_require_external_tool(self):
        check = MacOSVersionCheck()
        assert check.requires_tool is None

    def test_execute_returns_checkresult(self):
        from mactuner.checks.base import CheckResult
        result = MacOSVersionCheck().execute()
        assert isinstance(result, CheckResult)
        assert result.status in ("pass", "info", "warning", "critical", "skip", "error")

    def test_result_message_is_non_empty(self):
        result = MacOSVersionCheck().execute()
        assert result.message.strip()
