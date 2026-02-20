"""
Tests for checks/base.py.

Covers:
  - CheckResult field types and defaults
  - BaseCheck.execute() version / tool / arch gates
  - BaseCheck._result() propagates subclass profile_tags
  - BaseCheck.shell() error handling
"""

from unittest.mock import patch

import pytest

from macaudit.checks.base import BaseCheck, CheckResult, calculate_health_score


# ── Concrete check stubs ──────────────────────────────────────────────────────

class _AlwaysPass(BaseCheck):
    """Minimal concrete check that always returns pass."""
    id = "always_pass"
    name = "Always Pass"
    category = "system"
    category_icon = "✅"
    scan_description = "test"
    finding_explanation = "test"
    recommendation = "test"
    fix_level = "none"
    fix_description = "none"

    def run(self) -> CheckResult:
        return self._pass("All good")


class _AlwaysCrash(BaseCheck):
    """Check that always raises an exception inside run()."""
    id = "always_crash"
    name = "Always Crash"
    category = "system"
    category_icon = "💥"
    scan_description = "test"
    finding_explanation = "test"
    recommendation = "test"
    fix_level = "none"
    fix_description = "none"

    def run(self) -> CheckResult:
        raise RuntimeError("boom")


class _DevOnlyCheck(BaseCheck):
    """Check that overrides profile_tags to developer only."""
    id = "dev_only"
    name = "Dev Only"
    category = "dev_env"
    category_icon = "🛠️"
    scan_description = "test"
    finding_explanation = "test"
    recommendation = "test"
    fix_level = "none"
    fix_description = "none"
    profile_tags = ("developer",)

    def run(self) -> CheckResult:
        return self._pass("dev check ran")


# ── CheckResult defaults ──────────────────────────────────────────────────────

class TestCheckResultDefaults:
    def test_fix_command_defaults_to_none(self):
        r = _AlwaysPass().execute()
        assert r.fix_command is None

    def test_data_field_is_dict(self):
        r = _AlwaysPass().execute()
        assert isinstance(r.data, dict)

    def test_profile_tags_default_is_list_with_all_profiles(self):
        r = _AlwaysPass().execute()
        assert set(r.profile_tags) == {"developer", "creative", "standard"}

    def test_min_macos_is_tuple_of_ints(self):
        r = _AlwaysPass().execute()
        assert isinstance(r.min_macos, tuple)
        assert all(isinstance(v, int) for v in r.min_macos)

    def test_status_is_string(self):
        r = _AlwaysPass().execute()
        assert r.status == "pass"


# ── BaseCheck.execute() gates ─────────────────────────────────────────────────

class TestExecuteGates:
    def test_version_gate_skips_when_below_min(self):
        check = _AlwaysPass()
        check.min_macos = (99, 0)
        result = check.execute()
        assert result.status == "skip"
        assert "99.0" in result.message

    def test_version_gate_passes_when_below_current(self):
        check = _AlwaysPass()
        check.min_macos = (1, 0)
        result = check.execute()
        assert result.status == "pass"

    def test_tool_gate_skips_when_tool_missing(self):
        check = _AlwaysPass()
        check.requires_tool = "this_tool_does_not_exist_mactuner_test"
        result = check.execute()
        assert result.status == "skip"
        assert "this_tool_does_not_exist_mactuner_test" in result.message

    def test_tool_gate_passes_when_tool_present(self):
        check = _AlwaysPass()
        check.requires_tool = "python3"  # always available in test env
        result = check.execute()
        assert result.status == "pass"

    def test_arch_gate_skips_on_apple_silicon_when_not_compatible(self):
        check = _AlwaysPass()
        check.apple_silicon_compatible = False
        with patch("macaudit.checks.base.IS_APPLE_SILICON", True):
            result = check.execute()
        assert result.status == "skip"
        assert "Apple Silicon" in result.message

    def test_arch_gate_passes_on_intel_when_not_compatible(self):
        check = _AlwaysPass()
        check.apple_silicon_compatible = False
        with patch("macaudit.checks.base.IS_APPLE_SILICON", False):
            result = check.execute()
        assert result.status == "pass"

    def test_exception_in_run_returns_error_not_raise(self):
        check = _AlwaysCrash()
        result = check.execute()
        assert result.status == "error"
        assert "always_crash" in result.message
        assert "boom" in result.message

    def test_all_gates_checked_in_order_version_first(self):
        # If version gate fires, we never reach the tool gate
        check = _AlwaysPass()
        check.min_macos = (99, 0)
        check.requires_tool = "this_tool_does_not_exist_mactuner_test"
        result = check.execute()
        assert result.status == "skip"
        assert "99.0" in result.message  # version message, not tool message


# ── profile_tags propagation ──────────────────────────────────────────────────

class TestResultProfileTagsPropagation:
    def test_default_check_has_all_three_profiles(self):
        result = _AlwaysPass().execute()
        assert set(result.profile_tags) == {"developer", "creative", "standard"}

    def test_dev_only_check_propagates_developer_tag_only(self):
        result = _DevOnlyCheck().execute()
        assert result.profile_tags == ["developer"]

    def test_base_class_profile_tags_is_tuple(self):
        # Immutability check — class attribute must be a tuple
        assert isinstance(BaseCheck.profile_tags, tuple)

    def test_subclass_override_does_not_mutate_base_class(self):
        # _DevOnlyCheck overrides to ("developer",) — base must be unchanged
        _ = _DevOnlyCheck()
        assert "creative" in BaseCheck.profile_tags
        assert "standard" in BaseCheck.profile_tags


# ── BaseCheck.shell() ─────────────────────────────────────────────────────────

class TestShellHelper:
    def test_successful_command_returns_rc_0_and_stdout(self):
        check = _AlwaysPass()
        rc, out, err = check.shell(["echo", "hello"])
        assert rc == 0
        assert "hello" in out
        assert err == ""

    def test_missing_binary_returns_negative_one(self):
        check = _AlwaysPass()
        rc, out, err = check.shell(["this_command_definitely_does_not_exist_9999"])
        assert rc == -1
        assert out == ""
        assert "not found" in err

    def test_timeout_returns_negative_one_with_message(self):
        check = _AlwaysPass()
        rc, out, err = check.shell(["sleep", "10"], timeout=1)
        assert rc == -1
        assert "timed out" in err.lower()

    def test_stderr_captured_on_nonzero_exit(self):
        check = _AlwaysPass()
        rc, out, err = check.shell(["ls", "/path/that/does/not/exist/xyzzy"])
        assert rc != 0
