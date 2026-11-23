#!/usr/bin/env bash
set -euo pipefail

# S9 Maximum Power Rage - Shizuku & Foreground Watcher Controller (PC / ADB)
# Starts Shizuku, pushes s9_foreground_watch.sh + whitelist.txt to the S9,
# and starts/stops/checks the background watcher.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ACTION="${1:-start}"

if ! command -v adb >/dev/null 2>&1; then
  echo "Error: 'adb' is not installed or not in PATH." >&2
  exit 1
fi

if ! adb get-state >/dev/null 2>&1; then
  echo "Error: No authorized ADB device found." >&2
  exit 1
fi

start_shizuku() {
  if adb shell "ps -A | grep -q shizuku_server" 2>/dev/null; then
    echo "Shizuku server is already running."
    return
  fi
  SHIZUKU_BIN=$(adb shell "pm path moe.shizuku.privileged.api" | sed 's/^package://;s|/base\.apk.*||;s/\r//')
  if [[ -n "$SHIZUKU_BIN" ]]; then
    echo "Starting Shizuku server..."
    adb shell "nohup $SHIZUKU_BIN/lib/arm64/libshizuku.so >/dev/null 2>&1 &" || true
    sleep 1
  else
    echo "Shizuku app not found on device (skipping Shizuku start)."
  fi
}

case "$ACTION" in
  start)
    start_shizuku

    echo "Pushing whitelist and watcher script to /data/local/tmp/..."
    if [[ -f "$SCRIPT_DIR/whitelist.txt" ]]; then
      (grep -v '^[[:space:]]*#' "$SCRIPT_DIR/whitelist.txt" || true) | sed '/^[[:space:]]*$/d' > /tmp/s9_whitelist_clean.txt
      adb push /tmp/s9_whitelist_clean.txt /data/local/tmp/s9_whitelist.txt >/dev/null
      rm -f /tmp/s9_whitelist_clean.txt
    fi
    adb push "$SCRIPT_DIR/s9_foreground_watch.sh" /data/local/tmp/s9_foreground_watch.sh >/dev/null
    adb shell "chmod +x /data/local/tmp/s9_foreground_watch.sh"

    # Stop existing watcher if running
    adb shell "if [ -f /data/local/tmp/s9_watch.pid ]; then kill \$(cat /data/local/tmp/s9_watch.pid) 2>/dev/null || true; fi"
    sleep 1

    echo "Starting foreground watcher on S9..."
    adb shell "setsid sh /data/local/tmp/s9_foreground_watch.sh </dev/null >/dev/null 2>&1 &"
    sleep 1
    adb shell "cat /data/local/tmp/s9_watch.log 2>/dev/null | tail -n 5"
    echo "Watcher is now running on the phone (even after unplugging USB, until reboot)."
    ;;

  stop)
    echo "Stopping foreground watcher on S9..."
    adb shell "if [ -f /data/local/tmp/s9_watch.pid ]; then kill \$(cat /data/local/tmp/s9_watch.pid) 2>/dev/null || true; rm -f /data/local/tmp/s9_watch.pid; fi"
    echo "Watcher stopped."
    ;;

  status)
    echo "=== Shizuku ==="
    adb shell "ps -A | grep -i shizuku || echo 'Not running'"
    echo "=== Watcher ==="
    adb shell "if [ -f /data/local/tmp/s9_watch.pid ] && kill -0 \$(cat /data/local/tmp/s9_watch.pid) 2>/dev/null; then echo \"Running (PID \$(cat /data/local/tmp/s9_watch.pid))\"; else echo 'Not running'; fi"
    echo "=== Recent Log ==="
    adb shell "tail -n 10 /data/local/tmp/s9_watch.log 2>/dev/null || echo 'No log yet'"
    ;;

  *)
    echo "Usage: $0 [start|stop|status]" >&2
    exit 1
    ;;
esac
