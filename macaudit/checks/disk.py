"""
Disk and storage checks.

Covers free space, APFS snapshots (INFO only — never auto-delete),
Xcode artifacts, Docker multi-runtime, Trash, caches, logs,
and iOS backups.
"""

import re
import subprocess
from pathlib import Path

from macaudit.checks.base import BaseCheck, CheckResult

HOME = Path.home()


def _du(path: Path, timeout: int = 10) -> int:
    """
    Return size of path in bytes, or -1 on error.

    Accepts exit code 1 (du reports this when some subdirs are unreadable
    due to permissions but still produces valid output for what it could read).
    """
    if not path.exists():
        return 0
    try:
        r = subprocess.run(
            ["du", "-sk", str(path)],
            capture_output=True, text=True, timeout=timeout, check=False,
        )
        # du exits 1 when it hits permission-denied subdirs but still outputs
        # a total — accept that result
        if r.stdout and r.stdout.strip():
            parts = r.stdout.strip().split()
            if parts and parts[0].isdigit():
                return int(parts[0]) * 1024
    except Exception:
        pass
    return -1


def _fmt(size_bytes: int) -> str:
    """Human-readable size string."""
    if size_bytes < 0:
        return "unknown"
    for unit, threshold in [("GB", 1e9), ("MB", 1e6), ("KB", 1e3)]:
        if size_bytes >= threshold:
            return f"{size_bytes / threshold:.1f} {unit}"
    return f"{size_bytes} B"


def _df_free_bytes(path: str = "/") -> int:
    """Return free disk space in bytes, or -1 on error."""
    try:
        r = subprocess.run(
            ["df", "-k", path],
            capture_output=True, text=True, timeout=5, check=False,
        )
        if r.returncode == 0:
            lines = r.stdout.strip().splitlines()
            if len(lines) >= 2:
                parts = lines[1].split()
                # df -k: Filesystem 1K-blocks Used Available ...
                if len(parts) >= 4:
                    return int(parts[3]) * 1024
    except Exception:
        pass
    return -1


# ── Checks ────────────────────────────────────────────────────────────────────

class DiskSpaceCheck(BaseCheck):
    id = "disk_space"
    name = "Free Disk Space"
    category = "disk"
    category_icon = "💽"

    scan_description = (
        "Checking available disk space — macOS needs free space for virtual "
        "memory, software updates, temporary files, and app caches."
    )
    finding_explanation = (
        "When free space drops below ~10 GB, macOS struggles: swap gets "
        "compressed aggressively (slowing everything), software updates fail "
        "to download, and apps crash trying to write temporary files."
    )
    recommendation = (
        "Free up space by emptying the Trash, removing unused apps, "
        "clearing ~/Library/Caches, and deleting large files you no longer need. "
        "macOS's Storage Management (Apple menu → About This Mac → More Info → Storage) "
        "can help identify space hogs."
    )
    fix_level = "guided"
    fix_description = "Opens Storage Management"
    fix_url = "x-apple.systempreferences:com.apple.settings.Storage"
    fix_reversible = True
    fix_time_estimate = "Varies"

    def run(self) -> CheckResult:
        free = _df_free_bytes("/")

        if free < 0:
            return self._error("Could not determine free disk space")

        free_str = _fmt(free)
        free_gb = free / 1e9

        if free_gb < 5:
            return self._critical(
                f"Only {free_str} free — macOS may become unstable",
                data={"free_bytes": free},
            )
        if free_gb < 10:
            return self._warning(
                f"{free_str} free — getting low; macOS needs ~10 GB headroom",
                data={"free_bytes": free},
            )
        if free_gb < 20:
            return self._info(
                f"{free_str} free — adequate but worth monitoring",
                data={"free_bytes": free},
            )

        return self._pass(
            f"{free_str} free",
            data={"free_bytes": free},
        )


