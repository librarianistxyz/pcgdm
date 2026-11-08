#!/usr/bin/env python3
"""
pcGDM Apple SMC Keyboard Backlight Controller & Daemon (adjust_kbd_light.py)
Provides instant manual keyboard brightness adjustments and a systemd listener daemon
with seamless synchronization with mac_visualizer.py and mac_hud.py.
"""

import os
import signal
import struct
import sys
import time
from pathlib import Path

KBD_BRIGHTNESS = Path("/sys/class/leds/smc::kbd_backlight/brightness")
CONFIG_DIR = Path.home() / ".config" / "pcgdm"
SETTING_FILE = CONFIG_DIR / "kbd_brightness.val"
HUD_PREF_FILE = Path.home() / ".local" / "share" / "pcGDM" / "user_kbd_brightness"
OVERRIDE_FILE = Path("/tmp/mac_kbd_manual_override")

KBD_EVENT_DEVICE = Path("/dev/input/by-id/usb-Apple_Inc._Apple_Internal_Keyboard___Trackpad-event-kbd")
if not KBD_EVENT_DEVICE.exists():
    KBD_EVENT_DEVICE = Path("/dev/input/by-path/pci-0000:00:1d.0-usb-0:1.8.3:1.0-event-kbd")

STEP = 25
MAX_BRIGHTNESS = 255
MIN_BRIGHTNESS = 0


def get_current_setting() -> int:
    if SETTING_FILE.exists():
        try:
            val = int(SETTING_FILE.read_text().strip())
            return max(MIN_BRIGHTNESS, min(MAX_BRIGHTNESS, val))
        except (ValueError, OSError):
            pass
    if HUD_PREF_FILE.exists():
        try:
            val = int(HUD_PREF_FILE.read_text().strip())
            return max(MIN_BRIGHTNESS, min(MAX_BRIGHTNESS, val))
        except (ValueError, OSError):
            pass
    if KBD_BRIGHTNESS.exists():
        try:
            val = int(KBD_BRIGHTNESS.read_text().strip())
            return max(MIN_BRIGHTNESS, min(MAX_BRIGHTNESS, val))
        except (ValueError, OSError):
            pass
    return 100


def apply_brightness(val: int) -> int:
    val = max(MIN_BRIGHTNESS, min(MAX_BRIGHTNESS, val))
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    SETTING_FILE.write_text(f"{val}\n")

    try:
        HUD_PREF_FILE.parent.mkdir(parents=True, exist_ok=True)
        HUD_PREF_FILE.write_text(f"{val}\n")
    except Exception:
        pass

    # Signal manual override lock with timestamp so visualizer yields to manual level
    try:
        OVERRIDE_FILE.write_text(f"{time.time()}:{val}")
    except Exception:
        pass

    if KBD_BRIGHTNESS.exists():
        try:
            with open(KBD_BRIGHTNESS, "w") as f:
                f.write(f"{val}\n")
                f.truncate()
                f.flush()
        except Exception as e:
            sys.stderr.write(f"Error writing to backlight: {e}\n")

    return val


def run_daemon():
    """Runs a dedicated hardware keyboard illumination key listener service."""
    def sig_handler(_signo, _frame):
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    # Restore saved brightness on startup
    saved = get_current_setting()
    apply_brightness(saved)
    print(f"[pcGDM Backlight] Restored manual brightness to {saved}/255 ({round((saved/255)*100)}%)", flush=True)

    fmt = "qqHHi"
    while True:
        try:
            if not KBD_EVENT_DEVICE.exists():
                time.sleep(2)
                continue

            with open(KBD_EVENT_DEVICE, "rb") as dev_f:
                print(f"[pcGDM Backlight] Hardware key listener active on {KBD_EVENT_DEVICE}", flush=True)
                while True:
                    chunk = dev_f.read(24)
                    if not chunk or len(chunk) < 24:
                        time.sleep(0.05)
                        continue
                    sec, usec, ev_type, ev_code, ev_value = struct.unpack(fmt, chunk)
                    # ev_type == 1 is EV_KEY. ev_value: 1 = press, 2 = repeat
                    if ev_type == 1 and ev_value in (1, 2):
                        if ev_code == 229:  # KEY_KBDILLUMDOWN (F5)
                            cur = get_current_setting()
                            new_val = max(MIN_BRIGHTNESS, cur - STEP)
                            apply_brightness(new_val)
                        elif ev_code == 230:  # KEY_KBDILLUMUP (F6)
                            cur = get_current_setting()
                            new_val = min(MAX_BRIGHTNESS, cur + STEP if cur > 0 else STEP)
                            apply_brightness(new_val)
                        elif ev_code == 228:  # KEY_KBDILLUMTOGGLE
                            cur = get_current_setting()
                            new_val = 0 if cur > 0 else 125
                            apply_brightness(new_val)
        except Exception as e:
            time.sleep(1)


def main():
    if len(sys.argv) < 2:
        cur = get_current_setting()
        pct = round((cur / MAX_BRIGHTNESS) * 100)
        print(f"Current brightness: {cur} / {MAX_BRIGHTNESS} ({pct}%)")
        print("Usage: adjust_kbd_light.py [up|down|toggle|max|off|<0-255>|daemon]")
        return

    action = sys.argv[1].lower()

    if action in ("daemon", "--daemon", "-d", "listen"):
        run_daemon()
        return

    current = get_current_setting()

    if action in ("up", "+"):
        new_val = min(MAX_BRIGHTNESS, current + STEP if current > 0 else STEP)
    elif action in ("down", "-"):
        new_val = max(MIN_BRIGHTNESS, current - STEP)
    elif action in ("off", "0", "mute"):
        new_val = 0
    elif action in ("max", "100%", "full"):
        new_val = MAX_BRIGHTNESS
    elif action == "toggle":
        new_val = 0 if current > 0 else 125
    else:
        try:
            new_val = int(action)
        except ValueError:
            sys.stderr.write(f"Unknown action or value: {action}\n")
            sys.exit(1)

    result = apply_brightness(new_val)
    pct = round((result / MAX_BRIGHTNESS) * 100)
    print(f"Keyboard brightness: {result} / {MAX_BRIGHTNESS} ({pct}%)")


if __name__ == "__main__":
    main()
