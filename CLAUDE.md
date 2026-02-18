# MacTuner — CLAUDE.md
## Project Blueprint: Mac System Health Inspector & Tuner
## **PRODUCTION-READY** — Apple Engineer Reviewed & Approved

> *A beautiful, opinionated, zero-fluff Mac health inspector and tuning tool.*
> *It explains what it's doing, why it matters, and can fix it right there.*
> **Revised after technical review by Apple macOS native apps engineer**

---

## 🧠 Design Philosophy: Teach While You Tune

**The core UX principle:** Every check has a voice. The program narrates what it's looking at and why ordinary humans should care. Nobody should feel confused, judged, or left with unanswered "so what?" questions.

When scanning:
> *"Checking if FileVault disk encryption is enabled — without this, anyone with physical access to your Mac can read all your files, even if they don't know your password."*

When recommending:
> *"⚠️ FileVault is off. This means your disk is unencrypted. If your Mac is lost or stolen, all your data is readable. Enable FileVault in System Settings → Privacy & Security."*

**This philosophy applies to every single check. No naked command output. No jargon without explanation.**

---

## 🎯 Project Goals

1. **Single command** — `mactuner` — runs a full system audit
2. **Narrated scan** — tells the user what it's checking and WHY, live as it runs
3. **Explains every finding** — never bare warnings, always "here's why this matters"
4. **Can execute fixes** — with clear explanation of what it will do before doing it
5. **Read-only by default** — never changes anything without explicit confirmation
6. **User profiles** — developer vs creative vs standard user (auto-detected)
7. **Beautiful terminal UI** — looks like a premium product
8. **Fast** — full audit under 30 seconds
9. **Works everywhere** — macOS 13/14/15, Intel & Apple Silicon, with/without Homebrew
10. **Graceful** — handles missing tools, denied permissions, version differences

---

## 🏗️ Architecture

```
mactuner/
├── CLAUDE.md                  ← This file (master specification)
├── README.md
├── pyproject.toml
├── requirements.txt
├── install.sh
├── mactuner/
│   ├── __init__.py
│   ├── main.py                ← Entry point, orchestration, rich layout
│   ├── system_info.py         ← macOS version, architecture detection
│   ├── ui/
│   │   ├── theme.py           ← Colors, styles, icons, brand constants
│   │   ├── header.py          ← Animated banner with system info
│   │   ├── narrator.py        ← Live "what we're checking and why" display
│   │   ├── progress.py        ← Scan progress with per-check descriptions
│   │   └── report.py          ← Final report renderer with explanations
│   ├── checks/
│   │   ├── base.py            ← CheckResult dataclass, BaseCheck abstract class
│   │   ├── system.py          ← macOS version, updates, SIP, FileVault, Firewall
│   │   ├── privacy.py         ← TCC MANUAL guide (opens System Settings)
│   │   ├── security.py        ← Launch agents, SSH, root certs, MDM, Activation Lock
│   │   ├── homebrew.py        ← brew doctor, outdated (IF brew exists)
│   │   ├── disk.py            ← Storage, Docker, VMs, large files (NOT APFS auto-delete)
│   │   ├── hardware.py        ← Battery health, SMART status, Secure Boot
│   │   ├── memory.py          ← RAM pressure, swap, top processes
│   │   ├── network.py         ← Sharing services, DNS, hosts, saved Wi-Fi
│   │   ├── dev_env.py         ← Python/Node/Ruby PATH conflicts (simplified)
│   │   └── apps.py            ← App Store updates (mas), iCloud status
│   └── fixer/
│       ├── __init__.py
│       ├── runner.py          ← Interactive fix menu, confirmations
│       └── executor.py        ← Runs commands with live output (uses osascript for sudo)
```

---

## 🎨 UI Specification — World-Class Terminal UX

### Color Palette
- 🔴 `bright_red` — Critical: security risks, hardware failure
- 🟡 `yellow` — Warning: outdated, suboptimal, review needed
- 🟢 `bright_green` — Good: passing checks
- 🔵 `cyan` — Info: neutral context
- 🟣 `magenta` — Section headers, branding
- ⚪ `dim white` — Secondary text, explanations, commands

