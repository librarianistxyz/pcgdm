#!/usr/bin/env bash
# ==============================================================================
# pcGDM — MASTER GOD MODE CONTROLLER (Xubuntu / Linux)
# One command to install, start, and monitor all 6 God Mode daemons across reboots
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JANITOR_CTL="$SCRIPT_DIR/janitorctl.sh"
CRYO_PY="$SCRIPT_DIR/cryo_ram_boost.py"
FREEZER_PY="$SCRIPT_DIR/focus_freezer.py"
HUD_PY="$SCRIPT_DIR/mac_hud.py"
AIRDROP_PY="$SCRIPT_DIR/airdrop_zero.py"
WARP_PY="$SCRIPT_DIR/warp_ram.py"

USER_SERVICE_DIR="$HOME/.config/systemd/user"
AUTOSTART_DIR="$HOME/.config/autostart"

FREEZER_SERVICE="pcgdm-freezer.service"
FREEZER_SERVICE_FILE="$USER_SERVICE_DIR/$FREEZER_SERVICE"
FREEZER_AUTOSTART="$AUTOSTART_DIR/pcgdm-freezer.desktop"

HUD_SERVICE="pcgdm-hud.service"
HUD_SERVICE_FILE="$USER_SERVICE_DIR/$HUD_SERVICE"
HUD_AUTOSTART="$AUTOSTART_DIR/pcgdm-hud.desktop"

AIRDROP_SERVICE="pcgdm-airdrop.service"
AIRDROP_SERVICE_FILE="$USER_SERVICE_DIR/$AIRDROP_SERVICE"
AIRDROP_AUTOSTART="$AUTOSTART_DIR/pcgdm-airdrop.desktop"

WARP_SERVICE="pcgdm-warpram.service"
WARP_SERVICE_FILE="$USER_SERVICE_DIR/$WARP_SERVICE"
WARP_AUTOSTART="$AUTOSTART_DIR/pcgdm-warpram.desktop"

chmod +x "$JANITOR_CTL" "$CRYO_PY" "$FREEZER_PY" "$HUD_PY" "$AIRDROP_PY" "$WARP_PY"

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

install_freezer_service() {
    mkdir -p "$USER_SERVICE_DIR" "$AUTOSTART_DIR"
    cat > "$FREEZER_SERVICE_FILE" <<EOF
[Unit]
Description=pcGDM Focus Freezer (Zero-CPU Background Browser & Indexer Optimizer)
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 $FREEZER_PY daemon
ExecStop=/usr/bin/python3 $FREEZER_PY wake
Restart=on-failure
RestartSec=3
Environment=DISPLAY=${DISPLAY:-:0}
Environment=XAUTHORITY=${XAUTHORITY:-$HOME/.Xauthority}
Environment=DBUS_SESSION_BUS_ADDRESS=${DBUS_SESSION_BUS_ADDRESS:-unix:path=/run/user/$(id -u)/bus}

[Install]
WantedBy=default.target
EOF

    cat > "$FREEZER_AUTOSTART" <<EOF
[Desktop Entry]
Type=Application
Name=pcGDM Focus Freezer
Comment=Zero-CPU Background Browser Freezer for Xubuntu
Exec=systemctl --user start $FREEZER_SERVICE
Icon=utilities-system-monitor
Terminal=false
Hidden=false
X-GNOME-Autostart-enabled=true
EOF

    systemctl --user daemon-reload
    systemctl --user enable "$FREEZER_SERVICE"
    systemctl --user restart "$FREEZER_SERVICE"
    echo "[+] Focus Freezer service installed, enabled on boot/login, and running!"
}

