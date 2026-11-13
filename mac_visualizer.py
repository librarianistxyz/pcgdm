#!/usr/bin/env python3
"""
pcGDM Apple SMC Keyboard Audio Visualizer & Reactive Engine (mac_visualizer.py)
Turns your physical MacBook Pro keyboard into a real-time hardware music visualizer
while fully preserving 100% manual brightness control.

Key Features:
- Direct hardware illumination key detection (F5 / F6 / Fn+F5 / Fn+F6)
- Dynamic music beat equalizer scaling to user's manual brightness ceiling
- Zero-interference manual override mode
- Steady ambient lighting hold when music is paused/stopped or silent
- Pure speaker output monitor (zero microphone/voice bleed)
"""
 
import argparse
import math
import os
import signal
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path

KBD_BRIGHTNESS = Path("/sys/class/leds/smc::kbd_backlight/brightness")
PID_FILE = Path("/tmp/mac_visualizer.pid")
MODE_FILE = Path("/tmp/mac_visualizer.mode")
OVERRIDE_FILE = Path("/tmp/mac_kbd_manual_override")
CONFIG_DIR = Path.home() / ".config" / "pcgdm"
SETTING_FILE = CONFIG_DIR / "kbd_brightness.val"
HUD_PREF_FILE = Path.home() / ".local" / "share" / "pcGDM" / "user_kbd_brightness"
KBD_EVENT_DEVICE = Path("/dev/input/by-id/usb-Apple_Inc._Apple_Internal_Keyboard___Trackpad-event-kbd")
if not KBD_EVENT_DEVICE.exists():
    KBD_EVENT_DEVICE = Path("/dev/input/by-path/pci-0000:00:1d.0-usb-0:1.8.3:1.0-event-kbd")


def get_user_brightness() -> int:
    """Returns the user's manual brightness preference (0-255)."""
    if SETTING_FILE.exists():
        try:
            return max(0, min(255, int(SETTING_FILE.read_text().strip())))
        except Exception:
            pass
    if HUD_PREF_FILE.exists():
        try:
            return max(0, min(255, int(HUD_PREF_FILE.read_text().strip())))
        except Exception:
            pass
    if KBD_BRIGHTNESS.exists():
        try:
            return max(0, min(255, int(KBD_BRIGHTNESS.read_text().strip())))
        except Exception:
            pass
    return 100


def save_user_brightness(val: int) -> None:
    val = max(0, min(255, val))
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    SETTING_FILE.write_text(f"{val}\n")
    try:
        HUD_PREF_FILE.parent.mkdir(parents=True, exist_ok=True)
        HUD_PREF_FILE.write_text(f"{val}\n")
    except Exception:
        pass
    try:
        OVERRIDE_FILE.write_text(f"{time.time()}:{val}")
    except Exception:
        pass


def is_manual_override_active() -> bool:
    """Checks if the user manually adjusted brightness within the last 2.0 seconds."""
    if OVERRIDE_FILE.exists():
        try:
            data = OVERRIDE_FILE.read_text().strip().split(":")
            ts = float(data[0])
            if time.time() - ts < 2.0:
                return True
        except Exception:
            pass
    return False


def set_hardware_brightness(kbd_f, val: int) -> None:
    """Writes an exact integer brightness to sysfs with proper truncation."""
    val = max(0, min(255, int(val)))
    try:
        kbd_f.seek(0)
        kbd_f.write(f"{val}\n")
        kbd_f.truncate()
        kbd_f.flush()
    except Exception:
        pass


def is_running() -> bool:
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 0)
            return True
        except (ValueError, OSError):
            PID_FILE.unlink(missing_ok=True)
    return False


def stop_visualizer() -> None:
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            if pid != os.getpid():
                os.kill(pid, signal.SIGTERM)
                time.sleep(0.2)
        except (ValueError, OSError):
            pass
        PID_FILE.unlink(missing_ok=True)
    MODE_FILE.unlink(missing_ok=True)
    # Restore user manual brightness
    if KBD_BRIGHTNESS.exists():
        try:
            user_b = get_user_brightness()
            with open(KBD_BRIGHTNESS, "w") as f:
                f.write(f"{user_b}\n")
                f.truncate()
                f.flush()
        except Exception:
            pass


def get_monitor_source() -> str:
    """Gets the active audio sink monitor so we ONLY capture speaker playback (never mic)."""
    try:
        sink = subprocess.check_output(["pactl", "get-default-sink"], text=True, timeout=2).strip()
        if sink:
            return f"{sink}.monitor"
    except Exception:
        pass
    return "alsa_output.pci-0000_00_1b.0.analog-stereo.monitor"