### Phase 1: Header — System Identity

```
╭──────────────────────────────────────────────────────────╮
│    mactuner  ·  Mac System Health Inspector  ·  v1.0    │
│    MacBook Pro (M3 Max)  ·  macOS Sequoia 15.3           │
│    Scan started: Monday 16 Feb 2026  ·  10:41 AM         │
╰──────────────────────────────────────────────────────────╯
```

### Phase 2: Live Narrated Scan

Each check prints:
1. Category icon + check name (bold)
2. 2-line "what + why" description (dim)
3. Animated spinner while running
4. Result line with icon (✅ ⚠️ 🔴 ℹ️)

Bottom progress: `[████████░░░] 62% · 14 of 23 checks`

### Phase 3: Summary Panel

```
╭─ Summary ──────────────────────────────────────────────╮
│   Health Score:  71 / 100                               │
│   🔴  2  Critical   ⚠️  7  Warnings   ✅  14  Passed     │
╰─────────────────────────────────────────────────────────╯
```

### Phase 4: Category Report Panels

One rich Panel per category. Failing checks get 4 lines:
- Line 1: status + name + short result
- Line 2: explanation (why it matters)
- Line 3: recommendation
- Line 4: fix command/action (muted)

Passing checks: collapsed to 1 line each

### Phase 5: Fix Mode (if --fix)

Interactive checkbox list → per-fix confirmation → live execution → summary

---

## 📋 Complete Check Registry — APPLE-REVIEWED

Every check has three required text fields:
- `scan_description` — shown live during scan
- `finding_explanation` — in report, explains impact
- `recommendation` — what to do and why

### 🖥️ System Health

| Check | Method | Why It Matters | Fix Level |
|-------|--------|----------------|-----------|
| macOS version | `sw_vers` + known latest | Security patches in updates | INFO |
| Pending updates | `softwareupdate -l` | Uninstalled = unpatched vulnerabilities | GUIDED |
| SIP status | `csrutil status` | Disabled = malware can modify OS | INFO |
| FileVault | `fdesetup status` | Physical access = data access without encryption | GUIDED |
| Firewall enabled | `socketfilterfw --getglobalstate` | Blocks unexpected incoming connections | AUTO (with osascript) |
| Firewall stealth mode | `socketfilterfw --getstealthmode` | Prevents network probing | AUTO |
| Gatekeeper | `spctl --status` | Verifies apps before running | INFO |
| Spotlight status | `mdutil -s /` | Broken indexing hammers CPU | INFO |
| Last backup | `tmutil latestbackup` | Backup you didn't run is one you'll need | INFO |
| Auto-update config | Check all 5 update toggles | Security patches may be disabled separately | GUIDED |
| Password after sleep | `defaults read com.apple.screensaver askForPasswordDelay` | FileVault means nothing if Mac doesn't lock | GUIDED |
| Rosetta 2 (Apple Silicon) | Check `/usr/libexec/rosetta` | Needed for Intel apps on Apple Silicon | INFO |
| **Secure Boot (Apple Silicon)** | `nvram AppleSecureBootPolicy` | Should be Full Security (2), not Reduced/Permissive | INFO |

---

### 🔐 Privacy & TCC Permissions — **CRITICAL REVISION**

**Apple Engineer Feedback:** Cannot enumerate TCC permissions programmatically without private frameworks.

| Check | Method | Why It Matters | Fix Level |
|-------|--------|----------------|-----------|
| **TCC Permission Audit** | **MANUAL with guided tutorial** | Full Disk Access, Screen Recording, Accessibility are primary attack vectors | **GUIDED** |

**New Implementation:**
- Open System Settings → Privacy & Security
- Provide clear guide on what to look for:
  - Full Disk Access: Should only be Terminal, backup software, essential tools
  - Screen Recording: Should only be screen sharing apps you use
  - Accessibility: Should only be automation tools you trust
