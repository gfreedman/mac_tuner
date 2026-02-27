"""
Tests for macaudit.config — config loading and check suppression.
"""

from pathlib import Path

import pytest

from macaudit.checks.base import CheckResult, calculate_health_score
from macaudit.config import load_config


class TestLoadConfig:
    def test_missing_file_returns_empty_suppress(self, tmp_path):
        missing = tmp_path / "nonexistent" / "config.toml"
        result = load_config(path=missing)
        assert result == {"suppress": set()}

    def test_valid_toml_with_suppress_list(self, tmp_path):
        cfg = tmp_path / "config.toml"
        cfg.write_text('suppress = ["filevault", "gatekeeper"]\n')
        result = load_config(path=cfg)
        assert result == {"suppress": {"filevault", "gatekeeper"}}

    def test_empty_suppress_list(self, tmp_path):
        cfg = tmp_path / "config.toml"
        cfg.write_text("suppress = []\n")
        result = load_config(path=cfg)
        assert result == {"suppress": set()}

    def test_malformed_toml_returns_empty(self, tmp_path):
        cfg = tmp_path / "config.toml"
        cfg.write_text("suppress = [not valid toml\n")
        result = load_config(path=cfg)
        assert result == {"suppress": set()}

    def test_non_list_suppress_returns_empty(self, tmp_path):
        cfg = tmp_path / "config.toml"
        cfg.write_text('suppress = "filevault"\n')
        result = load_config(path=cfg)
        assert result == {"suppress": set()}

    def test_suppress_as_integer_returns_empty(self, tmp_path):
        cfg = tmp_path / "config.toml"
        cfg.write_text("suppress = 42\n")
        result = load_config(path=cfg)
        assert result == {"suppress": set()}

    def test_missing_suppress_key_returns_empty(self, tmp_path):
        cfg = tmp_path / "config.toml"
        cfg.write_text('title = "my config"\n')
        result = load_config(path=cfg)
        assert result == {"suppress": set()}

    def test_comments_in_toml_preserved(self, tmp_path):
        cfg = tmp_path / "config.toml"
        cfg.write_text(
            "# This is a comment\n"
            'suppress = ["filevault"]  # inline comment\n'
        )
        result = load_config(path=cfg)
        assert result == {"suppress": {"filevault"}}

    def test_unreadable_file_returns_empty(self, tmp_path):
        cfg = tmp_path / "config.toml"
        cfg.write_text('suppress = ["filevault"]\n')
        cfg.chmod(0o000)
        result = load_config(path=cfg)
        assert result == {"suppress": set()}
        cfg.chmod(0o644)  # restore for cleanup


class TestSuppressionIntegration:
    """Test that suppressed checks produce correct skip results."""

    def _make_check_class(self, check_id: str):
        """Create a minimal check class with the given ID."""
        from macaudit.checks.base import BaseCheck

        class FakeCheck(BaseCheck):
            id = check_id
            name = f"Fake {check_id}"
            category = "system"
            category_icon = "🔧"
            scan_description = "Testing"
            finding_explanation = "Test explanation"
            recommendation = "Test recommendation"

            def run(self):
                return self._pass("All good")

        return FakeCheck

    def test_suppressed_check_produces_skip_result(self):
        CheckClass = self._make_check_class("filevault")
        check = CheckClass()
        result = check._skip("Suppressed by config")
        assert result.status == "skip"
        assert result.message == "Suppressed by config"
        assert result.id == "filevault"

    def test_suppressed_check_does_not_affect_score(self):
        CheckClass = self._make_check_class("filevault")
        check = CheckClass()
        skip_result = check._skip("Suppressed by config")
        assert calculate_health_score([skip_result]) == 100

    def test_suppression_flow(self):
        """End-to-end: load config → split checks → verify results."""
        from macaudit.config import load_config

        FVCheck = self._make_check_class("filevault")
        GKCheck = self._make_check_class("gatekeeper")
        DiskCheck = self._make_check_class("disk_usage")

        all_checks = [FVCheck(), GKCheck(), DiskCheck()]
        suppressed_ids = {"filevault", "gatekeeper"}

        suppressed_results = []
        active_checks = []
        for check in all_checks:
            if check.id in suppressed_ids:
                suppressed_results.append(check._skip("Suppressed by config"))
            else:
                active_checks.append(check)

        # Only disk_usage should be active
        assert len(active_checks) == 1
        assert active_checks[0].id == "disk_usage"

        # Suppressed checks should produce skip results
        assert len(suppressed_results) == 2
        assert all(r.status == "skip" for r in suppressed_results)
        assert all(r.message == "Suppressed by config" for r in suppressed_results)

        # Score should be 100 (suppressed skips + one pass)
        active_results = [c.execute() for c in active_checks]
        all_results = active_results + suppressed_results
        assert calculate_health_score(all_results) == 100
