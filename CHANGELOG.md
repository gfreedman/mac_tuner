# Changelog

All notable changes to MacTuner are documented here.

## [1.2.0] — Unreleased

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
