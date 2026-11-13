#!/usr/bin/env python3
"""
pcGDM Bio-Unlock (bio_unlock.py)
Offline PC unlocker listening simultaneously on:
  1. TCP 0.0.0.0:29422 (Local Wi-Fi, Phone Hotspot, Tailscale, or USB adb reverse)
  2. UDP 0.0.0.0:29423 (LAN/Hotspot auto-discovery)
  3. Bluetooth RFCOMM channel 22 (fallback)

Supports both user mode and root system mode (for LightDM pam_exec + xfce4-screensaver).
"""

import argparse
import datetime
import hashlib
import hmac
import os
import secrets
import shutil
import signal
import socket
import subprocess
import threading
import time
from pathlib import Path

TARGET_USER = "librarianist"
USER_HOME = Path("/home/librarianist")
TCP_PORT = 29422
UDP_DISCOVERY_PORT = 29423
RFCOMM_CHANNEL = 22
CHALLENGE_TIMEOUT_SEC = 30
STATE_DIR = USER_HOME / ".local" / "share" / "pcGDM"
KEY_FILE = STATE_DIR / "bio_unlock.key"
LOG_FILE = STATE_DIR / "bio_unlock.log"
PAM_TOKEN_DIR = Path("/run/pcgdm-biounlock")
PAM_TOKEN_FILE = PAM_TOKEN_DIR / "verified"


def log(msg: str) -> None:
    line = f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load_or_create_key() -> bytes:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if KEY_FILE.exists():
        raw = KEY_FILE.read_text(encoding="utf-8").strip()
        if len(raw) == 64:
            return bytes.fromhex(raw)
    secret = secrets.token_bytes(32)
    KEY_FILE.write_text(secret.hex(), encoding="utf-8")
    os.chmod(KEY_FILE, 0o600)
    log(f"Generated new shared secret at {KEY_FILE}")
    return secret


def write_pam_token() -> None:
    if os.geteuid() != 0:
        return
    try:
        PAM_TOKEN_DIR.mkdir(parents=True, exist_ok=True)
        os.chmod(PAM_TOKEN_DIR, 0o700)
        PAM_TOKEN_FILE.write_text(f"{TARGET_USER}:{time.time():.3f}\n", encoding="utf-8")
        os.chmod(PAM_TOKEN_FILE, 0o600)
    except Exception as exc:
        log(f"Failed to write PAM token: {exc}")


