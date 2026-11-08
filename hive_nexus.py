#!/usr/bin/env python3
"""
pcGDM Hive Nexus (hive_nexus.py)
Local Mesh Device Coordinator & IoT Whisperer for Linux / MacBook Pro.

Capabilities:
1. Smart TV Integration (TCL ISMART / Google Cast / DIAL REST API):
   - Real-time telemetry: Online status, uptime, Cast build revision, SSDP UDN
   - Remote wake / status checks
2. Android Phone Integration (Galaxy S9+ via KDE Connect):
   - Ring phone (locate in room)
   - Push clipboard to phone
   - Send SMS from PC terminal
   - Share file / URL to phone
   - Ping & battery status
3. Autonomous LAN Radar & Discovery Daemon:
   - Discovers mDNS / ZeroConf / Avahi / GoogleCast / KDE Connect devices
   - Logs device arrivals / departures
   - Desktop notifications & keyboard pulses on new device connections
"""

import argparse
import datetime
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

LOG_FILE = Path.home() / ".local" / "share" / "pcGDM" / "hive_nexus.log"
STATE_FILE = Path.home() / ".local" / "share" / "pcGDM" / "hive_devices.json"

# Hardware defaults detected on your local network
DEFAULT_TV_IP = "10.1.0.144"
DEFAULT_PHONE_NAME = "Galaxy S9+"


def log(msg: str) -> None:
    line = f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def notify(title: str, msg: str, icon: str = "network-wireless") -> None:
    try:
        subprocess.run(
            ["notify-send", "-a", "Hive-Nexus", "-i", icon, "-t", "4000", title, msg],
            check=False,
        )
    except Exception:
        pass


# ==============================================================================
# 1. SMART TV (TCL / GOOGLE CAST / DIAL / REST TELEMETRY)
# ==============================================================================

