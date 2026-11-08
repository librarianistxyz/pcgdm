#!/usr/bin/env bash
# ==============================================================================
# GodMode TeleKey - Universal Linux Auto-Installer
# Runs on ANY Linux machine (Ubuntu, Debian, Mint, Fedora, Arch, etc.)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="$HOME/.local/share/pcGDM"
SERVICE_DIR="$HOME/.config/systemd/user"
AUTOSTART_DIR="$HOME/.config/autostart"

echo "========================================================"
echo "      GodMode TeleKey - Linux Auto-Installer"
echo "========================================================"

mkdir -p "$TARGET_DIR" "$SERVICE_DIR" "$AUTOSTART_DIR"

echo "[*] Copying TeleKey script to $TARGET_DIR..."
cp -f "$SCRIPT_DIR/tele_key_linux.py" "$TARGET_DIR/tele_key.py"
chmod +x "$TARGET_DIR/tele_key.py"

echo "[*] Registering systemd user service..."
cat > "$SERVICE_DIR/telekey.service" <<EOF
[Unit]
Description=Universal TeleKey Hardware USB Telegram Bridge
After=network.target graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 $TARGET_DIR/tele_key.py
Restart=always
RestartSec=3
Environment=PYTHONUNBUFFERED=1
Environment=DISPLAY=${DISPLAY:-:0}
Environment=XAUTHORITY=${XAUTHORITY:-$HOME/.Xauthority}

[Install]
WantedBy=default.target
EOF

cat > "$AUTOSTART_DIR/telekey.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=TeleKey Daemon
Exec=/usr/bin/python3 $TARGET_DIR/tele_key.py
Terminal=false
StartupNotify=false
X-GNOME-Autostart-enabled=true
EOF

systemctl --user daemon-reload
systemctl --user enable telekey.service
systemctl --user restart telekey.service

echo ""
echo "[✓] TeleKey installed and running on $(hostname)!"
echo "Whenever you plug your 16GB USB key into this machine,"
echo "it will instantly report to your Telegram Bot."
echo "========================================================"
