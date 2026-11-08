#!/usr/bin/env python3
"""
=============================================================================
  GodMode TeleKey - Physical Hardware USB Telegram Remote Bridge
  PC-GDM (MacBook Pro 2012 / Xubuntu Linux)
=============================================================================
Architecture:
  - Continuously monitors USB bus for authorized hardware serial/device ID.
  - When the specific 16GB USB drive is physically inserted:
      1. Pulses MacBook keyboard backlight (MacHUD)
      2. Gathers instant host telemetry (IP, CPU, RAM, Battery, Thermals)
      3. Sends online notification to your authorized Telegram Bot
      4. Starts secure Long-Polling command bridge
  - When the USB drive is unplugged:
      1. Instantly sends parting lockdown alert
      2. Terminates polling bridge and locks all command execution
=============================================================================
"""

import os
import sys
import time
import json
import socket
import subprocess
import threading
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Optional, Dict, Any, List

# Configuration paths
CONFIG_DIR = Path.home() / ".config" / "pcGDM"
CONFIG_FILE = CONFIG_DIR / "tele_config.json"
STATE_DIR = Path.home() / ".local" / "share" / "pcGDM"
SCREENSHOT_TMP = Path("/tmp/tele_screen.png")

# Hardware defaults (Detected from your 16GB Bootable Flash Drive)
DEFAULT_TARGET_SERIAL = "0377291581335169734"
DEFAULT_DISK_BY_ID = "/dev/disk/by-id/usb-Generic_Flash_Disk_0377291581335169734-0:0"

KEYBOARD_MARKUP = {
    "keyboard": [
        [{"text": "📊 Status"}, {"text": "📸 Screenshot"}],
        [{"text": "🔒 Lock Screen"}, {"text": "🔔 Ring Phone"}],
        [{"text": "📋 Clipboard"}, {"text": "❄️ Turbo Cryo"}],
        [{"text": "⏏️ Eject USB"}, {"text": "❓ Help"}]
    ],
    "resize_keyboard": True,
    "persistent": True
}


def load_config() -> Dict[str, Any]:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    # Default template
    default_cfg = {
        "bot_token": "",
        "chat_id": "",
        "target_serial": DEFAULT_TARGET_SERIAL,
        "target_disk_id": DEFAULT_DISK_BY_ID,
        "device_alias": socket.gethostname()
    }
    save_config(default_cfg)
    return default_cfg


