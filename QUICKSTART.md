# QUICKSTART — For Claude Code

## You're about to build MacTuner

**What it is:** Mac system health inspector with beautiful terminal UI and educational narration.

**Your blueprint:** `CLAUDE.md` — read it fully before starting. It's production-ready and Apple-engineer-reviewed.

---

## Pre-Flight Check

This project has been thoroughly reviewed by an Apple macOS native apps engineer. All critical technical issues have been addressed:

✅ TCC permissions → MANUAL/GUIDED (not database access)  
✅ APFS snapshots → INFO only (not auto-delete)  
✅ Homebrew → optional, not assumed  
✅ Health score → algorithm explicitly defined  
✅ Version detection → required before every check  
✅ Error handling → pattern defined for all subprocess calls  

---

## First Command

```bash
cd /home/claude/mactuner
cat CLAUDE.md  # Read the full spec first
```

**Critical sections to read:**
- 📋 Complete Check Registry (what checks to build)
- 🔧 Fix Capability Map (how fixes work)
- 🎯 Health Score Algorithm (scoring logic)
- 📦 Core Data Model (CheckResult dataclass)
- ⚠️ Safety Rules (non-negotiable constraints)
- 🧪 Testing Requirements (version matrix)

---

## Build Order — Follow Exactly

### Phase 1: Foundation (do this first, in order)

1. **Setup project structure**
   ```bash
   # Create pyproject.toml with dependencies
   # rich, click, questionary
   ```

2. **Build `system_info.py`**
   ```python
   import platform
   
   MACOS_VERSION = tuple(map(int, platform.mac_ver()[0].split('.')[:2]))
   IS_APPLE_SILICON = platform.machine() == 'arm64'
   
   def get_system_info():
       # Returns dict with macOS version, architecture, model
   ```
   **WHY FIRST:** Every check needs this. Don't skip.

3. **Build `ui/theme.py`**
   - All colors as named constants
   - All icons as named constants
   - Export everything

4. **Build `ui/header.py`**
   - Rich Panel with system info from system_info.py
   - Shows: tool name, version, Mac model, macOS, scan time

5. **Build `checks/base.py`**
   ```python
   @dataclass
   class CheckResult:
       # Copy full dataclass from CLAUDE.md
       # This is the contract — don't deviate
   
   class BaseCheck:
       # Copy full base class from CLAUDE.md
       # Includes version detection, tool detection, error handling
   ```

6. **Build `main.py` skeleton**
   - Click CLI with flags: --fix, --profile, --only, --skip, --explain, --json, --quiet
   - Orchestration loop (import checks, run sequentially, collect results)
   - Don't implement everything — just skeleton

**Checkpoint:** You should be able to run `python -m mactuner.main` and see header + "No checks implemented yet"

---

### Phase 2: Narration (the UX heart)

7. **Build `ui/narrator.py`**
   - For each check: print 2-line description before running
   - Use rich.live for animated spinner
   - Replace spinner with result line when done

8. **Build `ui/progress.py`**
   - Bottom progress bar: `[████░░░] 40% · 9 of 23`
   - Update live as checks complete

9. **Wire into main.py**

**Checkpoint:** Scan should feel alive, not frozen

---

### Phase 3: First Checks (prove the system works)

10. **Build `checks/system.py`**
    - Start with: macOS version check (easiest)
    - Then: FileVault, Firewall, SIP
    - Each check is a class inheriting from BaseCheck
    - Each check implements `run()` returning CheckResult
    - Follow error handling pattern from CLAUDE.md

11. **Build `checks/homebrew.py`**
    - CRITICAL: First check if brew exists
    - If not: return status='skip' for all Homebrew checks
    - If yes: run brew doctor, outdated, etc.

12. **Build `checks/disk.py`**
    - Free space check
    - Large files
    - Xcode DerivedData
    - APFS snapshots → INFO only, not auto-delete

**Checkpoint:** Run scan, see real checks execute, see results

---

### Phase 4: Report Renderer

13. **Build `ui/report.py`**
    - One rich.Panel per category
    - Failing checks: 4 lines (result / explanation / recommendation / fix)
    - Passing checks: 1 line
    - Use CLAUDE.md check registry for exact text

14. **Build health score calculation**
    - Copy algorithm exactly from CLAUDE.md
    - Critical: -10 base (×1.5 for security/system)
    - Warning: -3 base (×1.2 for security/system)
    - Start at 100, clamp to 0-100

15. **Build summary panel**
    - Score number (large, colored)
    - Count of Critical/Warning/Passed/Info
    - One-line verdict

**Checkpoint:** Full scan → beautiful report with score

---

### Phase 5: Remaining Checks

16-19. Build remaining check modules (follow CLAUDE.md registry)

**Checkpoint:** All checks implemented

---

### Phase 6: Fix Mode

20. **Build `fixer/runner.py`**
    - questionary checkbox menu
    - Pre-select: AUTO fixes that are reversible
    - For each selected fix: confirm before running

21. **Build `fixer/executor.py`**
    - Run commands with live output streaming
    - For sudo: use osascript, not terminal prompt
    ```python
    cmd = ['osascript', '-e', 
           f'do shell script "{command}" with administrator privileges']
    ```

22. **GUIDED fix handler**
    - Open System Settings with deep link
    - Example: `open "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles"`

**Checkpoint:** Fix mode works end-to-end

---

### Phase 7: Polish

23. Profile auto-detection
24. --explain verbose mode
25. --check-shell-secrets opt-in flag
26. --json output
27. README, install.sh

---

## Common Pitfalls to Avoid

❌ **Don't** try to read TCC.db directly → Open System Settings instead  
❌ **Don't** auto-delete APFS snapshots → Show size only, suggest thinlocalsnapshots  
❌ **Don't** assume Homebrew exists → Check first, skip gracefully  
❌ **Don't** use terminal sudo prompts → Use osascript for native dialogs  
❌ **Don't** forget version detection → Check macOS version before every check  
❌ **Don't** skip error handling → Every subprocess needs try/except/timeout  

---

## Critical Files to Reference

📘 `CLAUDE.md` — Your master spec (read sections as you build)  
📘 `apple_engineer_review.md` — Technical feedback (explains why things are the way they are)  
📘 `TECHNICAL_REVISIONS.md` — Before/after for every major change  

---

## When You're Stuck

1. Re-read the relevant section of CLAUDE.md
2. Check apple_engineer_review.md for the "why"
3. Look at the error handling pattern in BaseCheck
4. Remember: checks should skip gracefully, never crash the tool

---

## Success Looks Like

Running `mactuner` produces:
- Beautiful header with system info
- Live narrated scan (you can read what each check does)
- Rich report panels organized by severity
- Health score that makes sense
- Fix mode that's transparent and safe
- Works on Mac with or without Homebrew
- Handles errors gracefully

---

**Ready? Start with Phase 1, step 1. Build incrementally. Test frequently.**

*The spec is comprehensive. Trust it. Every edge case has been considered.*
