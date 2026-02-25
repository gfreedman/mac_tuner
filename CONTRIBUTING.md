# Contributing to Mac Audit

## Dev setup

```bash
git clone https://github.com/gfreedman/mac_audit.git
cd mac_audit
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

Run tests:

```bash
.venv/bin/python -m pytest
```

Run the tool locally:

```bash
.venv/bin/python -m macaudit.main
# or, after pip install -e:
macaudit
```

## Project structure

```
macaudit/
  main.py              CLI entry point (Click), scan orchestration
  system_info.py       macOS version/arch detection
  checks/
    base.py            CheckResult dataclass + BaseCheck ABC (the contract)
    system.py          macOS version, SIP, FileVault, Firewall, etc.
    security.py        SSH keys, launch agents, sharing services, etc.
    privacy.py         TCC guided review
    homebrew.py        brew doctor, outdated, orphaned deps
    disk.py            free space, APFS snapshots, Docker, trash
    hardware.py        battery, SMART, kernel panics, thermal
    memory.py          memory pressure, swap, top consumers
    network.py         AirDrop, listening ports, DNS, Wi-Fi
    dev_env.py         Xcode CLTools, Python/Ruby, conda, git
    apps.py            App Store updates, login items
    secrets.py         shell config credential scanning (opt-in)
  fixer/
    runner.py          fix session orchestration
    executor.py        4 fix executors (auto, auto_sudo, guided, instructions)
  ui/
    header.py          pre-scan header with mode indicators
    report.py          post-scan summary + category panels
    narrator.py        live scan progress (spinner + bar)
    theme.py           Rich palette — all colors/icons defined here
    welcome.py         first-run onboarding + last scan summary
    progress.py        check progress tracking
tests/
  conftest.py          autouse fixture to clear lru_cache between tests
  test_base.py         CheckResult fields, BaseCheck gates, shell() helper
  test_executor.py     all 4 fix types, subprocess mocking
  test_checks_system.py, test_health_score.py, test_profile_filter.py, ...
```

## How checks work

Every check is a class that inherits from `BaseCheck` and implements `run()`.

The orchestrator calls `execute()` (not `run()` directly) — it gates on macOS
version, required tools, and architecture before delegating to `run()`.

### The check contract

Each check class must set these attributes:

| Attribute | Example |
|-----------|---------|
| `id` | `"filevault_status"` |
| `name` | `"FileVault Encryption"` |
| `category` | `"system"` |
| `category_icon` | `"💻"` |
| `scan_description` | What + why (shown during scan) |
| `finding_explanation` | Why this matters (shown in report) |
| `recommendation` | What to do about it |
| `fix_level` | `"auto"`, `"auto_sudo"`, `"guided"`, `"instructions"`, or `"none"` |
| `fix_description` | Exactly what the fix does |
| `profile_tags` | Tuple of `"developer"`, `"creative"`, `"standard"` |

And implement `run()` which must return a `CheckResult` via the helper methods:

- `self._pass("message")` — check passed
- `self._warning("message")` — non-critical issue
- `self._critical("message")` — critical issue
- `self._info("message")` — informational (no pass/fail)
- `self._skip("reason")` — check skipped
- `self._error("message")` — check errored

### Running shell commands

Use `self.shell(cmd)` — never `subprocess.run()` directly:

```python
rc, stdout, stderr = self.shell(["diskutil", "info", "/"])
```

It handles timeouts (default 10s), forces `LANG=C` for consistent English
output, and returns `(-1, "", "error message")` on failure.

### Example: a minimal check

```python
class MyNewCheck(BaseCheck):
    id = "my_new_check"
    name = "My New Check"
    category = "system"
    category_icon = "💻"

    scan_description = "Checking something important on your Mac."
    finding_explanation = "This matters because..."
    recommendation = "You should do X to fix this."

    fix_level = "none"
    fix_description = "No automatic fix available."

    profile_tags = ("developer", "creative", "standard")

    def run(self) -> CheckResult:
        rc, out, _ = self.shell(["some", "command"])
        if rc != 0:
            return self._error("Could not run some command")
        if "bad" in out:
            return self._warning("Something is not ideal")
        return self._pass("Everything looks good")
```

### Registering a new check

Add your class to the `ALL_CHECKS` list at the bottom of the relevant
category file (e.g. `checks/system.py`). The orchestrator in `main.py`
imports these lists and runs them in order.

## Testing

Tests mock `shell()` return values and assert on `CheckResult` fields:

```python
def test_my_check_warns_on_bad_output(mocker):
    check = MyNewCheck()
    mocker.patch.object(check, "shell", return_value=(0, "bad stuff", ""))
    result = check.execute()   # always call execute(), not run()
    assert result.status == "warning"
    assert "not ideal" in result.message
```

Call `check.execute()` in tests (not `run()`) so the version/tool/arch
gates are exercised too.

The `conftest.py` autouse fixture clears `lru_cache` between tests to
prevent state leakage from cached system info.

## Profiles

Three profiles control which checks run:

| Profile | Auto-detected when | Checks included |
|---------|-------------------|-----------------|
| `developer` | Homebrew is installed | All checks |
| `standard` | No Homebrew | Skips homebrew + some dev_env checks |
| `creative` | `--profile creative` | Same as developer minus heavy dev checks |

Each check declares its applicable profiles via `profile_tags`. Filtering
happens in `_collect_checks()` in `main.py`.

## Cutting a release

```bash
# 1. Write a changelog entry in CHANGELOG.md:
#    ## [X.Y.Z] — YYYY-MM-DD
#    ### Added / Fixed / Changed
#    - description of changes

# 2. Run the release script:
./release.sh X.Y.Z
```

The script handles everything: preflight checks, version bump, commit, tag,
push, GitHub release (with your changelog as the body), and full Homebrew
formula regeneration.

Run `./release.sh --preflight-only` to check your environment without
changing anything.

## Style guide

No linter is configured yet. Follow the existing conventions:

- PascalCase for classes, snake_case for functions and variables
- Type hints on function signatures
- Docstrings on classes and public methods
- All colors and icons come from `ui/theme.py` — never hardcode markup
- `shell=False` on all subprocess calls (safety)
