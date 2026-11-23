#!/usr/bin/env bash
set -euo pipefail

# S9 Maximum Power Rage - Disable / Restore (No Root / ADB)
# Reverses all settings changed by s9_power_rage_enable.sh.

if ! command -v adb >/dev/null 2>&1; then
  echo "Error: 'adb' is not installed or not in PATH." >&2
  exit 1
fi

if ! adb get-state >/dev/null 2>&1; then
  echo "Error: No authorized ADB device found. Connect your S9 via USB debugging." >&2
  exit 1
fi

echo "[1/4] Restoring Battery Saver & Dark Mode settings..."
adb shell settings put global low_power 0
adb shell settings put global low_power_sticky 0

echo "[2/4] Restoring animations & display resolution..."
adb shell settings put global window_animation_scale 1
adb shell settings put global transition_animation_scale 1
adb shell settings put global animator_duration_scale 1
adb shell wm size reset
adb shell wm density reset

echo "[3/4] Restoring background permissions for third-party apps..."
RESTORED_COUNT=0
while IFS= read -r pkg; do
  pkg="${pkg#package:}"
  pkg="$(echo "$pkg" | tr -d '\r[:space:]')"
  [[ -z "$pkg" ]] && continue

  adb shell cmd appops set "$pkg" RUN_ANY_IN_BACKGROUND allow >/dev/null 2>&1 || true
  adb shell cmd appops set "$pkg" WAKE_LOCK allow >/dev/null 2>&1 || true
  adb shell am set-standby-bucket "$pkg" active >/dev/null 2>&1 || true
  ((RESTORED_COUNT+=1))
done < <(adb shell pm list packages -3)

echo "  -> Restored $RESTORED_COUNT apps."

echo "[4/4] Unforcing Deep Doze..."
adb shell dumpsys deviceidle unforce >/dev/null 2>&1 || true

echo "Done! Normal power settings restored."