class APFSSnapshotsCheck(BaseCheck):
    id = "apfs_snapshots"
    name = "APFS Local Snapshots"
    category = "disk"
    category_icon = "💽"

    scan_description = (
        "Checking APFS local snapshots — Time Machine stores invisible snapshots "
        "on your disk that can consume 10–40 GB without showing up in Finder."
    )
    finding_explanation = (
        "APFS snapshots are point-in-time copies of your filesystem stored "
        "locally while waiting to sync to a Time Machine backup drive. "
        "macOS manages these automatically and reclaims space when needed, "
        "but if you're low on space they can be manually thinned."
    )
    recommendation = (
        "If you're very low on disk space, run: "
        "tmutil thinlocalsnapshots / 50000000000 4\n"
        "This asks Time Machine to reclaim 50 GB where safe. "
        "Do NOT manually delete snapshots — let Time Machine manage them."
    )
    fix_level = "instructions"
    fix_description = "Thin local snapshots (let Time Machine decide what's safe)"
    fix_steps = [
        "Only do this if you're very low on space",
        "Run: tmutil thinlocalsnapshots / 50000000000 4",
        "Time Machine will reclaim space from old snapshots safely",
        "Do NOT run tmutil deletelocalsnapshots — it's destructive",
    ]
    fix_reversible = False
    fix_time_estimate = "~1 minute"

    def run(self) -> CheckResult:
        rc, stdout, _ = self.shell(
            ["tmutil", "listlocalsnapshots", "/"], timeout=8
        )

        if rc != 0 or not stdout.strip():
            return self._info("No local APFS snapshots found")

        snapshots = [ln.strip() for ln in stdout.splitlines() if ln.strip()]
        n = len(snapshots)

        # Try to get approximate size from .MobileBackups
        mb_path = Path("/.MobileBackups")
        size_bytes = _du(mb_path, timeout=5)
        size_str = _fmt(size_bytes) if size_bytes > 0 else "size unknown"

        return self._info(
            f"{n} local APFS snapshot{'s' if n != 1 else ''} "
            f"({size_str}) — managed automatically by Time Machine",
            data={"snapshot_count": n, "approx_size": size_str},
        )


class XcodeDerivedDataCheck(BaseCheck):
    id = "xcode_derived_data"
    name = "Xcode DerivedData"
    category = "disk"
    category_icon = "💽"
    profile_tags = ["developer"]

    scan_description = (
        "Checking Xcode's DerivedData folder — build artifacts accumulate here "
        "silently and can reach 20–50 GB for active developers."
    )
    finding_explanation = (
        "Xcode stores compiled build products, index data, and intermediate "
        "files in ~/Library/Developer/Xcode/DerivedData. It's completely safe "
        "to delete — Xcode recreates it on next build, though the first build "
        "will be slower."
    )
    recommendation = (
        "Delete DerivedData to reclaim space: "
        "rm -rf ~/Library/Developer/Xcode/DerivedData\n"
        "Or in Xcode: Product → Clean Build Folder"
    )
    fix_level = "auto"
    fix_description = "Deletes Xcode DerivedData (Xcode will rebuild it automatically)"
    fix_command = "rm -rf ~/Library/Developer/Xcode/DerivedData"
    fix_reversible = False
    fix_time_estimate = "~10 seconds (next Xcode build will be slower)"

    def run(self) -> CheckResult:
        path = HOME / "Library" / "Developer" / "Xcode" / "DerivedData"

        if not path.exists():
            return self._pass("No Xcode DerivedData folder found")

        size = _du(path, timeout=15)
        size_str = _fmt(size)

        if size < 0:
            return self._info("Xcode DerivedData exists (could not measure size)")

        size_gb = size / 1e9

        if size_gb >= 10:
            return self._warning(
                f"Xcode DerivedData is {size_str} — safe to delete",
                data={"path": str(path), "size_bytes": size},
            )
        if size_gb >= 2:
            return self._info(
                f"Xcode DerivedData is {size_str}",
                data={"path": str(path), "size_bytes": size},
            )

        return self._pass(
            f"Xcode DerivedData is {size_str} (manageable)",
            data={"size_bytes": size},
        )


