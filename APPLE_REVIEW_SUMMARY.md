# Apple Engineer Review - Executive Summary

## Review Outcome: ✅ Approved with Critical Revisions Required

**Overall Verdict:** "This is a genuinely useful tool with excellent UX thinking. The technical implementation needs revision to work reliably across macOS versions and respect system boundaries."

---

## What Works (Keep These)

✅ Educational "teach while you tune" UX philosophy  
✅ Jobs-to-be-Done framework and user mindset mapping  
✅ Read-only by default, fix mode requires explicit confirmation  
✅ Beautiful terminal UI with rich library  
✅ Profile system (developer / creative / standard)  
✅ Health score concept  
✅ Progressive disclosure (3-level information hierarchy)  

---

## Critical Technical Issues Fixed

### 🔴 BLOCKING ISSUES - Must Fix Before Build

1. **TCC Permission Enumeration** → Changed to MANUAL/GUIDED
   - Cannot read TCC.db programmatically without private frameworks
   - Tool opens System Settings, provides guide on what to look for

2. **APFS Snapshot Auto-Delete** → Changed to INFO only
   - Too dangerous to auto-delete
   - Time Machine manages these
   - Suggest `tmutil thinlocalsnapshots` instead

3. **Kernel Extension Checks** → REMOVED entirely
   - KEXTs are obsolete on macOS 11+
   - Use `systemextensionsctl list` instead if needed

4. **Homebrew Assumption** → Made optional
   - Many users don't have Homebrew
   - Auto-detect and skip if not present
   - Check for MacPorts as alternative

5. **Shell Credential Scanning** → Changed to opt-in only
   - Privacy violation risk
   - Requires `--check-shell-secrets` flag
   - Show clear warning before scanning

---

### 🟡 IMPORTANT REVISIONS - Improve Reliability

6. **MDM Profile Inspection** → Presence only, not deep inspection
7. **Root Certificates** → Use `security dump-trust-settings` not `find-certificate`
8. **Launch Agents** → Expanded paths (add /System, /Library/LaunchDaemons, etc.)
9. **Firewall Check** → Add stealth mode, logging status
10. **SSH Keys** → RSA 2048 is fine, flag <2048 and DSA only
11. **Auto-Login** → Use `defaults read` not plist parsing
12. **Python/Node** → Simplify to PATH conflicts only
13. **Docker** → Detect Docker Desktop vs Colima vs OrbStack vs Podman
14. **Sudo Prompts** → Use `osascript` for native password dialogs

---

## New Checks to Add

✨ **Activation Lock Status** (critical for used Macs)  
✨ **Secure Boot Policy** (Apple Silicon only - Full/Reduced/Permissive)  
✨ **iCloud Sync Status** (silent failures are common)  
✨ **Saved Wi-Fi Networks** (problematic networks cause issues)  

---

## Architecture Requirements Added

🏗️ **macOS Version Detection** - Required before every check  
🏗️ **Error Handling Pattern** - Every subprocess needs try/except/timeout  
🏗️ **Health Score Algorithm** - Now explicitly defined:
```
Start at 100
Critical: -10 points (×1.5 for security/system)
Warning: -3 points (×1.2 for security/system)
Info/Pass: 0 points
```

🏗️ **Test Matrix** - Must test on:
- macOS 13 / 14 / 15
- Intel + Apple Silicon
- With and without Homebrew

---

## UX Improvements

📝 **Tone Guidance** - Avoid condescension, be precise not dramatic  
📝 **Optional `--explain` Mode** - Verbose for non-technical, concise by default  
📝 **Native Password Dialogs** - Use osascript instead of terminal sudo  

---

## Next Steps

1. ✅ Review documented in `apple_engineer_review.md`
2. ✅ Technical changes listed in `TECHNICAL_REVISIONS.md`
3. 🔄 **TODO:** Update CLAUDE.md sections:
   - Check registry tables
   - Fix capability map
   - Add health score algorithm
   - Add version detection requirements
   - Update privacy check to MANUAL/GUIDED
4. 🔄 **TODO:** Update UX flows PDF with revised approach

---

**Ship Criteria:** 
- Every check tested on macOS 13, 14, 15 (Intel + Apple Silicon)
- Comprehensive error handling on all subprocess calls
- No private API usage
- All assumptions about tool availability checked explicitly

---

*Review completed by: Senior Software Engineer, macOS System Apps, Apple Park*  
*Review date: February 17, 2026*
