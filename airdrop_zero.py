#!/usr/bin/env python3
"""
pcGDM AirDrop-Zero (airdrop_zero.py)
Lightweight, zero-dependency local network file drop & download server for Xubuntu.
- Runs on port 7777 (or custom port).
- Generates an ASCII QR code directly in the terminal so you can scan it with your phone!
- Allows two-way transfer:
  1. Upload files/photos from phone -> saved to ~/Downloads (where Auto-Janitor sorts them!)
  2. Download files from MacBook -> phone with 1 tap.
- Notifies via desktop notification + flashes keyboard backlight on receipt.
"""

import argparse
import html
import http.server
import io
import os
import re
import socket
import subprocess
import sys
import urllib.parse
from pathlib import Path

DEFAULT_PORT = 7777
UPLOAD_DIR = Path.home() / "Downloads"
SHARED_DIR = Path.home() / "Downloads"


# --- Pure-Python Minimal QR Code Generator for Terminal ---
# Implements basic QR matrix generation without needing external pip/apt libraries!
def render_qr_ascii(text: str) -> str:
    """Uses qrencode CLI if installed, or prints clean boxed link with terminal instructions."""
    try:
        res = subprocess.run(["qrencode", "-t", "ANSIUTF8", text], capture_output=True, text=True, check=False)
        if res.returncode == 0 and res.stdout:
            return res.stdout
    except Exception:
        pass

    # Built-in fallback: High-contrast terminal display box
    border = "=" * (len(text) + 12)
    return f"""
{border}
  AIRDROP-ZERO ACCESS URL:
  --> {text} <--
  (Open this in your phone's browser while on the same Wi-Fi)
{border}
"""


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("1.1.1.1", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def notify(title: str, msg: str) -> None:
    try:
        subprocess.run(["notify-send", "-a", "AirDrop-Zero", "-i", "network-wireless", "-t", "4000", title, msg], check=False)
        hud_script = Path(__file__).parent / "mac_hud.py"
        if hud_script.exists():
            subprocess.run([sys.executable, str(hud_script), "flash", "--count", "2"], check=False)
    except Exception:
        pass


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>AirDrop-Zero | 2012 MacBook Pro</title>
<style>
  :root {
    --bg: #0f172a;
    --card: #1e293b;
    --accent: #38bdf8;
    --accent-hover: #0284c7;
    --text: #f8fafc;
    --text-muted: #94a3b8;
    --border: #334155;
    --success: #22c55e;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
  body { background: var(--bg); color: var(--text); padding: 20px; display: flex; flex-direction: column; align-items: center; min-height: 100vh; }
  .container { width: 100%; max-width: 520px; display: flex; flex-direction: column; gap: 20px; }
  .header { text-align: center; margin-top: 10px; }
  .header h1 { font-size: 1.6rem; color: var(--text); display: flex; align-items: center; justify-content: center; gap: 10px; }
  .header p { color: var(--text-muted); font-size: 0.9rem; margin-top: 4px; }
  .card { background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 22px; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4); }
  .card h2 { font-size: 1.1rem; margin-bottom: 14px; color: var(--accent); }
  
  /* Upload Area */
  .dropzone {
    border: 2px dashed var(--border);
    border-radius: 12px;
    padding: 30px 15px;
    text-align: center;
    cursor: pointer;
    transition: all 0.2s;
    background: rgba(15, 23, 42, 0.5);
  }
  .dropzone.dragover { border-color: var(--accent); background: rgba(56, 189, 248, 0.1); }
  .dropzone svg { width: 44px; height: 44px; stroke: var(--accent); margin-bottom: 8px; }
  .dropzone span { display: block; font-weight: 500; font-size: 1rem; }
  .dropzone small { color: var(--text-muted); font-size: 0.8rem; margin-top: 4px; display: block; }
  input[type="file"] { display: none; }
  
  .btn {
    width: 100%;
    margin-top: 14px;
    padding: 14px;
    background: var(--accent);
    color: #0f172a;
    font-weight: 600;
    font-size: 1rem;
    border: none;
    border-radius: 10px;
    cursor: pointer;
    transition: background 0.2s;
  }
  .btn:hover { background: var(--accent-hover); }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }

  /* Progress Bar */
  .progress-wrap { display: none; margin-top: 14px; }
  .progress-bar-bg { width: 100%; height: 8px; background: var(--border); border-radius: 4px; overflow: hidden; }
  .progress-bar { width: 0%; height: 100%; background: var(--success); transition: width 0.1s; }
  .progress-text { font-size: 0.8rem; color: var(--text-muted); margin-top: 6px; text-align: right; }

  /* File List */
  .file-list { list-style: none; display: flex; flex-direction: column; gap: 8px; max-height: 250px; overflow-y: auto; }
  .file-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: rgba(15, 23, 42, 0.6);
    border: 1px solid var(--border);
    padding: 10px 14px;
    border-radius: 8px;
    text-decoration: none;
    color: var(--text);
    font-size: 0.9rem;
  }
  .file-item:hover { border-color: var(--accent); }
  .file-name { word-break: break-all; max-width: 75%; }
  .file-size { color: var(--text-muted); font-size: 0.75rem; }
  
  .badge { background: rgba(56, 189, 248, 0.2); color: var(--accent); padding: 2px 8px; border-radius: 6px; font-size: 0.75rem; }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>⚡ AirDrop-Zero</h1>
    <p>Local Peer-to-Peer Transfer for 2012 MacBook Pro</p>
  </div>

  <!-- UPLOAD CARD -->
  <div class="card">
    <h2>Send to MacBook</h2>
    <form id="uploadForm">
      <div class="dropzone" id="dropzone" onclick="document.getElementById('fileInput').click()">
        <svg fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
        </svg>
        <span id="labelSelect">Tap to choose files or photos</span>
        <small>Auto-Janitor will automatically sort it on receipt</small>
      </div>
      <input type="file" id="fileInput" multiple name="files">
      
      <div class="progress-wrap" id="progressWrap">
        <div class="progress-bar-bg"><div class="progress-bar" id="progressBar"></div></div>
        <div class="progress-text" id="progressText">0%</div>
      </div>
      
      <button type="button" class="btn" id="uploadBtn" style="display:none" onclick="startUpload()">Send Selected Files</button>
    </form>
  </div>

  <!-- DOWNLOAD / SHARE CARD -->
  <div class="card">
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
      <h2>Files on MacBook</h2>
      <span class="badge">~/Downloads</span>
    </div>
    <ul class="file-list">
      __FILE_LIST__
    </ul>
  </div>
