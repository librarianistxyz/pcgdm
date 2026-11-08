#!/usr/bin/env python3
"""
pcGDM Warp-RAM Scratchpad (warp_ram.py)
Blazing-Fast In-Memory RAM Disk Accelerator for Builds & Heavy I/O.
Zero-Sudo, Zero-Friction Architecture:
- Mounts directly into Linux kernel shared RAM (/dev/shm/librarianist_ramdisk)
  and seamlessly symlinks to ~/ramdisk.
- Eliminates SSD write wear and I/O bottlenecks for Flutter/Dart/Rust/Node builds,
  temporary archive extractions, and fast rendering.
- Continuous Background Sync (every 60s) mirrors persistent changes to SSD backing
  (~/.local/share/pcGDM/ramdisk_backing).
- Auto-restores SSD image into RAM on startup and flushes immediately on shutdown.
"""

import argparse
import datetime
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

RAM_TARGET = Path("/dev/shm/librarianist_ramdisk")
USER_LINK = Path.home() / "ramdisk"
BACKING_DIR = Path.home() / ".local" / "share" / "pcGDM" / "ramdisk_backing"
LOG_FILE = Path.home() / ".local" / "share" / "pcGDM" / "warp_ram.log"

SYNC_INTERVAL = 60  # Seconds between proactive disk mirrors


def log(msg: str) -> None:
    line = f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def notify(title: str, msg: str) -> None:
    try:
        subprocess.run(["notify-send", "-a", "Warp-RAM", "-i", "drive-harddisk", "-t", "3000", title, msg], check=False)
        hud_script = Path(__file__).parent / "mac_hud.py"
        if hud_script.exists():
            subprocess.run([sys.executable, str(hud_script), "flash", "--count", "1", "--delay", "0.05"], check=False)
    except Exception:
        pass


def init_ramdisk() -> bool:
    """Initializes in-memory RAM directory in /dev/shm and ensures symlink ~/ramdisk exists."""
    RAM_TARGET.mkdir(parents=True, exist_ok=True)
    if not USER_LINK.exists() or not USER_LINK.is_symlink():
        try:
            if USER_LINK.exists():
                USER_LINK.unlink()
            USER_LINK.symlink_to(RAM_TARGET)
        except Exception as e:
            log(f"Error creating symlink: {e}")
            return False

    # Restore from backing if backing exists and ramdisk is fresh
    if BACKING_DIR.exists() and not any(RAM_TARGET.iterdir()):
        restore_from_disk()
        log("Restored persistent files from SSD backing into RAM.")
    return True


def sync_to_disk() -> bool:
    """Safely mirrors all files from the RAM disk to the persistent SSD backing directory."""
    if not RAM_TARGET.exists():
        return False
    BACKING_DIR.mkdir(parents=True, exist_ok=True)
    try:
        res = subprocess.run(
            ["rsync", "-a", "--delete", f"{RAM_TARGET}/", f"{BACKING_DIR}/"],
            capture_output=True,
            check=False,
        )
        return res.returncode == 0
    except Exception as e:
        log(f"Error syncing to disk: {e}")
        return False


def restore_from_disk() -> bool:
    """Restores saved SSD mirror into RAM."""
    if not RAM_TARGET.exists() or not BACKING_DIR.exists():
        return False
    try:
        res = subprocess.run(
            ["rsync", "-a", f"{BACKING_DIR}/", f"{RAM_TARGET}/"],
            capture_output=True,
            check=False,
        )
        return res.returncode == 0
    except Exception as e:
        log(f"Error restoring from disk: {e}")
        return False


def get_usage() -> tuple[str, str]:
    """Calculates used size and file count inside the RAM disk."""
    if not RAM_TARGET.exists():
        return "0 KB", "0 files"
    total_bytes = 0
    file_count = 0
    try:
        for p in RAM_TARGET.rglob("*"):
            if p.is_file():
                total_bytes += p.stat().st_size
                file_count += 1
        if total_bytes >= (1024 * 1024):
            size_str = f"{total_bytes / (1024 * 1024):.1f} MB"
        else:
            size_str = f"{total_bytes / 1024:.0f} KB"
        return size_str, f"{file_count} files"
    except Exception:
        return "0 KB", "0 files"


def run_daemon() -> None:
    """
    Background Daemon (Managed by systemd --user):
    - Initializes RAM disk at /dev/shm and link at ~/ramdisk.
    - Syncs to SSD backing every 60s.
    - Flushes to SSD backing immediately upon SIGTERM/SIGINT during shutdown.
    """
    log("Starting pcGDM Warp-RAM Accelerator Daemon...")
    init_ramdisk()

    def handle_shutdown(_signo, _frame):
        log("Received shutdown signal -> Flushing all RAM disk files to SSD...")
        sync_to_disk()
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    last_sync = time.time()
    while True:
        try:
            now = time.time()
            if (now - last_sync) >= SYNC_INTERVAL:
                size_str, count_str = get_usage()
                if sync_to_disk():
                    if size_str not in ("0 KB", "0.0 MB"):
                        log(f"Auto-Sync complete: {size_str} ({count_str}) mirrored to SSD.")
                last_sync = now
            time.sleep(5)
        except Exception as e:
            time.sleep(10)


def show_status() -> None:
    size_str, count_str = get_usage()
    print("=== pcGDM Warp-RAM Status ===")
    print(f"  Access Point   : {USER_LINK} -> {RAM_TARGET}")
    print(f"  Memory Type    : Linux Kernel tmpfs (/dev/shm)")
    print(f"  Current Usage  : {size_str} ({count_str})")
    print(f"  SSD Backing    : {BACKING_DIR}")
    print(f"  Persistence    : Continuous Auto-Sync (every 60s) + Flush on Shutdown")


def main() -> None:
    parser = argparse.ArgumentParser(description="Warp-RAM In-Memory Build Accelerator")
    parser.add_argument(
        "command",
        nargs="?",
        default="status",
        choices=["status", "init", "sync", "restore", "daemon"],
        help="Command to run (default: status)",
    )
    args = parser.parse_args()

    if args.command == "status":
        show_status()
    elif args.command == "init":
        if init_ramdisk():
            print(f"[+] Initialized Warp-RAM at {USER_LINK} ({RAM_TARGET})")
            notify("Warp-RAM Active", f"RAM scratchpad available at ~/ramdisk")
    elif args.command == "sync":
        if sync_to_disk():
            print("[+] Successfully mirrored Warp-RAM to persistent SSD backing.")
        else:
            print("[!] Sync failed.")
    elif args.command == "restore":
        if restore_from_disk():
            print("[+] Restored persistent files from SSD to RAM.")
    elif args.command == "daemon":
        run_daemon()


if __name__ == "__main__":
    main()