class DockerDiskCheck(BaseCheck):
    id = "docker_disk"
    name = "Docker / Container Runtime"
    category = "disk"
    category_icon = "💽"

    scan_description = (
        "Checking Docker and container runtime disk usage — images, containers, "
        "and volumes can silently consume 20–100 GB."
    )
    finding_explanation = (
        "Container images, stopped containers, and unused volumes accumulate "
        "over time. Docker Desktop alone can use 50–100 GB. OrbStack and "
        "Colima are more disk-efficient alternatives, but all need occasional cleanup."
    )
    recommendation = (
        "Run 'docker system prune -a' to remove unused images, containers, "
        "and networks (add --volumes to also remove unused volumes)."
    )
    fix_level = "auto"
    fix_description = "Runs 'docker system prune' to remove unused Docker data"
    fix_command = "docker system prune -f"
    fix_reversible = False
    fix_time_estimate = "~30 seconds"

    def run(self) -> CheckResult:
        runtimes: dict[str, int] = {}

        # Docker Desktop
        docker_data = HOME / "Library" / "Containers" / "com.docker.docker" / "Data"
        if docker_data.exists():
            size = _du(docker_data, timeout=15)
            runtimes["Docker Desktop"] = size

        # Colima
        colima = HOME / ".colima"
        if colima.exists():
            size = _du(colima, timeout=15)
            runtimes["Colima"] = size

        # OrbStack
        orbstack = HOME / ".orbstack"
        if orbstack.exists():
            size = _du(orbstack, timeout=15)
            runtimes["OrbStack"] = size

        # Podman
        podman = HOME / ".local" / "share" / "containers"
        if podman.exists():
            size = _du(podman, timeout=15)
            runtimes["Podman"] = size

        if not runtimes:
            return self._pass("No container runtime detected")

        # Also get docker system df if docker is in PATH
        df_summary = ""
        if self.has_tool("docker"):
            rc, stdout, _ = self.shell(["docker", "system", "df"], timeout=10)
            if rc == 0 and stdout:
                # Pull out the "RECLAIMABLE" total
                for line in stdout.splitlines():
                    if "total" in line.lower() or "build cache" in line.lower():
                        df_summary = line.strip()
                        break

        total_bytes = sum(s for s in runtimes.values() if s > 0)
        total_str = _fmt(total_bytes)

        lines = [f"{name}: {_fmt(size)}" for name, size in runtimes.items()]
        summary = ", ".join(lines)

        total_gb = total_bytes / 1e9

        if total_gb >= 20:
            return self._warning(
                f"Container runtime using {total_str}: {summary}",
                data={"runtimes": {k: v for k, v in runtimes.items()}, "total": total_bytes},
            )

        return self._info(
            f"Container runtime using {total_str}: {summary}",
            data={"runtimes": {k: v for k, v in runtimes.items()}},
        )


class TrashCheck(BaseCheck):
    id = "trash"
    name = "Trash"
    category = "disk"
    category_icon = "💽"

    scan_description = (
        "Checking how much space is in the Trash — deleted files still consume "
        "disk space until the Trash is permanently emptied."
    )
    finding_explanation = (
        "Files in the Trash are deleted from Finder but still occupy disk space "
        "until you empty the Trash. This is a common source of 'mystery' disk usage."
    )
    recommendation = "Empty the Trash: right-click the Trash icon → Empty Trash."
    fix_level = "auto"
    fix_description = "Empties the Trash"
    fix_command = "rm -rf ~/.Trash/*"
    fix_reversible = False
    fix_time_estimate = "~5 seconds"

    def run(self) -> CheckResult:
        trash = HOME / ".Trash"

        if not trash.exists():
            return self._pass("Trash is empty")

        size = _du(trash, timeout=10)

        if size <= 0:
            # Check if directory is empty
            try:
                children = list(trash.iterdir())
                if not children:
                    return self._pass("Trash is empty")
                return self._info("Trash has items (could not measure size)")
            except OSError:
                return self._pass("Trash appears empty")

        size_str = _fmt(size)
        size_mb = size / 1e6

        if size_mb >= 500:
            return self._warning(
                f"Trash contains {size_str} — empty it to reclaim space",
                data={"size_bytes": size},
            )

        return self._info(
            f"Trash contains {size_str}",
            data={"size_bytes": size},
        )


class AppCachesCheck(BaseCheck):
    id = "app_caches"
    name = "Application Caches"
    category = "disk"
    category_icon = "💽"

    scan_description = (
        "Checking ~/Library/Caches size — app caches grow without bound and "
        "can reach several gigabytes of data most apps will recreate on demand."
    )
    finding_explanation = (
        "Apps store temporary data in ~/Library/Caches to speed up future "
        "operations. Caches are designed to be safe to delete — apps rebuild "
        "them as needed. They can quietly grow to 5–20 GB over time."
    )
    recommendation = (
        "Clear caches carefully: some caches can be deleted directly from "
        "~/Library/Caches. Tools like CleanMyMac or OnyX can help. "
        "Alternatively, 'rm -rf ~/Library/Caches/*' is generally safe."
    )
    fix_level = "instructions"
    fix_description = "Clear app caches manually"
    fix_steps = [
        "Open Finder, press Cmd+Shift+G, enter ~/Library/Caches",
        "Review the largest folders",
        "Delete caches for apps you use regularly (they'll rebuild)",
        "Or run: rm -rf ~/Library/Caches/* (log out and back in first)",
    ]
    fix_reversible = True
    fix_time_estimate = "~5 minutes"

    def run(self) -> CheckResult:
        caches = HOME / "Library" / "Caches"

        if not caches.exists():
            return self._pass("~/Library/Caches not found")

        size = _du(caches, timeout=15)

        if size < 0:
            return self._info("Could not measure ~/Library/Caches size")

        size_str = _fmt(size)
        size_gb = size / 1e9

        if size_gb >= 10:
            return self._warning(
                f"App caches are {size_str} — consider clearing",
                data={"size_bytes": size},
            )
        if size_gb >= 3:
            return self._info(
                f"App caches are {size_str}",
                data={"size_bytes": size},
            )

        return self._pass(
            f"App caches are {size_str} (reasonable)",
            data={"size_bytes": size},
        )


