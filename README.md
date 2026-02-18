# MacTuner

**Mac System Health Inspector & Tuner** — narrated, educational, and beautiful.

Runs a full audit of your Mac: security settings, disk health, memory, developer environment, and more. Explains every finding in plain language and can fix issues for you.

```
╭──────────────────────────────────────────────────────────────────╮
│       mactuner  ·  Mac System Health Inspector  ·  v1.0.0        │
│       MacBook Pro (M3 Max)  ·  macOS Sequoia 15.3                │
│       Scan started: Monday 16 Feb 2026  ·  10:41 AM              │
╰──────────────────────────────────────────────────────────────────╯

  Scanning — every check is explained as it runs

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

**Recommended — [pipx](https://pipx.pypa.io)** (installs globally without affecting system Python):

```bash
pipx install mactuner
```

**Alternatively — pip:**

```bash
pip3 install --user mactuner
```

**From source:**

```bash
git clone https://github.com/your-org/mactuner
cd mactuner
bash install.sh
```

**Requirements:** macOS 13 Ventura or later · Python 3.10+

---

## Usage

```bash
# Full narrated audit (read-only)
mactuner

# Show only warnings and criticals
mactuner --issues-only

# Verbose mode — extra educational context for every finding
mactuner --explain

# Enter interactive fix mode after the scan
mactuner --fix

# Auto-apply safe fixes without prompting
mactuner --fix --auto

# Run only specific categories
mactuner --only security,disk,homebrew

# Skip specific categories
mactuner --skip dev_env,network

# Force a profile
mactuner --profile developer
mactuner --profile creative
mactuner --profile standard

# Opt-in privacy check: scan shell configs for hardcoded secrets
mactuner --check-shell-secrets

# Quiet mode — just the score
mactuner --quiet

# JSON output for scripting
mactuner --json > report.json
mactuner --json | jq '.score'
```

---

## What It Checks

MacTuner runs **59 checks** across 10 categories:

| Category | Checks |
|---|---|
| **System** | macOS version, pending updates, SIP, FileVault, Firewall, Gatekeeper, Time Machine, screen lock, Rosetta, Secure Boot |
| **Security** | Auto-login, SSH keys, launch agents, /etc/hosts, sharing services, Activation Lock, MDM profiles |
| **Privacy** | Guided review of Full Disk Access, Screen Recording, and Accessibility grants |
| **Homebrew** | brew doctor, outdated formulae & casks, orphaned dependencies, cleanup savings |
| **Disk** | Free space, APFS snapshots, Xcode DerivedData, Docker usage, Trash, caches |
| **Hardware** | Battery cycle count & condition, SMART status, kernel panics, thermal throttling |
| **Memory** | Memory pressure, swap usage, top CPU & memory consumers |
| **Network** | AirDrop visibility, Remote Login, Screen/File Sharing, DNS, proxy, saved Wi-Fi |
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

Run `mactuner --fix` after the scan to enter the interactive fix menu.

```
  Found 4 fixable issues:  3 🤖 Automatic    1 👆 Opens Settings

  ◉  🤖  Homebrew Orphaned Dependencies — 79 deps can be removed
  ◉  🤖  Homebrew Cache — 1.2 GB can be reclaimed
  ○  👆  FileVault — disk encryption is off
  ○  👆  Firewall — incoming connections are unrestricted
```

- **🤖 Automatic** — runs a shell command, streams output live
- **🤖🔐 Requires password** — uses a native macOS authentication dialog (not a terminal sudo prompt)
- **👆 Opens Settings** — opens the exact System Settings pane with guidance on what to change
- **📋 Step-by-step** — prints manual instructions

MacTuner never modifies anything without `--fix`. Every fix shows what it will do before asking for confirmation. Irreversible fixes are labelled clearly.

---

## Profiles

MacTuner auto-detects the right profile based on your setup:

| Profile | When | Checks |
|---|---|---|
| `developer` | Homebrew detected | Full suite including Homebrew, dev env |
| `standard` | No Homebrew | Security, disk, hardware, network |
| `creative` | Force with `--profile creative` | Storage, battery, performance, security |

Override with `--profile developer/creative/standard`.

---

## Requirements

- macOS 13 Ventura, 14 Sonoma, or 15 Sequoia
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

---

## JSON Output

```bash
mactuner --json | jq '{score, summary: .summary}'
```

```json
{
  "mactuner_version": "1.0.0",
  "scan_time": "2026-02-17T20:00:00+00:00",
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