install_hud_service() {
    mkdir -p "$USER_SERVICE_DIR" "$AUTOSTART_DIR"
    cat > "$HUD_SERVICE_FILE" <<EOF
[Unit]
Description=pcGDM Apple SMC Keyboard Hardware Pulse & Ambient HUD
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 $HUD_PY hud
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
EOF

    cat > "$HUD_AUTOSTART" <<EOF
[Desktop Entry]
Type=Application
Name=pcGDM Keyboard HUD
Comment=Apple SMC Ambient Keyboard Telemetry HUD
Exec=systemctl --user start $HUD_SERVICE
Icon=input-keyboard
Terminal=false
Hidden=false
X-GNOME-Autostart-enabled=true
EOF

    systemctl --user daemon-reload
    systemctl --user enable "$HUD_SERVICE"
    systemctl --user restart "$HUD_SERVICE"
    echo "[+] Keyboard HUD service installed, enabled on boot/login, and running!"
}

install_airdrop_service() {
    mkdir -p "$USER_SERVICE_DIR" "$AUTOSTART_DIR"
    cat > "$AIRDROP_SERVICE_FILE" <<EOF
[Unit]
Description=pcGDM AirDrop-Zero (Instant Local Network Micro-Web Transfer)
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 $AIRDROP_PY run
Restart=on-failure
RestartSec=3
Environment=DISPLAY=${DISPLAY:-:0}
Environment=DBUS_SESSION_BUS_ADDRESS=${DBUS_SESSION_BUS_ADDRESS:-unix:path=/run/user/$(id -u)/bus}

[Install]
WantedBy=default.target
EOF

    cat > "$AIRDROP_AUTOSTART" <<EOF
[Desktop Entry]
Type=Application
Name=pcGDM AirDrop-Zero
Comment=Instant Local Network Micro-Web File Transfer
Exec=systemctl --user start $AIRDROP_SERVICE
Icon=network-wireless
Terminal=false
Hidden=false
X-GNOME-Autostart-enabled=true
EOF

    systemctl --user daemon-reload
    systemctl --user enable "$AIRDROP_SERVICE"
    systemctl --user restart "$AIRDROP_SERVICE"
    echo "[+] AirDrop-Zero service installed, enabled on boot/login, and running!"
}

install_warp_service() {
    mkdir -p "$USER_SERVICE_DIR" "$AUTOSTART_DIR"
    cat > "$WARP_SERVICE_FILE" <<EOF
[Unit]
Description=pcGDM Warp-RAM Accelerator (In-Memory Build Scratchpad & Auto-Sync)
After=default.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 $WARP_PY daemon
ExecStop=/usr/bin/python3 $WARP_PY sync
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
EOF

    cat > "$WARP_AUTOSTART" <<EOF
[Desktop Entry]
Type=Application
Name=pcGDM Warp-RAM
Comment=In-Memory High-Speed Build Scratchpad
Exec=systemctl --user start $WARP_SERVICE
Icon=drive-harddisk
Terminal=false
Hidden=false
X-GNOME-Autostart-enabled=true
EOF

    systemctl --user daemon-reload
    systemctl --user enable "$WARP_SERVICE"
    systemctl --user restart "$WARP_SERVICE"
    echo "[+] Warp-RAM service installed, enabled on boot/login, and running!"
}

install_all() {
    echo -e "${BOLD}╔══════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}║       pcGDM MASTER INSTALLER — Activating All Boot Services      ║${NC}"
    echo -e "${BOLD}╚══════════════════════════════════════════════════════════════════╝${NC}"

    echo -e "\n${CYAN}[1/6] Enabling Broad Auto-Janitor (35+ Folders Real-Time Sorter)...${NC}"
    "$JANITOR_CTL" install --no-initial-sweep

    echo -e "\n${CYAN}[2/6] Enabling Focus Freezer (Zero-CPU Background Browser Freezer)...${NC}"
    install_freezer_service

    echo -e "\n${CYAN}[3/6] Enabling Keyboard Pulse HUD (Hardware Ambient Monitor)...${NC}"
    install_hud_service

    echo -e "\n${CYAN}[4/6] Enabling AirDrop-Zero (Peer-to-Peer Local Network File Dropper)...${NC}"
    install_airdrop_service

    echo -e "\n${CYAN}[5/6] Enabling Warp-RAM Scratchpad (In-Memory Build Accelerator)...${NC}"
    install_warp_service

    echo -e "\n${CYAN}[6/6] Enabling Unified Cryo + Power + RAM Engine (Root Boot Daemon)...${NC}"
    sudo python3 "$CRYO_PY" install

    echo -e "\n${GREEN}${BOLD}[✓] ALL 6 GOD MODE SERVICES INSTALLED AND ENABLED ON BOOT!${NC}"
}

