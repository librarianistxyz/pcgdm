#!/usr/bin/env python3
"""
=============================================================================
  GodMode TeleKey - Physical Hardware USB Telegram Remote Bridge
  Features:
    - Multi-Key Whitelisting (Keyring)
    - One-Tap Telegram Authorization for New USBs (Zero Popups on PC)
    - Instant Hardware Sniffer (<10ms)
    - Remote Safe-Eject via /eject
=============================================================================
"""

import os
import sys
import time
import json
import html
import socket
import shutil
import mimetypes
import traceback
import subprocess
import threading
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Optional, Dict, Any, List, Set, Tuple

# Configuration paths
CONFIG_DIR = Path.home() / ".config" / "pcGDM"
CONFIG_FILE = CONFIG_DIR / "tele_config.json"
STATE_DIR = Path.home() / ".local" / "share" / "pcGDM"
SCREENSHOT_TMP = Path("/tmp/tele_screen.png")
WEBCAM_TMP = Path("/tmp/tele_cam.jpg")
VOICE_TMP = Path("/tmp/tele_mic.ogg")

# Hardware defaults (Detected from your 16GB Bootable Flash Drive)
DEFAULT_TARGET_SERIAL = "0377291581335169734"
DEFAULT_DISK_BY_ID = "/dev/disk/by-id/usb-Generic_Flash_Disk_0377291581335169734-0:0"

