#!/usr/bin/env bash
# pcGDM Auto-Janitor Controller
# Manage the real-time inotify Auto-Janitor daemon on Xubuntu

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JANITOR_PY="$SCRIPT_DIR/auto_janitor.py"
SERVICE_DIR="$HOME/.config/systemd/user"
SERVICE_NAME="pcgdm-janitor.service"
SERVICE_FILE="$SERVICE_DIR/$SERVICE_NAME"
AUTOSTART_DIR="$HOME/.config/autostart"
AUTOSTART_FILE="$AUTOSTART_DIR/pcgdm-janitor.desktop"
LOG_FILE="$HOME/.local/share/pcGDM/janitor.log"

chmod +x "$JANITOR_PY"

usage() {
    cat <<EOF
Usage: ./janitorctl.sh <command>

Commands:
  install     Install and start Auto-Janitor as a background systemd user service
  uninstall   Stop and remove the systemd user service
  status      Show daemon status and recent sorted files
  sweep       Sort all existing loose files in ~/Downloads and ~/Desktop right now
  dry-run     Preview what existing files would be sorted without moving anything
  logs        Tail the live Auto-Janitor activity log
EOF
}

install_service() {
    local extra_flags="${1:-}"
    mkdir -p "$SERVICE_DIR"
    cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=pcGDM Auto-Janitor (Real-Time File Sorter for Downloads & Desktop)
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 $JANITOR_PY $extra_flags
Restart=on-failure
RestartSec=3
Environment=DISPLAY=${DISPLAY:-:0}
Environment=DBUS_SESSION_BUS_ADDRESS=${DBUS_SESSION_BUS_ADDRESS:-unix:path=/run/user/$(id -u)/bus}

[Install]
WantedBy=default.target
EOF

    systemctl --user daemon-reload
    systemctl --user enable "$SERVICE_NAME"
    systemctl --user restart "$SERVICE_NAME"

    # Also add an XFCE Session Autostart entry so Xubuntu guarantees it starts on login
    mkdir -p "$AUTOSTART_DIR"
    cat > "$AUTOSTART_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=pcGDM Auto-Janitor
Comment=Real-time file organizer for Downloads and Desktop
Exec=systemctl --user start $SERVICE_NAME
Icon=folder-saved-search
Terminal=false
Hidden=false
X-GNOME-Autostart-enabled=true
EOF

    echo "[+] Auto-Janitor service installed, enabled on boot/login, and running!"
    systemctl --user status "$SERVICE_NAME" --no-pager
}

uninstall_service() {
    if systemctl --user list-unit-files | grep -q "$SERVICE_NAME"; then
        systemctl --user disable --now "$SERVICE_NAME" || true
    fi
    rm -f "$SERVICE_FILE" "$AUTOSTART_FILE"
    systemctl --user daemon-reload
    echo "[-] Auto-Janitor service stopped and removed."
}

case "${1:-help}" in
    install)
        install_service "${2:-}"
        ;;
    uninstall)
        uninstall_service
        ;;
    status)
        systemctl --user status "$SERVICE_NAME" --no-pager || true
        echo ""
        echo "=== Recent Activity ($LOG_FILE) ==="
        tail -n 15 "$LOG_FILE" 2>/dev/null || echo "No logs yet."
        ;;
    sweep)
        python3 "$JANITOR_PY" --once
        ;;
    dry-run)
        python3 "$JANITOR_PY" --dry-run
        ;;
    logs)
        mkdir -p "$(dirname "$LOG_FILE")"
        touch "$LOG_FILE"
        tail -f "$LOG_FILE"
        ;;
    *)
        usage
        ;;
esac