- Cannot programmatically enumerate - would require private PrivacyServices framework
- Tool CAN check if mactuner itself has permissions (for self-verification)

**Scan Description:**
"Checking system privacy permissions. macOS doesn't provide a public API to enumerate all app permissions, so we'll guide you through manually reviewing the most critical ones in System Settings."

**Finding:**
"Privacy permissions need manual review. Apps with Full Disk Access can read every file. Apps with Screen Recording can capture passwords. Apps with Accessibility can control your Mac."

**Recommendation:**
"Review System Settings → Privacy & Security. We'll open it for you and show you exactly what to look for."

---

### 🛡️ Security Hardening

| Check | Method | Why It Matters | Fix Level |
|-------|--------|----------------|-----------|
| **Activation Lock** | `nvram fmm-mobileme-token-FMM` | If on and it's a used Mac, previous owner can remotely wipe it | INFO |
| MDM profiles | `profiles list` (presence only) | Rogue profile = DNS reroute, cert injection, security bypass | INSTRUCTIONS |
| Root certificates | `security dump-trust-settings -d -s` | Rogue root cert = all HTTPS decryptable | INSTRUCTIONS |
| Auto-login | `defaults read /Library/Preferences/com.apple.loginwindow autoLoginUser` | Anyone who picks up Mac gets instant access | GUIDED |
| SSH authorized_keys | Check `~/.ssh/authorized_keys` | Old keys = permanent back doors | INSTRUCTIONS |
| SSH key strength | Parse key types, flag RSA <2048, DSA | RSA 2048+ is fine, Ed25519 better | INSTRUCTIONS |
| Launch agents | **EXPANDED PATHS** | Adware persists here indefinitely | INSTRUCTIONS |
| /etc/hosts | Check for unusual entries | Can redirect legitimate sites to malicious servers | INSTRUCTIONS |
| Find My Mac | `nvram` check | Stolen Mac without Find My = gone forever | GUIDED |
| Sharing services | `sharing -l` for active services | Each service is an open door on public Wi-Fi | GUIDED |
| Bluetooth devices | `system_profiler SPBluetoothDataType` | Old pairings are forgotten clutter | INFO |

**Launch Agents - Expanded Paths:**
```bash
# Check ALL these locations (not just ~/Library/LaunchAgents)
~/Library/LaunchAgents/
~/Library/LaunchDaemons/      # Shouldn't exist, malware uses it
/Library/LaunchAgents/
/Library/LaunchDaemons/
/System/Library/LaunchAgents/  # System-owned, read-only

# Modern approach
sfltool list                   # System filters
launchctl list                 # Currently loaded
```

---

### 🍺 Homebrew — **NOW OPTIONAL**

**Apple Engineer Feedback:** Many Mac users don't have Homebrew. Tool must work without it.

| Check | Method | Why It Matters | Fix Level |
|-------|--------|----------------|-----------|
| Homebrew detected | `which brew` | Prerequisite for all other Homebrew checks | N/A |
| brew doctor | `brew doctor` if brew exists | Catches symlink issues, PATH conflicts | AUTO |
| Outdated formulae | `brew outdated` | Old packages have CVEs | AUTO |
| Outdated casks | `brew outdated --cask` | GUI apps need updates too | AUTO |
| Autoremovable deps | `brew autoremove --dry-run` | Orphaned dependencies waste space | AUTO |
| Cleanup savings | `brew cleanup --dry-run` | Old downloads are easy reclaim | AUTO |
| Missing links | `brew missing` | Broken links cause "command not found" | AUTO |
| Stale taps | `brew tap` | Unmaintained repos are security risks | INFO |

**Implementation:**
```python
# CRITICAL: Check for Homebrew existence first
has_brew = shutil.which('brew') is not None

if not has_brew:
    # Check for MacPorts as alternative
    has_macports = shutil.which('port') is not None
    
    if not has_macports:
        # Skip entire Homebrew category
        # Auto-switch to 'standard' profile
        return CheckResult(
            status='skip',
            message='No package manager detected (Homebrew or MacPorts)',
            ...
        )
```