def hardware_key_listener_loop(kbd_f) -> None:
    """Background listener that detects physical Apple F5 / F6 illumination keys."""
    if not KBD_EVENT_DEVICE.exists():
        return
    try:
        dev_file = open(KBD_EVENT_DEVICE, "rb")
    except Exception:
        return

    fmt = "qqHHi"
    while True:
        try:
            chunk = dev_file.read(24)
            if not chunk or len(chunk) < 24:
                time.sleep(0.05)
                continue
            sec, usec, ev_type, ev_code, ev_value = struct.unpack(fmt, chunk)
            # EV_KEY = 1, ev_value: 1 = press, 2 = repeat
            if ev_type == 1 and ev_value in (1, 2):
                if ev_code == 229:  # KEY_KBDILLUMDOWN (F5)
                    cur = get_user_brightness()
                    new_val = max(0, cur - 25)
                    save_user_brightness(new_val)
                    set_hardware_brightness(kbd_f, new_val)
                elif ev_code == 230:  # KEY_KBDILLUMUP (F6)
                    cur = get_user_brightness()
                    new_val = min(255, cur + 25 if cur > 0 else 25)
                    save_user_brightness(new_val)
                    set_hardware_brightness(kbd_f, new_val)
                elif ev_code == 228:  # KEY_KBDILLUMTOGGLE
                    cur = get_user_brightness()
                    new_val = 0 if cur > 0 else 125
                    save_user_brightness(new_val)
                    set_hardware_brightness(kbd_f, new_val)
        except Exception:
            time.sleep(0.1)


def run_music_visualizer() -> None:
    """Captures ONLY speaker playback audio (music/media) and pulses keyboard brightness to beats.

    Harmonizes with manual user brightness:
    - Scales pulse ceiling to user's chosen manual brightness level.
    - If user sets brightness to 0 (off), the visualizer stays off.
    - When music is stopped / silent, smoothly holds steady ambient light at user level.
    - When user adjusts brightness manually (F5/F6 or keys), yields instantly without fighting.
    """
    PID_FILE.write_text(str(os.getpid()))
    MODE_FILE.write_text("music")

    def sig_handler(_signo, _frame):
        sys.exit(0)

    signal.signal(signal.SIGTERM, sig_handler)
    signal.signal(signal.SIGINT, sig_handler)

    monitor_source = get_monitor_source()

    cmd = [
        "ffmpeg", "-loglevel", "quiet",
        "-f", "pulse",
        "-i", monitor_source,
        "-f", "s16le",
        "-ac", "1",
        "-ar", "22050",
        "-"
    ]

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except Exception as e:
        sys.exit(f"Failed to launch audio monitor: {e}")

    chunk_size = 512 * 2  # 512 samples (~23ms per chunk)
    user_ceiling = get_user_brightness()
    cur_brightness = float(user_ceiling)
    decay_rate = 0.80
    rolling_peak = 1200.0
    silent_frames = 0
    last_written_brightness = -1
    last_ceiling_check = time.time()

    try:
        with open(KBD_BRIGHTNESS, "w") as kbd_f:
            # Start background hardware key listener
            key_thread = threading.Thread(target=hardware_key_listener_loop, args=(kbd_f,), daemon=True)
            key_thread.start()

            # Initialize to user preference
            set_hardware_brightness(kbd_f, user_ceiling)
            last_written_brightness = user_ceiling

            while True:
                now = time.time()
                if now - last_ceiling_check > 0.25:
                    user_ceiling = get_user_brightness()
                    last_ceiling_check = now

                # If user recently adjusted brightness manually via keys, respect it & yield
                if is_manual_override_active():
                    cur_brightness = float(user_ceiling)
                    last_written_brightness = int(cur_brightness)
                    time.sleep(0.04)
                    continue

                chunk = proc.stdout.read(chunk_size)
                if not chunk or len(chunk) < chunk_size:
                    time.sleep(0.02)
                    continue

                # If user manually turned lights completely OFF (0), keep it dark
                if user_ceiling <= 0:
                    if last_written_brightness != 0:
                        set_hardware_brightness(kbd_f, 0)
                        last_written_brightness = 0
                    time.sleep(0.05)
                    continue

                samples = struct.unpack(f"{len(chunk)//2}h", chunk)
                rms = math.sqrt(sum(s * s for s in samples) / len(samples))

                # Hard silence gate: If speaker output is silent (music paused/stopped/talking)
                if rms < 150.0:
                    silent_frames += 1
                    if silent_frames > 6:  # ~140ms of silence
                        # Music paused: smoothly return to steady manual ambient light
                        target_idle = float(user_ceiling)
                        if abs(cur_brightness - target_idle) > 1.0:
                            cur_brightness = cur_brightness * 0.82 + target_idle * 0.18
                            int_b = int(round(cur_brightness))
                            if int_b != last_written_brightness:
                                set_hardware_brightness(kbd_f, int_b)
                                last_written_brightness = int_b
                        elif last_written_brightness != int(target_idle):
                            cur_brightness = target_idle
                            set_hardware_brightness(kbd_f, int(target_idle))
                            last_written_brightness = int(target_idle)
                        time.sleep(0.03)
                        continue
                else:
                    silent_frames = 0

                # Music is actively playing: dynamic AGC pulse scaled to user ceiling
                if rms > rolling_peak:
                    rolling_peak = rms * 0.9 + rolling_peak * 0.1
                else:
                    rolling_peak = max(600.0, rolling_peak * 0.995)

                noise_floor = 180.0
                effective = max(0.0, rms - noise_floor)
                dynamic_range = max(400.0, rolling_peak - noise_floor)
                pulse_ratio = min(1.0, effective / dynamic_range)

                # Floor scales with user ceiling
                min_floor = max(8.0, user_ceiling * 0.15)
                target = min_floor + pulse_ratio * (user_ceiling - min_floor)

                # Instant attack on kick drum/beat, smooth decay
                if target > cur_brightness:
                    cur_brightness = target
                else:
                    cur_brightness = max(min_floor, cur_brightness * decay_rate)

                int_b = int(round(min(float(user_ceiling), max(0.0, cur_brightness))))
                if int_b != last_written_brightness:
                    set_hardware_brightness(kbd_f, int_b)
                    last_written_brightness = int_b

    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        proc.terminate()
        stop_visualizer()


