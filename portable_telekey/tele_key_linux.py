#!/usr/bin/env python3
"""
=============================================================================
  GodMode TeleKey - Universal Linux Edition
  Pre-configured for Hardware USB Serial: 0377291581335169734
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
from pathlib import Path
from typing import Optional, Dict, Any, List

BOT_TOKEN = "8638559927:AAEsHxtIbdkRV24l7rK6qsZ_AkYmg1cCt1o"
CHAT_ID = "8556430828"
TARGET_SERIAL = "0377291581335169734"
SCREENSHOT_TMP = Path("/tmp/tele_screen.png")

KEYBOARD_MARKUP = {
    "keyboard": [
        [{"text": "📊 Status"}, {"text": "📸 Screenshot"}],
        [{"text": "🔒 Lock Screen"}, {"text": "📋 Clipboard"}],
        [{"text": "❓ Help"}]
    ],
    "resize_keyboard": True,
    "persistent": True
}


def is_usb_present() -> bool:
    by_id = Path("/dev/disk/by-id")
    if by_id.exists():
        for item in by_id.iterdir():
            if TARGET_SERIAL in item.name:
                return True
    return False


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

    return {
        "hostname": hostname,
        "ip": ip,
        "ram": ram_str
    }


class TelegramBotBridge:
    def __init__(self):
        self.api_url = f"https://api.telegram.org/bot{BOT_TOKEN}"
        self.running = False
        self.last_update_id = 0
        self.worker_thread: Optional[threading.Thread] = None
        self.clear_webhook()

    def clear_webhook(self) -> None:
        try:
            url = f"{self.api_url}/deleteWebhook?drop_pending_updates=False"
            req = urllib.request.Request(url)
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass

    def send_message(self, text: str, parse_mode: str = "Markdown") -> bool:
        url = f"{self.api_url}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": parse_mode,
            "reply_markup": KEYBOARD_MARKUP
        }
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except Exception:
            return False

    def send_photo(self, photo_path: Path, caption: str = "") -> bool:
        if not photo_path.exists():
            return False
        url = f"{self.api_url}/sendPhoto"
        boundary = f"----WebKitFormBoundary{int(time.time()*1000)}"
        body = []
        body.append(f"--{boundary}".encode("utf-8"))
        body.append(f'Content-Disposition: form-data; name="chat_id"'.encode("utf-8"))
        body.append(b"")
        body.append(str(CHAT_ID).encode("utf-8"))
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
            with urllib.request.urlopen(req, timeout=25) as resp:
                return resp.status == 200
        except Exception:
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
            t = get_system_telemetry()
            self.send_message(f"📊 *Host Status Report:*\n• Host: `{t['hostname']}`\n• IP: `{t['ip']}`\n• RAM: `{t['ram']}`")
        elif "screenshot" in lower or "photo" in lower:
            self.send_message("📸 Capturing desktop...")
            env = os.environ.copy()
            if "DISPLAY" not in env:
                env["DISPLAY"] = ":0"
            if SCREENSHOT_TMP.exists():
                SCREENSHOT_TMP.unlink()
            subprocess.run(["scrot", "-z", str(SCREENSHOT_TMP)], env=env, timeout=5)
            if not SCREENSHOT_TMP.exists():
                subprocess.run(["import", "-window", "root", str(SCREENSHOT_TMP)], env=env, timeout=5)
            if SCREENSHOT_TMP.exists():
                self.send_photo(SCREENSHOT_TMP, caption=f"🖥️ Desktop | {socket.gethostname()}")
                SCREENSHOT_TMP.unlink(missing_ok=True)
            else:
                self.send_message("❌ Failed to capture screenshot.")
        elif "lock" in lower:
            env = os.environ.copy()
            if "DISPLAY" not in env:
                env["DISPLAY"] = ":0"
            subprocess.Popen(["xflock4"], env=env)
            self.send_message("🔒 Session locked.")
        elif "clip" in lower:
            try:
                env = os.environ.copy()
                if "DISPLAY" not in env:
                    env["DISPLAY"] = ":0"
                clip = subprocess.check_output(["xclip", "-selection", "clipboard", "-o"], env=env, timeout=2).decode("utf-8", errors="replace")
                self.send_message(f"📋 *Clipboard:*\n```\n{clip[:1000]}\n```" if clip else "📋 Clipboard is empty.")
            except Exception as e:
                self.send_message(f"❌ Clipboard error: {e}")
        elif cmd_text.startswith("/cmd"):
            cmd = cmd_text[4:].strip()
            if cmd:
                try:
                    proc = subprocess.run(cmd, shell=True, executable="/bin/bash", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=15)
                    out = proc.stdout.strip() or "[Executed with no output]"
                    if len(out) > 3500:
                        out = out[:3500] + "\n...[Truncated]"
                    self.send_message(f"⚙️ *Output (`{cmd[:60]}`):*\n```\n{out}\n```")
                except Exception as e:
                    self.send_message(f"❌ Execution error: {e}")
        elif "help" in lower or "start" in lower:
            self.send_message(f"⚡ *Linux TeleKey ({socket.gethostname()}) Commands:*\n• `/status` - Live CPU & RAM\n• `/screenshot` - Desktop Capture\n• `/lock` - Lock Desktop\n• `/clip` - Get Clipboard\n• `/cmd <bash>` - Run Command")

    def run_polling(self) -> None:
        self.running = True
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
                    if sender_id != CHAT_ID:
                        continue
                    text = msg.get("text", "")
                    if text:
                        self.handle_command(text)
            except Exception:
                time.sleep(2)

    def start(self) -> None:
        if self.running:
            return
        self.worker_thread = threading.Thread(target=self.run_polling, daemon=True)
        self.worker_thread.start()

    def stop(self) -> None:
        self.running = False


def main():
    bridge: Optional[TelegramBotBridge] = None
    was_plugged = False
    print(f"⚡ TeleKey Universal Linux Daemon Active. Watching for Serial: {TARGET_SERIAL}")

    while True:
        try:
            is_plugged = is_usb_present()
            if is_plugged and not was_plugged:
                t = get_system_telemetry()
                bridge = TelegramBotBridge()
                msg = (
                    f"🔑 *HARDWARE KEY ATTACHED (LINUX)*\n"
                    f"• Host: `{t['hostname']}`\n"
                    f"• Local IP: `{t['ip']}`\n"
                    f"• RAM: `{t['ram']}`\n\n"
                    f"⚡ *Remote Terminal Bridge: READY*\n"
                    f"Type `/help` or tap buttons to control this PC."
                )
                bridge.send_message(msg)
                bridge.start()
                was_plugged = True
            elif not is_plugged and was_plugged:
                if bridge:
                    bridge.send_message(f"🔒 *HARDWARE KEY REMOVED*\nHost: `{socket.gethostname()}`\nRemote bridge deactivated.")
                    bridge.stop()
                    bridge = None
                was_plugged = False
            time.sleep(1)
        except KeyboardInterrupt:
            break
        except Exception:
            time.sleep(2)


if __name__ == "__main__":
    main()