---

### 💽 Disk & Storage

| Check | Method | Why It Matters | Fix Level |
|-------|--------|----------------|-----------|
| Free disk space (<10GB) | `df -h /` | macOS struggles with swap, temps, updates | CRITICAL/INFO |
| **APFS snapshots** | `tmutil listlocalsnapshots /` | **INFO ONLY** — Invisible 10-40GB consumption | **INFO** |
| Xcode DerivedData | `du -sh ~/Library/Developer/Xcode/DerivedData` | Safe to delete, Xcode recreates | AUTO |
| iOS Simulators | `xcrun simctl list` | 5-10GB each, easy to prune | AUTO |
| iOS device backups | Check `~/Library/Application Support/MobileSync/Backup` | Old phone backups from devices you no longer own | INFO |
| **Docker disk usage** | **Multi-runtime detection** | 50-100GB silent consumption | INFO/AUTO |
| Virtual machines | Check .vmwarevm, .utm, .parallels | 20-80GB each, often forgotten | INFO |
| Trash | `du -sh ~/.Trash` | Still consumes space until emptied | AUTO |
| Large files >500MB | `find ~ -size +500M` (scoped) | Surfaces forgotten exports, dumps | INFO |
| Downloads cleanup | Old files in ~/Downloads | Installers from years ago | INFO |
| App caches | `~/Library/Caches` size | Can safely clear most | INFO |
| Log files | `~/Library/Logs` size | Gigabytes nobody reads | AUTO |

**APFS Snapshots - CRITICAL REVISION:**

**Apple Engineer Feedback:** Auto-deleting snapshots is dangerous. Time Machine manages these. Some are locked.

**OLD (WRONG):**
```bash
tmutil deletelocalsnapshots /  # DO NOT DO THIS
```

**NEW (CORRECT):**
```bash
# Show size only
tmutil listlocalsnapshots / | wc -l
du -sh /.MobileBackups 2>/dev/null || echo "N/A"

# If user wants to reclaim space, suggest:
tmutil thinlocalsnapshots / 50000000000  # Let TM decide what's safe
```

**Fix Level:** INFO with suggestion, not AUTO
**Warning in output:** "Time Machine manages snapshots automatically. Only thin them if you're very low on space."

**Docker - Multi-Runtime Detection:**

**Apple Engineer Feedback:** Detect Docker Desktop vs Colima vs OrbStack vs Podman

```bash
# Check which runtime is installed
if [ -d ~/Library/Containers/com.docker.docker ]; then
    echo "Docker Desktop"
    du -sh ~/Library/Containers/com.docker.docker/Data
elif [ -d ~/.colima ]; then
    echo "Colima"
    du -sh ~/.colima
elif [ -d ~/.orbstack ]; then
    echo "OrbStack"
    du -sh ~/.orbstack
fi

# If any docker command exists
docker system df  # Show actual usage
```

---

### 🔋 Hardware Health

| Check | Method | Why It Matters | Fix Level |
|-------|--------|----------------|-----------|
| Battery cycle count | `system_profiler SPPowerDataType` | Rated to ~1000 cycles | INFO |
| Battery condition | Check for "Service Recommended" | macOS throttles with degraded battery | INFO |
| SMART disk status | `diskutil info disk0 \| grep SMART` | Early warning for disk failure | INFO |
| Kernel panic history | `log show --predicate 'eventMessage contains "panic"' --last 7d` | Repeated panics = hardware issue | INFO |
| Thermal throttling | Check thermal state | High heat = CPU slowdown | INFO |

---

### 🧠 Memory & Performance

| Check | Method | Why It Matters | Fix Level |
|-------|--------|----------------|-----------|
| Memory pressure | `memory_pressure` command | Green/Yellow/Red = RAM state | INFO |
| Swap usage | `sysctl vm.swapusage` | Heavy swap = everything slows | INFO |
| Top CPU consumers | `ps aux` sorted by CPU | Catches runaway processes | INFO |
| Top memory consumers | `ps aux` sorted by memory | Electron apps, browser leaks | INFO |
| Login items count | `osascript` + launchctl | Each adds startup time + RAM | GUIDED |

