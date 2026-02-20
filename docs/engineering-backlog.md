# Mac Audit — Engineering Backlog

Issues identified during senior-engineer review (Apple HW + Google Systems perspectives).
The four hardware.py issues have already been fixed. The six items below are documented
for future work.

---

## ~~1. `shell=True` audit liability in executor.py~~ ✅ Fixed

Stored fix commands as `list[str]` in all check definitions. `run_auto_fix()` now uses
`shell=False`. Display strings produced via `shlex.join()` at render time.

---

## ~~2. Incomplete `osascript do shell script` escaping in executor.py~~ ✅ Fixed

`run_auto_sudo_fix()` now uses `shlex.join()` to produce a properly-quoted shell string from
the command list before embedding in AppleScript. This handles all shell metacharacters
correctly.

---

## ~~3. Parallel check execution~~ ✅ Fixed

`_run_checks()` now uses `ThreadPoolExecutor(max_workers=8)` for narrated mode. Results flush
in input order via an in-order buffer so the report stays deterministic. `ScanNarrator` shows a
generic spinner + progress bar instead of per-check panels. Serial path preserved for
`--quiet`/`--json`.

---

## ~~4. Module-level console captures terminal width at import time~~ ✅ Fixed

Removed `_WIDTH` computation and explicit `width=` arg from `Console(...)`. Rich now queries
terminal width dynamically on each render.

---

## ~~5. `lru_cache` state leaks between test runs~~ ✅ Fixed

Added `tests/conftest.py` with an `autouse` fixture that calls `.cache_clear()` on all three
cached functions (`_get_power_data`, `_fetch_software_updates`, `get_system_info`) after each test.

---

## 6. No integration tests for subprocess output parsing

**Issue:** The test suite exercises check logic with mocked `shell()` return values, but there
are no tests that verify parsing against real (or realistic) `diskutil`, `system_profiler`,
`pmset`, or `socketfilterfw` output. If Apple changes the output format of any of these tools
in a future macOS release, the parsing will silently break and checks will return wrong results.

**Recommended fix:** Add a `tests/fixtures/` directory with captured real output from each
checked tool (one file per tool, per architecture where output differs). Write parametrised
tests that feed these fixtures through the parsing logic and assert on the parsed fields
(not the final `CheckResult` status, which depends on business logic).

Example fixture: `tests/fixtures/diskutil_info_apple_silicon.txt` (captured from `diskutil info /`
on an M-series Mac) → test that `SMARTStatusCheck._parse_smart_status()` returns `"Not Supported"`.

**Priority:** Medium. Protects against silent regressions as macOS evolves.

---

*Reviewed: 2026-02-19 · Engineers: Apple HW + Google Systems*
