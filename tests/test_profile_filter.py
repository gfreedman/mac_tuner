"""
Tests for the profile tag system.

Verifies:
  - All dev_env checks are tagged developer-only
  - System checks are tagged for all profiles
  - The profile filter logic (_collect_checks) correctly includes/excludes
    checks based on the active profile
"""

import pytest

from macaudit.checks.dev_env import ALL_CHECKS as DEV_ENV_CHECKS
from macaudit.checks.system import ALL_CHECKS as SYSTEM_CHECKS


# ── dev_env profile tags ──────────────────────────────────────────────────────

class TestDevEnvProfileTags:
    def test_all_dev_env_checks_have_developer_tag(self):
        for cls in DEV_ENV_CHECKS:
            tags = getattr(cls, "profile_tags", ())
            assert "developer" in tags, (
                f"{cls.__name__} is missing the 'developer' profile tag"
            )

    def test_no_dev_env_check_has_standard_tag(self):
        for cls in DEV_ENV_CHECKS:
            tags = getattr(cls, "profile_tags", ())
            assert "standard" not in tags, (
                f"{cls.__name__} has 'standard' tag — "
                "dev checks should not run for non-developer users"
            )

    def test_no_dev_env_check_has_creative_tag(self):
        for cls in DEV_ENV_CHECKS:
            tags = getattr(cls, "profile_tags", ())
            assert "creative" not in tags, (
                f"{cls.__name__} has 'creative' tag — "
                "dev checks should not run for creative-profile users"
            )

    def test_profile_tags_is_tuple_on_all_dev_env_checks(self):
        for cls in DEV_ENV_CHECKS:
            tags = getattr(cls, "profile_tags", ())
            assert isinstance(tags, tuple), (
                f"{cls.__name__}.profile_tags should be a tuple, got {type(tags).__name__}"
            )


# ── system profile tags ───────────────────────────────────────────────────────

class TestSystemProfileTags:
    def test_all_system_checks_have_all_three_profiles(self):
        for cls in SYSTEM_CHECKS:
            tags = getattr(cls, "profile_tags", ("developer", "creative", "standard"))
            for profile in ("developer", "creative", "standard"):
                assert profile in tags, (
                    f"{cls.__name__} is missing '{profile}' — "
                    "system checks should run for all profiles"
                )


# ── Profile filter simulation ─────────────────────────────────────────────────

class TestProfileFilter:
    """Simulate the filtering logic from main._collect_checks."""

    @staticmethod
    def _filter(checks, profile: str) -> list:
        return [
            c for c in checks
            if profile in getattr(c, "profile_tags", [profile])
        ]

    def test_dev_checks_excluded_for_standard_profile(self):
        checks = [cls() for cls in DEV_ENV_CHECKS]
        filtered = self._filter(checks, "standard")
        assert filtered == [], (
            "Dev env checks should be completely excluded for the 'standard' profile"
        )

    def test_dev_checks_excluded_for_creative_profile(self):
        checks = [cls() for cls in DEV_ENV_CHECKS]
        filtered = self._filter(checks, "creative")
        assert filtered == [], (
            "Dev env checks should be completely excluded for the 'creative' profile"
        )

    def test_dev_checks_all_included_for_developer_profile(self):
        checks = [cls() for cls in DEV_ENV_CHECKS]
        filtered = self._filter(checks, "developer")
        assert len(filtered) == len(DEV_ENV_CHECKS), (
            "All dev env checks should be included for the 'developer' profile"
        )

    def test_system_checks_included_for_standard_profile(self):
        checks = [cls() for cls in SYSTEM_CHECKS]
        filtered = self._filter(checks, "standard")
        assert len(filtered) == len(SYSTEM_CHECKS), (
            "All system checks should be included for the 'standard' profile"
        )

    def test_system_checks_included_for_developer_profile(self):
        checks = [cls() for cls in SYSTEM_CHECKS]
        filtered = self._filter(checks, "developer")
        assert len(filtered) == len(SYSTEM_CHECKS)