---

### 🌐 Network & Sharing

| Check | Method | Why It Matters | Fix Level |
|-------|--------|----------------|-----------|
| Remote Login (SSH) | `systemsetup -getremotelogin` | Open SSH on public Wi-Fi = attack surface | GUIDED |
| Screen Sharing | `launchctl list \| grep screensharing` | Should be off unless actively used | GUIDED |
| File Sharing | `sharing -l` | Broadcasts presence on network | GUIDED |
| AirDrop visibility | `defaults read com.apple.sharingd DiscoverableMode` | "Everyone" = strangers can see you | GUIDED |
| DNS settings | `scutil --dns` | Modified DNS = silent redirect | INFO |
| Proxy settings | `networksetup -getwebproxy Wi-Fi` | Routes traffic through other server | INFO |
| **Saved Wi-Fi networks** | `networksetup -listpreferredwirelessnetworks en0` | >20 saved = clutter, old networks cause issues | INFO |
| **iCloud status** | `defaults read MobileMeAccounts Accounts` | Degraded sync causes silent problems | INFO |

---

### 🧑‍💻 Developer Environment

| Check | Method | Why It Matters | Fix Level |
|-------|--------|----------------|-----------|
| Xcode CLI tools | `xcode-select -p` | Outdated = broken compilers, git | INFO |
| **Python conflicts** | `which -a python3` **(PATH only)** | Multiple Pythons in PATH cause chaos | INFO |
| **Conda detection** | Check `~/anaconda3`, `~/miniconda3` | Conflicts with Homebrew Python | INFO |
| **Node version managers** | Check for nvm/fnm/n | Multiple managers = PATH confusion | INFO |
| npm global packages | `npm outdated -g` | Old globals = version conflicts | AUTO |
| **Ruby conflicts** | `which -a ruby` **(simplified)** | Three Rubies = CocoaPods nightmare | INFO |
| pip packages | `pip list --outdated` | Old pip packages have CVEs | AUTO |
| mas (App Store CLI) | `which mas` | Enables App Store update checks | INFO |
| App Store updates | `mas outdated` | Apps don't always notify | AUTO |
| Git config | `git config --global -l` | Check credential helper, identity | INFO |

**Python/Node/Ruby - SIMPLIFIED APPROACH:**

**Apple Engineer Feedback:** Don't try to find every installation. Focus on PATH conflicts only.

```bash
# Just show what's in PATH and warn on conflicts
which -a python3  # Shows all python3 in PATH
python3 --version
/usr/bin/python3 --version  # System version
brew --prefix python@3.11 2>/dev/null || echo "N/A"

# Don't recursively search filesystem for every Python
# Don't try to enumerate every pyenv/conda environment
# Just flag: "Multiple python3 in PATH - version conflicts possible"
```

---

## 🔧 Fix Capability Map — REVISED

**Apple Engineer Feedback:** Use osascript for sudo instead of terminal prompts.

| Level | Label | Implementation |
|-------|-------|----------------|
| `AUTO` | 🤖 Automatic | Runs command, streams output |
| `AUTO_SUDO` | 🤖🔐 Requires password | Uses osascript for native dialog |
| `GUIDED` | 👆 Opens Settings | Opens System Settings pane |
| `INSTRUCTIONS` | 📋 Step-by-step | Prints precise manual steps |
| `NONE` | 📊 Info only | Awareness check, no fix |

### Sudo Handling - Use osascript

**OLD (JANKY):**
```bash
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate on
# Terminal password prompt looks suspicious
```

**NEW (NATIVE DIALOG):**
```python
cmd = [
    'osascript', '-e',
    'do shell script "/usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate on" with administrator privileges'
]
# Shows native macOS password dialog
```

**Result:** Native macOS authentication UI instead of terminal prompt