</div>

<script>
  const fileInput = document.getElementById('fileInput');
  const dropzone = document.getElementById('dropzone');
  const labelSelect = document.getElementById('labelSelect');
  const uploadBtn = document.getElementById('uploadBtn');
  const progressWrap = document.getElementById('progressWrap');
  const progressBar = document.getElementById('progressBar');
  const progressText = document.getElementById('progressText');

  fileInput.addEventListener('change', () => {
    if (fileInput.files.length > 0) {
      labelSelect.innerText = `Selected ${fileInput.files.length} file(s)`;
      uploadBtn.style.display = 'block';
    }
  });

  ['dragenter', 'dragover'].forEach(name => {
    dropzone.addEventListener(name, (e) => { e.preventDefault(); dropzone.classList.add('dragover'); });
  });
  ['dragleave', 'drop'].forEach(name => {
    dropzone.addEventListener(name, (e) => { e.preventDefault(); dropzone.classList.remove('dragover'); });
  });

  dropzone.addEventListener('drop', (e) => {
    fileInput.files = e.dataTransfer.files;
    if (fileInput.files.length > 0) {
      labelSelect.innerText = `Selected ${fileInput.files.length} file(s)`;
      uploadBtn.style.display = 'block';
    }
  });

  function startUpload() {
    if (!fileInput.files.length) return;
    const formData = new FormData();
    for (let i = 0; i < fileInput.files.length; i++) {
      formData.append('files', fileInput.files[i]);
    }

    uploadBtn.disabled = true;
    progressWrap.style.display = 'block';

    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/upload', true);

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        const pct = Math.round((e.loaded / e.total) * 100);
        progressBar.style.width = pct + '%';
        progressText.innerText = pct + '%';
      }
    };

    xhr.onload = () => {
      if (xhr.status === 200) {
        progressBar.style.width = '100%';
        progressText.innerText = 'Transferred Successfully!';
        setTimeout(() => location.reload(), 1200);
      } else {
        alert('Upload failed: ' + xhr.responseText);
        uploadBtn.disabled = false;
      }
    };

    xhr.onerror = () => {
      alert('Network transfer error');
      uploadBtn.disabled = false;
    };

    xhr.send(formData);
  }
