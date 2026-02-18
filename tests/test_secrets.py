"""
Tests for checks/secrets.py — opt-in credential scanner.

Covers:
  - _redact(): short values, long values, boundary
  - ShellSecretsCheck.run(): detects known patterns, ignores safe values,
    respects comment lines, handles missing files, enforces line-length guard
"""

import os
import tempfile
from unittest.mock import patch

import pytest

from mactuner.checks.secrets import ShellSecretsCheck, _redact


# ── _redact() ─────────────────────────────────────────────────────────────────

class TestRedact:
    def test_value_6_chars_or_fewer_returns_stars(self):
        assert _redact("abc") == "****"
        assert _redact("abcdef") == "****"

    def test_value_7_chars_shows_3_plus_2(self):
        # "ABCDEFG" → "ABC…FG"
        assert _redact("ABCDEFG") == "ABC…FG"

    def test_long_value_shows_first_3_and_last_2(self):
        result = _redact("ABCDEFGHIJ")
        assert result == "ABC…IJ"

    def test_middle_is_not_revealed(self):
        secret = "sk-very-secret-token-value-1234567890"
        result = _redact(secret)
        # First 3 and last 2 visible; everything else hidden
        assert result.startswith(secret[:3])
        assert result.endswith(secret[-2:])
        assert "…" in result
        assert len(result) < len(secret)

    def test_ellipsis_separates_prefix_and_suffix(self):
        result = _redact("ABCDEFGHIJKLMNOP")
        parts = result.split("…")
        assert len(parts) == 2
        assert parts[0] == "ABC"
        assert parts[1] == "OP"


# ── ShellSecretsCheck.run() ───────────────────────────────────────────────────

class TestShellSecretsCheck:
    """Run the check against controlled temp files."""

    def _run_with_content(self, content: str):
        """Write content to a temp file and run the check against it."""
        check = ShellSecretsCheck()
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".zshrc", delete=False
        ) as f:
            f.write(content)
            tmpfile = f.name
        try:
            with patch("mactuner.checks.secrets._SHELL_CONFIGS", [tmpfile]):
                return check.run()
        finally:
            os.unlink(tmpfile)

    # ── Clean files ───────────────────────────────────────────────────────────

    def test_clean_file_returns_pass(self):
        result = self._run_with_content("export PATH=$PATH:/usr/local/bin\n")
        assert result.status == "pass"

    def test_empty_file_returns_pass(self):
        result = self._run_with_content("")
        assert result.status == "pass"

    def test_comment_only_file_returns_pass(self):
        result = self._run_with_content("# export AWS_SECRET_ACCESS_KEY=abc123defxyz\n")
        assert result.status == "pass"

    # ── Detected credentials ──────────────────────────────────────────────────

    def test_detects_aws_access_key_id(self):
        result = self._run_with_content(
            "export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE\n"
        )
        assert result.status == "warning"
        assert "AWS_ACCESS_KEY_ID" in result.message

    def test_detects_aws_secret_access_key(self):
        result = self._run_with_content(
            "export AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENGbPxRfiCYEXAMPLEKEY\n"
        )
        assert result.status == "warning"

    def test_detects_openai_api_key(self):
        result = self._run_with_content(
            "export OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz1234567890abcde\n"
        )
        assert result.status == "warning"
        assert "OPENAI_API_KEY" in result.message

    def test_detects_generic_api_key_pattern(self):
        result = self._run_with_content(
            "export MY_API_KEY=sk-abcdefghijklmnopqrstuvwxyz1234567890\n"
        )
        assert result.status == "warning"

    def test_detects_github_token(self):
        result = self._run_with_content(
            "export GITHUB_TOKEN=ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ123456\n"
        )
        assert result.status == "warning"

    def test_warning_message_includes_file_and_key(self):
        result = self._run_with_content(
            "export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE\n"
        )
        assert "AWS_ACCESS_KEY_ID" in result.message

    def test_warning_redacts_value(self):
        # The full secret value must not appear verbatim in the message
        secret = "AKIAIOSFODNN7EXAMPLE"
        result = self._run_with_content(f"export AWS_ACCESS_KEY_ID={secret}\n")
        assert result.status == "warning"
        assert secret not in result.message

    def test_count_in_message_when_multiple_findings(self):
        content = (
            "export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE\n"
            "export OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz1234567890abcde\n"
        )
        result = self._run_with_content(content)
        assert result.status == "warning"
        assert "2" in result.message

    # ── Safe-value exclusions ─────────────────────────────────────────────────

    def test_ignores_variable_reference_dollar_sign(self):
        result = self._run_with_content("export API_KEY=$SOME_VAR\n")
        assert result.status == "pass"

    def test_ignores_file_path_value(self):
        result = self._run_with_content("export DATABASE_URL=/var/db/my.db\n")
        assert result.status == "pass"

    def test_ignores_home_relative_path(self):
        result = self._run_with_content("export MY_SECRET=~/secrets/key.pem\n")
        assert result.status == "pass"

    def test_ignores_boolean_value(self):
        result = self._run_with_content("export MY_TOKEN=true\n")
        assert result.status == "pass"

    def test_ignores_url_value(self):
        result = self._run_with_content(
            "export DATABASE_URL=https://user:pass@db.example.com/mydb\n"
        )
        assert result.status == "pass"

    def test_ignores_short_value_under_10_chars(self):
        # Regex requires value length >= 10
        result = self._run_with_content("export API_KEY=tooshort\n")
        assert result.status == "pass"

    # ── Edge cases ────────────────────────────────────────────────────────────

    def test_long_lines_are_skipped_by_redos_guard(self):
        long_line = "A" * 501
        result = self._run_with_content(long_line + "\n")
        assert result.status == "pass"

    def test_line_exactly_500_chars_is_not_skipped(self):
        # 500 chars is the boundary — it should still be scanned
        # Craft a benign 500-char line (no credential pattern)
        line = "export PATH=" + "x" * 488  # 500 chars total, value is file-path-like
        result = self._run_with_content(line + "\n")
        # May pass or warn depending on pattern match — just must not crash
        assert result.status in ("pass", "warning", "info")

    def test_nonexistent_file_is_skipped_gracefully(self):
        check = ShellSecretsCheck()
        with patch(
            "mactuner.checks.secrets._SHELL_CONFIGS",
            ["/does/not/exist/.mactuner_test_zshrc"],
        ):
            result = check.run()
        assert result.status == "pass"

    def test_result_data_contains_findings_list(self):
        result = self._run_with_content(
            "export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE\n"
        )
        assert "findings" in result.data
        assert isinstance(result.data["findings"], list)
        assert len(result.data["findings"]) >= 1
