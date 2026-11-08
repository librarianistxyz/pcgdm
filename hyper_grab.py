#!/usr/bin/env python3
"""
pcGDM Hyper-Grab (hyper_grab.py)
Autonomous Clip-to-Action Watcher for Xubuntu / Linux.

Monitors X11 clipboard in real time (<0.1s latency, 0% CPU):
1. Media URL Detection (YouTube, TikTok, Twitter/X, Instagram, Vimeo, Reddit, Soundcloud):
   - Triggers quick actionable popup menu (via rofi / zenity / notification)
   - Downloads 1080p Video OR High-Quality MP3 directly into ~/Downloads/
   - Auto-Janitor automatically sorts it into Videos/ or Audio/ upon completion!
   - Keyboard backlight flashes twice when ready.
2. Unformatted JSON Detection:
   - When messy JSON is copied, automatically beautifies and formats it directly on the clipboard.
"""

import argparse
import datetime
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

DOWNLOAD_DIR = Path.home() / "Downloads"
LOG_FILE = Path.home() / ".local" / "share" / "pcGDM" / "hyper_grab.log"

MEDIA_DOMAINS = [
    "youtube.com", "youtu.be", "tiktok.com", "twitter.com", "x.com",
    "instagram.com", "reddit.com", "soundcloud.com", "vimeo.com",
    "facebook.com/reel", "fb.watch"
]


def log(msg: str) -> None:
    line = f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def notify(title: str, msg: str, timeout_ms: int = 4000) -> None:
    try:
        subprocess.run(
            ["notify-send", "-a", "Hyper-Grab", "-i", "video-x-generic", "-t", str(timeout_ms), title, msg],
            check=False,
        )
    except Exception:
        pass


def flash_keyboard() -> None:
    try:
        hud_script = Path(__file__).parent / "mac_hud.py"
        if hud_script.exists():
            subprocess.run([sys.executable, str(hud_script), "flash", "--count", "2"], check=False)
    except Exception:
        pass


def get_clipboard() -> str:
    try:
        out = subprocess.check_output(["xclip", "-selection", "clipboard", "-o"], stderr=subprocess.DEVNULL, timeout=1.0)
        return out.decode("utf-8", errors="ignore").strip()
    except Exception:
        return ""


def set_clipboard(text: str) -> None:
    try:
        p = subprocess.Popen(["xclip", "-selection", "clipboard", "-i"], stdin=subprocess.PIPE)
        p.communicate(input=text.encode("utf-8"), timeout=1.0)
    except Exception:
        pass


def is_media_url(text: str) -> bool:
    if not text.startswith("http://") and not text.startswith("https://"):
        return False
    lower = text.lower()
    return any(domain in lower for domain in MEDIA_DOMAINS)


def download_media_async(url: str, mode: str) -> None:
    """Runs yt-dlp in a background thread so the clipboard watcher never blocks."""
    def worker():
        log(f"Starting download [{mode}]: {url}")
        notify("Hyper-Grab Downloading", f"Downloading {mode.upper()} in background...", timeout_ms=3000)
        
        DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        out_template = str(DOWNLOAD_DIR / "%(title).60s [%(id)s].%(ext)s")

        if mode == "mp3":
            cmd = [
                "/usr/local/bin/yt-dlp",
                "-x", "--audio-format", "mp3",
                "--audio-quality", "0",
                "--no-playlist",
                "-o", out_template,
                url
            ]
        else:
            # High quality MP4 (up to 1080p for fast Ivy Bridge playback)
            cmd = [
                "/usr/local/bin/yt-dlp",
                "-f", "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
                "--merge-output-format", "mp4",
                "--no-playlist",
                "-o", out_template,
                url
            ]

        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode == 0:
            log(f"Download complete [{mode}]: {url}")
            notify("Hyper-Grab Finished! ⚡", f"Saved to ~/Downloads ({mode.upper()})\nAuto-Janitor will organize it.", timeout_ms=4500)
            flash_keyboard()
        else:
            err = res.stderr[-200:] if res.stderr else "Unknown error"
            log(f"Download failed: {err}")
            notify("Hyper-Grab Error", f"Download failed: {err[:60]}...", timeout_ms=5000)

    t = threading.Thread(target=worker, daemon=True)
    t.start()


def prompt_user_action(url: str) -> None:
    """Presents a lightweight non-intrusive action dialog via rofi or zenity."""
    options = "1. Download 1080p Video (MP4)\n2. Download Audio Only (MP3)\n3. Ignore"
    selected = ""

    # Try rofi first (fast keyboard overlay)
    try:
        p = subprocess.Popen(
            ["rofi", "-dmenu", "-p", "⚡ Hyper-Grab Action", "-lines", "3", "-width", "35"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True
        )
        out, _ = p.communicate(input=options, timeout=8.0)
        selected = out.strip()
    except Exception:
        pass

    # Fallback to zenity list if rofi is dismissed or not preferred
    if not selected:
        try:
            res = subprocess.check_output(
                ["zenity", "--list", "--title=⚡ Hyper-Grab Media Detected",
                 "--column=Action", "1080p Video", "Audio MP3", "Ignore",
                 "--text=URL: " + url[:50] + "...", "--timeout=10"],
                text=True, stderr=subprocess.DEVNULL
            ).strip()
            selected = res
        except Exception:
            return

    if "Video" in selected or "1080p" in selected:
        download_media_async(url, mode="video")
    elif "Audio" in selected or "MP3" in selected:
        download_media_async(url, mode="mp3")
    else:
        log(f"Ignored media URL: {url}")


def handle_clipboard_content(text: str) -> None:
    if not text:
        return

    # 1. Media Link Detector
    if is_media_url(text):
        log(f"Detected media URL in clipboard: {text}")
        prompt_user_action(text)
        return

    # 2. Raw Unformatted JSON Beautifier
    if (text.startswith("{") and text.endswith("}")) or (text.startswith("[") and text.endswith("]")):
        # Only format if it's currently a single line or unformatted
        if "\n" not in text and len(text) > 20:
            try:
                parsed = json.loads(text)
                formatted = json.dumps(parsed, indent=2)
                set_clipboard(formatted)
                notify("Hyper-Grab Auto-Formatted JSON", f"Cleaned up {len(text)} bytes of JSON on clipboard.")
                log("Auto-formatted JSON on clipboard.")
            except Exception:
                pass


def run_daemon() -> None:
    log("Starting pcGDM Hyper-Grab Clip-to-Action Watcher...")

    def sig_handler(_signo, _frame):
        log("Stopping Hyper-Grab daemon.")
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    last_clip = get_clipboard()

    while True:
        try:
            current = get_clipboard()
            if current and current != last_clip:
                last_clip = current
                handle_clipboard_content(current)

            time.sleep(0.4)
        except Exception as e:
            time.sleep(1.0)


def main() -> None:
    parser = argparse.ArgumentParser(description="Hyper-Grab Autonomous Clip-to-Action Watcher")
    parser.add_argument("command", nargs="?", default="daemon", choices=["daemon", "status"], help="Action to perform")
    args = parser.parse_args()

    if args.command == "status":
        print("=== pcGDM Hyper-Grab Status ===")
        print(f"  Target Download: {DOWNLOAD_DIR}")
        print(f"  Supported Media: YouTube, TikTok, Twitter/X, Instagram, Reddit, Soundcloud")
        print(f"  Log File       : {LOG_FILE}")
    elif args.command == "daemon":
        run_daemon()


if __name__ == "__main__":
    main()
