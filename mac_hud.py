#!/usr/bin/env python3
"""
pcGDM Apple SMC Keyboard Hardware Pulse & HUD Engine (mac_hud.py)
Controls /sys/class/leds/smc::kbd_backlight to turn your physical 2012 MacBook Pro
keyboard into an ambient hardware telemetry & notification indicator.

Capabilities:
- flash [count] [speed]: Rapid notification flashes (e.g., download / build done)
- breathe [cycles] [speed]: Smooth sine-wave breathing pulse
- alert: Strobe alert pattern for warnings
- set <0-255>: Set absolute brightness level
- fade <0-255> [duration]: Smoothly ramp to a specific brightness level
- hud: Ambient daemon that pulses on high thermal loads or low battery
"""

import argparse
import glob
import math
import os
import signal
import sys
import time
from pathlib import Path

KBD_DIR = Path("/sys/class/leds/smc::kbd_backlight")
BRIGHTNESS_FILE = KBD_DIR / "brightness"
MAX_BRIGHTNESS_FILE = KBD_DIR / "max_brightness"

# Path to check battery and thermals for the HUD daemon
AC_ONLINE = Path("/sys/class/power_supply/ADP1/online")
BAT_CAPACITY = Path("/sys/class/power_supply/BAT0/capacity")


def get_max_brightness() -> int:
    try:
        return int(MAX_BRIGHTNESS_FILE.read_text().strip())
    except Exception:
        return 255


def get_current_brightness() -> int:
    try:
        return int(BRIGHTNESS_FILE.read_text().strip())
    except Exception:
        return 0


PREF_FILE = Path.home() / ".local" / "share" / "pcGDM" / "user_kbd_brightness"


def get_stored_preference() -> int:
    """Read the last user-intended baseline brightness, or default to current sysfs value."""
    try:
        if PREF_FILE.exists():
            val = int(PREF_FILE.read_text().strip())
            if 0 <= val <= 255:
                return val
    except Exception:
        pass
    cur = get_current_brightness()
    return cur if cur > 0 else 24


def save_stored_preference(val: int) -> None:
    try:
        PREF_FILE.parent.mkdir(parents=True, exist_ok=True)
        PREF_FILE.write_text(f"{max(0, min(255, val))}\n")
    except Exception:
        pass


def set_brightness(val: int, save_pref: bool = False) -> bool:
    val = max(0, min(255, int(val)))
    if save_pref:
        save_stored_preference(val)
    try:
        BRIGHTNESS_FILE.write_text(f"{val}\n")
        return True
    except PermissionError:
        res = os.system(f"echo {val} | sudo tee {BRIGHTNESS_FILE} > /dev/null 2>&1")
        return res == 0
    except Exception as e:
        print(f"[!] Error setting brightness: {e}", file=sys.stderr)
        return False


def flash(count: int = 2, delay: float = 0.10, target: int | None = None) -> None:
    """
    Flash the keyboard to signal notifications and return strictly to the baseline!
    If current baseline is 20, flashes between 20 and 120 (relative pop) instead of blinding 255!
    """
    baseline = get_stored_preference()
    
    # Calculate a proportional flash peak instead of blasting 100% (255)
    if target is None:
        if baseline == 0:
            flash_peak = 70
            flash_trough = 0
        elif baseline < 80:
            flash_peak = min(255, baseline + 80)
            flash_trough = max(0, baseline - 20)
        else:
            flash_peak = min(255, baseline + 60)
            flash_trough = max(0, baseline - 50)
    else:
        flash_peak = target
        flash_trough = 0

    try:
        for _ in range(count):
            set_brightness(flash_peak)
            time.sleep(delay)
            set_brightness(flash_trough)
            time.sleep(delay)
    finally:
        # Strictly enforce returning to the exact baseline percentage!
        set_brightness(baseline)


def fade_to(target: int, duration: float = 0.5, steps: int = 25) -> None:
    """Smoothly transitions brightness to target and stores as new user baseline."""
    current = get_current_brightness()
    target = max(0, min(255, target))
    if current == target:
        save_stored_preference(target)
        return

    step_delay = duration / steps
    diff = target - current
    for i in range(1, steps + 1):
        progress = i / steps
        factor = (1 - math.cos(progress * math.pi)) / 2
        val = int(current + (diff * factor))
        set_brightness(val)
        time.sleep(step_delay)
    set_brightness(target, save_pref=True)