status_all() {
    python3 "$CRYO_PY" status
    echo ""
    python3 "$FREEZER_PY" status
    echo ""
    python3 "$WARP_PY" status
    echo ""
    echo -e "${BOLD}╔══════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}║     pcGDM SYSTEMCTL DAEMON STATUS (Survives Every Restart)       ║${NC}"
    echo -e "${BOLD}╚══════════════════════════════════════════════════════════════════╝${NC}"
    echo -ne "  ${BOLD}1. Auto-Janitor (User)  :${NC} "
    systemctl --user is-active pcgdm-janitor.service || true
    echo -ne "  ${BOLD}2. Focus Freezer (User) :${NC} "
    systemctl --user is-active pcgdm-freezer.service || true
    echo -ne "  ${BOLD}3. Keyboard HUD (User)  :${NC} "
    systemctl --user is-active pcgdm-hud.service || true
    echo -ne "  ${BOLD}4. AirDrop-Zero (User)  :${NC} "
    systemctl --user is-active pcgdm-airdrop.service || true
    echo -ne "  ${BOLD}5. Warp-RAM (User)      :${NC} "
    systemctl --user is-active pcgdm-warpram.service || true
    echo -ne "  ${BOLD}6. Cryo+RAM Engine      :${NC} "
    systemctl is-active pcgdm-cryo.service || true
    echo -e "  ${BOLD}7. Keyboard Backlight   :${NC} $(python3 "$HUD_PY" get 2>/dev/null || echo 'N/A')"
    echo -e "  ${BOLD}8. AirDrop-Zero URL     :${NC} $(python3 "$AIRDROP_PY" url 2>/dev/null || echo 'N/A')"
}

case "${1:-status}" in
    install|enable)
        install_all
        ;;
    install-freezer)
        install_freezer_service
        ;;
    install-hud)
        install_hud_service
        ;;
    install-airdrop)
        install_airdrop_service
        ;;
    install-warp)
        install_warp_service
        ;;
    warp-sync)
        python3 "$WARP_PY" sync
        ;;
    drop|airdrop|qr)
        python3 "$AIRDROP_PY" qr
        ;;
    status)
        status_all
        ;;
    sweep)
        "$JANITOR_CTL" sweep
        ;;
    purge)
        sudo python3 "$CRYO_PY" purge
        ;;
    wake)
        python3 "$FREEZER_PY" wake
        ;;
    flash)
        python3 "$HUD_PY" flash --count "${2:-2}"
        ;;
    breathe)
        python3 "$HUD_PY" breathe --cycles "${2:-3}"
        ;;
    alert)
        python3 "$HUD_PY" alert
        ;;
    turbo|stealth|cryo|balanced)
        sudo python3 "$CRYO_PY" "$1"
        ;;
    *)
        cat <<EOF
Usage: ./godmode.sh <command>

Commands:
  install          One-click install & enable ALL 6 God Mode services on boot (systemctl)
  status           Show live hardware telemetry, frozen tabs, and systemctl service states
  warp-sync        Manually flush in-memory ~/ramdisk to SSD right now
  drop / qr        Print AirDrop-Zero connection QR code/URL for your phone
  sweep            Manually sort all existing loose files across your folders right now
  purge            Manually flush Linux RAM caches right now
  wake             Manually wake all frozen browser tabs immediately
  flash            Flash keyboard backlight twice
  breathe          Run smooth keyboard breathing pulse
  alert            Strobe alert on keyboard backlight
  turbo            Override daemon with max 3.1 GHz Turbo + 5500 RPM cooling
  stealth          Override daemon with 2.5 GHz Ice-Cold Battery Saver
  cryo             Override daemon with 6200 RPM max fan blast
EOF
        ;;
esac
