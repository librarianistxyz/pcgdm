#!/system/bin/sh
# S9 Maximum Power Rage - On-Device Foreground Watcher
# Keeps One UI in Optimized mode, allows only the currently active app to run,
# and restricts + force-stops non-whitelisted third-party apps when you leave them
# or turn off the screen.

WHITELIST_FILE="/data/local/tmp/s9_whitelist.txt"
PID_FILE="/data/local/tmp/s9_watch.pid"
LOG_FILE="/data/local/tmp/s9_watch.log"
POLL_SECONDS=4

echo $$ > "$PID_FILE"
echo "[$(date '+%H:%M:%S')] Watcher started (PID $$)" > "$LOG_FILE"

is_whitelisted() {
  pkg="$1"
  case "$pkg" in
    moe.shizuku.privileged.api|com.termux|com.aistra.hail|io.github.samolego.canta|com.sec.android.*|com.samsung.*|com.android.*|android)
      return 0
      ;;
  esac
  if [ -f "$WHITELIST_FILE" ]; then
    if grep -Fxq "$pkg" "$WHITELIST_FILE" 2>/dev/null; then
      return 0
    fi
  fi
  return 1
}

is_third_party() {
  pm list packages -3 2>/dev/null | grep -Fqx "package:$1"
}

restrict_and_stop() {
  pkg="$1"
  [ -z "$pkg" ] && return
  is_whitelisted "$pkg" && return
  is_third_party "$pkg" || return

  cmd appops set "$pkg" RUN_ANY_IN_BACKGROUND ignore >/dev/null 2>&1
  cmd appops set "$pkg" WAKE_LOCK ignore >/dev/null 2>&1
  am set-standby-bucket "$pkg" rare >/dev/null 2>&1
  am force-stop "$pkg" >/dev/null 2>&1
  echo "[$(date '+%H:%M:%S')] Stopped & restricted: $pkg" >> "$LOG_FILE"
}

PREV_PKG=""
WAS_AWAKE=1

while true; do
  WAKE_STATE=$(dumpsys power 2>/dev/null | grep -m1 'mWakefulness=' | cut -d= -f2 | tr -d '\r ')

  if [ "$WAKE_STATE" = "Awake" ]; then
    if [ "$WAS_AWAKE" -eq 0 ]; then
      WAS_AWAKE=1
    fi

    # Extract resumed activity package name (e.g. com.example.app/.MainActivity -> com.example.app)
    RESUMED=$(dumpsys activity activities 2>/dev/null | grep -m1 'mResumedActivity' | sed -n 's/.* u[0-9]* \([^/ ]*\)\/.*/\1/p' | tr -d '\r ')

    if [ -n "$RESUMED" ] && [ "$RESUMED" != "$PREV_PKG" ]; then
      if [ -n "$PREV_PKG" ]; then
        restrict_and_stop "$PREV_PKG"
      fi

      # Ensure the newly opened app can run smoothly while in foreground
      if ! is_whitelisted "$RESUMED" && is_third_party "$RESUMED"; then
        am set-standby-bucket "$RESUMED" active >/dev/null 2>&1
      fi

      PREV_PKG="$RESUMED"
    fi
  else
    # Screen just turned off
    if [ "$WAS_AWAKE" -eq 1 ]; then
      WAS_AWAKE=0
      if [ -n "$PREV_PKG" ]; then
        restrict_and_stop "$PREV_PKG"
        PREV_PKG=""
      fi
      dumpsys deviceidle force-idle >/dev/null 2>&1
      echo "[$(date '+%H:%M:%S')] Screen off -> Deep Doze forced" >> "$LOG_FILE"
    fi
  fi

  # Keep log file small (trim if > 200 lines)
  if [ -f "$LOG_FILE" ] && [ "$(wc -l < "$LOG_FILE" 2>/dev/null || echo 0)" -gt 200 ]; then
    tail -n 100 "$LOG_FILE" > "${LOG_FILE}.tmp" && mv "${LOG_FILE}.tmp" "$LOG_FILE"
  fi

  sleep "$POLL_SECONDS"
done