def breathe(cycles: int = 3, cycle_duration: float = 2.0, min_val: int | None = None, max_val: int | None = None) -> None:
    """Smooth ambient sine-wave breathing pulse around user's current baseline."""
    baseline = get_stored_preference()
    if min_val is None:
        min_val = max(0, baseline - 25)
    if max_val is None:
        max_val = min(255, baseline + 60)

    steps_per_cycle = 40
    step_delay = cycle_duration / steps_per_cycle
    span = (max_val - min_val) / 2.0
    mid = min_val + span

    try:
        for _ in range(cycles):
            for i in range(steps_per_cycle):
                angle = (i / steps_per_cycle) * (2 * math.pi) - (math.pi / 2)
                brightness = int(mid + (span * math.sin(angle)))
                set_brightness(brightness)
                time.sleep(step_delay)
    finally:
        set_brightness(baseline)


def alert(pulses: int = 3) -> None:
    """Urgent strobe pattern for warnings that strictly restores original level."""
    baseline = get_stored_preference()
    try:
        for _ in range(pulses):
            for _ in range(2):
                set_brightness(min(255, baseline + 120))
                time.sleep(0.08)
                set_brightness(max(0, baseline - 20))
                time.sleep(0.08)
            time.sleep(0.2)
    finally:
        set_brightness(baseline)


def run_hud_daemon() -> None:
    """
    Background Ambient HUD:
    - If CPU Temp >= 82°C: Does a gentle breathing pulse to warn of heavy thermal load
    - If Battery <= 15% and discharging: Distinct slow warning pulse
    - Restores user's standard brightness otherwise
    """
    print("[+] Starting Apple SMC Keyboard Hardware HUD...", flush=True)

    def sig_handler(_signo, _frame):
        print("\n[-] Stopping Keyboard HUD.", flush=True)
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    user_preferred_brightness = get_current_brightness()
    if user_preferred_brightness == 0:
        user_preferred_brightness = 30  # Default gentle ambient

    warned_battery = False

    while True:
        try:
            temp = get_cpu_temp()
            is_ac = AC_ONLINE.exists() and AC_ONLINE.read_text().strip() == "1"
            battery_pct = 100
            if BAT_CAPACITY.exists():
                try:
                    battery_pct = int(BAT_CAPACITY.read_text().strip())
                except ValueError:
                    pass

            # Thermal warning (soft ambient pulse when CPU >= 85°C)
            if temp >= 85.0:
                breathe(cycles=1, cycle_duration=2.0, min_val=20, max_val=255)
                time.sleep(3.0)
            # Low battery alert: flash ONCE when crossing below 15%, not in an infinite loop!
            elif not is_ac and battery_pct <= 15:
                if not warned_battery:
                    flash(count=2, delay=0.15, target=180)
                    warned_battery = True
                time.sleep(10.0)
            else:
                if is_ac or battery_pct > 20:
                    warned_battery = False
                time.sleep(5.0)

        except Exception as e:
            time.sleep(5.0)


def main() -> None:
    parser = argparse.ArgumentParser(description="Apple SMC Keyboard Hardware Pulse & HUD")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # set
    set_parser = subparsers.add_parser("set", help="Set brightness (0-255)")
    set_parser.add_argument("value", type=int, help="Brightness value (0-255)")

    # fade
    fade_parser = subparsers.add_parser("fade", help="Smoothly fade to brightness level")
    fade_parser.add_argument("value", type=int, help="Target brightness value (0-255)")
    fade_parser.add_argument("--duration", type=float, default=0.5, help="Duration in seconds")

    # flash
    flash_parser = subparsers.add_parser("flash", help="Flash keyboard (e.g. notify job completion)")
    flash_parser.add_argument("--count", type=int, default=2, help="Number of flashes")
    flash_parser.add_argument("--delay", type=float, default=0.12, help="Flash delay in seconds")

    # breathe
    breathe_parser = subparsers.add_parser("breathe", help="Sine wave breathing pulse")
    breathe_parser.add_argument("--cycles", type=int, default=3, help="Number of breathing cycles")
    breathe_parser.add_argument("--duration", type=float, default=2.0, help="Seconds per cycle")

    # alert
    alert_parser = subparsers.add_parser("alert", help="Strobe alert pattern")
    alert_parser.add_argument("--pulses", type=int, default=3, help="Number of alert pulses")

    # get
    subparsers.add_parser("get", help="Get current brightness level")

    # hud
    subparsers.add_parser("hud", help="Run background ambient thermal/battery monitor daemon")

    args = parser.parse_args()

    if args.command == "get":
        cur = get_current_brightness()
        print(f"Current Keyboard Backlight: {cur} / 255")
    elif args.command == "set":
        set_brightness(args.value)
    elif args.command == "fade":
        fade_to(args.value, duration=args.duration)
    elif args.command == "flash":
        flash(count=args.count, delay=args.delay)
    elif args.command == "breathe":
        breathe(cycles=args.cycles, cycle_duration=args.duration)
    elif args.command == "alert":
        alert(pulses=args.pulses)
    elif args.command == "hud":
        run_hud_daemon()


if __name__ == "__main__":
    main()
