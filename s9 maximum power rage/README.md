# S9 Maximum Power Rage

Portable scripts to apply **Maximum Power Saving**–style battery optimizations on any **Samsung Galaxy S9 / S9+** while keeping your normal launcher and all your apps usable.

## Files

- `s9_power_rage_enable.sh` — Run from your PC via `adb` (no root required). Keeps One UI in **Optimized** mode while applying Maximum-style limits: Dark Mode, animations & AOD off, background/wakelock restrictions for third-party apps (excluding `whitelist.txt`), and optional HD+ (`720x1480`) resolution + Deep Doze. Pass `--battery-saver` only if you also want One UI's Medium Power Saving toggle on.
- `s9_power_rage_disable.sh` — Reverses all changes made by `s9_power_rage_enable.sh` and restores normal behavior.
- `s9_foreground_watch.sh` & `s9_watch_control.sh` — Starts Shizuku, pushes the on-device watcher to `/data/local/tmp/`, and automatically restricts + force-stops non-whitelisted third-party apps as soon as you leave them or turn off the screen.
- `s9_root_cpu_cap.sh` — **Root-only** script (run on-device via `su` or `adb shell su`) that caps CPU max frequencies directly in `/sys/devices/system/cpu/`.
- `whitelist.txt` — Package names (one per line) to exclude from background/wakelock restrictions (e.g. messaging apps you still want notifications from).

## Quick Start (No Root, via ADB)

1. Enable **Developer Options** and **USB Debugging** on your S9/S9+.
2. Connect the phone via USB and verify connection:
   ```bash
   adb devices
   ```
3. (Optional) Add any apps you want to keep receiving instant notifications for in `whitelist.txt`.
4. Enable Power Rage mode:
   ```bash
   ./s9_power_rage_enable.sh
   ```
   To also drop screen resolution to HD+ (`720x1480` @ `320` dpi):
   ```bash
   ./s9_power_rage_enable.sh --720p
   ```
   To also force immediate Deep Doze:
   ```bash
   ./s9_power_rage_enable.sh --720p --deep-doze
   ```
5. To restore normal mode at any time:
   ```bash
   ./s9_power_rage_disable.sh
   ```

## Rooted S9/S9+ (Optional CPU Cap)

Push `s9_root_cpu_cap.sh` to the phone or run it via `adb shell`:
```bash
adb push s9_root_cpu_cap.sh /data/local/tmp/
adb shell "su -c 'sh /data/local/tmp/s9_root_cpu_cap.sh enable'"
```
To restore full CPU speed:
```bash
adb shell "su -c 'sh /data/local/tmp/s9_root_cpu_cap.sh disable'"
```
cd "s9 maximum power rage"
./s9_watch_control.sh start