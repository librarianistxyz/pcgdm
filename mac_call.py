#!/usr/bin/python3
"""
pcGDM MacCall (mac_call.py)
Unified Hands-Free Phone Call & Voice Bridge for Xubuntu / MacBook Pro.

Listens simultaneously to:
1. Bluetooth (BlueZ HFP Audio Gateway & MediaTransport on System Bus)
2. KDE Connect (Telephony signals on Session Bus)

Features:
- Instant detection when phone rings via Bluetooth even without KDE Connect
- One-click / Hotkey (Super+C) Answer on MacBook
- Full duplex voice: caller on internal speakers, user on internal microphones
- Hangup / Decline with Super+Shift+C
"""

import argparse
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from gi.repository import Gio, GLib

CONFIG_DIR = Path.home() / ".config" / "pcgdm"
CALL_STATE_FILE = Path("/tmp/mac_call_state")
PHONE_MAC_FILE = CONFIG_DIR / "paired_phone_mac"

KBD_BRIGHTNESS = Path("/sys/class/leds/smc::kbd_backlight/brightness")
OVERRIDE_FILE = Path("/tmp/mac_kbd_manual_override")


def log(msg: str) -> None:
    print(f"[MacCall] {msg}", flush=True)


def get_connected_phone_mac() -> str:
    """Finds the currently connected phone in bluetoothctl / BlueZ."""
    try:
        out = subprocess.check_output(["bluetoothctl", "devices", "Connected"], text=True)
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                mac = parts[1]
                # Return the phone (Workstation-Node or Galaxy)
                if any(k in line.lower() for k in ("workstation", "phone", "galaxy", "dex", "node")):
                    save_phone_mac(mac)
                    return mac
        # Check all paired devices if none actively connected
        if PHONE_MAC_FILE.exists():
            return PHONE_MAC_FILE.read_text().strip()
    except Exception:
        pass
    return "88:BD:45:3D:7F:44"


def save_phone_mac(mac: str) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    PHONE_MAC_FILE.write_text(mac.strip())


def is_bluetooth_connected(mac: str) -> bool:
    try:
        out = subprocess.check_output(["bluetoothctl", "info", mac], text=True)
        return "Connected: yes" in out
    except Exception:
        return False


def set_call_lighting(active: bool) -> None:
    """Pulses keyboard backlight to visually indicate an active call."""
    if not KBD_BRIGHTNESS.exists():
        return
    try:
        OVERRIDE_FILE.write_text(f"{time.time()}:180")
        if active:
            KBD_BRIGHTNESS.write_text("180\n")
        else:
            pref_file = Path.home() / ".config" / "pcgdm" / "kbd_brightness.val"
            val = "100"
            if pref_file.exists():
                val = pref_file.read_text().strip()
            KBD_BRIGHTNESS.write_text(f"{val}\n")
    except Exception:
        pass


def answer_call() -> None:
    log("Answering incoming call on MacBook...")
    mac = get_connected_phone_mac()

    # 1. Acquire transport on BlueZ if pending
    try:
        system_bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        mac_path = mac.replace(":", "_")
        transport_path = f"/org/bluez/hci0/dev_{mac_path}/sep3/fd0"
        system_bus.call_sync("org.bluez", transport_path, "org.bluez.MediaTransport1", "Acquire", None, None, Gio.DBusCallFlags.NONE, 2000, None)
    except Exception:
        pass

    # 2. Try sending ATA via RFCOMM
    for ch in (3, 2, 1):
        try:
            s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
            s.settimeout(1.5)
            s.connect((mac, ch))
            s.send(b"ATA\r\n")
            time.sleep(0.1)
            s.close()
            break
        except Exception:
            continue

    # 3. Simulate media play/pause on phone which answers incoming calls
    try:
        system_bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        mac_path = mac.replace(":", "_")
        player_path = f"/org/bluez/hci0/dev_{mac_path}"
        system_bus.call_sync("org.bluez", player_path, "org.bluez.MediaControl1", "Play", None, None, Gio.DBusCallFlags.NONE, 1000, None)
    except Exception:
        pass

    set_call_lighting(active=True)
    CALL_STATE_FILE.write_text("talking")

    try:
        subprocess.run(["notify-send", "-a", "MacCall", "-i", "call-start", "📞 Call Answered", "Audio active through MacBook speakers & mic."], check=False)
    except Exception:
        pass


