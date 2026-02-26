# Changelog

All notable changes to Mac Audit are documented here.

## [1.7.2] — 2026-02-25

### Added
- **Category headers in live scan** — bold icon + name header with thin underline and spacing between each category section, so checks are no longer one flat list

---

## [1.7.1] — 2026-02-24

### Fixed
- Summary panel emoji alignment — status counts line (`Critical / Warnings / Passed / Info`) now uses consistent 2-cell-wide icons from the theme instead of hardcoded `⚠️` and `ℹ️` which have variation selectors that render at inconsistent widths across terminals

### Added
- **CONTRIBUTING.md** — dev setup, project structure, check contract, testing patterns, profile system, release process, and style guide for new contributors

---

## [1.7.0] — 2026-02-24

### Added
- **`release.sh` — single-command release script:** `./release.sh X.Y.Z` handles version bump, changelog validation, commit/tag/push, GitHub release with human-written notes, and full Homebrew formula regeneration (BFS-resolved dependency tree from PyPI) in one idempotent command

---

## [1.6.0] — 2026-02-24

### Added
- **Arrow-key fix prompts:** replaced raw `input()` with interactive arrow-key menus powered by `simple-term-menu` — highlight follows cursor properly
- **Quit option:** every fix prompt now has a Quit choice to bail out of the session
- **`--dry-run` flag:** walk through the entire fix flow without executing any changes
- **Homebrew install docs:** README and docs site now include Homebrew install instructions for new users

### Fixed
- Menu title no longer duplicates when holding down arrow keys (moved title out of `TerminalMenu` redraw loop)
- Loop variable `idx` no longer shadowed by `menu.show()` return value, fixing card numbering on subsequent fixes
- Release workflow now skips gracefully if the GitHub Release already exists

### Changed
- Replaced `questionary` dependency with `simple-term-menu` (no `prompt_toolkit` conflict with Rich)

---

## [1.5.0] — 2026-02-20

### Changed
- **Parallel check execution:** checks now run concurrently via `ThreadPoolExecutor(max_workers=8)`, cutting scan time from ~35–45s to ~10–15s. Results print in deterministic category order. Serial path preserved for `--quiet`/`--json`.
- Scan narrator simplified: spinner + progress bar replaces per-check description panels

---

## [1.3.0] — 2026-02-19

### Added
- **Mode-aware header:** right column shows active mode (🔍 scan / 🔧 fix / 🎯 targeted) with contextual tips
- **Recommendations panel:** after every scan, surfaces the top fixable items and the exact command to run next
- **Pre-scan prompt:** count of checks + press ↵ to begin (skip with `-y`)
- **Sequential fix cards:** `--fix` now shows one rich card per fix (status, explanation, command, time, reversibility) and prompts inline — no more checkbox pre-selection menu
- **MDM warning suppression:** advisory banner only appears on first run; silenced on subsequent runs
- **Console width cap:** all panels capped at 120 columns regardless of terminal width
- **Light-mode palette:** all `white`/`dim white` style strings replaced with palette-aware constants — readable in both dark and light terminals
- **Hero copy button:** clipboard icon on the `brew install` command in the docs site

### Fixed
- Removed `questionary` dependency (no longer used since fix mode was rewritten)
- Docs site Quick Start code boxes now align vertically across all three step cards
- Docs site install/uninstall grid uses equal-width 3-column layout

---

## [1.2.0] — 2026-02-18

### Added
- **10 new security checks:** Guest Account, SSH Server Config (sshd_config), Login/Logout Hooks, Cron Jobs, System Extensions, XProtect signature freshness
- **2 new network checks:** Internet Sharing, improved Listening Ports (now covers UDP as well as TCP)
- **`--fail-on-critical` flag:** exits with code 2 when critical issues are found (enables scripting/CI use)
- **Scan duration** displayed in the Summary panel at the end of every scan
- **Localization fix:** all subprocess calls now force `LANG=C`/`LC_ALL=C`, preventing false results on non-English macOS

### Fixed
- SMART disk check now targets the boot volume (`diskutil info /`) instead of hardcoded `disk0`
- `BaseCheck.shell()` now forces C locale for consistent English output on all systems
- Secrets scanner now finds all credentials per file (was stopping after first match per file)
- LoginItemsCheck now uses `osascript System Events` for accurate login item counts (previously `launchctl list` over-counted dramatically)
- Executor `run_auto_fix` now passes `fix_command` as a string with `shell=True` so `~` and glob patterns expand correctly
- `auto_sudo` fix commands in system.py are now plain shell commands (previously double-wrapped in AppleScript)

### Changed
- Firewall check now discloses that macOS Application Firewall (ALF) is **inbound-only** and notes that outbound filtering requires a third-party tool
- ListeningPortsCheck now also scans UDP and skips loopback-only listeners (reducing false positives)

---

## [1.1.0] — 2026-02-17

### Added
- **3 new checks:** Bluetooth discoverability, Listening Ports (TCP), System Root Certificates (MITM detection)
- MDM-enrolled Mac detection: prints advisory banner if device is under MDM management
- `SavedWifiCheck` now dynamically discovers the Wi-Fi interface (was assuming `en0`)
- `SIPCheck` now detects partially-disabled SIP ("custom configuration") and reports it as a warning

### Fixed
- Critical bug: `auto_sudo` fix commands were double-wrapped in AppleScript, silently breaking all 4 privileged fixes
- Critical bug: `run_auto_fix` used `shlex.split()` + `shell=False`, preventing `~` and `*` expansion
- `LoginItemsCheck` replaced `launchctl list` (massively over-counts) with `osascript System Events` query
- `score_impact` field removed (was dead code — `calculate_health_score` never read it)
- Removed `_SYSTEM_LABEL_PREFIXES` from `LoginItemsCheck` (no longer needed)

### Changed
- `ActivationLockCheck` message now correctly says "Find My is configured — Activation Lock is likely active" (avoids overstating certainty)

---

## [1.0.0] — 2026-02-16

Initial release.

### Checks (62 total across 10 categories)
- **System:** macOS version, pending updates, SIP, FileVault, Firewall, Gatekeeper, Time Machine, auto-updates, screen lock, Rosetta 2, Secure Boot
- **Security:** auto-login, SSH keys (presence + strength), launch agents, /etc/hosts, sharing services, Activation Lock, MDM profiles, system root CAs
- **Privacy:** TCC guided review (Full Disk Access, Screen Recording, Accessibility)
- **Homebrew:** brew doctor, outdated formulae/casks, orphaned dependencies, cache size
- **Disk:** free space, APFS snapshots, DerivedData, Docker usage, Trash, caches
- **Hardware:** battery cycle count/condition, SMART status, kernel panics, thermal throttling
- **Memory:** pressure, swap, top CPU/memory consumers
- **Network:** AirDrop, Remote Login, Screen/File Sharing, DNS, proxy, saved Wi-Fi
- **Dev Env:** Xcode CLTools, Python/Ruby PATH, conda, Node managers, git config
- **Apps:** App Store updates (via mas), iCloud status, login items

### Features
- Narrated scan with live spinner and Rich progress
- Health score 0–100 with category-weighted deductions
- Fix mode (`--fix`): interactive menu + auto mode (`--auto`)
- Four fix levels: `auto`, `auto_sudo` (native macOS password dialog), `guided`, `instructions`
- Profiles: `developer`, `standard`, `creative` (auto-detected)
- Opt-in credential scanner: `--check-shell-secrets`
- JSON output: `--json`
- Category filtering: `--only`, `--skip`
- MDM-aware, graceful error handling, read-only by default