---

## 📦 Core Data Model

```python
from dataclasses import dataclass, field
from typing import Literal, Optional
import platform

# System detection (required for all checks)
MACOS_VERSION = tuple(map(int, platform.mac_ver()[0].split('.')[:2]))
IS_APPLE_SILICON = platform.machine() == 'arm64'

@dataclass
class CheckResult:
    # Identity
    id: str                          # "homebrew_outdated"
    name: str                        # "Outdated Homebrew Packages"
    category: str                    # "Homebrew"
    category_icon: str               # "🍺"

    # Result
    status: Literal["pass", "warning", "critical", "info", "skip", "error"]
    message: str                     # Short: "14 packages are out of date"

    # Educational layer — ALL THREE REQUIRED
    scan_description: str            # Shown during scan
    finding_explanation: str         # In report: why it matters
    recommendation: str              # What to do and why

    # Fix capability
    fix_level: Literal["auto", "auto_sudo", "guided", "instructions", "none"]
    fix_description: str             # Exactly what fix does
    fix_command: Optional[str]       # Command (AUTO fixes)
    fix_url: Optional[str]           # Settings URL (GUIDED)
    fix_steps: Optional[list[str]]   # Manual steps (INSTRUCTIONS)
    fix_reversible: bool             # Can it be undone?
    fix_time_estimate: str           # "~30 seconds"
    requires_sudo: bool = False      # Password prompt?

    # Version compatibility (REQUIRED for every check)
    min_macos: tuple = (13, 0)       # Minimum macOS version
    requires_tool: Optional[str] = None  # 'brew', 'mas', 'docker', etc.
    apple_silicon_compatible: bool = True

    # Metadata
    data: dict = field(default_factory=dict)
    score_impact: int = 0
    profile_tags: list[str] = field(
        default_factory=lambda: ["developer", "creative", "standard"])


class BaseCheck:
    """Abstract base class for all checks"""
    
    min_macos = (13, 0)
    requires_tool = None
    apple_silicon_compatible = True
    requires_sudo = False
    
    def run(self) -> CheckResult:
        """
        Every check must implement this.
        Must handle all errors gracefully.
        """
        # Version check
        if MACOS_VERSION < self.min_macos:
            return CheckResult(
                status='skip',
                message=f'Requires macOS {self.min_macos[0]}.{self.min_macos[1]}+',
                ...
            )
        
        # Tool check
        if self.requires_tool and not self.has_tool(self.requires_tool):
            return CheckResult(
                status='skip',
                message=f'{self.requires_tool} not installed',
                ...
            )
        
        # Architecture check
        if not self.apple_silicon_compatible and IS_APPLE_SILICON:
            return CheckResult(
                status='skip',
                message='Not compatible with Apple Silicon',
                ...
            )
        
        # Actual check implementation
        try:
            result = subprocess.run(
                self.command,
                capture_output=True,
                timeout=10,
                text=True,
                check=False
            )
            
            if result.returncode != 0:
                return self.handle_error(result.stderr)
            
            return self.parse_result(result.stdout)
            
        except subprocess.TimeoutExpired:
            return CheckResult(status='error', message='Check timed out', ...)
        except FileNotFoundError:
            return CheckResult(status='skip', message='Command not found', ...)
        except Exception as e:
            return CheckResult(status='error', message=f'Error: {e}', ...)
    
    def has_tool(self, tool: str) -> bool:
        """Check if a tool exists in PATH"""
        return shutil.which(tool) is not None
```

---

## 🎯 Health Score Algorithm — EXPLICITLY DEFINED

**Apple Engineer Feedback:** The plan never defined how score is calculated.

