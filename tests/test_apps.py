"""
Tests for checks/apps.py.

Covers:
  - LoginItemsCheck.run(): pass / info / warning thresholds with mocked osascript
  - AppStoreUpdatesCheck: skip when mas absent, pass/warning with mocked output
"""

from unittest.mock import patch

import pytest

from mactuner.checks.apps import AppStoreUpdatesCheck, LoginItemsCheck


# ── LoginItemsCheck.run() ─────────────────────────────────────────────────────

def _osascript_output(*names: str) -> str:
    """Build fake osascript output for the given login item name strings."""
    return ", ".join(names)


class TestLoginItemsCheckRun:
    def _run_with_output(self, osascript_stdout: str, rc: int = 0):
        check = LoginItemsCheck()
        with patch.object(check, "shell", return_value=(rc, osascript_stdout, "")):
            return check.run()

    def test_no_items_returns_pass(self):
        result = self._run_with_output("")
        assert result.status == "pass"

    def test_few_items_returns_pass(self):
        # 3 items — well under the >8 info threshold
        output = _osascript_output("Dropbox", "Spotify", "Zoom")
        result = self._run_with_output(output)
        assert result.status == "pass"

    def test_moderate_items_returns_info(self):
        # 9 items — just over >8 threshold → info
        names = [f"App{i}" for i in range(9)]
        output = _osascript_output(*names)
        result = self._run_with_output(output)
        assert result.status == "info"

    def test_many_items_returns_warning(self):
        # 16 items — over >15 threshold → warning
        names = [f"App{i}" for i in range(16)]
        output = _osascript_output(*names)
        result = self._run_with_output(output)
        assert result.status == "warning"

    def test_shell_error_returns_info(self):
        result = self._run_with_output("", rc=1)
        assert result.status == "info"

    def test_data_contains_count(self):
        names = [f"App{i}" for i in range(16)]
        output = _osascript_output(*names)
        result = self._run_with_output(output)
        assert result.data is not None
        assert result.data["count"] == 16

    def test_eight_items_returns_pass(self):
        # Exactly 8 items — at boundary, should be pass (threshold is >8)
        names = [f"App{i}" for i in range(8)]
        output = _osascript_output(*names)
        result = self._run_with_output(output)
        assert result.status == "pass"


# ── AppStoreUpdatesCheck.run() ────────────────────────────────────────────────

class TestAppStoreUpdatesCheck:
    def test_skips_when_mas_not_installed(self):
        check = AppStoreUpdatesCheck()
        # Force requires_tool check to fail
        with patch.object(check, "has_tool", return_value=False):
            result = check.execute()
        assert result.status == "skip"
        assert "mas" in result.message

    def test_pass_when_no_outdated_apps(self):
        check = AppStoreUpdatesCheck()
        with patch.object(check, "shell", return_value=(0, "", "")):
            result = check.run()
        assert result.status == "pass"

    def test_warning_when_apps_outdated(self):
        mas_output = (
            "497799835 Xcode (14.3.1)\n"
            "409183694 Keynote (13.2)\n"
            "409201541 Pages (13.2)\n"
        )
        check = AppStoreUpdatesCheck()
        with patch.object(check, "shell", return_value=(0, mas_output, "")):
            result = check.run()
        assert result.status == "warning"
        assert "3" in result.message

    def test_data_contains_outdated_list(self):
        mas_output = "497799835 Xcode (14.3.1)\n"
        check = AppStoreUpdatesCheck()
        with patch.object(check, "shell", return_value=(0, mas_output, "")):
            result = check.run()
        assert "outdated" in result.data
        assert len(result.data["outdated"]) == 1
