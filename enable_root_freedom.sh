#!/usr/bin/env bash
# ==============================================================================
# PC-GDM — Option B: Full Root Freedom (True God Mode)
# Grants passwordless sudo to $USER so Telegram Bot can execute root commands
# ==============================================================================

set -euo pipefail

TARGET_USER="${SUDO_USER:-$USER}"
SUDOERS_FILE="/etc/sudoers.d/pcgdm-admin"

echo "⚡ Enabling Option B: Full Root Freedom for user '$TARGET_USER'..."

if [[ $EUID -ne 0 ]]; then
    echo "This script requires sudo. Re-running with sudo..."
    exec sudo bash "$0" "$@"
fi

echo "$TARGET_USER ALL=(ALL) NOPASSWD: ALL" > "$SUDOERS_FILE"
chmod 0440 "$SUDOERS_FILE"

# Validate sudoers syntax with visudo
if visudo -cf "$SUDOERS_FILE"; then
    echo "✅ Sudoers syntax verified successfully."
    echo "🎉 Full Root Freedom (Option B) is now ACTIVE!"
    echo "You can now run any root command from your phone on Telegram (e.g. /update, /upgrade, /cmd sudo ...)."
else
    echo "❌ Error in sudoers syntax! Removing broken file..."
    rm -f "$SUDOERS_FILE"
    exit 1
fi