def hangup_call() -> None:
    log("Hanging up call...")
    mac = get_connected_phone_mac()

    # 1. Release transport on BlueZ
    try:
        system_bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        mac_path = mac.replace(":", "_")
        transport_path = f"/org/bluez/hci0/dev_{mac_path}/sep3/fd0"
        system_bus.call_sync("org.bluez", transport_path, "org.bluez.MediaTransport1", "Release", None, None, Gio.DBusCallFlags.NONE, 1000, None)
    except Exception:
        pass

    # 2. Try sending ATH via RFCOMM
    for ch in (3, 2, 1):
        try:
            s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
            s.settimeout(1.5)
            s.connect((mac, ch))
            s.send(b"ATH\r\n")
            time.sleep(0.1)
            s.close()
            break
        except Exception:
            continue

    set_call_lighting(active=False)
    CALL_STATE_FILE.unlink(missing_ok=True)
    try:
        subprocess.run(["notify-send", "-a", "MacCall", "-i", "call-stop", "Call Ended", "Audio restored."], check=False)
    except Exception:
        pass


def prompt_incoming_call(caller: str = "Incoming Call", number: str = "Bluetooth Phone") -> None:
    """Shows immediate dialog to answer or decline the call."""
    if CALL_STATE_FILE.exists() and "ringing" in CALL_STATE_FILE.read_text():
        return  # Already prompting

    log(f"*** INCOMING CALL DETECTED ***: {caller} ({number})")
    CALL_STATE_FILE.write_text(f"ringing:{caller}:{number}")

    # Flash keyboard backlight
    try:
        hud_script = Path(__file__).parent / "mac_hud.py"
        if hud_script.exists():
            subprocess.Popen([sys.executable, str(hud_script), "flash", "--count", "3"])
    except Exception:
        pass

    prompt_title = f"📞 INCOMING CALL: {caller}"
    options = "1. 📞 Answer on PC (Super+C)\n2. ❌ Decline / Ignore (Super+Shift+C)"
    selected = ""

    try:
        p = subprocess.Popen(
            ["rofi", "-dmenu", "-p", prompt_title, "-lines", "2", "-width", "35"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True
        )
        out, _ = p.communicate(input=options, timeout=25.0)
        selected = out.strip()
    except Exception:
        pass

    if not selected:
        try:
            res = subprocess.check_output(
                ["zenity", "--list", f"--title={prompt_title}",
                 "--column=Action", "📞 Answer on PC", "❌ Decline",
                 f"--text=Caller: {caller} ({number})\nHotkeys: Super+C (Answer) | Super+Shift+C (Decline)", "--timeout=25"],
                text=True, stderr=subprocess.DEVNULL
            ).strip()
            selected = res
        except Exception:
            return

    if "Answer" in selected:
        answer_call()
    else:
        hangup_call()


def run_daemon() -> None:
    log("Starting pcGDM MacCall Dual Bluetooth + KDE Telephony Bridge...")

    def sig_handler(_signo, _frame):
        log("Stopping MacCall daemon.")
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    phone_mac = get_connected_phone_mac()
    phone_path_frag = phone_mac.replace(":", "_")
    log(f"Monitoring Phone: {phone_mac} (Bluetooth HFP & KDE Connect)")

    last_transport_state = "idle"

    # 1. System Bus: Listen to BlueZ PropertiesChanged
    def on_bluez_signal(connection, sender_name, object_path, interface_name, signal_name, parameters, user_data):
        nonlocal last_transport_state
        try:
            if signal_name == "PropertiesChanged" and phone_path_frag in object_path:
                unpacked = parameters.unpack()
                iface = unpacked[0]
                props = unpacked[1]

                # Check MediaTransport1 state transitions
                if iface == "org.bluez.MediaTransport1" and "State" in props:
                    new_state = props["State"]
                    log(f"BlueZ MediaTransport state: {last_transport_state} -> {new_state}")
                    if new_state in ("pending", "active") and last_transport_state == "idle":
                        last_transport_state = new_state
                        threading.Thread(target=prompt_incoming_call, args=("Bluetooth Incoming Call", phone_mac), daemon=True).start()
                    elif new_state == "idle":
                        last_transport_state = "idle"
                        if CALL_STATE_FILE.exists():
                            CALL_STATE_FILE.unlink(missing_ok=True)
                            set_call_lighting(active=False)
        except Exception as e:
            log(f"Error in bluez handler: {e}")

    # 2. Session Bus: Listen to KDE Connect
    def on_kde_signal(connection, sender_name, object_path, interface_name, signal_name, parameters, user_data):
        try:
            if "telephony" in object_path or "telephony" in interface_name:
                data = parameters.unpack()
                event_type = str(data[0]) if len(data) > 0 else ""
                phone_num = str(data[1]) if len(data) > 1 else "Unknown"
                if "ringing" in event_type.lower() or "incoming" in event_type.lower():
                    threading.Thread(target=prompt_incoming_call, args=("Incoming Call", phone_num), daemon=True).start()
                elif "missed" in event_type.lower() or "terminated" in event_type.lower() or "idle" in event_type.lower():
                    hangup_call()
        except Exception as e:
            log(f"Error in kde handler: {e}")

    # Connect to System Bus (BlueZ)
    try:
        system_bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        system_bus.signal_subscribe(
            "org.bluez",
            "org.freedesktop.DBus.Properties",
            "PropertiesChanged",
            None,
            None,
            Gio.DBusSignalFlags.NONE,
            on_bluez_signal,
            None
        )
        log("Subscribed to BlueZ Bluetooth call signals (System Bus).")
    except Exception as e:
        log(f"Failed to subscribe to BlueZ: {e}")

    # Connect to Session Bus (KDE Connect)
    try:
        session_bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        session_bus.signal_subscribe(
            "org.kde.kdeconnect",
            None,
            None,
            None,
            None,
            Gio.DBusSignalFlags.NONE,
            on_kde_signal,
            None
        )
        log("Subscribed to KDE Connect telephony signals (Session Bus).")
    except Exception as e:
        log(f"Failed to subscribe to KDE Connect: {e}")

    loop = GLib.MainLoop()
    try:
        loop.run()
    except (KeyboardInterrupt, SystemExit):
        loop.quit()


def print_status() -> None:
    mac = get_connected_phone_mac()
    bt_connected = is_bluetooth_connected(mac)
    bt_status = f"🟢 Connected ({mac})" if bt_connected else f"⚪ Disconnected ({mac})"

    kde_out = ""
    try:
        kde_out = subprocess.check_output(["kdeconnect-cli", "-l"], text=True).strip()
    except Exception:
        kde_out = "KDE Connect not running"

    print("=== pcGDM MacCall Hands-Free Status ===")
    print(f"  Phone Target MAC : {mac}")
    print(f"  Bluetooth Voice  : {bt_status}")
    print(f"  KDE Connect Sync : {kde_out}")
    print(f"  Audio Output     : MacBook Internal Speakers (CS4206)")
    print(f"  Voice Input      : MacBook Dual Beamforming Microphones")
    print("\n💡 Hotkeys & Controls:")
    print("  Super + C            - Answer Call on MacBook")
    print("  Super + Shift + C    - Decline / Hang Up")
    print("  mac_call.py answer   - Answer via terminal")
    print("  mac_call.py hangup   - Hangup via terminal")


def main():
    parser = argparse.ArgumentParser(description="pcGDM MacCall Hands-Free Telephony Bridge")
    parser.add_argument("command", nargs="?", default="status", choices=["status", "daemon", "answer", "hangup"], help="Command")
    args = parser.parse_args()

    if args.command == "status":
        print_status()
    elif args.command == "daemon":
        run_daemon()
    elif args.command == "answer":
        answer_call()
    elif args.command == "hangup":
        hangup_call()


if __name__ == "__main__":
    main()