def run_typing_reactive() -> None:
    """Flares keyboard backlight to manual ceiling on keypress with exponential fade."""
    PID_FILE.write_text(str(os.getpid()))
    MODE_FILE.write_text("typing")

    def sig_handler(_signo, _frame):
        sys.exit(0)

    signal.signal(signal.SIGTERM, sig_handler)
    signal.signal(signal.SIGINT, sig_handler)

    if not KBD_EVENT_DEVICE.exists():
        sys.exit(f"Keyboard event device not found: {KBD_EVENT_DEVICE}")

    try:
        event_f = open(KBD_EVENT_DEVICE, "rb")
        os.set_blocking(event_f.fileno(), False)
    except Exception as e:
        sys.exit(f"Failed to open keyboard event device: {e}")

    user_ceiling = get_user_brightness()
    cur_brightness = float(user_ceiling)
    decay_rate = 0.88
    last_written_brightness = -1
    last_ceiling_check = time.time()

    try:
        with open(KBD_BRIGHTNESS, "w") as kbd_f:
            while True:
                now = time.time()
                if now - last_ceiling_check > 0.25:
                    user_ceiling = get_user_brightness()
                    last_ceiling_check = now

                if is_manual_override_active():
                    cur_brightness = float(user_ceiling)
                    time.sleep(0.05)
                    continue

                idle_floor = max(0.0, user_ceiling * 0.10)
                try:
                    data = event_f.read(24)
                    if data:
                        cur_brightness = float(user_ceiling)
                    else:
                        cur_brightness = max(idle_floor, cur_brightness * decay_rate)
                except BlockingIOError:
                    cur_brightness = max(idle_floor, cur_brightness * decay_rate)

                int_b = int(round(min(float(user_ceiling), max(0.0, cur_brightness))))
                if int_b != last_written_brightness:
                    set_hardware_brightness(kbd_f, int_b)
                    last_written_brightness = int_b

                time.sleep(0.02)

    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        event_f.close()
        stop_visualizer()


def main():
    parser = argparse.ArgumentParser(description="pcGDM Apple Keyboard Music Visualizer & Backlight Engine")
    parser.add_argument("action", choices=["music", "pulse", "typing", "stop", "status", "light"], help="Action or mode")
    parser.add_argument("value", nargs="?", default=None, help="Value for light action (up, down, off, max, or 0-255)")
    parser.add_argument("--daemon", action="store_true", help="Run in background daemon mode")
    args = parser.parse_args()

    if args.action == "light":
        adjust_script = Path(__file__).resolve().parent / "adjust_kbd_light.py"
        sub_args = [args.value] if args.value else []
        subprocess.run([sys.executable, str(adjust_script)] + sub_args)
        return

    if args.action == "status":
        if is_running():
            mode = MODE_FILE.read_text().strip() if MODE_FILE.exists() else "active"
            print(f"✅ Keyboard Visualizer is ACTIVE (Mode: {mode}, PID: {PID_FILE.read_text().strip()})")
            print(f"   Manual Ceiling Level: {get_user_brightness()} / 255")
        else:
            print(f"⚪ Keyboard Visualizer is INACTIVE. Manual Level: {get_user_brightness()} / 255")
        return

    if args.action == "stop":
        stop_visualizer()
        print(f"🛑 Keyboard visualizer stopped. Ambient brightness restored to {get_user_brightness()} / 255.")
        return

    if is_running():
        stop_visualizer()

    target_func = run_music_visualizer if args.action in ("music", "pulse") else run_typing_reactive

    if args.daemon:
        pid = os.fork()
        if pid > 0:
            print(f"🎵 Keyboard visualizer started in background ({args.action} mode, PID {pid}).")
            sys.exit(0)
        os.setsid()
        target_func()
    else:
        print(f"🎵 Keyboard visualizer running in foreground ({args.action} mode). Press Ctrl+C to stop.")
        target_func()


if __name__ == "__main__":
    main()