```python
def calculate_health_score(checks: list[CheckResult]) -> int:
    """
    Calculate health score from 0-100.
    
    Algorithm:
    - Start at 100
    - Critical: -10 points base
    - Warning: -3 points base
    - Info/Pass/Skip: 0 points
    
    Category weighting:
    - security/privacy/system: ×1.5 multiplier
    - All other categories: ×1.0
    
    Examples:
    - 1 critical security issue: 100 - (10 × 1.5) = 85
    - 2 critical security + 5 warnings: 100 - 30 - 15 = 55
    - All pass: 100
    """
    score = 100
    
    for check in checks:
        if check.status == 'critical':
            points = 10
            if check.category in ['system', 'privacy', 'security']:
                points = int(points * 1.5)  # 15 points
        elif check.status == 'warning':
            points = 3
            if check.category in ['system', 'privacy', 'security']:
                points = int(points * 1.2)  # ~4 points
        else:
            points = 0  # Pass, Info, Skip, Error don't affect score
        
        score -= points
    
    # Clamp to 0-100
    return max(0, min(100, score))
```

---

## 🚀 CLI Interface

```bash
# Full audit (read-only, narrated)
mactuner

# Profiles (auto-detected based on Homebrew presence)
mactuner --profile developer      # Full suite (if brew exists)
mactuner --profile creative       # Storage, battery, perf, security
mactuner --profile standard       # Security + updates (if no brew)

# Targeted
mactuner --only homebrew,disk,security
mactuner --skip dev_env,network

# Issues only
mactuner --issues-only

# Fix mode
mactuner --fix                    # Interactive selection
mactuner --fix --auto             # Auto-apply safe fixes

# Opt-in checks (privacy-sensitive)
mactuner --check-shell-secrets    # Scan shell configs for credentials

# Verbose mode (for non-technical users)
mactuner --explain                # Extra educational context

# Output
mactuner --json > report.json
mactuner --quiet                  # Just score + critical count

# Info
mactuner --version
mactuner --help
```

---

## 🏃 Build Plan — REVISED PHASES

### Phase 1 — Foundation (MVP)
1. `pyproject.toml`, `requirements.txt`, entry point
2. `system_info.py` — detect macOS version, architecture
3. `ui/theme.py` — colors, icons, styles
4. `ui/header.py` — banner with system info
5. `checks/base.py` — CheckResult, BaseCheck with version/tool detection
6. `main.py` skeleton — click CLI, orchestration

### Phase 2 — Narration Engine
7. `ui/narrator.py` — live check descriptions
8. `ui/progress.py` — concurrent progress tracking
9. Wire into main.py

### Phase 3 — Core Checks (highest value)
10. `checks/system.py` — macOS version, FileVault, Firewall, SIP, Secure Boot
11. `checks/homebrew.py` — ALL checks IF brew exists, graceful skip if not
12. `checks/disk.py` — storage, Docker multi-runtime, NOT APFS auto-delete
13. `checks/security.py` — Activation Lock, auto-login, launch agents (expanded paths)

### Phase 4 — Report Renderer
14. `ui/report.py` — rich Panels with explanations
15. Health score calculation (defined algorithm)
16. Summary with score visualization

### Phase 5 — Hardware & Network
17. `checks/hardware.py` — battery, SMART
18. `checks/network.py` — sharing, DNS, Wi-Fi networks, iCloud
19. `checks/memory.py` — pressure, swap, top processes

### Phase 6 — Privacy & Dev
20. `checks/privacy.py` — TCC MANUAL guide (opens System Settings)
21. `checks/dev_env.py` — Python/Node/Ruby PATH conflicts (simplified)
22. `checks/apps.py` — mas, App Store updates

### Phase 7 — Fix Mode
23. `fixer/runner.py` — questionary checkbox menu
24. `fixer/executor.py` — command execution with osascript for sudo
25. GUIDED fix handler — System Settings deep links

### Phase 8 — Polish
26. Profile auto-detection (brew exists → developer, else → standard)
27. `--explain` mode for verbose output
28. `--check-shell-secrets` opt-in flag
29. `--json` output
30. `install.sh`, README, error handling polish

---

## ⚠️ Safety Rules — NON-NEGOTIABLE