class LogFilesCheck(BaseCheck):
    id = "log_files"
    name = "Log Files"
    category = "disk"
    category_icon = "💽"

    scan_description = (
        "Checking ~/Library/Logs size — app logs accumulate indefinitely and "
        "often reach gigabytes that nobody will ever read."
    )
    finding_explanation = (
        "Apps write diagnostic logs to ~/Library/Logs. Unlike system logs "
        "managed by macOS, user-space logs from apps rarely get cleaned up "
        "automatically and can quietly grow to several GB."
    )
    recommendation = (
        "Delete old logs: rm -rf ~/Library/Logs/*\n"
        "This is safe — apps create new log files as needed. "
        "System logs (/var/log) are managed by macOS and should not be deleted."
    )
    fix_level = "auto"
    fix_description = "Deletes user log files (apps recreate them as needed)"
    fix_command = "rm -rf ~/Library/Logs/*"
    fix_reversible = False
    fix_time_estimate = "~5 seconds"

    def run(self) -> CheckResult:
        logs = HOME / "Library" / "Logs"

        if not logs.exists():
            return self._pass("~/Library/Logs not found")

        size = _du(logs, timeout=10)

        if size < 0:
            return self._info("Could not measure ~/Library/Logs size")

        size_str = _fmt(size)
        size_mb = size / 1e6

        if size_mb >= 1000:
            return self._warning(
                f"Log files are {size_str} — safe to delete",
                data={"size_bytes": size},
            )
        if size_mb >= 200:
            return self._info(
                f"Log files are {size_str}",
                data={"size_bytes": size},
            )

        return self._pass(
            f"Log files are {size_str} (fine)",
            data={"size_bytes": size},
        )


class iOSBackupsCheck(BaseCheck):
    id = "ios_backups"
    name = "iOS Device Backups"
    category = "disk"
    category_icon = "💽"

    scan_description = (
        "Checking for old iOS/iPadOS device backups — each backup is 5–30 GB "
        "and backups from devices you no longer own accumulate unnoticed."
    )
    finding_explanation = (
        "iTunes/Finder stores full device backups in ~/Library/Application Support/"
        "MobileSync/Backup. Each device gets its own folder. Old phones, "
        "loaner devices, and replaced iPads leave behind backups nobody needs."
    )
    recommendation = (
        "In Finder, connect your device → Manage Backups to see and delete old ones. "
        "Or browse ~/Library/Application Support/MobileSync/Backup directly."
    )
    fix_level = "instructions"
    fix_description = "Delete old device backups through Finder"
    fix_steps = [
        "Connect any iOS device to your Mac",
        "In Finder's sidebar, select the device",
        "Click 'Manage Backups' to see all stored backups",
        "Right-click old/unknown device backups and delete them",
        "Or navigate to ~/Library/Application Support/MobileSync/Backup",
    ]
    fix_reversible = False
    fix_time_estimate = "~5 minutes"

    def run(self) -> CheckResult:
        backup_dir = (
            HOME / "Library" / "Application Support" / "MobileSync" / "Backup"
        )

        if not backup_dir.exists():
            return self._pass("No iOS device backups found")

        try:
            devices = [d for d in backup_dir.iterdir() if d.is_dir()]
        except PermissionError:
            return self._info(
                "iOS backup directory exists but requires Full Disk Access to read "
                "(grant in System Settings → Privacy & Security → Full Disk Access)"
            )
        except OSError:
            return self._info("Could not read iOS backup directory")

        n = len(devices)
        if n == 0:
            return self._pass("No iOS device backups found")

        size = _du(backup_dir, timeout=20)
        size_str = _fmt(size) if size > 0 else "unknown size"

        size_gb = size / 1e9 if size > 0 else 0

        if n > 3 or size_gb >= 20:
            return self._warning(
                f"{n} iOS backup{'s' if n != 1 else ''} ({size_str}) — "
                f"consider removing old device backups",
                data={"backup_count": n, "size_bytes": size},
            )

        return self._info(
            f"{n} iOS backup{'s' if n != 1 else ''} ({size_str})",
            data={"backup_count": n, "size_bytes": size},
        )


# ── Public list for main.py ───────────────────────────────────────────────────

ALL_CHECKS: list[type[BaseCheck]] = [
    DiskSpaceCheck,
    APFSSnapshotsCheck,
    XcodeDerivedDataCheck,
    DockerDiskCheck,
    TrashCheck,
    AppCachesCheck,
    LogFilesCheck,
    iOSBackupsCheck,
]
