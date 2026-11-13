#!/usr/bin/env bash
set -euo pipefail

if [ "$EUID" -ne 0 ]; then
  echo "Run with sudo: sudo $0"
  exit 1
fi

USER_NAME="librarianist"
USER_UID=$(id -u "$USER_NAME")

echo "[1/4] Disabling user-level pcgdm-biounlock.service..."
runuser -u "$USER_NAME" -- env XDG_RUNTIME_DIR="/run/user/$USER_UID" \
  systemctl --user disable --now pcgdm-biounlock.service 2>/dev/null || true

echo "[2/4] Installing /usr/local/bin/pcgdm-pam-check..."
cat <<'EOF' > /usr/local/bin/pcgdm-pam-check
#!/usr/bin/env python3
import os
import time
from pathlib import Path

TOKEN = Path("/run/pcgdm-biounlock/verified")
TARGET_USER = "librarianist"
MAX_AGE_SEC = 15.0

if os.environ.get("PAM_USER") != TARGET_USER or not TOKEN.exists():
    raise SystemExit(1)

try:
    raw = TOKEN.read_text(encoding="utf-8").strip()
    user, ts_str = raw.split(":", 1)
    age = time.time() - float(ts_str)
    TOKEN.unlink(missing_ok=True)
    if user == TARGET_USER and 0.0 <= age <= MAX_AGE_SEC:
        raise SystemExit(0)
except Exception:
    TOKEN.unlink(missing_ok=True)

raise SystemExit(1)
EOF
chmod 0755 /usr/local/bin/pcgdm-pam-check

echo "[3/4] Installing /etc/systemd/system/pcgdm-biounlock.service..."
cat <<'EOF' > /etc/systemd/system/pcgdm-biounlock.service
[Unit]
Description=pcGDM Bio-Unlock System Daemon (LightDM + XFCE)
After=bluetooth.target network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /home/librarianist/pcGDM/bio_unlock.py daemon
Restart=always
RestartSec=3
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now pcgdm-biounlock.service

echo "[4/4] Hooking pam_exec into /etc/pam.d/lightdm (backup at /etc/pam.d/lightdm.bak)..."
if [ ! -f /etc/pam.d/lightdm.bak ]; then
  cp /etc/pam.d/lightdm /etc/pam.d/lightdm.bak
fi

if ! grep -q "pcgdm-pam-check" /etc/pam.d/lightdm; then
  sed -i 's|^@include common-auth|auth      sufficient pam_exec.so quiet /usr/local/bin/pcgdm-pam-check\n@include common-auth|' /etc/pam.d/lightdm
fi

echo "Done! Status:"
systemctl status pcgdm-biounlock.service --no-pager
