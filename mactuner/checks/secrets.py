"""
Shell secrets check — opt-in via --check-shell-secrets.

Scans shell configuration files for patterns that look like hardcoded
credentials: API keys, passwords, tokens, AWS credentials, etc.

This check is intentionally opt-in because it reads the full content of
shell config files. Values are always truncated before display — the full
secret is never shown.

Design:
  - Match by KEY name pattern (case-insensitive)
  - Require value to look like a real secret (not a variable reference,
    file path, or common non-secret string)
  - One finding per line (stop at first match)
  - Truncate displayed value to first 4 + last 2 chars
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from mactuner.checks.base import BaseCheck, CheckResult


# ── Files to scan ─────────────────────────────────────────────────────────────

_SHELL_CONFIGS = [
    "~/.zshrc",
    "~/.zprofile",
    "~/.zshenv",
    "~/.bashrc",
    "~/.bash_profile",
    "~/.bash_aliases",
    "~/.profile",
]


# ── Key-name patterns that suggest credentials ─────────────────────────────────
#
# Match: export KEY=value  |  KEY=value  |  KEY: value  |  KEY="value"
# Group 1 = the key name, Group 2 = the raw value

_CRED_RE = re.compile(
    r"""
    (?ix)               # case-insensitive, verbose
    (?:export\s+)?      # optional 'export '
    (                   # GROUP 1: key name
        # Specific well-known keys
        AWS_ACCESS_KEY_ID
      | AWS_SECRET_ACCESS_KEY
      | AWS_SESSION_TOKEN
      | GITHUB_TOKEN | GH_TOKEN | GITHUB_PAT
      | OPENAI_API_KEY
      | STRIPE_SECRET_KEY | STRIPE_PUBLISHABLE_KEY
      | SENDGRID_API_KEY
      | TWILIO_AUTH_TOKEN
      | SLACK_TOKEN | SLACK_BOT_TOKEN
      | HEROKU_API_KEY
      | DIGITALOCEAN_ACCESS_TOKEN
      | NPM_TOKEN
      | PYPI_TOKEN
      # Generic patterns (must be a recognisable credential noun)
      | [A-Z][A-Z0-9_]*(?:_API_KEY | _SECRET_KEY | _SECRET | _TOKEN | _PASSWORD | _PASSWD | _PWD | _AUTH | _CREDENTIALS)
      | (?:API_KEY | SECRET_KEY | AUTH_TOKEN | ACCESS_TOKEN | PRIVATE_KEY | DATABASE_URL)[A-Z0-9_]*
    )
    \s*[=:]\s*          # separator
    ["']?               # optional quote
    ([^\s"'#\$\{]{10,}) # GROUP 2: value — at least 10 non-space chars,
                        #           must not start with $ or { (variable refs)
    """,
    re.VERBOSE | re.IGNORECASE,
)


# ── Value allow-list — things that look like values but are NOT secrets ────────

_SAFE_VALUE_RE = re.compile(
    r"""
    ^(
        \$[\w{]       |   # $VARIABLE or ${VAR}
        /             |   # file path
        ~             |   # home-relative path
        https?://     |   # URL (likely not a secret in assignment position)
        [a-z_-]{1,30}$|   # short lowercase word (e.g. "none", "default")
        \d+$          |   # pure number
        true|false|yes|no|on|off  # booleans
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)


# ── Check ─────────────────────────────────────────────────────────────────────

class ShellSecretsCheck(BaseCheck):
    id = "shell_secrets"
    name = "Shell Config Secrets"
    category = "security"
    category_icon = "🔑"

    scan_description = (
        "Scanning shell config files for hardcoded credentials — "
        "API keys and tokens in ~/.zshrc leak into every process you launch "
        "and may end up in committed dotfiles."
    )
    finding_explanation = (
        "Shell config files (like ~/.zshrc) are inherited by every process you start "
        "and are frequently committed to public dotfiles repositories. "
        "Hardcoded secrets in these files mean: (1) every child process inherits them "
        "via the environment, (2) they may be exposed if you ever share your config, "
        "and (3) they cannot be easily rotated without editing the file."
    )
    recommendation = (
        "Move secrets to a dedicated file that is never committed: "
        "create ~/.secrets with your export statements, "
        "add 'source ~/.secrets' to ~/.zshrc, "
        "and add ~/.secrets to ~/.gitignore. "
        "If any secrets were ever committed to a public repo, rotate them immediately."
    )

    fix_level = "instructions"
    fix_description = "Move hardcoded secrets to a gitignored ~/.secrets file."
    fix_steps = [
        "Create ~/.secrets (touch ~/.secrets && chmod 600 ~/.secrets)",
        "Move any 'export SECRET=...' lines from ~/.zshrc to ~/.secrets",
        "Add to ~/.zshrc:  [ -f ~/.secrets ] && source ~/.secrets",
        "Add ~/.secrets to ~/.gitignore (echo '~/.secrets' >> ~/.gitignore)",
        "If any secret was ever committed to a public repo: rotate it now",
    ]
    fix_reversible = True
    fix_time_estimate = "~10 minutes"

    def run(self) -> CheckResult:
        findings: list[dict] = []
        files_scanned: list[str] = []

        for config_str in _SHELL_CONFIGS:
            config_path = Path(os.path.expanduser(config_str))
            if not config_path.exists():
                continue

            files_scanned.append(config_path.name)

            try:
                lines = config_path.read_text(errors="replace").splitlines()
            except (PermissionError, OSError):
                continue

            for lineno, line in enumerate(lines, 1):
                stripped = line.strip()

                # Skip blank lines and comments
                if not stripped or stripped.startswith("#"):
                    continue

                # Guard against pathological lines before running the regex.
                # _CRED_RE uses alternation and quantifiers that can cause
                # quadratic backtracking on extremely long inputs.
                if len(stripped) > 500:
                    continue

                m = _CRED_RE.search(stripped)
                if not m:
                    continue

                key   = m.group(1)
                value = m.group(2)

                # Skip values that are clearly not real secrets
                if _SAFE_VALUE_RE.search(value):
                    continue

                # Redact the value — show only a hint
                display_value = _redact(value)

                findings.append({
                    "file":    str(config_path),
                    "line":    lineno,
                    "key":     key,
                    "display": f"{config_path.name}:{lineno}  {key}={display_value}",
                })
                # Continue to next line — multiple credentials per file are possible

        if not findings:
            n = len(files_scanned)
            return self._pass(
                f"No credential patterns found "
                f"({n} file{'s' if n != 1 else ''} scanned: "
                f"{', '.join(files_scanned) or 'none found'})"
            )

        count = len(findings)
        preview = "  ·  ".join(f["display"] for f in findings[:2])
        suffix  = f"  (+{count - 2} more)" if count > 2 else ""

        return self._warning(
            f"{count} potential hardcoded credential{'s' if count != 1 else ''} "
            f"in shell config: {preview}{suffix}",
            data={"findings": findings, "files_scanned": files_scanned},
        )


def _redact(value: str) -> str:
    """Show first 3 chars + last 2 chars; mask everything in between."""
    if len(value) <= 6:
        return "****"
    return value[:3] + "…" + value[-2:]


# ── Export ────────────────────────────────────────────────────────────────────

ALL_CHECKS = [ShellSecretsCheck]