KEYBOARD_MARKUP = {
    "keyboard": [
        [{"text": "📊 Status"}, {"text": "📸 Screenshot"}],
        [{"text": "📁 Files"}, {"text": "🔒 Lock Screen"}],
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
                cfg = json.load(f)
                if "authorized_serials" not in cfg:
                    cfg["authorized_serials"] = [cfg.get("target_serial", DEFAULT_TARGET_SERIAL)]
                return cfg
        except Exception:
            pass
    # Default template
    default_cfg = {
        "bot_token": "",
        "chat_id": "",
        "target_serial": DEFAULT_TARGET_SERIAL,
        "authorized_serials": [DEFAULT_TARGET_SERIAL],
        "device_alias": socket.gethostname()
    }
    save_config(default_cfg)
    return default_cfg


def save_config(cfg: Dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def get_connected_usb_devices() -> List[Dict[str, str]]:
    devices = []
    by_id = Path("/dev/disk/by-id")
    if not by_id.exists():
        return devices
    for item in by_id.iterdir():
        if item.name.startswith("usb-"):
            try:
                out = subprocess.check_output(
                    ["udevadm", "info", "-q", "property", "-n", str(item)],
                    text=True,
                    stderr=subprocess.DEVNULL
                )
                props = dict(line.split("=", 1) for line in out.splitlines() if "=" in line)
                serial = props.get("ID_SERIAL_SHORT") or props.get("ID_SERIAL")
                vendor = props.get("ID_VENDOR", "Generic").strip()
                model = props.get("ID_MODEL", "USB Device").strip()
                if serial and not any(d["serial"] == serial for d in devices):
                    devices.append({
                        "serial": serial,
                        "vendor": vendor,
                        "model": model,
                        "path": str(item)
                    })
            except Exception:
                pass
    return devices


def flash_keyboard(pulses: int = 2) -> None:
    try:
        hud_script = Path(__file__).parent / "mac_hud.py"
        if hud_script.exists():
            subprocess.run([sys.executable, str(hud_script), "flash", "--count", str(pulses)], timeout=2)
    except Exception:
        pass


def get_system_telemetry() -> Dict[str, str]:
    hostname = socket.gethostname()
    ip = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass

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

    cpu_temp = "N/A"
    for hwmon in Path("/sys/class/hwmon").glob("hwmon*"):
        t = hwmon / "temp1_input"
        if t.exists():
            try:
                cpu_temp = f"{int(t.read_text().strip()) // 1000}°C"
                break
            except Exception:
                pass

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


class TelegramBotBridge:
    def __init__(self, token: str, chat_id: str, alias: str):
        self.token = token.strip()
        self.chat_id = str(chat_id).strip()
        self.alias = alias
        self.api_url = f"https://api.telegram.org/bot{self.token}"
        self.running = False
        self.last_update_id = 0
        self.worker_thread: Optional[threading.Thread] = None
        self.current_dir: Path = Path.home()
        self.file_cache: Dict[str, Path] = {}
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
            {"command": "files", "description": "📁 Browse Folders & Files"},
            {"command": "screenshot", "description": "📸 Snap MacBook Desktop Photo"},
            {"command": "get", "description": "📥 Download File to Phone (/get <file>)"},
            {"command": "cat", "description": "📄 View Text File (/cat <file>)"},
            {"command": "lock", "description": "🔒 Lock Laptop Session"},
            {"command": "clip", "description": "📋 Get Laptop Clipboard Text"},
            {"command": "ring", "description": "🔔 Ring Galaxy S9+ Phone"},
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

    def send_message(self, text: str, parse_mode: str = "Markdown", reply_markup: Optional[Dict[str, Any]] = None) -> bool:
        if not self.token or not self.chat_id:
            return False
        url = f"{self.api_url}/sendMessage"
        payload: Dict[str, Any] = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        else:
            payload["reply_markup"] = KEYBOARD_MARKUP
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except Exception as e:
            print(f"[TeleKey] send_message error: {e}", file=sys.stderr)
            return False

    def answer_callback(self, callback_id: str, text: str = "") -> None:
        url = f"{self.api_url}/answerCallbackQuery"
        try:
            payload = {"callback_query_id": callback_id, "text": text}
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass

    def send_photo(self, photo_path: Path, caption: str = "") -> bool:
        if not self.token or not self.chat_id or not photo_path.exists():
            return False

        # Prefer curl for streaming reliability
        if shutil.which("curl"):
            cmd = [
                "curl", "-s", "-S",
                "--connect-timeout", "15",
                "--max-time", "90",
                "-F", f"chat_id={self.chat_id}",
                "-F", f"photo=@{str(photo_path)}",
            ]
            if caption:
                cmd.extend(["-F", f"caption={caption}"])
            cmd.append(f"{self.api_url}/sendPhoto")
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=100)
                if res.returncode == 0 and '"ok":true' in res.stdout:
                    return True
                print(f"[TeleKey] curl send_photo failed: {res.stderr or res.stdout}", file=sys.stderr)
            except Exception as e:
                print(f"[TeleKey] curl send_photo error: {e}", file=sys.stderr)

        # Fallback to urllib
        url = f"{self.api_url}/sendPhoto"
        boundary = f"----WebKitFormBoundary{int(time.time()*1000)}"
        body = []
        body.append(f"--{boundary}".encode("utf-8"))
        body.append(f'Content-Disposition: form-data; name="chat_id"'.encode("utf-8"))
        body.append(b"")
        body.append(str(self.chat_id).encode("utf-8"))
        if caption:
            body.append(f"--{boundary}".encode("utf-8"))
            body.append(f'Content-Disposition: form-data; name="caption"'.encode("utf-8"))
            body.append(b"")
            body.append(caption.encode("utf-8"))
        body.append(f"--{boundary}".encode("utf-8"))
        body.append(f'Content-Disposition: form-data; name="photo"; filename="{photo_path.name}"'.encode("utf-8"))
        body.append(b"Content-Type: image/png")
        body.append(b"")
        body.append(photo_path.read_bytes())
        body.append(f"--{boundary}--".encode("utf-8"))
        body.append(b"")

        payload = b"\r\n".join(body)
        try:
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.status == 200
        except Exception as e:
            print(f"[TeleKey] send_photo error: {e}", file=sys.stderr)
            return False

    def send_voice(self, voice_path: Path, caption: str = "") -> bool:
        if not self.token or not self.chat_id or not voice_path.exists():
            return False

        if shutil.which("curl"):
            cmd = [
                "curl", "-s", "-S",
                "--connect-timeout", "15",
                "--max-time", "90",
                "-F", f"chat_id={self.chat_id}",
                "-F", f"voice=@{str(voice_path)}",
            ]
            if caption:
                cmd.extend(["-F", f"caption={caption}"])
            cmd.append(f"{self.api_url}/sendVoice")
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=100)
                if res.returncode == 0 and '"ok":true' in res.stdout:
                    return True
                print(f"[TeleKey] curl send_voice failed: {res.stderr or res.stdout}", file=sys.stderr)
            except Exception as e:
                print(f"[TeleKey] curl send_voice error: {e}", file=sys.stderr)

        return self.send_document(voice_path, caption=caption)

    def send_document(self, file_path: Path, caption: str = "") -> bool:
        if not self.token or not self.chat_id or not file_path.exists():
            return False
        if file_path.is_dir():
            self.send_message(f"❌ <code>{html.escape(file_path.name)}</code> is a directory, not a file.", parse_mode="HTML")
            return False

        file_size = file_path.stat().st_size
        size_mb = file_size / (1024 * 1024)

        # Telegram Bot API hard ceiling: 50MB
        if file_size > 50 * 1024 * 1024:
            t = get_system_telemetry()
            ip = t.get("ip", "localhost")
            self.send_message(
                f"⚠️ <b>{html.escape(file_path.name)}</b> is <b>{size_mb:.1f} MB</b>.\n"
                f"Telegram strictly limits bot uploads to <b>50 MB</b>.\n\n"
                f"🚀 <b>Direct Wi-Fi Download (Full Speed):</b>\n"
                f"Download over your local network via AirDrop-Zero:\n"
                f"👉 <code>http://{ip}:7777</code>",
                parse_mode="HTML"
            )
            return False

        # Pick appropriate icon & caption if none provided
        ext = file_path.suffix.lower()
        if not caption:
            if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"):
                icon = "🖼️"
            elif ext in (".mp4", ".mov", ".mkv", ".avi", ".webm", ".flv"):
                icon = "🎬"
            elif ext in (".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg"):
                icon = "🎵"
            elif ext in (".zip", ".tar", ".gz", ".xz", ".7z", ".bz2", ".rar"):
                icon = "📦"
            elif ext in (".pdf",):
                icon = "📕"
            else:
                icon = "📄"
            caption = f"{icon} {file_path.name} ({size_mb:.1f} MB)"

        # Calculate dynamic timeout: 60s base + 25s per MB (e.g. 10MB => 310s, 40MB => 1060s)
        timeout_sec = max(90, int(60 + size_mb * 25))

        # Prefer curl for streaming uploads: no RAM bloat, native chunks, SSL resilience
        if shutil.which("curl"):
            url = f"{self.api_url}/sendDocument"
            cmd = [
                "curl", "-s", "-S",
                "--connect-timeout", "25",
                "--max-time", str(timeout_sec),
                "-F", f"chat_id={self.chat_id}",
                "-F", f"document=@{str(file_path)}",
            ]
            if caption:
                cmd.extend(["-F", f"caption={caption}"])
            cmd.append(url)
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec + 15)
                if res.returncode == 0 and '"ok":true' in res.stdout:
                    return True
                else:
                    err_output = (res.stderr or res.stdout).strip()
                    print(f"[TeleKey] curl sendDocument failed: {err_output[:200]}", file=sys.stderr)
            except subprocess.TimeoutExpired:
                print(f"[TeleKey] curl sendDocument timed out ({file_path.name})", file=sys.stderr)
            except Exception as e:
                print(f"[TeleKey] curl sendDocument error: {e}", file=sys.stderr)

        # Fallback to urllib if curl is unavailable or failed
        mime_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        url = f"{self.api_url}/sendDocument"
        boundary = f"----WebKitFormBoundary{int(time.time()*1000)}"
        body = []
        body.append(f"--{boundary}".encode("utf-8"))
        body.append(f'Content-Disposition: form-data; name="chat_id"'.encode("utf-8"))
        body.append(b"")
        body.append(str(self.chat_id).encode("utf-8"))
        if caption:
            body.append(f"--{boundary}".encode("utf-8"))
            body.append(f'Content-Disposition: form-data; name="caption"'.encode("utf-8"))
            body.append(b"")
            body.append(caption.encode("utf-8"))
        body.append(f"--{boundary}".encode("utf-8"))
        body.append(f'Content-Disposition: form-data; name="document"; filename="{file_path.name}"'.encode("utf-8"))
        body.append(f"Content-Type: {mime_type}".encode("utf-8"))
        body.append(b"")
        try:
            body.append(file_path.read_bytes())
        except Exception as e:
            print(f"[TeleKey] read_bytes failed: {e}", file=sys.stderr)
            return False
        body.append(f"--{boundary}--".encode("utf-8"))
        body.append(b"")

        payload = b"\r\n".join(body)
        try:
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                return resp.status == 200
        except Exception as e:
            print(f"[TeleKey] urllib send_document error: {e}", file=sys.stderr)
            return False

    def build_dir_view(self, target: Path) -> Tuple[str, Dict[str, Any]]:
        target = target.resolve()
        if not target.exists():
            return f"❌ Path does not exist: <code>{html.escape(str(target))}</code>", {}
        if not target.is_dir():
            return f"❌ Path is not a directory: <code>{html.escape(str(target))}</code>", {}

        dirs = []
        files = []
        try:
            for item in sorted(target.iterdir()):
                if item.name.startswith("."):
                    continue
                if item.is_dir():
                    dirs.append(item.name)
                else:
                    try:
                        sz = item.stat().st_size
                        if sz < 1024:
                            fsize = f"{sz}B"
                        elif sz < 1024 * 1024:
                            fsize = f"{sz // 1024}KB"
                        else:
                            fsize = f"{sz // (1024*1024)}MB"
                        files.append((item, item.name, fsize))
                    except Exception:
                        files.append((item, item.name, "?"))
        except PermissionError:
            return f"❌ Permission denied: <code>{html.escape(str(target))}</code>", {}

        lines = [
            "📁 <b>File Explorer & Downloader</b>",
            f"📍 Location: <code>{html.escape(str(target))}</code>\n"
        ]
        if dirs:
            lines.append(f"<b>Directories ({len(dirs)}):</b>")
            for d in dirs[:10]:
                lines.append(f"  📁 <code>{html.escape(d)}/</code>")
            if len(dirs) > 10:
                lines.append(f"  <i>...and {len(dirs) - 10} more folders</i>")
            lines.append("")

        if files:
            lines.append(f"<b>Files ({len(files)}):</b>")
            for fpath, fname, fsize in files[:12]:
                lines.append(f"  📄 <code>{html.escape(fname)}</code> ({fsize})")
            if len(files) > 12:
                lines.append(f"  <i>...and {len(files) - 12} more files</i>")
            lines.append("")

        if not dirs and not files:
            lines.append("<i>(This folder is empty)</i>\n")

        lines.append("💡 <b>Tap any button below:</b>")
        lines.append("• 📁 Tap a folder to enter")
        lines.append("• 📥 Tap a file to <b>download directly to phone</b>")

        keyboard_rows = []

        # 1. Directory navigation buttons (2 columns)
        if dirs:
            row = []
            for d in dirs[:8]:
                row.append({"text": f"📁 {d[:14]}", "callback_data": f"cd:{d[:25]}"})
                if len(row) == 2:
                    keyboard_rows.append(row)
                    row = []
            if row:
                keyboard_rows.append(row)

        # 2. Clickable File Download buttons! (2 columns for neat fit)
        self.file_cache = {}
        if files:
            row = []
            for idx, (fpath, fname, fsize) in enumerate(files[:8]):
                f_key = f"f{idx}"
                self.file_cache[f_key] = fpath

                ext = fpath.suffix.lower()
                if ext == ".pdf":
                    icon = "📕"
                elif ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"):
                    icon = "🖼️"
                elif ext in (".zip", ".tar", ".gz", ".7z", ".rar", ".iso"):
                    icon = "📦"
                elif ext in (".mp4", ".mkv", ".mov", ".avi"):
                    icon = "🎬"
                elif ext in (".mp3", ".wav", ".flac", ".ogg"):
                    icon = "🎵"
                elif ext in (".doc", ".docx", ".odt", ".txt", ".md", ".json", ".py", ".sh"):
                    icon = "📄"
                else:
                    icon = "💾"

                label = f"{icon} {fname[:13]} ({fsize})"
                row.append({"text": label, "callback_data": f"dl:{f_key}"})
                if len(row) == 2:
                    keyboard_rows.append(row)
                    row = []
            if row:
                keyboard_rows.append(row)

        # 3. Nav row
        nav_row = []
        if target != Path.home():
            nav_row.append({"text": "⬆️ Up", "callback_data": "cd_up"})
            nav_row.append({"text": "🏠 Home", "callback_data": "cd_home"})
        else:
            nav_row.append({"text": "🔄 Refresh", "callback_data": "cd_refresh"})
        keyboard_rows.append(nav_row)

        return "\n".join(lines), {"inline_keyboard": keyboard_rows}

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

        parts = cmd_text.split()
        lower = cmd_text.lower()
        if "status" in lower:
            cmd = "/status"
            args = []
        elif "files" in lower or lower in ("ls", "dir", "/ls", "/files", "browse", "📁 files"):
            cmd = "/files"
            args = parts[1:] if len(parts) > 1 else []
        elif lower.startswith("cd ") or lower == "cd":
            cmd = "/cd"
            args = parts[1:] if len(parts) > 1 else []
        elif lower.startswith("cat ") or lower.startswith("view "):
            cmd = "/cat"
            args = parts[1:] if len(parts) > 1 else []
        elif lower.startswith("get ") or lower.startswith("download "):
            cmd = "/get"
            args = parts[1:] if len(parts) > 1 else []
        elif lower.startswith("find ") or lower.startswith("search "):
            cmd = "/find"
            args = parts[1:] if len(parts) > 1 else []
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
        elif lower in ("/cam", "/webcam", "cam", "webcam", "camera"):
            cmd = "/cam"
            args = []
        elif lower.startswith("mic") or lower.startswith("/mic") or lower.startswith("record") or lower.startswith("/record"):
            cmd = "/mic"
            args = parts[1:] if len(parts) > 1 else []
        elif lower in ("/update", "update", "apt update"):
            cmd = "/update"
            args = []
        elif lower in ("/upgrade", "upgrade", "apt upgrade"):
            cmd = "/upgrade"
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
                f"• `/files` or `/ls` - Interactive Folder Explorer\n"
                f"• `/cd <folder>` - Change Directory\n"
                f"• `/cat <file>` - View Text / Code File\n"
                f"• `/get <file>` - Download File to Phone\n"
                f"• `/find <name>` - Search for Files\n"
                f"• `/status` - Live CPU, RAM, Battery & Thermals\n"
                f"• `/screenshot` - Instant Desktop Photo\n"
                f"• `/cam` - FaceTime HD Webcam Sentry Photo\n"
                f"• `/mic [sec]` - Record Room Audio Bug (default: 5s)\n"
                f"• `/lock` - Lock Screen Session\n"
                f"• `/ring` - Ring Galaxy S9+\n"
                f"• `/clip` - Get Clipboard Text\n"
                f"• `/eject` - Flush Caches & Safe Unmount USB\n"
                f"• `/update` - Check for Xubuntu updates (apt update)\n"
                f"• `/upgrade` - Install system updates (apt upgrade -y)\n"
                f"• `/cmd <bash>` - Run Shell Command (supports sudo)\n"
                f"• `/cryo <turbo|stealth>` - Switch Power Profile\n"
            )
            self.send_message(msg)

        elif cmd in ("/files", "/ls"):
            target = Path(args[0]).expanduser() if args else self.current_dir
            if not target.is_absolute():
                target = (self.current_dir / target).resolve()
            if target.exists() and target.is_dir():
                self.current_dir = target
            text, markup = self.build_dir_view(self.current_dir)
            self.send_message(text, parse_mode="HTML", reply_markup=markup)

        elif cmd == "/cd":
            if not args:
                self.current_dir = Path.home()
            else:
                target = Path(args[0]).expanduser()
                if not target.is_absolute():
                    target = (self.current_dir / target).resolve()
                if target.exists() and target.is_dir():
                    self.current_dir = target
                else:
                    self.send_message(f"❌ Directory not found: <code>{html.escape(args[0])}</code>", parse_mode="HTML")
                    return
            text, markup = self.build_dir_view(self.current_dir)
            self.send_message(text, parse_mode="HTML", reply_markup=markup)

        elif cmd == "/cat":
            if not args:
                self.send_message("Usage: `/cat <filename>`")
                return
            target = Path(" ".join(args)).expanduser()
            if not target.is_absolute():
                target = (self.current_dir / target).resolve()
            if not target.exists():
                self.send_message(f"❌ File not found: `{target.name}`")
                return
            if target.is_dir():
                self.send_message(f"❌ `{target.name}` is a folder, use `/files` to browse it.")
                return
            try:
                content = target.read_text(encoding="utf-8", errors="replace")
                if not content:
                    content = "[File is empty]"
                if len(content) > 3500:
                    content = content[:3500] + "\n\n...[Truncated - use /get to download full file]"
                self.send_message(f"📄 *`{target.name}`:*\n```\n{content}\n```")
            except Exception as e:
                self.send_message(f"❌ Error reading file: {e}")

        elif cmd in ("/get", "/download"):
            if not args:
                self.send_message("Usage: `/get <filename>`")
                return
            target = Path(" ".join(args)).expanduser()
            if not target.is_absolute():
                target = (self.current_dir / target).resolve()
            if not target.exists():
                self.send_message(f"❌ File not found: `{target.name}`")
                return
            f_size_mb = target.stat().st_size / (1024 * 1024)
            self.send_message(f"📤 Uploading <b>{html.escape(target.name)}</b> ({f_size_mb:.1f} MB)... Please wait.", parse_mode="HTML")
            if not self.send_document(target):
                if f_size_mb <= 50:
                    self.send_message(f"❌ Upload failed for `{target.name}`.")

        elif cmd in ("/find", "/search"):
            if not args:
                self.send_message("Usage: `/find <search_query>`")
                return
            query = args[0]
            try:
                proc = subprocess.run(
                    f"find '{self.current_dir}' -maxdepth 3 -iname '*{query}*' 2>/dev/null | head -n 20",
                    shell=True,
                    stdout=subprocess.PIPE,
                    text=True,
                    timeout=5
                )
                results = proc.stdout.strip().splitlines()
                if not results:
                    self.send_message(f"🔍 No files found matching `*{query}*` in `{self.current_dir}`.")
                else:
                    lines = [f"🔍 *Search Results for `*{query}*`:*"]
                    for r in results:
                        p = Path(r)
                        icon = "📁" if p.is_dir() else "📄"
                        try:
                            rel = p.relative_to(self.current_dir)
                        except Exception:
                            rel = p
                        lines.append(f"{icon} `{rel}`")
                    lines.append("\n💡 Use `/get <filename>` or `/cd <folder>`")
                    self.send_message("\n".join(lines))
            except Exception as e:
                self.send_message(f"❌ Search error: {e}")

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
                env = os.environ.copy()
                if "DISPLAY" not in env:
                    env["DISPLAY"] = ":0"
                if "XAUTHORITY" not in env:
                    env["XAUTHORITY"] = str(Path.home() / ".Xauthority")

                if SCREENSHOT_TMP.exists():
                    SCREENSHOT_TMP.unlink()

                res = subprocess.run(["scrot", "-z", str(SCREENSHOT_TMP)], env=env, timeout=5)
                if not SCREENSHOT_TMP.exists() or res.returncode != 0:
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

        elif cmd in ("/cam", "/webcam", "/camera"):
            self.send_message("📸 Activating FaceTime HD Camera Sentry...")
            try:
                if WEBCAM_TMP.exists():
                    WEBCAM_TMP.unlink()

                cmd_ffmpeg = [
                    "ffmpeg", "-y",
                    "-f", "v4l2",
                    "-input_format", "mjpeg",
                    "-video_size", "1280x720",
                    "-ss", "0.3",
                    "-i", "/dev/video0",
                    "-frames:v", "1",
                    "-update", "1",
                    str(WEBCAM_TMP)
                ]
                subprocess.run(cmd_ffmpeg, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
                if WEBCAM_TMP.exists() and WEBCAM_TMP.stat().st_size > 0:
                    t = get_system_telemetry()
                    caption = f"📸 FaceTime HD Sentry Photo | {t['hostname']} | {time.strftime('%H:%M:%S')}"
                    self.send_photo(WEBCAM_TMP, caption=caption)
                    WEBCAM_TMP.unlink(missing_ok=True)
                else:
                    self.send_message("❌ Webcam capture failed (/dev/video0 busy or not accessible).")
            except subprocess.TimeoutExpired:
                self.send_message("⏱️ Webcam capture timed out.")
            except Exception as e:
                self.send_message(f"❌ Webcam error: {e}")

        elif cmd in ("/mic", "/record", "/audio"):
            duration = 5
            if args:
                try:
                    duration = max(2, min(30, int(args[0])))
                except ValueError:
                    duration = 5

            self.send_message(f"🎙️ Recording room audio bug ({duration}s)... Please wait.")
            try:
                if VOICE_TMP.exists():
                    VOICE_TMP.unlink()

                cmd_ffmpeg = [
                    "ffmpeg", "-y",
                    "-f", "pulse",
                    "-i", "default",
                    "-t", str(duration),
                    "-c:a", "libopus",
                    str(VOICE_TMP)
                ]
                subprocess.run(cmd_ffmpeg, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=duration + 10)
                if VOICE_TMP.exists() and VOICE_TMP.stat().st_size > 0:
                    caption = f"🎙️ Room Audio Bug ({duration}s) | {time.strftime('%H:%M:%S')}"
                    if not self.send_voice(VOICE_TMP, caption=caption):
                        self.send_document(VOICE_TMP, caption=caption)
                    VOICE_TMP.unlink(missing_ok=True)
                else:
                    self.send_message("❌ Audio recording failed (microphone stream unavailable).")
            except subprocess.TimeoutExpired:
                self.send_message("⏱️ Audio recording timed out.")
            except Exception as e:
                self.send_message(f"❌ Audio recording error: {e}")

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
                auth_serials = set(cfg.get("authorized_serials", [DEFAULT_TARGET_SERIAL]))
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
                                if any(s in udev_out for s in auth_serials):
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
                self.send_message("Usage: `/cmd <bash command>`\nExample: `/cmd git clone https://github.com/...`")
                return
            command = " ".join(args)

            # Determine dynamic timeout based on command workload
            long_workload_triggers = ("git", "apt", "npm", "pip", "curl", "wget", "docker", "make", "build", "tar", "zip")
            timeout_sec = 300 if any(t in command.lower() for t in long_workload_triggers) else 60

            self.send_message(f"⏳ Executing: `{command[:70]}`\n📍 Directory: `{self.current_dir}`\n⏱️ Timeout: {timeout_sec}s...")

            try:
                env = os.environ.copy()
                env["DEBIAN_FRONTEND"] = "noninteractive"
                env["PATH"] = f"{Path.home()}/.local/bin:{Path.home()}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:" + env.get("PATH", "")

                proc = subprocess.run(
                    command,
                    shell=True,
                    cwd=str(self.current_dir),
                    executable="/bin/bash",
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    env=env,
                    timeout=timeout_sec
                )
                output = proc.stdout.strip()
                if not output:
                    output = "[Command executed successfully with no output]"

                status_emoji = "✅" if proc.returncode == 0 else f"⚠️ (Exit code: {proc.returncode})"

                if len(output) > 3500:
                    summary = output[:3000] + f"\n\n...[Truncated - total {len(output)} bytes]"
                    self.send_message(f"{status_emoji} *Output (`{command[:60]}`):*\n```\n{summary}\n```")
                    # Save and send full log file
                    log_tmp = Path("/tmp/cmd_output.log")
                    log_tmp.write_text(proc.stdout, encoding="utf-8")
                    self.send_document(log_tmp, caption=f"📄 Full output for: {command[:40]}")
                    log_tmp.unlink(missing_ok=True)
                else:
                    self.send_message(f"{status_emoji} *Output (`{command[:60]}`):*\n```\n{output}\n```")

            except subprocess.TimeoutExpired:
                self.send_message(f"⏱️ Command timed out after {timeout_sec} seconds.")
            except Exception as e:
                self.send_message(f"❌ Execution error: {e}")

        elif cmd == "/update":
            self.send_message("🔄 Checking for Xubuntu system updates (`sudo apt update`)... Please wait.")
            try:
                env = os.environ.copy()
                env["DEBIAN_FRONTEND"] = "noninteractive"
                proc = subprocess.run(
                    "sudo apt update",
                    shell=True,
                    executable="/bin/bash",
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    env=env,
                    timeout=180
                )
                output = proc.stdout.strip()
                if "can be upgraded" in output.lower():
                    self.send_message(f"📦 *Updates Available:*\n```\n{output[-1200:]}\n```\n\n💡 Send `/upgrade` to install all updates now!")
                else:
                    self.send_message(f"✅ *System is Up to Date:*\n```\n{output[-1000:]}\n```")
            except subprocess.TimeoutExpired:
                self.send_message("⏱️ Update check timed out.")
            except Exception as e:
                self.send_message(f"❌ Update check error: {e}")

        elif cmd == "/upgrade":
            self.send_message("🚀 Upgrading Xubuntu packages (`sudo apt upgrade -y`)... This may take several minutes.")
            try:
                env = os.environ.copy()
                env["DEBIAN_FRONTEND"] = "noninteractive"
                proc = subprocess.run(
                    "sudo apt upgrade -y",
                    shell=True,
                    executable="/bin/bash",
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    env=env,
                    timeout=900
                )
                output = proc.stdout.strip()
                status_emoji = "✅" if proc.returncode == 0 else f"⚠️ (Exit code: {proc.returncode})"
                if len(output) > 3500:
                    summary = output[-2500:]
                    self.send_message(f"{status_emoji} *Upgrade Complete:*\n```\n{summary}\n```")
                    log_tmp = Path("/tmp/apt_upgrade.log")
                    log_tmp.write_text(proc.stdout, encoding="utf-8")
                    self.send_document(log_tmp, caption="📄 Full APT Upgrade Log")
                    log_tmp.unlink(missing_ok=True)
                else:
                    self.send_message(f"{status_emoji} *Upgrade Complete:*\n```\n{output}\n```")
            except subprocess.TimeoutExpired:
                self.send_message("⏱️ Upgrade timed out after 15 minutes.")
            except Exception as e:
                self.send_message(f"❌ Upgrade error: {e}")

        else:
            self.send_message(f"❓ Unknown command: `{cmd}`. Type `/help` for options.")

    def run_polling(self) -> None:
        self.running = True
        print(f"[TeleKey] Bot polling activated for Chat ID: {self.chat_id}")
        
        updates = self.get_updates(offset=0, timeout=1)
        if updates:
            self.last_update_id = updates[-1]["update_id"] + 1

        while self.running:
            try:
                updates = self.get_updates(offset=self.last_update_id, timeout=10)
                for update in updates:
                    self.last_update_id = update["update_id"] + 1

                    # Handle Callback Queries (Inline Button Clicks)
                    callback = update.get("callback_query")
                    if callback:
                        cb_id = str(callback.get("id"))
                        sender_id = str(callback.get("from", {}).get("id", ""))
                        data = str(callback.get("data", ""))

                        if sender_id != self.chat_id:
                            continue

                        if data.startswith("auth_key:"):
                            new_serial = data.split("auth_key:", 1)[1].strip()
                            self.answer_callback(cb_id, text="Key Authorized!")
                            cfg = load_config()
                            if "authorized_serials" not in cfg:
                                cfg["authorized_serials"] = []
                            if new_serial not in cfg["authorized_serials"]:
                                cfg["authorized_serials"].append(new_serial)
                                save_config(cfg)
                            flash_keyboard(2)
                            t = get_system_telemetry()
                            confirm_msg = (
                                f"🎉 *KEY APPROVED & WHITELISTED!*\n"
                                f"• Serial: `{new_serial}` has been saved permanently to your keyring.\n"
                                f"• Host: `{t['hostname']}` is UNLOCKED and ready for commands!\n"
                                f"• Local IP: `{t['ip']}` | Battery: `{t['battery']}`\n\n"
                                f"Tap any button below to execute commands."
                            )
                            self.send_message(confirm_msg, reply_markup=KEYBOARD_MARKUP)

                        elif data.startswith("block_key:"):
                            self.answer_callback(cb_id, text="Key Blocked")
                            self.send_message("🚫 *DEVICE BLOCKED*\nThe unrecognized USB was rejected. No commands will be permitted.")

                        elif data.startswith("cd:"):
                            sub_dir = data.split("cd:", 1)[1]
                            self.answer_callback(cb_id, text=f"Opening {sub_dir}")
                            target = (self.current_dir / sub_dir).resolve()
                            if target.exists() and target.is_dir():
                                self.current_dir = target
                            text, markup = self.build_dir_view(self.current_dir)
                            self.send_message(text, parse_mode="HTML", reply_markup=markup)

                        elif data == "cd_up":
                            self.answer_callback(cb_id, text="Up one level")
                            if self.current_dir != Path("/"):
                                self.current_dir = self.current_dir.parent
                            text, markup = self.build_dir_view(self.current_dir)
                            self.send_message(text, parse_mode="HTML", reply_markup=markup)

                        elif data == "cd_home":
                            self.answer_callback(cb_id, text="Home folder")
                            self.current_dir = Path.home()
                            text, markup = self.build_dir_view(self.current_dir)
                            self.send_message(text, parse_mode="HTML", reply_markup=markup)

                        elif data == "cd_refresh":
                            self.answer_callback(cb_id, text="Refreshed")
                            text, markup = self.build_dir_view(self.current_dir)
                            self.send_message(text, parse_mode="HTML", reply_markup=markup)

                        elif data.startswith("dl:"):
                            f_key = data.split("dl:", 1)[1]
                            target_file = self.file_cache.get(f_key)
                            if target_file and target_file.exists():
                                f_size_mb = target_file.stat().st_size / (1024 * 1024)
                                self.answer_callback(cb_id, text=f"Uploading {target_file.name} ({f_size_mb:.1f} MB)...")
                                self.send_message(f"📤 Uploading <b>{html.escape(target_file.name)}</b> ({f_size_mb:.1f} MB)... Please wait.", parse_mode="HTML")
                                if not self.send_document(target_file):
                                    if f_size_mb <= 50:
                                        self.send_message(f"❌ Failed to upload <b>{html.escape(target_file.name)}</b>. Network connection timed out.", parse_mode="HTML")
                            else:
                                self.answer_callback(cb_id, text="File not found or expired.")
                        continue

                    # Handle Regular Messages
                    msg = update.get("message")
                    if not msg:
                        continue
                    
                    sender_id = str(msg.get("from", {}).get("id", ""))
                    chat_id = str(msg.get("chat", {}).get("id", ""))
                    text = msg.get("text", "")

                    if sender_id != self.chat_id and chat_id != self.chat_id:
                        print(f"[TeleKey] Blocked unauthorized message from ID: {sender_id}")
                        continue

                    if text:
                        self.handle_command(text)
            except Exception as e:
                traceback.print_exc()
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
    print("[TeleKey] Initializing Hardware USB Telegram Key Daemon (Multi-Key Sentry Edition)...")
    cfg = load_config()

    bot_bridge: Optional[TelegramBotBridge] = None
    active_serial: Optional[str] = None
    notified_unauthorized: Set[str] = set()

    token = cfg.get("bot_token", "").strip()
    chat_id = str(cfg.get("chat_id", "")).strip()

    # Sentry bridge is always active to process authorizations and commands
    if token and chat_id:
        bot_bridge = TelegramBotBridge(token, chat_id, cfg.get("device_alias", socket.gethostname()))
        bot_bridge.start()

    while True:
        try:
            cfg = load_config()
            token = cfg.get("bot_token", "").strip()
            chat_id = str(cfg.get("chat_id", "")).strip()

            if not token or not chat_id:
                print("[TeleKey] ⚠️ Token or Chat ID not configured. Run: ./godmode.sh tele-config <token> <chat_id>")
                time.sleep(2)
                continue

            if bot_bridge is None:
                bot_bridge = TelegramBotBridge(token, chat_id, cfg.get("device_alias", socket.gethostname()))
                bot_bridge.start()

            auth_serials = set(cfg.get("authorized_serials", [DEFAULT_TARGET_SERIAL]))
            connected = get_connected_usb_devices()
            connected_serials = {d["serial"]: d for d in connected}

            # Check if an authorized key is currently plugged in
            matching_auth = [s for s in connected_serials if s in auth_serials]

            if matching_auth and active_serial is None:
                active_serial = matching_auth[0]
                d_info = connected_serials[active_serial]
                print(f"[TeleKey] 🔑 Authorized Key Inserted: {active_serial} ({d_info['vendor']} {d_info['model']})")
                flash_keyboard(2)

                telemetry = get_system_telemetry()
                welcome_msg = (
                    f"🔑 *HARDWARE KEY ATTACHED*\n"
                    f"• Host: `{telemetry['hostname']}`\n"
                    f"• Serial: `{active_serial}`\n"
                    f"• Device: `{d_info['vendor']} {d_info['model']}`\n"
                    f"• Local IP: `{telemetry['ip']}`\n"
                    f"• Battery: `{telemetry['battery']}`\n"
                    f"• CPU Temp: `{telemetry['temp']}`\n"
                    f"• RAM: `{telemetry['ram']}`\n\n"
                    f"⚡ *Remote Terminal Bridge: READY*\n"
                    f"Tap any button below to control this PC."
                )
                bot_bridge.send_message(welcome_msg, reply_markup=KEYBOARD_MARKUP)

            elif not matching_auth and active_serial is not None:
                print(f"[TeleKey] 🔒 Hardware Key Removed: {active_serial}! Deactivating bridge...")
                flash_keyboard(1)
                bot_bridge.send_message("🔒 *HARDWARE KEY REMOVED*\nRemote terminal bridge locked.")
                active_serial = None

            # Check for any UNRECOGNIZED USB devices
            for serial, dev in connected_serials.items():
                if serial not in auth_serials and serial not in notified_unauthorized:
                    print(f"[TeleKey] ⚠️ Unrecognized USB Detected: {serial} ({dev['vendor']} {dev['model']})")
                    # Send authorization request with inline buttons to Telegram
                    inline_keyboard = {
                        "inline_keyboard": [
                            [
                                {"text": "✅ Authorize & Whitelist Key", "callback_data": f"auth_key:{serial}"},
                                {"text": "🚫 Block / Ignore", "callback_data": f"block_key:{serial}"}
                            ]
                        ]
                    }
                    prompt = (
                        f"⚠️ *NEW UNRECOGNIZED USB DETECTED*\n"
                        f"• Host: `{socket.gethostname()}`\n"
                        f"• Device: `{dev['vendor']} {dev['model']}`\n"
                        f"• Serial: `{serial}`\n\n"
                        f"Do you want to pair this USB as an authorized GodMode Master Key?"
                    )
                    bot_bridge.send_message(prompt, reply_markup=inline_keyboard)
                    notified_unauthorized.add(serial)

            # Cleanup removed unauthorized devices from notification set
            notified_unauthorized = {s for s in notified_unauthorized if s in connected_serials}

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
            print("✅ TeleKey configuration saved successfully.")
            sys.exit(0)
        elif cmd == "status":
            cfg = load_config()
            auths = cfg.get("authorized_serials", [DEFAULT_TARGET_SERIAL])
            connected = get_connected_usb_devices()
            matching = [d for d in connected if d["serial"] in auths]
            print(f"Authorized Serials ({len(auths)}): {', '.join(auths)}")
            print(f"Connected USBs ({len(connected)}):")
            for d in connected:
                status = "AUTHORIZED ✅" if d["serial"] in auths else "UNRECOGNIZED ⚠️"
                print(f"  - [{status}] {d['vendor']} {d['model']} (Serial: {d['serial']})")
            sys.exit(0)
        elif cmd == "pair" or cmd == "add-key":
            cfg = load_config()
            connected = get_connected_usb_devices()
            if not connected:
                print("❌ No USB block devices detected. Plug in your USB and try again.")
                sys.exit(1)
            print("Detected USB Devices:")
            for idx, d in enumerate(connected, 1):
                print(f"  [{idx}] {d['vendor']} {d['model']} (Serial: {d['serial']})")
            pick = input("Select device to authorize (number): ").strip()
            try:
                chosen = connected[int(pick) - 1]
                if chosen["serial"] not in cfg["authorized_serials"]:
                    cfg["authorized_serials"].append(chosen["serial"])
                    save_config(cfg)
                    print(f"✅ Serial {chosen['serial']} successfully authorized!")
                else:
                    print("ℹ️ This serial is already authorized.")
            except Exception as e:
                print(f"❌ Error: {e}")
            sys.exit(0)
    main()
