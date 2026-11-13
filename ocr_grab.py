#!/usr/bin/env python3
"""
pcGDM OCR Grab (ocr_grab.py)
Draw a box over anything on screen (video, PDF, screenshot, error popup),
run offline Tesseract OCR, and copy the extracted text straight to clipboard.

Shortcut:
  Super + O  -> Grab screen region & copy text to clipboard
"""

import argparse
import datetime
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from PIL import Image, ImageEnhance, ImageOps

STATE_DIR = Path.home() / ".local" / "share" / "pcGDM"
LOG_FILE = STATE_DIR / "ocr_grab.log"


def log(msg: str) -> None:
    line = f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def notify(title: str, body: str = "") -> None:
    if shutil.which("notify-send"):
        subprocess.run(["notify-send", "-t", "2500", title, body], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def preprocess_image(src: Path, dst: Path) -> None:
    """Upscale only small selections and boost contrast so UI/video text reads fast."""
    with Image.open(src) as img:
        gray = ImageOps.grayscale(img)
        if gray.width < 600 and gray.height < 250:
            gray = gray.resize((gray.width * 2, gray.height * 2), Image.Resampling.LANCZOS)
        enhanced = ImageEnhance.Contrast(gray).enhance(1.5)
        enhanced.save(dst)


def copy_to_clipboard(text: str) -> None:
    for selection in ("clipboard", "primary"):
        subprocess.run(
            ["xclip", "-selection", selection],
            input=text,
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def grab_ocr(lang: str = "eng") -> None:
    if shutil.which("tesseract") is None:
        msg = "Install tesseract first: sudo apt install tesseract-ocr"
        log(f"ERROR: {msg}")
        notify("OCR Grab: Missing tesseract-ocr", msg)
        sys.exit(1)

    with tempfile.TemporaryDirectory(prefix="pcgdm_ocr_") as tmpdir:
        raw_png = Path(tmpdir) / "raw.png"
        proc_png = Path(tmpdir) / "proc.png"

        # Let user drag a selection box; Esc cancels without creating the file
        subprocess.run(
            ["xfce4-screenshooter", "-r", "-s", str(raw_png)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if not raw_png.exists() or raw_png.stat().st_size == 0:
            log("Selection cancelled.")
            return

        preprocess_image(raw_png, proc_png)

        env = os.environ.copy()
        env["OMP_THREAD_LIMIT"] = "1"
        try:
            res = subprocess.run(
                ["tesseract", str(proc_png), "stdout", "-l", lang, "--psm", "6"],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=8,
            )
        except subprocess.TimeoutExpired:
            log("ERROR: Tesseract timed out (>8s) on selection.")
            notify("OCR Grab Timed Out", "Try selecting a smaller text region.")
            sys.exit(1)
        if res.returncode != 0:
            err = res.stderr.strip() or "Tesseract failed"
            log(f"ERROR: {err}")
            notify("OCR Grab Failed", err[:140])
            sys.exit(1)

        text = res.stdout.strip()
        if not text:
            log("No text detected in selected region.")
            notify("OCR Grab", "No text detected in selection.")
            return

        copy_to_clipboard(text)
        preview = text.replace("\n", " ")[:120]
        log(f"Copied {len(text)} chars to clipboard: {preview}")
        notify(f"OCR Copied ({len(text)} chars)", preview)


def ensure_shortcut() -> None:
    script = str(Path(__file__).resolve())
    subprocess.run(
        [
            "xfconf-query", "-c", "xfce4-keyboard-shortcuts",
            "-p", "/commands/custom/<Super>o",
            "-n", "-t", "string", "-s", f"{script} grab",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    log("Ensured Super+O shortcut for OCR Grab.")


def main() -> None:
    parser = argparse.ArgumentParser(description="pcGDM OCR Grab - Screen region to clipboard")
    parser.add_argument("command", nargs="?", default="grab", choices=["grab", "init"])
    parser.add_argument("--lang", default="eng", help="Tesseract language (default: eng)")
    args = parser.parse_args()

    if args.command == "init":
        ensure_shortcut()
    else:
        grab_ocr(args.lang)


if __name__ == "__main__":
    main()
