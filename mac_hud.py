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


def set_brightness(val: int) -> bool:
    val = max(0, min(255, int(val)))
    try:
        BRIGHTNESS_FILE.write_text(f"{val}\n")
        return True
    except PermissionError:
        # Fallback to sudo tee if user doesn't have direct write access
        res = os.system(f"echo {val} | sudo tee {BRIGHTNESS_FILE} > /dev/null 2>&1")
        return res == 0
    except Exception as e:
        print(f"[!] Error setting brightness: {e}", file=sys.stderr)
        return False


def get_cpu_temp() -> float:
    temps = []
    for p in glob.glob("/sys/class/hwmon/hwmon*/temp*_input"):
        try:
            name_path = Path(p).parent / "name"
            if name_path.exists() and name_path.read_text().strip() == "coretemp":
                val = int(Path(p).read_text().strip()) / 1000.0
                if 10.0 < val < 120.0:
                    temps.append(val)
        except Exception:
            pass
    return max(temps) if temps else 50.0


def flash(count: int = 2, delay: float = 0.12, target: int = 255) -> None:
    """Flash the keyboard on and off rapidly to signal completion or notifications."""
    original = get_current_brightness()
    for _ in range(count):
        set_brightness(target)
        time.sleep(delay)
        set_brightness(0)
        time.sleep(delay)
    set_brightness(original)


def fade_to(target: int, duration: float = 0.5, steps: int = 25) -> None:
    """Smoothly transitions brightness to target."""
    current = get_current_brightness()
    target = max(0, min(255, target))
    if current == target:
        return

    step_delay = duration / steps
    diff = target - current
    for i in range(1, steps + 1):
        # Cosine ease in/out
        progress = i / steps
        factor = (1 - math.cos(progress * math.pi)) / 2
        val = int(current + (diff * factor))
        set_brightness(val)
        time.sleep(step_delay)
    set_brightness(target)


def breathe(cycles: int = 3, cycle_duration: float = 2.0, min_val: int = 0, max_val: int = 255) -> None:
    """Smooth ambient sine-wave breathing pulse."""
    original = get_current_brightness()
    steps_per_cycle = 40
    step_delay = cycle_duration / steps_per_cycle
    span = (max_val - min_val) / 2.0
    mid = min_val + span

    try:
        for _ in range(cycles):
            for i in range(steps_per_cycle):
                # Sine curve from min to max and back
                angle = (i / steps_per_cycle) * (2 * math.pi) - (math.pi / 2)
                brightness = int(mid + (span * math.sin(angle)))
                set_brightness(brightness)
                time.sleep(step_delay)
    finally:
        set_brightness(original)


def alert(pulses: int = 5) -> None:
    """Urgent strobe pattern for warnings."""
    original = get_current_brightness()
    try:
        for _ in range(pulses):
            for _ in range(3):
                set_brightness(255)
                time.sleep(0.06)
                set_brightness(0)
                time.sleep(0.06)
            time.sleep(0.3)
    finally:
        set_brightness(original)


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

            # Thermal warning
            if temp >= 82.0:
                # Breathe once gently as high-temp alert
                breathe(cycles=1, cycle_duration=1.8, min_val=20, max_val=255)
                time.sleep(1.0)
            # Critical battery warning
            elif not is_ac and battery_pct <= 15:
                flash(count=3, delay=0.1, target=200)
                time.sleep(5.0)
            else:
                # Regular state: maintain standard user level
                time.sleep(3.0)

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
