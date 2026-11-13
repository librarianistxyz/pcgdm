#!/usr/bin/env python3
"""
pcGDM CCTV Grid (cctv_grid.py)
Arrange all open windows across all XFCE workspaces into a live, interactive
CCTV grid on your current screen, with instant zoom/unzoom and full restore.

Shortcuts / Gestures:
  Super + G  / 3-finger swipe up   -> Toggle CCTV Grid ON / Restore workspaces
  Super + Z  / 3-finger swipe down -> Zoom focused tile / Snap back into Grid
"""

import argparse
import datetime
import fcntl
import json
import math
import subprocess
import time
from pathlib import Path

STATE_DIR = Path.home() / ".local" / "share" / "pcGDM"
SNAPSHOT_FILE = STATE_DIR / "cctv_snapshot.json"
LOCK_FILE = STATE_DIR / "cctv_grid.lock"
STAMP_FILE = STATE_DIR / "cctv_last_toggle"
LOG_FILE = STATE_DIR / "cctv_grid.log"

SKIP_TITLES = {"xfce4-panel", "Desktop", "plank", "Whisker Menu"}
TOP_MARGIN = 32
BOTTOM_MARGIN = 6
GAP = 6
DEBOUNCE_SEC = 0.4


def log(msg: str) -> None:
    line = f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def get_screen_size() -> tuple[int, int]:
    out = run(["xdotool", "getdisplaygeometry"]).stdout.strip().split()
    return int(out[0]), int(out[1])


def get_active_workspace() -> int:
    for line in run(["wmctrl", "-d"]).stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "*":
            return int(parts[0])
    return 0


def get_wm_state(win_id: str) -> list[str]:
    out = run(["xprop", "-id", win_id, "_NET_WM_STATE"]).stdout
    states = []
    for key in ("_NET_WM_STATE_MAXIMIZED_VERT", "_NET_WM_STATE_MAXIMIZED_HORZ", "_NET_WM_STATE_FULLSCREEN"):
        if key in out:
            states.append(key)
    return states


def list_real_windows() -> list[dict]:
    """List all normal user windows across all workspaces, grouped by workspace."""
    windows = []
    for line in run(["wmctrl", "-lG"]).stdout.splitlines():
        parts = line.split(None, 7)
        if len(parts) < 8:
            continue
        win_id, ws_str, x, y, w, h, _host, title = parts
        ws = int(ws_str)
        width, height = int(w), int(h)
        if ws == -1 or title in SKIP_TITLES or width < 40 or height < 40:
            continue
        windows.append({
            "id": win_id,
            "ws": ws,
            "x": int(x),
            "y": int(y),
            "w": width,
            "h": height,
            "title": title,
            "states": get_wm_state(win_id),
        })
    windows.sort(key=lambda item: (item["ws"], item["id"]))
    return windows


def existing_win_ids() -> set[str]:
    ids = set()
    for line in run(["wmctrl", "-l"]).stdout.splitlines():
        parts = line.split(None, 1)
        if parts:
            ids.add(parts[0].lower())
    return ids


def tile_windows(win_ids: list[str]) -> None:
    live = existing_win_ids()
    win_ids = [wid for wid in win_ids if wid.lower() in live]
    if not win_ids:
        return

    active_ws = str(get_active_workspace())
    sw, sh = get_screen_size()
    usable_h = sh - TOP_MARGIN - BOTTOM_MARGIN
    n = len(win_ids)
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    cell_w = (sw - GAP * (cols + 1)) // cols
    cell_h = (usable_h - GAP * (rows + 1)) // rows

    # Pass 1: Move silently to active workspace & clear maximized/fullscreen states
    for wid in win_ids:
        run(["wmctrl", "-i", "-r", wid, "-t", active_ws])
        run(["wmctrl", "-i", "-r", wid, "-b", "remove,maximized_vert,maximized_horz"])
        run(["wmctrl", "-i", "-r", wid, "-b", "remove,fullscreen"])

    # Let xfwm4 finish unmaximizing before applying exact grid geometry
    time.sleep(0.15)

    # Pass 2: Place into clean grid cells and raise without workspace-hopping
    for idx, wid in enumerate(win_ids):
        r, c = divmod(idx, cols)
        x = GAP + c * (cell_w + GAP)
        y = TOP_MARGIN + GAP + r * (cell_h + GAP)
        run(["wmctrl", "-i", "-r", wid, "-e", f"0,{x},{y},{cell_w},{cell_h}"])
        run(["xdotool", "windowraise", wid])

    # Keep focus on the first tile so zoom/keyboard works immediately
    run(["wmctrl", "-i", "-a", win_ids[0]])


def enter_cctv() -> None:
    windows = list_real_windows()
    if not windows:
        log("No open windows found to arrange.")
        return

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "origin_ws": get_active_workspace(),
        "windows": windows,
    }
    SNAPSHOT_FILE.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    tile_windows([w["id"] for w in windows])
    log(f"CCTV grid active: arranged {len(windows)} windows across all workspaces.")


