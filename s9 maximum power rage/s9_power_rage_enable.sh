#!/usr/bin/env bash
set -euo pipefail

# S9 Maximum Power Rage - Enable (No Root / ADB)
# Applies aggressive power-saving limits on any Galaxy S9 / S9+
# while keeping the normal launcher and all apps accessible.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WHITELIST_FILE="$SCRIPT_DIR/whitelist.txt"

USE_720P=false
DEEP_DOZE=false
BATTERY_SAVER=false

for arg in "$@"; do
  case "$arg" in
    --720p) USE_720P=true ;;
    --deep-doze) DEEP_DOZE=true ;;
    --battery-saver) BATTERY_SAVER=true ;;
    -h|--help)
      echo "Usage: $0 [--720p] [--deep-doze] [--battery-saver]"
      echo "  --720p           Drop display resolution to 720x1480 (320 dpi)"
      echo "  --deep-doze      Force Android into immediate Deep Doze mode"
      echo "  --battery-saver  Also toggle Android low_power (switches One UI to Medium mode)"
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      exit 1
      ;;
  esac
done

if ! command -v adb >/dev/null 2>&1; then
  echo "Error: 'adb' is not installed or not in PATH." >&2
  exit 1
fi

if ! adb get-state >/dev/null 2>&1; then
  echo "Error: No authorized ADB device found. Enable USB debugging and connect your S9." >&2
  exit 1
fi

MODEL=$(adb shell getprop ro.product.model | tr -d '\r')
echo "Connected device: $MODEL"

# Load whitelist into an associative array if present
declare -A WHITELIST
if [[ -f "$WHITELIST_FILE" ]]; then
  while IFS= read -r line; do
    line="${line%%#*}"
    line="$(echo "$line" | tr -d '[:space:]')"
    [[ -n "$line" ]] && WHITELIST["$line"]=1
  done < "$WHITELIST_FILE"
fi

if [[ "$BATTERY_SAVER" == true ]]; then
  echo "[1/5] Enabling Battery Saver (Medium mode) & Dark Mode..."
  adb shell settings put global low_power 1
  adb shell settings put global low_power_sticky 1
else
  echo "[1/5] Keeping One UI in Optimized mode & enabling Dark Mode..."
  adb shell settings put global low_power 0
  adb shell settings put global low_power_sticky 0
fi
adb shell cmd uimode night yes >/dev/null 2>&1 || true

echo "[2/5] Disabling animations & Always-On Display..."
adb shell settings put global window_animation_scale 0
adb shell settings put global transition_animation_scale 0
adb shell settings put global animator_duration_scale 0
adb shell settings put system aod_mode 0

if [[ "$USE_720P" == true ]]; then
  echo "[3/5] Setting display to HD+ (720x1480 @ 320 dpi)..."
  adb shell wm size 720x1480
  adb shell wm density 320
else
  echo "[3/5] Keeping current display resolution (pass --720p to lower it)."
fi

echo "[4/5] Restricting background execution & wakelocks for third-party apps..."
RESTRICTED_COUNT=0
SKIPPED_COUNT=0

while IFS= read -r pkg; do
  pkg="${pkg#package:}"
  pkg="$(echo "$pkg" | tr -d '\r[:space:]')"
  [[ -z "$pkg" ]] && continue

  if [[ -n "${WHITELIST[$pkg]:-}" ]]; then
    ((SKIPPED_COUNT+=1))
    continue
  fi

  adb shell cmd appops set "$pkg" RUN_ANY_IN_BACKGROUND ignore >/dev/null 2>&1 || true
  adb shell cmd appops set "$pkg" WAKE_LOCK ignore >/dev/null 2>&1 || true
  adb shell am set-standby-bucket "$pkg" rare >/dev/null 2>&1 || true
  ((RESTRICTED_COUNT+=1))
done < <(adb shell pm list packages -3)

echo "  -> Restricted $RESTRICTED_COUNT apps (skipped $SKIPPED_COUNT whitelisted)."

if [[ "$DEEP_DOZE" == true ]]; then
  echo "[5/5] Forcing Deep Doze..."
  adb shell dumpsys deviceidle force-idle >/dev/null 2>&1 || true
else
  echo "[5/5] Skipping forced Deep Doze (pass --deep-doze to enable)."
fi

echo "Done! S9 Maximum Power Rage is active."
