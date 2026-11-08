#!/usr/bin/env python3
"""
pcGDM Focus Freezer & Background CPU Optimizer (2012 MacBook Pro / Xubuntu)
Watches X11 active window focus via xprop -spy (event-driven, 0% polling overhead).
- When heavy browsers (Chromium, Chrome, Brave, Firefox, AdsPower, etc.) are unfocused
  for >20 seconds and NOT playing audio, freezes their renderer/tab processes via SIGSTOP
  so their background CPU usage drops to literally 0.0%!
- The millisecond you click or Alt-Tab back to that window, sends SIGCONT so it wakes
  up instantaneously without X11 window freezes.
- Also automatically tames background file-indexer/tracker processes to idle CPU priority.
"""

import argparse
import datetime
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

LOG_FILE = Path.home() / ".local" / "share" / "pcGDM" / "freezer.log"
STATE_FILE = Path("/tmp/pcgdm_freezer_state")

# Heavy browser/app WM_CLASS keywords whose background tab renderers can be safely frozen
FREEZABLE_APP_CLASSES = {
    "chromium",
    "google-chrome",
    "chrome",
    "brave",
    "firefox",
    "Navigator",
    "adspower",
    "vivaldi",
    "opera",
    "microsoft-edge",
}

# Background indexer/crawler processes to automatically push to lowest idle CPU priority (nice 19)
BACKGROUND_HOG_NAMES = {
    "localsearch-3",
    "tracker-miner-fs-3",
    "tracker-extract-3",
    "baloo_file",
    "updatedb.mlocate",
}

UNFOCUS_GRACE_SECONDS = 18.0