def exit_cctv() -> None:
    if not SNAPSHOT_FILE.exists():
        log("CCTV grid is not active.")
        return

    snapshot = json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
    live = existing_win_ids()
    saved_windows = [w for w in snapshot.get("windows", []) if w["id"].lower() in live]

    # Pass 1: Unmaximize and move back to original workspaces + original geometry
    for w in saved_windows:
        wid = w["id"]
        run(["wmctrl", "-i", "-r", wid, "-b", "remove,maximized_vert,maximized_horz"])
        run(["wmctrl", "-i", "-r", wid, "-b", "remove,fullscreen"])
        run(["wmctrl", "-i", "-r", wid, "-t", str(w["ws"])])

    time.sleep(0.12)

    # Pass 2: Restore exact geometry and maximized/fullscreen states
    for w in saved_windows:
        wid = w["id"]
        run(["wmctrl", "-i", "-r", wid, "-e", f"0,{w['x']},{w['y']},{w['w']},{w['h']}"])
        states = w.get("states", [])
        if "_NET_WM_STATE_MAXIMIZED_VERT" in states and "_NET_WM_STATE_MAXIMIZED_HORZ" in states:
            run(["wmctrl", "-i", "-r", wid, "-b", "add,maximized_vert,maximized_horz"])
        if "_NET_WM_STATE_FULLSCREEN" in states:
            run(["wmctrl", "-i", "-r", wid, "-b", "add,fullscreen"])

    origin_ws = snapshot.get("origin_ws")
    if origin_ws is not None:
        run(["wmctrl", "-s", str(origin_ws)])

    SNAPSHOT_FILE.unlink(missing_ok=True)
    log("Restored all windows to their original workspaces and sizes.")


def is_debounced() -> bool:
    now = time.time()
    try:
        if STAMP_FILE.exists():
            last = float(STAMP_FILE.read_text(encoding="utf-8").strip())
            if 0 <= now - last < DEBOUNCE_SEC:
                return True
        STAMP_FILE.write_text(str(now), encoding="utf-8")
    except Exception:
        pass
    return False


def toggle_cctv() -> None:
    if is_debounced():
        return
    if SNAPSHOT_FILE.exists():
        exit_cctv()
    else:
        enter_cctv()


def zoom_active() -> None:
    if is_debounced():
        return
    active_dec = run(["xdotool", "getactivewindow"]).stdout.strip()
    if not active_dec.isdigit():
        return
    win_id = f"0x{int(active_dec):08x}"
    states = get_wm_state(win_id)

    if "_NET_WM_STATE_MAXIMIZED_VERT" in states or "_NET_WM_STATE_FULLSCREEN" in states:
        run(["wmctrl", "-i", "-r", win_id, "-b", "remove,maximized_vert,maximized_horz"])
        run(["wmctrl", "-i", "-r", win_id, "-b", "remove,fullscreen"])
        if SNAPSHOT_FILE.exists():
            snapshot = json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
            tile_windows([w["id"] for w in snapshot.get("windows", [])])
    else:
        run(["wmctrl", "-i", "-r", win_id, "-b", "add,maximized_vert,maximized_horz"])
        run(["wmctrl", "-i", "-a", win_id])


def switch_workspace(delta: int) -> None:
    lines = run(["wmctrl", "-d"]).stdout.splitlines()
    if not lines:
        return
    total = len(lines)
    cur = get_active_workspace()
    target = (cur + delta) % total
    run(["wmctrl", "-s", str(target)])
    log(f"Switched workspace: {cur + 1} -> {target + 1}")


def ensure_shortcuts() -> None:
    SNAPSHOT_FILE.unlink(missing_ok=True)
    STAMP_FILE.unlink(missing_ok=True)
    script = str(Path(__file__).resolve())
    run(["xfconf-query", "-c", "xfce4-keyboard-shortcuts", "-p", "/commands/custom/<Super>g", "-n", "-t", "string", "-s", f"{script} toggle"])
    run(["xfconf-query", "-c", "xfce4-keyboard-shortcuts", "-p", "/commands/custom/<Super>z", "-n", "-t", "string", "-s", f"{script} zoom"])
    log("Ensured Super+G (toggle) and Super+Z (zoom) shortcuts.")


def main() -> None:
    parser = argparse.ArgumentParser(description="pcGDM CCTV Grid - Arrange all workspaces into a live grid")
    parser.add_argument("command", choices=["toggle", "start", "stop", "tile", "zoom", "init", "ws-prev", "ws-next"])
    args = parser.parse_args()

    if args.command == "ws-prev":
        switch_workspace(-1)
        return
    if args.command == "ws-next":
        switch_workspace(1)
        return

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOCK_FILE, "w", encoding="utf-8") as lock_f:
        fcntl.flock(lock_f, fcntl.LOCK_EX)

        if args.command == "toggle":
            toggle_cctv()
        elif args.command == "start":
            enter_cctv()
        elif args.command == "stop":
            exit_cctv()
        elif args.command == "tile":
            if SNAPSHOT_FILE.exists():
                snapshot = json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
                tile_windows([w["id"] for w in snapshot.get("windows", [])])
            else:
                enter_cctv()
        elif args.command == "zoom":
            zoom_active()
        elif args.command == "init":
            ensure_shortcuts()


if __name__ == "__main__":
    main()