def save_config(cfg: Dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def is_usb_present(cfg: Dict[str, Any]) -> bool:
    target_disk = cfg.get("target_disk_id", DEFAULT_DISK_BY_ID)
    if os.path.exists(target_disk):
        return True
    
    # Secondary check: search /dev/disk/by-id for the serial
    target_serial = cfg.get("target_serial", DEFAULT_TARGET_SERIAL)
    by_id_dir = Path("/dev/disk/by-id")
    if by_id_dir.exists():
        for item in by_id_dir.iterdir():
            if target_serial in item.name:
                return True
    return False


def get_system_telemetry() -> Dict[str, str]:
    # Hostname
    hostname = socket.gethostname()
    
    # Local IP
    ip = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass

    # Battery
    battery_pct = "AC"
    bat_file = Path("/sys/class/power_supply/BAT0/capacity")
    status_file = Path("/sys/class/power_supply/BAT0/status")
    if bat_file.exists():
        try:
            cap = bat_file.read_text().strip()
            stat = status_file.read_text().strip() if status_file.exists() else ""
            battery_pct = f"{cap}% ({stat})"
        except Exception:
            pass

    # CPU Temperature
    cpu_temp = "N/A"
    temp_file = Path("/sys/devices/platform/coretemp.0/hwmon/hwmon2/temp1_input")
    if not temp_file.exists():
        # Fallback search
        for hwmon in Path("/sys/class/hwmon").glob("hwmon*"):
            t = hwmon / "temp1_input"
            if t.exists():
                temp_file = t
                break
    if temp_file.exists():
        try:
            milli = int(temp_file.read_text().strip())
            cpu_temp = f"{milli // 1000}°C"
        except Exception:
            pass

    # RAM
    ram_str = "N/A"
    try:
        with open("/proc/meminfo", "r") as f:
            lines = f.readlines()
        mem = {}
        for line in lines:
            parts = line.split(":")
            if len(parts) == 2:
                mem[parts[0].strip()] = parts[1].strip()
        total_kb = int(mem.get("MemTotal", "0 kB").split()[0])
        avail_kb = int(mem.get("MemAvailable", "0 kB").split()[0])
        used_mb = (total_kb - avail_kb) // 1024
        total_mb = total_kb // 1024
        pct = int((used_mb / total_mb) * 100) if total_mb else 0
        ram_str = f"{used_mb}MB / {total_mb}MB ({pct}%)"
    except Exception:
        pass

    # Uptime
    uptime_str = "N/A"
    try:
        with open("/proc/uptime", "r") as f:
            up_secs = float(f.readline().split()[0])
            hours = int(up_secs // 3600)
            minutes = int((up_secs % 3600) // 60)
            uptime_str = f"{hours}h {minutes}m"
    except Exception:
        pass

    return {
        "hostname": hostname,
        "ip": ip,
        "battery": battery_pct,
        "temp": cpu_temp,
        "ram": ram_str,
        "uptime": uptime_str
    }


def flash_keyboard(pulses: int = 2) -> None:
    try:
        hud_script = Path(__file__).parent / "mac_hud.py"
        if hud_script.exists():
            subprocess.run([sys.executable, str(hud_script), "flash", "--count", str(pulses)], timeout=2)
    except Exception:
        pass


class TelegramBotBridge:
    def __init__(self, token: str, chat_id: str, alias: str):
        self.token = token.strip()
        self.chat_id = str(chat_id).strip()
        self.alias = alias
        self.api_url = f"https://api.telegram.org/bot{self.token}"
        self.running = False
        self.last_update_id = 0
        self.worker_thread: Optional[threading.Thread] = None
        self.clear_webhook()
        self.register_commands()

    def clear_webhook(self) -> None:
        try:
            url = f"{self.api_url}/deleteWebhook?drop_pending_updates=False"
            req = urllib.request.Request(url)
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass

    def register_commands(self) -> None:
        commands = [
            {"command": "status", "description": "📊 Live CPU, RAM, Battery & Temps"},
            {"command": "screenshot", "description": "📸 Snap MacBook Desktop Photo"},
            {"command": "lock", "description": "🔒 Lock Laptop Session"},
            {"command": "clip", "description": "📋 Get Laptop Clipboard Text"},
            {"command": "ring", "description": "🔔 Ring Galaxy S9+ Phone"},
            {"command": "cryo", "description": "❄️ Set Turbo/Stealth Power"},
            {"command": "eject", "description": "⏏️ Safely Flush & Unmount USB"},
            {"command": "cmd", "description": "⚙️ Run Shell Command"},
            {"command": "help", "description": "⚡ Show Command Matrix"}
        ]
        url = f"{self.api_url}/setMyCommands"
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps({"commands": commands}).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass

    def send_message(self, text: str, parse_mode: str = "Markdown", with_keyboard: bool = True) -> bool:
        if not self.token or not self.chat_id:
            return False
        url = f"{self.api_url}/sendMessage"
        payload: Dict[str, Any] = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode
        }
        if with_keyboard:
            payload["reply_markup"] = KEYBOARD_MARKUP
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except Exception as e:
            print(f"[TeleKey] send_message error: {e}", file=sys.stderr)
            return False

    def send_photo(self, photo_path: Path, caption: str = "") -> bool:
        if not self.token or not self.chat_id or not photo_path.exists():
            return False
        url = f"{self.api_url}/sendPhoto"
        boundary = f"----WebKitFormBoundary{int(time.time()*1000)}"
        body = []

        # chat_id field
        body.append(f"--{boundary}".encode("utf-8"))
        body.append(f'Content-Disposition: form-data; name="chat_id"'.encode("utf-8"))
        body.append(b"")
        body.append(str(self.chat_id).encode("utf-8"))

        # caption field
        if caption:
            body.append(f"--{boundary}".encode("utf-8"))
            body.append(f'Content-Disposition: form-data; name="caption"'.encode("utf-8"))
            body.append(b"")
            body.append(caption.encode("utf-8"))

        # photo file
        body.append(f"--{boundary}".encode("utf-8"))
        body.append(f'Content-Disposition: form-data; name="photo"; filename="{photo_path.name}"'.encode("utf-8"))
        body.append(b"Content-Type: image/png")
        body.append(b"")
        body.append(photo_path.read_bytes())
        body.append(f"--{boundary}--".encode("utf-8"))
        body.append(b"")

        payload = b"\r\n".join(body)
        try:
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
            )
            with urllib.request.urlopen(req, timeout=25) as resp:
                return resp.status == 200
        except Exception as e:
            print(f"[TeleKey] send_photo error: {e}", file=sys.stderr)
            return False

    def get_updates(self, offset: int = 0, timeout: int = 15) -> List[Dict[str, Any]]:
        url = f"{self.api_url}/getUpdates?offset={offset}&timeout={timeout}"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=timeout + 5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("ok"):
                    return data.get("result", [])
        except Exception:
            pass
        return []

    def handle_command(self, cmd_text: str) -> None:
        cmd_text = cmd_text.strip()
        if not cmd_text:
            return

        lower = cmd_text.lower()
        if "status" in lower:
            cmd = "/status"
            args = []
        elif "screenshot" in lower or "photo" in lower:
            cmd = "/screenshot"
            args = []
        elif "lock" in lower:
            cmd = "/lock"
            args = []
        elif "ring" in lower:
            cmd = "/ring"
            args = []
        elif "clip" in lower:
            cmd = "/clip"
            args = []
        elif "turbo" in lower:
            cmd = "/cryo"
            args = ["turbo"]
        elif "stealth" in lower:
            cmd = "/cryo"
            args = ["stealth"]
        elif "eject" in lower:
            cmd = "/eject"
            args = []
        elif "help" in lower or "start" in lower:
            cmd = "/help"
            args = []
        else:
            parts = cmd_text.split()
            cmd = parts[0].lower()
            args = parts[1:]

        if cmd in ("/start", "/help"):
            msg = (
                f"⚡ *GodMode TeleKey Control Matrix*\n"
                f"Host: `{self.alias}`\n\n"
                f"• `/status` - Live CPU, RAM, Battery & Thermals\n"
                f"• `/screenshot` - Instant Desktop Photo\n"
                f"• `/lock` - Lock XFCE Screen Session\n"
                f"• `/ring` - Ring Galaxy S9+ (Hive Nexus)\n"
                f"• `/clip` - Get current PC clipboard text\n"
                f"• `/eject` - Flush disk caches & safe unmount USB\n"
                f"• `/cmd <bash>` - Run arbitrary terminal command\n"
                f"• `/cryo <turbo|stealth>` - Switch power profile\n"
            )
            self.send_message(msg)

        elif cmd == "/status":
            t = get_system_telemetry()
            msg = (
                f"📊 *Host Status Report*\n"
                f"• Host: `{t['hostname']}`\n"
                f"• IP: `{t['ip']}`\n"
                f"• Battery: `{t['battery']}`\n"
                f"• Temp: `{t['temp']}`\n"
                f"• RAM: `{t['ram']}`\n"
                f"• Uptime: `{t['uptime']}`\n"
            )
            self.send_message(msg)

        elif cmd == "/screenshot":
            self.send_message("📸 Capturing desktop...")
            try:
                # Set DISPLAY environment for cron/systemd compatibility
                env = os.environ.copy()
                if "DISPLAY" not in env:
                    env["DISPLAY"] = ":0"
                if "XAUTHORITY" not in env:
                    env["XAUTHORITY"] = str(Path.home() / ".Xauthority")

                if SCREENSHOT_TMP.exists():
                    SCREENSHOT_TMP.unlink()

                # Attempt scrot first
                res = subprocess.run(["scrot", "-z", str(SCREENSHOT_TMP)], env=env, timeout=5)
                if not SCREENSHOT_TMP.exists() or res.returncode != 0:
                    # Fallback to xfce4-screenshooter
                    subprocess.run(["xfce4-screenshooter", "-f", "-s", str(SCREENSHOT_TMP)], env=env, timeout=5)

                if SCREENSHOT_TMP.exists():
                    t = get_system_telemetry()
                    caption = f"🖥️ Desktop Capture | {t['hostname']} | {time.strftime('%H:%M:%S')}"
                    self.send_photo(SCREENSHOT_TMP, caption=caption)
                    SCREENSHOT_TMP.unlink(missing_ok=True)
                else:
                    self.send_message("❌ Failed to capture screenshot (display session not available).")
            except Exception as e:
                self.send_message(f"❌ Screenshot error: {e}")

        elif cmd == "/lock":
            try:
                env = os.environ.copy()
                if "DISPLAY" not in env:
                    env["DISPLAY"] = ":0"
                subprocess.Popen(["xflock4"], env=env)
                self.send_message("🔒 Session locked.")
            except Exception as e:
                self.send_message(f"❌ Failed to lock: {e}")

        elif cmd == "/ring":
            try:
                godmode = Path(__file__).parent / "godmode.sh"
                subprocess.run([str(godmode), "ring"], timeout=5)
                self.send_message("🔔 Ring signal sent to Galaxy S9+.")
            except Exception as e:
                self.send_message(f"❌ Ring error: {e}")

        elif cmd == "/clip":
            try:
                env = os.environ.copy()
                if "DISPLAY" not in env:
                    env["DISPLAY"] = ":0"
                clip = subprocess.check_output(["xclip", "-selection", "clipboard", "-o"], env=env, timeout=2).decode("utf-8", errors="replace")
                if clip:
                    self.send_message(f"📋 *Clipboard Contents:*\n```\n{clip[:1000]}\n```")
                else:
                    self.send_message("📋 Clipboard is empty.")
            except Exception as e:
                self.send_message(f"❌ Clipboard error: {e}")

        elif cmd == "/cryo":
            mode = args[0] if args else "auto"
            try:
                godmode = Path(__file__).parent / "godmode.sh"
                subprocess.run([str(godmode), mode], timeout=5)
                self.send_message(f"❄️ Cryo governor set to: *{mode}*")
            except Exception as e:
                self.send_message(f"❌ Cryo error: {e}")

        elif cmd == "/eject":
            self.send_message("⏳ Flushing disk cache and safely unmounting USB...")
            try:
                subprocess.run(["sync"], timeout=5)
                unmounted = []
                cfg = load_config()
                target_serial = cfg.get("target_serial", DEFAULT_TARGET_SERIAL)
                with open("/proc/mounts", "r") as f:
                    for line in f:
                        parts = line.split()
                        if len(parts) >= 2 and parts[0].startswith("/dev/sd"):
                            dev = parts[0]
                            mp = parts[1].replace("\\040", " ")
                            try:
                                udev_out = subprocess.check_output(
                                    ["udevadm", "info", "-q", "property", "-n", dev],
                                    text=True,
                                    stderr=subprocess.DEVNULL
                                )
                                if target_serial in udev_out:
                                    subprocess.run(["udisksctl", "unmount", "-b", dev, "--no-user-interaction"], capture_output=True, timeout=5)
                                    unmounted.append(mp)
                            except Exception:
                                pass
                flash_keyboard(3)
                details = f"Unmounted: `{', '.join(unmounted)}`" if unmounted else "Partitions already unmounted."
                self.send_message(
                    f"✅ *USB SAFELY UNMOUNTED*\n"
                    f"Host: `{self.alias}`\n"
                    f"All disk buffers flushed (`sync`).\n"
                    f"{details}\n\n"
                    f"👉 **You can pull the drive out now!**"
                )
            except Exception as e:
                self.send_message(f"❌ Eject error: {e}")

        elif cmd == "/cmd":
            if not args:
                self.send_message("Usage: `/cmd <bash command>`")
                return
            command = " ".join(args)
            try:
                proc = subprocess.run(
                    command,
                    shell=True,
                    executable="/bin/bash",
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=15
                )
                output = proc.stdout.strip()
                if not output:
                    output = "[Command executed successfully with no output]"
                if len(output) > 3500:
                    output = output[:3500] + "\n...[Output Truncated]"
                self.send_message(f"⚙️ *Output (`{command[:60]}`):*\n```\n{output}\n```")
            except subprocess.TimeoutExpired:
                self.send_message("⏱️ Command timed out after 15 seconds.")
            except Exception as e:
                self.send_message(f"❌ Execution error: {e}")

        else:
            self.send_message(f"❓ Unknown command: `{cmd}`. Type `/help` for options.")

    def run_polling(self) -> None:
        self.running = True
        print(f"[TeleKey] Bot polling activated for Chat ID: {self.chat_id}")
        
        # Flush existing backlog so we don't execute old commands
        updates = self.get_updates(offset=0, timeout=1)
        if updates:
            self.last_update_id = updates[-1]["update_id"] + 1

        while self.running:
            try:
                updates = self.get_updates(offset=self.last_update_id, timeout=10)
                for update in updates:
                    self.last_update_id = update["update_id"] + 1
                    msg = update.get("message")
                    if not msg:
                        continue
                    
                    sender_id = str(msg.get("from", {}).get("id", ""))
                    chat_id = str(msg.get("chat", {}).get("id", ""))
                    text = msg.get("text", "")

                    # Strict sender authentication check
                    if sender_id != self.chat_id and chat_id != self.chat_id:
                        print(f"[TeleKey] Blocked unauthorized message from ID: {sender_id}")
                        continue

                    if text:
                        self.handle_command(text)
            except Exception as e:
                time.sleep(2)

    def start(self) -> None:
        if self.running:
            return
        self.worker_thread = threading.Thread(target=self.run_polling, daemon=True)
        self.worker_thread.start()

    def stop(self) -> None:
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=2)