def unlock_session() -> None:
    write_pam_token()
    subprocess.run(["loginctl", "unlock-sessions"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    if os.geteuid() == 0:
        uid = subprocess.run(["id", "-u", TARGET_USER], stdout=subprocess.PIPE, text=True).stdout.strip()
        env_args = [
            "runuser", "-u", TARGET_USER, "--",
            "env", "DISPLAY=:0", f"XAUTHORITY={USER_HOME / '.Xauthority'}",
            f"DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{uid}/bus",
        ]
        if shutil.which("xfce4-screensaver-command"):
            subprocess.run(env_args + ["xfce4-screensaver-command", "-d"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if shutil.which("notify-send"):
            subprocess.run(
                env_args + ["notify-send", "-t", "2000", "Bio-Unlock", "Unlocked via Galaxy S9+ fingerprint"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
    else:
        if shutil.which("xfce4-screensaver-command"):
            subprocess.run(["xfce4-screensaver-command", "-d"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if shutil.which("light-locker-command"):
            subprocess.run(["light-locker-command", "-d"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if shutil.which("notify-send"):
            subprocess.run(
                ["notify-send", "-t", "2000", "Bio-Unlock", "Unlocked via Galaxy S9+ fingerprint"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
    log("Session unlocked via Galaxy S9+ fingerprint.")


def handle_client(conn: socket.socket, peer: str, secret: bytes) -> None:
    log(f"Incoming connection from {peer}")
    try:
        conn.settimeout(CHALLENGE_TIMEOUT_SEC)
        nonce = secrets.token_bytes(32).hex()
        conn.sendall(f"CHALLENGE:{nonce}\n".encode("ascii"))

        buf = b""
        while b"\n" not in buf and len(buf) < 256:
            chunk = conn.recv(128)
            if not chunk:
                break
            buf += chunk

        line = buf.decode("ascii", errors="ignore").strip()
        if not line.startswith("AUTH:"):
            conn.sendall(b"FAIL\n")
            log(f"Rejected {peer}: invalid response")
            return

        received_hex = line[5:].strip().lower()
        expected_hex = hmac.new(secret, nonce.encode("ascii"), hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected_hex, received_hex):
            conn.sendall(b"OK\n")
            unlock_session()
        else:
            conn.sendall(b"FAIL\n")
            log(f"Rejected {peer}: HMAC mismatch")
    except Exception as exc:
        log(f"Client {peer} error: {exc}")
    finally:
        try:
            conn.close()
        except Exception:
            pass


def tcp_listener(secret: bytes, stop_evt: threading.Event) -> None:
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", TCP_PORT))
    srv.listen(8)
    srv.settimeout(1.0)
    log(f"Bio-Unlock TCP listening on 0.0.0.0:{TCP_PORT}")
    try:
        while not stop_evt.is_set():
            try:
                conn, addr = srv.accept()
            except TimeoutError:
                continue
            threading.Thread(target=handle_client, args=(conn, f"tcp:{addr[0]}", secret), daemon=True).start()
    finally:
        srv.close()


def udp_discovery_listener(stop_evt: threading.Event) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.bind(("0.0.0.0", UDP_DISCOVERY_PORT))
    sock.settimeout(1.0)
    log(f"Bio-Unlock UDP discovery listening on 0.0.0.0:{UDP_DISCOVERY_PORT}")
    try:
        while not stop_evt.is_set():
            try:
                data, addr = sock.recvfrom(128)
            except TimeoutError:
                continue
            if data.strip() == b"PCGDM_DISCOVER":
                sock.sendto(f"PCGDM_HERE:{TCP_PORT}".encode("ascii"), addr)
    finally:
        sock.close()


def bt_listener(secret: bytes, stop_evt: threading.Event) -> None:
    try:
        srv = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("00:00:00:00:00:00", RFCOMM_CHANNEL))
        srv.listen(4)
        srv.settimeout(1.0)
        log(f"Bio-Unlock Bluetooth RFCOMM listening on channel {RFCOMM_CHANNEL}")
    except Exception as exc:
        log(f"Bluetooth RFCOMM unavailable: {exc}")
        return

    try:
        while not stop_evt.is_set():
            try:
                conn, addr = srv.accept()
            except TimeoutError:
                continue
            peer = f"bt:{addr[0] if addr else 'unknown'}"
            threading.Thread(target=handle_client, args=(conn, peer, secret), daemon=True).start()
    finally:
        srv.close()


def ensure_bluetooth_ready() -> None:
    if shutil.which("bluetoothctl") is None:
        return
    subprocess.run(["bluetoothctl", "power", "on"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["bluetoothctl", "trust", "88:BD:45:3D:7F:44"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    log("Ensured Bluetooth controller powered ON and S9+ trusted.")


def run_daemon() -> None:
    ensure_bluetooth_ready()
    secret = load_or_create_key()
    stop_evt = threading.Event()

    def stop_handler(_sig, _frame):
        stop_evt.set()

    signal.signal(signal.SIGTERM, stop_handler)
    signal.signal(signal.SIGINT, stop_handler)

    threads = [
        threading.Thread(target=tcp_listener, args=(secret, stop_evt), daemon=True),
        threading.Thread(target=udp_discovery_listener, args=(stop_evt,), daemon=True),
        threading.Thread(target=bt_listener, args=(secret, stop_evt), daemon=True),
    ]
    for t in threads:
        t.start()

    while not stop_evt.is_set():
        stop_evt.wait(1.0)
    for t in threads:
        t.join(timeout=2.0)
    log("Bio-Unlock daemon stopped.")


def main() -> None:
    parser = argparse.ArgumentParser(description="pcGDM Bio-Unlock Daemon")
    parser.add_argument("command", nargs="?", default="daemon", choices=["daemon", "key", "unlock-test"])
    args = parser.parse_args()

    if args.command == "key":
        print(load_or_create_key().hex())
    elif args.command == "unlock-test":
        unlock_session()
    else:
        run_daemon()


if __name__ == "__main__":
    main()