def get_tv_status(ip: str = DEFAULT_TV_IP) -> dict:
    """Queries Smart TV Cast/DIAL engine on port 8008 for status and uptime."""
    url = f"http://{ip}:8008/setup/eureka_info"
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "pcGDM-Hive/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            uptime_sec = data.get("uptime", 0)
            hours = int(uptime_sec // 3600)
            mins = int((uptime_sec % 3600) // 60)
            return {
                "online": True,
                "name": data.get("name", "Smart TV"),
                "build": data.get("cast_build_revision", "Unknown"),
                "ip": ip,
                "uptime": f"{hours}h {mins}m",
                "ssdp_udn": data.get("ssdp_udn", ""),
                "hotspot_bssid": data.get("hotspot_bssid", ""),
            }
    except Exception:
        # Check raw TCP port 8009 or 8008
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.0)
        res = s.connect_ex((ip, 8008))
        s.close()
        return {
            "online": (res == 0),
            "name": "Smart TV (ISMART)",
            "build": "Unavailable",
            "ip": ip,
            "uptime": "N/A",
            "ssdp_udn": "",
            "hotspot_bssid": "",
        }


# ==============================================================================
# 2. GALAXY S9+ & ANDROID PHONE (KDE CONNECT BRIDGE)
# ==============================================================================

def get_phone_device_id(name_hint: str = DEFAULT_PHONE_NAME) -> str | None:
    """Finds KDE Connect device ID for paired phone."""
    try:
        out = subprocess.check_output(["kdeconnect-cli", "-a", "--id-name-only"], text=True)
        for line in out.splitlines():
            parts = line.strip().split()
            if len(parts) >= 2 and name_hint.lower() in line.lower():
                return parts[0]
        # Fallback to any paired device ID
        if out.strip():
            return out.strip().splitlines()[0].split()[0]
    except Exception:
        pass
    return None


def ring_phone() -> bool:
    dev_id = get_phone_device_id()
    if not dev_id:
        log("[!] No paired phone found online via KDE Connect.")
        notify("Hive-Nexus Error", "Phone not reachable on Wi-Fi")
        return False
    log(f"Ringing phone (Device ID: {dev_id})...")
    notify("Hive-Nexus", "Ringing Galaxy S9+...")
    res = subprocess.run(["kdeconnect-cli", "-d", dev_id, "--ring"], check=False)
    return res.returncode == 0


def push_clipboard_to_phone() -> bool:
    dev_id = get_phone_device_id()
    if not dev_id:
        log("[!] No paired phone found.")
        return False
    log(f"Pushing PC clipboard to phone ({dev_id})...")
    res = subprocess.run(["kdeconnect-cli", "-d", dev_id, "--send-clipboard"], check=False)
    if res.returncode == 0:
        notify("Hive-Nexus", "Pushed clipboard to Galaxy S9+")
    return res.returncode == 0


def share_to_phone(path_or_url: str) -> bool:
    dev_id = get_phone_device_id()
    if not dev_id:
        log("[!] No paired phone found.")
        return False
    log(f"Sharing {path_or_url} to phone ({dev_id})...")
    res = subprocess.run(["kdeconnect-cli", "-d", dev_id, "--share", path_or_url], check=False)
    if res.returncode == 0:
        notify("Hive-Nexus", f"Shared {Path(path_or_url).name} to Galaxy S9+")
    return res.returncode == 0


def send_sms(phone_number: str, message: str) -> bool:
    dev_id = get_phone_device_id()
    if not dev_id:
        log("[!] No paired phone found.")
        return False
    log(f"Sending SMS to {phone_number} via Galaxy S9+...")
    res = subprocess.run(
        ["kdeconnect-cli", "-d", dev_id, "--destination", phone_number, "--send-sms", message],
        check=False,
    )
    if res.returncode == 0:
        notify("Hive-Nexus SMS Sent", f"To: {phone_number}\nMsg: {message[:40]}")
    return res.returncode == 0


# ==============================================================================
# 3. AUTONOMOUS LAN DEVICE DISCOVERY (AVAHI / MDNS SWEEP)
# ==============================================================================

def scan_lan_devices() -> list[dict]:
    """Scans local mDNS airspace using avahi-browse."""
    devices = []
    seen = set()
    try:
        # Resolve all services quickly with timeout
        cmd = ["avahi-browse", "-a", "-t", "-r"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=3.5, check=False)
        for block in res.stdout.split("="):
            lines = block.strip().splitlines()
            if len(lines) >= 3:
                header = lines[0]
                addr = None
                port = None
                hostname = None
                for l in lines[1:]:
                    l = l.strip()
                    if l.startswith("address ="):
                        addr = l.split("[")[1].split("]")[0]
                    elif l.startswith("port ="):
                        port = l.split("[")[1].split("]")[0]
                    elif l.startswith("hostname ="):
                        hostname = l.split("[")[1].split("]")[0]
                if addr and addr not in seen:
                    seen.add(addr)
                    devices.append({
                        "name": header.split()[-1] if header else "Unknown",
                        "ip": addr,
                        "port": port,
                        "hostname": hostname,
                    })
    except Exception:
        pass
    return devices


def run_daemon() -> None:
    """
    Background Daemon (Managed by systemd --user):
    - Polls Smart TV and phone state.
    - Monitors local airspace for newly connecting devices.
    - Logs state cleanly into hive_devices.json.
    """
    log("Starting pcGDM Hive Nexus Mesh Daemon...")

    def sig_handler(_signo, _frame):
        log("Stopping Hive Nexus daemon.")
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    known_ips = set()
    last_sweep = 0.0

    while True:
        try:
            now = time.time()
            tv = get_tv_status()
            phone_id = get_phone_device_id()

            # Record current mesh state
            mesh_data = {
                "timestamp": datetime.datetime.now().isoformat(),
                "tv": tv,
                "phone": {
                    "connected": bool(phone_id),
                    "device_id": phone_id or "Offline",
                    "name": DEFAULT_PHONE_NAME,
                },
            }

            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            STATE_FILE.write_text(json.dumps(mesh_data, indent=2))

            # Periodic mDNS network sweep every 90s
            if (now - last_sweep) >= 90.0:
                devices = scan_lan_devices()
                current_ips = {d["ip"] for d in devices}
                new_ips = current_ips - known_ips
                if known_ips and new_ips:
                    for d in devices:
                        if d["ip"] in new_ips:
                            log(f"Hive Radar: Detected new device {d['hostname'] or d['name']} at {d['ip']}")
                            notify("Hive Radar Detected Device", f"{d['hostname'] or d['name']}\nIP: {d['ip']}")
                known_ips = current_ips
                last_sweep = now

            time.sleep(10)
        except Exception as e:
            time.sleep(15)


def show_status() -> None:
    tv = get_tv_status()
    phone_id = get_phone_device_id()

    print("=== pcGDM Hive Nexus Status ===")
    print(f"  Smart TV (TCL/Cast): {'ONLINE' if tv['online'] else 'STANDBY / OFFLINE'} (IP: {tv['ip']})")
    if tv['online']:
        print(f"    - Friendly Name : {tv['name']}")
        print(f"    - Cast Build    : {tv['build']}")
        print(f"    - TV Uptime     : {tv['uptime']}")
        print(f"    - SSDP UDN      : {tv['ssdp_udn']}")
    print(f"  Phone (Galaxy S9+): {'CONNECTED & REACHABLE' if phone_id else 'OFFLINE / DISCONNECTED'}")
    if phone_id:
        print(f"    - Device ID     : {phone_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Hive Nexus Local Device Coordinator")
    parser.add_argument(
        "command",
        nargs="?",
        default="status",
        choices=["status", "ring-phone", "sync-clip", "share-phone", "send-sms", "tv-status", "scan", "daemon"],
        help="Command to run",
    )
    parser.add_argument("--target", type=str, help="Target file or URL for share-phone, or phone number for send-sms")
    parser.add_argument("--msg", type=str, default="", help="Message text for send-sms")
    args = parser.parse_args()

    if args.command == "status":
        show_status()
    elif args.command == "tv-status":
        tv = get_tv_status()
        print(json.dumps(tv, indent=2))
    elif args.command == "ring-phone":
        ring_phone()
    elif args.command == "sync-clip":
        push_clipboard_to_phone()
    elif args.command == "share-phone":
        if args.target:
            share_to_phone(args.target)
        else:
            print("[!] Specify --target <file_path_or_url>")
    elif args.command == "send-sms":
        if args.target and args.msg:
            send_sms(args.target, args.msg)
        else:
            print("[!] Specify --target <phone_number> and --msg <message_text>")
    elif args.command == "scan":
        print("[*] Sweeping local network for mDNS/ZeroConf devices...")
        devs = scan_lan_devices()
        print(f"[+] Found {len(devs)} active network devices:")
        for d in devs:
            print(f"  - {d['name']} ({d['hostname'] or 'N/A'}) -> {d['ip']}:{d['port']}")
    elif args.command == "daemon":
        run_daemon()


if __name__ == "__main__":
    main()