def main():
    print("[TeleKey] Initializing Hardware USB Telegram Key Daemon...")
    cfg = load_config()

    bot_bridge: Optional[TelegramBotBridge] = None
    was_plugged = False

    while True:
        try:
            cfg = load_config()
            currently_plugged = is_usb_present(cfg)

            if currently_plugged and not was_plugged:
                print(f"[TeleKey] 🔑 Hardware Key Detected: {cfg.get('target_serial')}")
                flash_keyboard(2)

                token = cfg.get("bot_token", "").strip()
                chat_id = str(cfg.get("chat_id", "")).strip()

                if not token or not chat_id:
                    print("[TeleKey] ⚠️ Token or Chat ID not configured. Run: ./godmode.sh tele-config <token> <chat_id>")
                else:
                    bot_bridge = TelegramBotBridge(token, chat_id, cfg.get("device_alias", "MacBookPro"))
                    telemetry = get_system_telemetry()
                    welcome_msg = (
                        f"🔑 *HARDWARE KEY ATTACHED*\n"
                        f"• Host: `{telemetry['hostname']}`\n"
                        f"• Local IP: `{telemetry['ip']}`\n"
                        f"• Battery: `{telemetry['battery']}`\n"
                        f"• CPU Temp: `{telemetry['temp']}`\n"
                        f"• RAM: `{telemetry['ram']}`\n"
                        f"• Uptime: `{telemetry['uptime']}`\n\n"
                        f"⚡ *Remote Terminal Bridge: READY*\n"
                        f"Type `/help` to view available commands."
                    )
                    bot_bridge.send_message(welcome_msg)
                    bot_bridge.start()

                was_plugged = True

            elif not currently_plugged and was_plugged:
                print("[TeleKey] 🔒 Hardware Key Removed! Deactivating bridge...")
                flash_keyboard(1)
                if bot_bridge:
                    bot_bridge.send_message("🔒 *HARDWARE KEY REMOVED*\nRemote terminal bridge deactivated.")
                    bot_bridge.stop()
                    bot_bridge = None
                was_plugged = False

            time.sleep(1)
        except KeyboardInterrupt:
            print("\n[TeleKey] Terminating...")
            if bot_bridge:
                bot_bridge.stop()
            break
        except Exception as e:
            print(f"[TeleKey] Daemon loop error: {e}", file=sys.stderr)
            time.sleep(2)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == "config" and len(sys.argv) >= 4:
            cfg = load_config()
            cfg["bot_token"] = sys.argv[2].strip()
            cfg["chat_id"] = sys.argv[3].strip()
            save_config(cfg)
            print(f"✅ TeleKey configuration saved successfully.")
            print(f"Target Serial: {cfg['target_serial']}")
            print(f"Chat ID: {cfg['chat_id']}")
            sys.exit(0)
        elif cmd == "status":
            cfg = load_config()
            plugged = is_usb_present(cfg)
            print(f"USB Key Plugged In: {'YES ✅' if plugged else 'NO ❌'}")
            print(f"Target Serial: {cfg.get('target_serial')}")
            print(f"Bot Configured: {'YES' if cfg.get('bot_token') else 'NO (Run config)'}")
            sys.exit(0)
    main()
