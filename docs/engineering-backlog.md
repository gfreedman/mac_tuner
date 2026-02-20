# Mac Audit — Engineering Backlog

Issues identified during senior-engineer review (Apple HW + Google Systems perspectives).
The four hardware.py issues have already been fixed. The six items below are documented
for future work.

---

## 1. `shell=True` audit liability in executor.py

**File:** `macaudit/fixer/executor.py` — `run_auto_fix()`

**Issue:** Fix commands from check metadata (e.g. `"brew autoremove"`, `"brew cleanup -s"`) are
passed to `subprocess.run()` with `shell=True`. This means the OS shell interprets the command
string, which creates a command-injection surface if a future check ever derives a command from
user-supplied or environment data.

**Recommended fix:** Store fix commands as lists (`["brew", "autoremove"]`) in each check's
metadata. Pass them to `subprocess.run()` as a list with `shell=False`. Where a single string
is needed for display (the "What this fix does" card), join the list with spaces at render time.

**Priority:** Medium. Current fix commands are all hardcoded literals, so actual risk is low
today, but the pattern should be corrected before any check derives command parts dynamically.

---

## 2. Incomplete `osascript do shell script` escaping in executor.py

**File:** `macaudit/fixer/executor.py` — `run_auto_sudo_fix()`

**Issue:** The current escaper only handles `\` and `"` characters:

```python
safe = cmd.replace("\\", "\\\\").replace('"', '\\"')
script = f'do shell script "{safe}" with administrator privileges'
```

This misses: `$()`, backticks (`` ` ``), single quotes, and other shell metacharacters. If a
future sudo fix command ever includes a `$` variable reference or backtick substitution (even
unintentionally in a path), the `osascript` shell will interpret it.

**Recommended fix:** Same as item 1 — store commands as lists and use `shlex.join()` to produce
a properly-quoted string for embedding in the AppleScript:

```python
import shlex
safe = shlex.join(cmd_list)
script = f'do shell script "{safe.replace(chr(34), chr(92)+chr(34))}" with administrator privileges'
```

Or, better, pass the command via `argv` rather than embedding it in an AppleScript string.

**Priority:** Medium. Same low-risk-today caveat as item 1.

---

## 3. Parallel check execution

**File:** `macaudit/main.py` — `_run_checks()`

**Issue:** 69 checks run serially. Most checks are I/O-bound (subprocess calls, file reads).
A `concurrent.futures.ThreadPoolExecutor` with 8–12 workers would cut total scan time from
~35–45 s to ~10–15 s on an M-series Mac.

**Constraints to handle:**
- `@lru_cache` on `_get_power_data()` and similar module-level caches must be thread-safe (they
  are — Python's GIL protects `lru_cache` dict writes, and `subprocess.run` is I/O that releases
  the GIL).
- Narrator (`start_check` / `finish_check`) uses Rich's `Live` context — needs a lock around
  `finish_check` to prevent interleaved output.
- Check ordering in the final report should remain deterministic regardless of completion order
  (sort results by original `all_checks` index after collection).

**Estimated effort:** ~2–3 hours.
**Priority:** Low (UX improvement, not correctness). Users perceive the current narrated scan
as interactive, so the time doesn't feel wasted.

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
