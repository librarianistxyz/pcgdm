#!/system/bin/sh
# S9 Maximum Power Rage - Root CPU Frequency Capper
# Run ON the rooted S9/S9+ as root (e.g. via Termux `su` or `adb shell su`).
# Usage: sh s9_root_cpu_cap.sh [enable|disable] [percent]
#   percent defaults to 55 (caps each CPU cluster to ~55% of its max hardware frequency).

ACTION="${1:-enable}"
CAP_PERCENT="${2:-55}"

if [ "$(id -u)" -ne 0 ]; then
  echo "Error: This script must be run as root (use su)." >&2
  exit 1
fi

case "$ACTION" in
  enable)
    echo "Capping CPU max frequencies to ~${CAP_PERCENT}% of hardware max..."
    for cpu_dir in /sys/devices/system/cpu/cpu[0-9]*/cpufreq; do
      [ -d "$cpu_dir" ] || continue
      MAX_HW=$(cat "$cpu_dir/cpuinfo_max_freq" 2>/dev/null)
      MIN_HW=$(cat "$cpu_dir/cpuinfo_min_freq" 2>/dev/null)
      [ -n "$MAX_HW" ] && [ -n "$MIN_HW" ] || continue

      TARGET=$(( MAX_HW * CAP_PERCENT / 100 ))
      if [ "$TARGET" -lt "$MIN_HW" ]; then
        TARGET="$MIN_HW"
      fi

      # Pick the lowest available frequency >= TARGET if scaling_available_frequencies exists
      if [ -f "$cpu_dir/scaling_available_frequencies" ]; then
        CHOSEN="$MAX_HW"
        for f in $(cat "$cpu_dir/scaling_available_frequencies"); do
          if [ "$f" -ge "$TARGET" ] && [ "$f" -lt "$CHOSEN" ]; then
            CHOSEN="$f"
          fi
        done
        TARGET="$CHOSEN"
      fi

      echo "$TARGET" > "$cpu_dir/scaling_max_freq" 2>/dev/null || true
    done
    echo "CPU cap applied."
    ;;

  disable)
    echo "Restoring full CPU max frequencies..."
    for cpu_dir in /sys/devices/system/cpu/cpu[0-9]*/cpufreq; do
      [ -d "$cpu_dir" ] || continue
      MAX_HW=$(cat "$cpu_dir/cpuinfo_max_freq" 2>/dev/null)
      [ -n "$MAX_HW" ] || continue
      echo "$MAX_HW" > "$cpu_dir/scaling_max_freq" 2>/dev/null || true
    done
    echo "Full CPU frequencies restored."
    ;;

  *)
    echo "Usage: $0 [enable|disable] [percent]" >&2
    exit 1
    ;;
esac