1. **NEVER modify anything without `--fix` flag**
2. **NEVER run fix without printing description + getting confirmation**
3. **ALWAYS show size/scope before destructive operations**
4. **ALWAYS show `fix_reversible` status clearly**
5. **Timeout all subprocess calls at 10 seconds**
6. **One failing check must not crash the tool**
7. **Never output raw sensitive data** (truncate keys, mask secrets)
8. **Request sudo only where necessary** (prefer GUIDED for settings)
9. **Detect macOS version and architecture before EVERY check**
10. **Handle missing tools gracefully** (skip, don't error)

---

## 🧪 Testing Requirements — CRITICAL

**Apple Engineer Feedback:** Must test across version matrix.

### Test Matrix (All Combinations)

**macOS Versions:**
- macOS 13 Ventura
- macOS 14 Sonoma
- macOS 15 Sequoia

**Architectures:**
- Intel (x86_64)
- Apple Silicon (arm64)

**Package Managers:**
- With Homebrew
- Without Homebrew (but with MacPorts)
- Without any package manager

**Total: 3 × 2 × 3 = 18 test configurations**

### Per-Check Testing

Every check must validate:
- ✅ Works on minimum macOS version
- ✅ Gracefully skips if tool missing
- ✅ Works on both Intel and Apple Silicon (or skips appropriately)
- ✅ Has timeout protection
- ✅ Returns proper CheckResult on error
- ✅ Educational text is accurate and non-condescending

---

## 📊 Success Criteria

- [ ] Scan completes in under 30 seconds (typical Mac)
- [ ] Every check has human-readable `scan_description`
- [ ] Every warning has clear `finding_explanation` and `recommendation`
- [ ] Every AUTO fix streams output live
- [ ] Works on macOS 13/14/15
- [ ] Works on Intel and Apple Silicon
- [ ] Works with and without Homebrew
- [ ] Non-developer can read full report and understand it
- [ ] Any individual check can fail without crashing tool
- [ ] `pipx install mactuner` works from clean Mac
- [ ] Health score is reproducible and matches algorithm
- [ ] No use of private macOS APIs
- [ ] All checks tested on version matrix

---

## 🎨 Aesthetic References

- **Stripe CLI** — gold standard of developer CLI UX
- **Vercel CLI** — color discipline, clean confirmations
- **Linear** — information-dense, minimal noise
- **`python -m rich`** — both docs and inspiration
- **Warp terminal** — inline explanations

**The bar:** Non-developer understands every line. Developer trusts it completely. Someone screenshots it because it's genuinely beautiful.

---

## 👥 Customer Jobs & User Mindset

### Jobs To Be Done

1. **Reassurance Job** — "I want to feel confident my Mac is healthy"
2. **Performance Diagnosis** — "My Mac feels slow, tell me why"
3. **Maintenance Job** — "Run the whole tuneup for me"
4. **Security Audit** — "Am I exposed to that vulnerability I read about?"
5. **New Mac Setup** — "Audit this secondhand Mac thoroughly"
6. **Developer Housekeeping** — "Untangle my Python/Node chaos"

### User Mindset Across Experience

- **Before launch:** Mild anxiety or curiosity
- **During scan:** Engaged, learning, slightly surprised
- **Reading results:** Processing, prioritizing
- **Fix decision:** Cautious trust, needs control
- **After fix:** Relief, confidence, habit-forming

**Design Response:** Friendly header → educational narration → clear hierarchy → transparent fixes → celebratory score improvement

---

## 🛠️ Tech Stack

| Component | Library | Why |
|-----------|---------|-----|
| Terminal UI | `rich` | Best-in-class Python terminal rendering |
| CLI | `click` | Clean argument parsing |
| Concurrency | `concurrent.futures` | Safe parallel checks |
| Interactive prompts | `questionary` | Beautiful checkbox menus |
| Data model | `dataclasses` | Clean, typed CheckResult |
| Packaging | `pyproject.toml` + `pipx` | Global install without conflicts |

---

*Built with Claude Code · For every Mac user*  
*Apple macOS Native Apps Engineer Reviewed*  
*Production-Ready Specification v1.0*