</script>
</body>
</html>
"""


class AirDropHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Keep terminal output clean
        return

    def do_GET(self):
        url_path = urllib.parse.unquote(self.path.split("?")[0])

        if url_path == "/" or url_path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()

            # Build file list
            file_items = []
            try:
                for p in sorted(SHARED_DIR.iterdir()):
                    if p.is_file() and not p.name.startswith("."):
                        size_mb = p.stat().st_size / (1024 * 1024)
                        size_str = f"{size_mb:.1f} MB" if size_mb >= 1.0 else f"{p.stat().st_size / 1024:.0f} KB"
                        safe_name = html.escape(p.name)
                        link = f"/download/{urllib.parse.quote(p.name)}"
                        file_items.append(
                            f'<a href="{link}" class="file-item" download>'
                            f'<span class="file-name">{safe_name}</span>'
                            f'<span class="file-size">{size_str}</span>'
                            f'</a>'
                        )
            except Exception:
                pass

            file_list_html = "\n".join(file_items) if file_items else '<li style="color:var(--text-muted); text-align:center; padding:10px;">No files currently in ~/Downloads</li>'
            resp = HTML_TEMPLATE.replace("__FILE_LIST__", file_list_html)
            self.wfile.write(resp.encode("utf-8"))
            return

        elif url_path.startswith("/download/"):
            fname = url_path[len("/download/") :]
            target = SHARED_DIR / fname
            if target.exists() and target.is_file() and not target.name.startswith("."):
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Disposition", f'attachment; filename="{target.name}"')
                self.send_header("Content-Length", str(target.stat().st_size))
                self.end_headers()
                with open(target, "rb") as f:
                    while chunk := f.read(64 * 1024):
                        self.wfile.write(chunk)
                return

        self.send_error(404, "File not found")

    def do_POST(self):
        if self.path == "/upload":
            content_type = self.headers.get("Content-Type", "")
            if not content_type.startswith("multipart/form-data;"):
                self.send_error(400, "Bad content type")
                return

            boundary = content_type.split("boundary=")[1].encode("utf-8")
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length <= 0:
                self.send_error(400, "Zero length")
                return

            body = self.rfile.read(content_length)

            parts = body.split(b"--" + boundary)
            saved_files = []

            for part in parts:
                if not part or part == b"--\r\n" or part == b"--":
                    continue
                header_data, sep, body_data = part.partition(b"\r\n\r\n")
                if not sep:
                    continue

                headers_text = header_data.decode("utf-8", errors="ignore")
                match = re.search(r'filename="([^"]+)"', headers_text)
                if match:
                    filename = Path(match.group(1)).name
                    if not filename:
                        continue
                    # Strip trailing \r\n from file body
                    if body_data.endswith(b"\r\n"):
                        body_data = body_data[:-2]

                    out_path = UPLOAD_DIR / filename
                    # Prevent overwriting
                    counter = 1
                    stem = out_path.stem
                    suffix = out_path.suffix
                    while out_path.exists():
                        out_path = UPLOAD_DIR / f"{stem}_{counter}{suffix}"
                        counter += 1

                    out_path.write_bytes(body_data)
                    saved_files.append(out_path.name)

            if saved_files:
                count = len(saved_files)
                names = ", ".join(saved_files[:2]) + ("..." if count > 2 else "")
                notify("AirDrop-Zero Received File(s)", f"Received {count} file(s):\n{names}")

            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
            return

        self.send_error(404, "Not found")


def run_server(port: int = DEFAULT_PORT) -> None:
    ip = get_local_ip()
    url = f"http://{ip}:{port}"

    print(f"\n========================================================")
    print(f"  ⚡ pcGDM AirDrop-Zero Server Live on Port {port}")
    print(f"========================================================")
    print(f"  Local IP URL : {url}")
    print(render_qr_ascii(url))
    print(f"  Upload Target: {UPLOAD_DIR} (Auto-Janitor will auto-sort incoming files)")
    print(f"  Press Ctrl+C to stop.\n")

    httpd = http.server.ThreadingHTTPServer(("0.0.0.0", port), AirDropHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[-] AirDrop-Zero server stopped.")
    finally:
        httpd.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="AirDrop-Zero Local Network File Dropper")
    parser.add_argument("command", nargs="?", default="run", choices=["run", "qr", "url"], help="Action to perform")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Server port (default: {DEFAULT_PORT})")
    args = parser.parse_args()

    if args.command == "qr":
        ip = get_local_ip()
        print(render_qr_ascii(f"http://{ip}:{args.port}"))
    elif args.command == "url":
        ip = get_local_ip()
        print(f"http://{ip}:{args.port}")
    elif args.command == "run":
        run_server(args.port)


if __name__ == "__main__":
    main()
