"""
Tests for checks/apps.py.

Covers:
  - LoginItemsCheck._SYSTEM_LABEL_PREFIXES: correct inclusions / exclusions
  - LoginItemsCheck.run(): pass / warning thresholds with mocked launchctl
  - AppStoreUpdatesCheck: skip when mas absent, pass/warning with mocked output
"""

from unittest.mock import patch

import pytest

from mactuner.checks.apps import AppStoreUpdatesCheck, LoginItemsCheck


# ── LoginItemsCheck label prefix list ────────────────────────────────────────

class TestSystemLabelPrefixes:
    prefixes = LoginItemsCheck._SYSTEM_LABEL_PREFIXES

    def test_com_apple_is_excluded(self):
        assert "com.apple." in self.prefixes

    def test_com_openssh_is_excluded(self):
        assert "com.openssh." in self.prefixes

    def test_numeric_hex_pids_are_excluded(self):
        assert "0x" in self.prefixes

    def test_com_microsoft_is_not_excluded(self):
        assert not any("microsoft" in p for p in self.prefixes), (
            "Microsoft is a third party — its agents should count as user-installed"
        )

    def test_com_adobe_is_not_excluded(self):
        assert not any("adobe" in p for p in self.prefixes), (
            "Adobe is a third party — its agents should count as user-installed"
        )

    def test_prefixes_is_a_tuple(self):
        assert isinstance(self.prefixes, tuple)


# ── LoginItemsCheck.run() ─────────────────────────────────────────────────────

_LAUNCHCTL_HEADER = "PID\tStatus\tLabel\n"


def _launchctl_output(*labels: str) -> str:
    """Build fake `launchctl list` output for the given label strings."""
    lines = [_LAUNCHCTL_HEADER]
    for label in labels:
        lines.append(f"-\t0\t{label}")
    return "\n".join(lines)


class TestLoginItemsCheckRun:
    def _run_with_output(self, launchctl_stdout: str):
        check = LoginItemsCheck()
        with patch.object(check, "shell", return_value=(0, launchctl_stdout, "")):
            return check.run()

    def test_only_apple_agents_returns_pass(self):
        output = _launchctl_output(
            "com.apple.Finder",
            "com.apple.mds",
            "com.openssh.sshd",
            "0x1234",
        )
        result = self._run_with_output(output)
        assert result.status == "pass"

    def test_few_third_party_agents_returns_pass(self):
        output = _launchctl_output(
            "com.apple.Finder",
            "com.dropbox.DropboxMacUpdate",
            "com.google.keystone.agent",
            "com.spotify.webhelper",
        )
        result = self._run_with_output(output)
        assert result.status in ("pass", "info")

    def test_many_third_party_agents_returns_warning(self):
        # 21 third-party agents → warning (threshold is >20)
        labels = [f"com.vendor.app{i}" for i in range(21)]
        output = _launchctl_output(*labels)
        result = self._run_with_output(output)
        assert result.status == "warning"

    def test_shell_error_returns_info(self):
        check = LoginItemsCheck()
        with patch.object(check, "shell", return_value=(1, "", "permission denied")):
            result = check.run()
        assert result.status == "info"

    def test_microsoft_agents_are_counted(self):
        # 25 microsoft agents — should count towards the third-party total
        labels = [f"com.microsoft.app{i}" for i in range(25)]
        output = _launchctl_output(*labels)
        result = self._run_with_output(output)
        assert result.status == "warning"
        assert result.data["count"] == 25


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