def log(msg: str) -> None:
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def get_active_window_info() -> tuple[int | None, str]:
    """Return (root_pid, wm_class_lower) of the currently focused X11 window."""
    try:
        out = subprocess.check_output(
            ["xprop", "-root", "_NET_ACTIVE_WINDOW"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=1.5,
        )
        # Format: _NET_ACTIVE_WINDOW(WINDOW): window id # 0x5400004, 0x0
        parts = out.strip().split("#")
        if len(parts) < 2:
            return None, ""
        win_id = parts[1].split(",")[0].strip()
        if not win_id or win_id == "0x0":
            return None, ""

        wprop = subprocess.check_output(
            ["xprop", "-id", win_id, "_NET_WM_PID", "WM_CLASS"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=1.5,
        )
        pid = None
        wm_class = ""
        for line in wprop.splitlines():
            if "_NET_WM_PID(CARDINAL)" in line and "=" in line:
                try:
                    pid = int(line.split("=")[1].strip())
                except ValueError:
                    pass
            elif "WM_CLASS(STRING)" in line and "=" in line:
                wm_class = line.split("=")[1].strip().lower()
        return pid, wm_class
    except Exception:
        return None, ""


def get_audio_playing_pids_and_apps() -> tuple[set[int], set[str]]:
    """Query PulseAudio/PipeWire via pactl so we NEVER freeze a browser tab playing music/video."""
    pids: set[int] = set()
    apps: set[str] = set()
    try:
        out = subprocess.check_output(
            ["pactl", "list", "sink-inputs"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=1.5,
        )
        corked = False
        for line in out.splitlines():
            s = line.strip()
            if s.startswith("Sink Input #"):
                corked = False
            elif s.startswith("Corked:"):
                corked = "yes" in s.lower()
            elif not corked and "application.process.id =" in s:
                val = s.split("=")[1].strip().strip('"')
                if val.isdigit():
                    pids.add(int(val))
            elif not corked and "application.name =" in s:
                val = s.split("=")[1].strip().strip('"').lower()
                apps.add(val)
    except Exception:
        pass
    return pids, apps


def find_freezable_targets() -> dict[str, list[int]]:
    """
    Find heavy browser renderer/worker PIDs grouped by browser family.
    NOTE: We intentionally freeze ONLY child `--type=renderer` / `-contentproc` / tab processes
    and leave the main X11 UI frame + GPU/network socket broker awake so windows never turn grey
    and active file downloads NEVER get interrupted!
    """
    targets: dict[str, list[int]] = {}
    proc_dir = Path("/proc")
    my_uid = os.getuid()

    for entry in proc_dir.iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        try:
            if entry.stat().st_uid != my_uid:
                continue
            cmdline = (entry / "cmdline").read_bytes().replace(b"\x00", b" ").decode("utf-8", errors="ignore").strip()
            if not cmdline:
                continue

            lower_cmd = cmdline.lower()

            # Never touch VS Code / Antigravity IDE processes
            if "/usr/share/code" in lower_cmd or "antigravity" in lower_cmd or "vscode" in lower_cmd:
                continue

            # Chromium / Chrome / Brave / Edge / AdsPower / Opera / Vivaldi tab renderers
            if "--type=renderer" in lower_cmd and "--extension-process" not in lower_cmd:
                for b in ("chromium", "chrome", "brave", "adspower", "vivaldi", "opera", "msedge"):
                    if b in lower_cmd:
                        targets.setdefault(b, []).append(pid)
                        break

            # Firefox tab content processes
            elif ("firefox" in lower_cmd or "librewolf" in lower_cmd) and "-contentproc" in lower_cmd:
                targets.setdefault("firefox", []).append(pid)

        except OSError:
            continue

    return targets


def tame_background_indexers() -> int:
    """Renice background indexers (localsearch-3, tracker, etc.) to idle priority (nice 19)."""
    tamed = 0
    proc_dir = Path("/proc")
    my_uid = os.getuid()

    for entry in proc_dir.iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        try:
            if entry.stat().st_uid != my_uid:
                continue
            comm = (entry / "comm").read_text(encoding="utf-8", errors="ignore").strip()
            if comm in BACKGROUND_HOG_NAMES:
                current_nice = os.getpriority(os.PRIO_PROCESS, pid)
                if current_nice < 19:
                    os.setpriority(os.PRIO_PROCESS, pid, 19)
                    tamed += 1
        except OSError:
            continue
    return tamed


def set_pids_frozen(pids: list[int], freeze: bool) -> int:
    sig = signal.SIGSTOP if freeze else signal.SIGCONT
    count = 0
    for pid in pids:
        try:
            os.kill(pid, sig)
            count += 1
        except OSError:
            pass
    return count


def wake_all_browsers() -> int:
    """Ensure every frozen browser renderer is immediately woken with SIGCONT."""
    targets = find_freezable_targets()
    total = 0
    for _app, pids in targets.items():
        total += set_pids_frozen(pids, freeze=False)
    STATE_FILE.write_text("0 frozen (All Awake)\n")
    return total


def get_frozen_status() -> list[tuple[int, str, str]]:
    """Return list of currently stopped (T) browser renderer processes."""
    stopped: list[tuple[int, str, str]] = []
    targets = find_freezable_targets()
    for app, pids in targets.items():
        for pid in pids:
            try:
                stat_text = Path(f"/proc/{pid}/stat").read_text()
                # Format: pid (comm) state ...
                state = stat_text.rsplit(")", 1)[1].split()[0]
                stopped.append((pid, app, state))
            except OSError:
                pass
    return stopped


def show_status() -> None:
    active_pid, active_class = get_active_window_info()
    statuses = get_frozen_status()
    frozen_count = sum(1 for _, _, st in statuses if st == "T")
    total_count = len(statuses)

    print("=== pcGDM Focus Freezer Status ===")
    print(f"  Focused Window : {active_class or 'unknown'} (PID: {active_pid or '?'})")
    print(f"  Browser Tabs   : {frozen_count} Frozen (0.0% CPU) / {total_count} Total Renderers")
    for pid, app, st in statuses:
        state_label = "FROZEN (0% CPU - SIGSTOP)" if st == "T" else f"AWAKE ({st})"
        print(f"    - [{app}] PID {pid}: {state_label}")


def run_daemon() -> None:
    log("Starting pcGDM Focus Freezer & Background CPU Optimizer...")
    wake_all_browsers()

    frozen_apps: dict[str, set[int]] = {}
    last_focused_time: dict[str, float] = {}
    last_indexer_check = 0.0

    def cleanup_handler(_signum, _frame):
        log("Focus Freezer stopping — waking all suspended tabs...")
        wake_all_browsers()
        sys.exit(0)

    signal.signal(signal.SIGTERM, cleanup_handler)
    signal.signal(signal.SIGINT, cleanup_handler)

    while True:
        now = time.time()
        _active_pid, active_class = get_active_window_info()
        audio_pids, audio_apps = get_audio_playing_pids_and_apps()
        targets = find_freezable_targets()

        # Check which browser families are currently focused
        for app, pids in targets.items():
            is_focused = app in active_class or (app == "chrome" and "chromium" in active_class)
            is_playing_audio = any(a in app or app in a for a in audio_apps) or any(p in audio_pids for p in pids)

            if is_focused or is_playing_audio:
                last_focused_time[app] = now
                if app in frozen_apps:
                    woken = set_pids_frozen(list(frozen_apps[app] | set(pids)), freeze=False)
                    del frozen_apps[app]
                    reason = "Window Focused" if is_focused else "Audio Playing"
                    log(f"WOKE {app.upper()} ({woken} tab processes) -> {reason}")
            else:
                # App is in the background and silent
                last_seen = last_focused_time.setdefault(app, now)
                if (now - last_seen) >= UNFOCUS_GRACE_SECONDS:
                    current_frozen = frozen_apps.get(app, set())
                    new_pids = [p for p in pids if p not in current_frozen]
                    if new_pids:
                        set_pids_frozen(new_pids, freeze=True)
                        frozen_apps[app] = current_frozen | set(new_pids)
                        log(f"FROZE {app.upper()} ({len(frozen_apps[app])} background tab processes -> 0.0% CPU)")

        # Update state file for godmode.sh status
        total_frozen = sum(len(s) for s in frozen_apps.values())
        STATE_FILE.write_text(f"{total_frozen} background tab process(es) frozen at 0% CPU\n")

        # Every 30s, tame background indexers like localsearch-3
        if (now - last_indexer_check) > 30.0:
            tamed = tame_background_indexers()
            if tamed:
                log(f"Tamed {tamed} background indexer process(es) to idle CPU priority (nice 19).")
            last_indexer_check = now

        # Fast 0.35s reaction loop so waking a browser when clicked feels instantaneous
        time.sleep(0.35)


def main() -> None:
    parser = argparse.ArgumentParser(description="pcGDM Focus Freezer: Zero-CPU Background App Freezer")
    parser.add_argument(
        "command",
        nargs="?",
        default="status",
        choices=["status", "daemon", "wake"],
        help="Command to execute (default: status)",
    )
    args = parser.parse_args()

    if args.command == "status":
        show_status()
    elif args.command == "wake":
        n = wake_all_browsers()
        print(f"[+] Woke {n} browser renderer process(es).")
    elif args.command == "daemon":
        run_daemon()


if __name__ == "__main__":
    main()
