"""
Tests for fixer/executor.py.

Covers:
  - run_auto_fix:        missing command, successful run, failing exit code
  - run_instructions_fix: with steps, recommendation fallback, empty
  - run_guided_fix:      missing URL, successful open, fallback open
"""

from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from macaudit.checks.base import CheckResult
from macaudit.fixer.executor import (
    run_auto_fix,
    run_guided_fix,
    run_instructions_fix,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _console() -> tuple[Console, StringIO]:
    """Return a Console that captures output in a StringIO buffer."""
    buf = StringIO()
    con = Console(file=buf, highlight=False, no_color=True)
    return con, buf


def _result(**kwargs) -> CheckResult:
    """Build a minimal CheckResult; kwargs override any field."""
    defaults = dict(
        id="test_fix",
        name="Test Fix",
        category="system",
        category_icon="✅",
        status="warning",
        message="something is off",
        scan_description="",
        finding_explanation="",
        recommendation="",
        fix_level="auto",
        fix_description="",
    )
    defaults.update(kwargs)
    return CheckResult(**defaults)


# ── run_auto_fix ──────────────────────────────────────────────────────────────

class TestRunAutoFix:
    def test_no_fix_command_returns_false(self):
        con, _ = _console()
        assert run_auto_fix(_result(fix_command=None), con) is False

    def test_successful_command_returns_true(self):
        con, _ = _console()
        assert run_auto_fix(_result(fix_command="echo hello"), con) is True

    def test_failing_command_returns_false(self):
        con, _ = _console()
        # `false` is a POSIX command that always exits 1
        assert run_auto_fix(_result(fix_command="false"), con) is False

    def test_output_is_streamed_to_console(self):
        con, buf = _console()
        run_auto_fix(_result(fix_command="echo mactuner_test_output"), con)
        assert "mactuner_test_output" in buf.getvalue()

    def test_uses_shell_true(self):
        """Verify shell=True is used so ~ and glob patterns are expanded."""
        con, _ = _console()
        import subprocess
        with patch("subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_proc.stdout = iter(["line1\n"])
            mock_proc.returncode = 0
            mock_proc.wait.return_value = 0
            mock_popen.return_value = mock_proc

            run_auto_fix(_result(fix_command="echo hello"), con)

            call_kwargs = mock_popen.call_args
            assert call_kwargs.kwargs.get("shell") is True

    def test_command_passed_as_string(self):
        """fix_command is passed as a string (not split) so shell can expand ~ and globs."""
        con, _ = _console()
        import subprocess
        with patch("subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_proc.stdout = iter([])
            mock_proc.returncode = 0
            mock_proc.wait.return_value = 0
            mock_popen.return_value = mock_proc

            run_auto_fix(_result(fix_command="brew cleanup --prune=all"), con)

            call_args = mock_popen.call_args
            cmd = call_args.args[0]  # First positional arg is the command
            assert isinstance(cmd, str), "Command should be a string when shell=True"
            assert "brew" in cmd


# ── run_instructions_fix ──────────────────────────────────────────────────────

class TestRunInstructionsFix:
    def test_with_steps_returns_true(self):
        con, _ = _console()
        assert run_instructions_fix(_result(fix_steps=["Step 1", "Step 2"]), con) is True

    def test_steps_are_printed(self):
        con, buf = _console()
        run_instructions_fix(_result(fix_steps=["Do thing A", "Do thing B"]), con)
        output = buf.getvalue()
        assert "Do thing A" in output
        assert "Do thing B" in output

    def test_steps_are_numbered(self):
        con, buf = _console()
        run_instructions_fix(_result(fix_steps=["First step"]), con)
        assert "1." in buf.getvalue()

    def test_no_steps_falls_back_to_recommendation(self):
        con, buf = _console()
        result = run_instructions_fix(
            _result(fix_steps=None, recommendation="Read the manual"), con
        )
        assert result is True
        assert "Read the manual" in buf.getvalue()

    def test_no_steps_no_recommendation_returns_false(self):
        con, _ = _console()
        assert run_instructions_fix(_result(fix_steps=None, recommendation=""), con) is False


# ── run_guided_fix ────────────────────────────────────────────────────────────

class TestRunGuidedFix:
    def test_no_url_returns_false(self):
        con, _ = _console()
        assert run_guided_fix(_result(fix_url=None), con) is False

    def test_successful_open_returns_true(self):
        con, _ = _console()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = run_guided_fix(
                _result(fix_url="x-apple.systempreferences:com.apple.preferences.security"),
                con,
            )
        assert result is True

    def test_deep_link_failure_falls_back_to_system_settings(self):
        con, buf = _console()
        import subprocess

        def side_effect(cmd, **kwargs):
            if "x-apple" in str(cmd):
                raise subprocess.CalledProcessError(1, cmd)
            return MagicMock(returncode=0)

        with patch("subprocess.run", side_effect=side_effect):
            result = run_guided_fix(
                _result(fix_url="x-apple.systempreferences:com.apple.test"),
                con,
            )
        assert result is True
        assert "System Settings" in buf.getvalue()

    def test_fix_steps_are_printed_before_opening(self):
        con, buf = _console()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            run_guided_fix(
                _result(
                    fix_url="x-apple.systempreferences:com.apple.test",
                    fix_steps=["Look for Full Disk Access", "Remove unknown apps"],
                ),
                con,
            )
        output = buf.getvalue()
        assert "Full Disk Access" in output
