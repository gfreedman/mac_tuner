# Mac Audit

**[Full documentation → gfreedman.github.io/mac_audit](https://gfreedman.github.io/mac_audit/)**

**Mac System Health Inspector & Tuner** — narrated, educational, and beautiful.

Runs a full audit of your Mac: security settings, disk health, memory, developer environment, and more. Explains every finding in plain language and can fix issues for you.

```
╭──────────────────────────────────────────────────────────────────╮
│       macaudit  ·  Mac System Health Inspector  ·  v1.0.0        │
│       MacBook Pro (M3 Max)  ·  macOS Sequoia 15.3                │
│       Scan started: Monday 16 Feb 2026  ·  10:41 AM              │
╰──────────────────────────────────────────────────────────────────╯

  Scanning — checks run in parallel

  ✅  macOS Version              macOS 15.3 — current release
  ⚠️   FileVault                 Disk encryption is OFF
  🔴  Firewall                  Firewall is disabled
  ✅  SIP                       System Integrity Protection is enabled
  ℹ️   Outdated Formulae         3 packages out of date
  ⚠️   Disk Space                14.2 GB free — getting low
  ✅  Battery                   342 cycles  ·  96% capacity  ·  Normal
  ...

╭─── Summary ──────────────────────────────────────────────────────╮
│   Health Score   71  [████████████████░░░░░░]  / 100             │
│   🔴 1 Critical    ⚠️ 5 Warnings    ✅ 17 Passed    ℹ️ 4 Info     │
│   🚨  1 critical issue detected — address this first.            │
╰──────────────────────────────────────────────────────────────────╯
```

---

## Install

**Homebrew:**

```bash
brew install gfreedman/macaudit/macaudit
```

**From source:**

```bash
git clone https://github.com/gfreedman/mac_audit
cd mac_audit
bash install.sh
```

**Requirements:** macOS 13 Ventura or later · Python 3.10+

---

## Uninstall

**Homebrew:**

```bash
brew uninstall macaudit
brew untap gfreedman/macaudit   # optional — removes the tap entirely
```

**Remove saved config and scan history**:

```bash
rm -rf ~/.config/macaudit
```

This removes the first-run flag, last scan summary, and MDM notice history. It does not affect any system settings Mac Audit may have changed via `--fix`.

---

## Usage

```bash
# Full narrated audit (read-only)
macaudit

# Show only warnings and criticals
macaudit --issues-only

# Verbose mode — extra educational context for every finding
macaudit --explain

# Enter interactive fix mode after the scan
macaudit --fix

# Auto-apply safe fixes without prompting
macaudit --fix --auto

# Run only specific categories
macaudit --only security,disk,homebrew

# Skip specific categories
macaudit --skip dev_env,network

# Force a profile
macaudit --profile developer
macaudit --profile creative
macaudit --profile standard

# Opt-in privacy check: scan shell configs for hardcoded secrets
macaudit --check-shell-secrets

# Exit with code 2 if critical issues found (useful in CI / scripts)
macaudit --fail-on-critical

# Quiet mode — just the score
macaudit --quiet

# JSON output for scripting (schema_version field included for forward compatibility)
macaudit --json > report.json
macaudit --json | jq '.score'

# Disable colour output (also respected via NO_COLOR=1 env var)
NO_COLOR=1 macaudit
```

---

## What It Checks

Mac Audit runs **69 checks** across 10 categories:

| Category | Checks |
|---|---|
| **System** | macOS version, pending updates, SIP, FileVault, Firewall (inbound-only), Firewall stealth mode, Gatekeeper, Time Machine, automatic security updates, screen lock, Rosetta, Secure Boot |
| **Security** | Auto-login, guest account, SSH keys (presence + strength + config), launch agents, login/logout hooks, cron jobs, /etc/hosts, sharing services, Activation Lock, MDM profiles, system root CA certificates, system extensions, XProtect signature freshness |
| **Privacy** | Guided review of Full Disk Access, Screen Recording, and Accessibility grants |
| **Homebrew** | brew doctor, outdated formulae & casks, orphaned dependencies, cleanup savings |
| **Disk** | Free space, APFS snapshots, Xcode DerivedData, Docker usage, Trash, caches |
| **Hardware** | Battery cycle count & condition, SMART status (boot volume), kernel panics, thermal throttling |
| **Memory** | Memory pressure, swap usage, top CPU & memory consumers |
| **Network** | AirDrop visibility, Remote Login, Screen Sharing, File Sharing, Internet Sharing, DNS, proxy, saved Wi-Fi, Bluetooth, listening ports (TCP + UDP) |
| **Dev Env** | Xcode CLTools, Python/Ruby PATH conflicts, conda, Node managers, git config |
| **Apps** | App Store updates (via mas), iCloud status, login items |

Plus **opt-in**: `--check-shell-secrets` scans `~/.zshrc` and other shell configs for hardcoded API keys, passwords, and tokens.

---

## Health Score

Scores run from 0–100, starting at 100:

| Finding | Deduction |
|---|---|
| Critical issue | −10 pts |
| Critical in security/privacy/system | −15 pts |
| Warning | −3 pts |
| Warning in security/privacy/system | −4 pts |
| Info / Pass / Skip | 0 pts |

**Score bands:** 95–100 Excellent · 85–94 Very Good · 70–84 Good · 55–69 Fair · <55 Poor

---

## Fix Mode

Run `macaudit --fix` after the scan to step through fixes one at a time.

Each fix gets its own card showing the full context — what was found, why it matters, what the fix does, and an estimated time. You approve or skip before anything runs:

```
╭─── [1/4]  Homebrew Orphaned Dependencies ────────────────────────────╮
│  ⚠️  WARNING   🤖  Automatic                                          │
│                                                                       │
│  79 orphaned dependencies taking up space                             │
│  Packages installed as dependencies but no longer needed by any      │
│  formula. Safe to remove.                                             │
│                                                                       │
│  What this fix does                                                   │
│  Runs brew autoremove to remove orphaned packages                     │
│  $ brew autoremove                                                    │
│                                                                       │
│  ⏱ ~10s  ·  reversible  ·                                            │
╰───────────────────────────────────────────────────────────────────────╯
  Apply? [y/N] ›
```

- **🤖 Automatic** — runs a shell command, streams output live
- **🤖🔐 Requires password** — uses a native macOS authentication dialog (not a terminal sudo prompt)
- **👆 Opens Settings** — opens the exact System Settings pane with guidance on what to change
- **📋 Step-by-step** — prints manual instructions

Auto-apply all safe fixes without prompting:

```bash
macaudit --fix --auto
```

Mac Audit never modifies anything without `--fix`. Every fix shows what it will do before asking for confirmation. Irreversible fixes are labelled clearly.

---

## Profiles

Mac Audit auto-detects the right profile based on your setup:

| Profile | When | Checks |
|---|---|---|
| `developer` | Homebrew detected | Full suite including Homebrew, dev env |
| `standard` | No Homebrew | Security, disk, hardware, network |
| `creative` | Force with `--profile creative` | Storage, battery, performance, security |

Override with `--profile developer/creative/standard`.

---

## Requirements

- macOS 13 Ventura or later (including pre-release versions)
- Intel or Apple Silicon
- Python 3.10+
- Homebrew optional (checks skip gracefully if absent)
- [mas](https://github.com/mas-cli/mas) optional (for App Store update checks)

---

## Safety Guarantees

- **Read-only by default** — nothing changes without `--fix`
- **No private APIs** — no TCC.db access, no private frameworks
- **No data sent** — runs entirely offline
- **Graceful** — one failing check never crashes the scan
- **Transparent** — every command is shown before running
- **Reversibility labelled** — irreversible fixes are always marked
- **MDM-aware** — detects managed Macs and notes that IT-enforced settings may appear as warnings
- **Locale-safe** — forces `LANG=C` on all subprocess calls for consistent results regardless of system language
- **Multi-user note** — checks run in the context of the current user only; other accounts are not audited

---

## JSON Output

```bash
macaudit --json | jq '{score, summary: .summary}'
```

```json
{
  "schema_version": 1,
  "macaudit_version": "1.3.0",
  "scan_time": "2026-02-18T20:00:00+00:00",
  "system": {
    "macos_version": "15.3",
    "architecture": "arm64",
    "model": "MacBook Pro"
  },
  "score": 84,
  "summary": {
    "pass": 17,
    "warning": 5,
    "critical": 1,
    "info": 4,
    "skip": 2
  },
  "results": [...]
}
```

---

*Built with [Claude Code](https://claude.ai/claude-code) · macOS Native Apps Engineer Reviewed*
